"""Derived views computed from a parsed :class:`~sopcc.model.Project`.

Nothing here is stored in the file: these helpers turn raw fields into things
that are useful to *look at* -- parsed NodeIds, a symbol hierarchy, per
subscription statistics and a safe summary of the (possibly secret) user
identity.
"""

from __future__ import annotations

import base64
import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field

from .model import MonitoredItem, Project, SessionInfo, Subscription

_NODE_ID_RE = re.compile(r"^(?:ns=(?P<ns>\d+);)?(?:(?P<type>[isgb])=)?(?P<id>.*)$")

_IDENTIFIER_TYPE_NAMES = {
    "i": "Numeric",
    "s": "String",
    "g": "Guid",
    "b": "Opaque",
    "": "Unspecified",
}


@dataclass
class NodeIdInfo:
    """A parsed OPC UA NodeId."""

    raw: str
    namespace_index: int | None
    identifier_type: str
    identifier: str
    symbol_parts: list[str] = field(default_factory=list)

    @property
    def identifier_type_name(self) -> str:
        return _IDENTIFIER_TYPE_NAMES.get(self.identifier_type, self.identifier_type)


def parse_node_id(node_id: str) -> NodeIdInfo:
    """Parse ``ns=2;s=S7-1.IDB.OP`` style NodeIds into structured parts."""
    match = _NODE_ID_RE.match(node_id.strip())
    if match is None:  # pragma: no cover - regex matches empty string
        return NodeIdInfo(node_id, None, "", node_id, [node_id])

    ns_raw = match.group("ns")
    identifier_type = match.group("type") or ""
    identifier = match.group("id")

    symbol_parts: list[str] = []
    if identifier_type == "s" and identifier:
        symbol_parts = [part for part in identifier.split(".") if part]

    return NodeIdInfo(
        raw=node_id,
        namespace_index=int(ns_raw) if ns_raw is not None else None,
        identifier_type=identifier_type,
        identifier=identifier,
        symbol_parts=symbol_parts,
    )


# ---------------------------------------------------------------------------
# Symbol tree
# ---------------------------------------------------------------------------


@dataclass
class SymbolNode:
    """A node in the hierarchy derived from monitored-item NodeId strings."""

    name: str
    children: dict[str, "SymbolNode"] = field(default_factory=dict)
    entries: list[tuple[SessionInfo, Subscription, MonitoredItem]] = field(
        default_factory=list
    )

    @property
    def subtree_item_count(self) -> int:
        total = len(self.entries)
        for child in self.children.values():
            total += child.subtree_item_count
        return total


def build_symbol_tree(project: Project) -> SymbolNode:
    """Group every monitored item by the dot-separated symbol path of its NodeId.

    Items whose NodeIds are not string identifiers are grouped under a synthetic
    ``<non-symbolic>`` branch so they remain visible.
    """
    root = SymbolNode(name="(root)")
    for session in project.sessions:
        for subscription in session.subscriptions:
            for item in subscription.items:
                info = parse_node_id(item.node_id)
                parts = info.symbol_parts or ["<non-symbolic>"]
                node = root
                for part in parts:
                    node = node.children.setdefault(part, SymbolNode(name=part))
                node.entries.append((session, subscription, item))
    return root


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def subscription_stats(subscription: Subscription) -> dict[str, object]:
    """Return a small summary of one subscription."""
    intervals = Counter(item.sampling_interval for item in subscription.items)
    states = Counter(item.target_state for item in subscription.items)
    return {
        "item_count": len(subscription.items),
        "intervals": dict(sorted(intervals.items())),
        "states": dict(states),
    }


def project_stats(project: Project) -> dict[str, object]:
    """Return aggregate statistics for the whole project."""
    namespaces: Counter[int] = Counter()
    identifier_types: Counter[str] = Counter()
    intervals: Counter[str] = Counter()
    states: Counter[str] = Counter()

    for session in project.sessions:
        for subscription in session.subscriptions:
            for item in subscription.items:
                info = parse_node_id(item.node_id)
                if info.namespace_index is not None:
                    namespaces[info.namespace_index] += 1
                identifier_types[info.identifier_type_name] += 1
                intervals[item.sampling_interval] += 1
                states[item.target_state] += 1

    return {
        "sessions": len(project.sessions),
        "subscriptions": project.subscription_count,
        "items": project.item_count,
        "namespaces": dict(sorted(namespaces.items())),
        "identifier_types": dict(identifier_types),
        "sampling_intervals": dict(sorted(intervals.items(), key=lambda kv: kv[0])),
        "target_states": dict(states),
    }


# ---------------------------------------------------------------------------
# User identity
# ---------------------------------------------------------------------------


@dataclass
class IdentitySummary:
    """A safe, display-oriented view of the session's user identity."""

    identity_type: str = "Unknown"
    is_anonymous: bool = False
    masked: bool = True
    fields: dict[str, str] = field(default_factory=dict)
    decoded_xml: str = ""

    @property
    def label(self) -> str:
        if self.is_anonymous:
            return "Anonymous"
        return self.identity_type


def _decode_identity_bytes(raw: str) -> str | None:
    """Decode the base64 identity blob to XML text, trying UTF-16LE then UTF-8."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        data = base64.b64decode(raw, validate=True)
    except (ValueError, base64.binascii.Error):
        try:
            data = base64.b64decode(raw)
        except Exception:
            return None

    for encoding in ("utf-16-le", "utf-16", "utf-8"):
        try:
            text = data.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
        if "<" in text and ">" in text:
            return text
    return None


def identity_summary(
    user_identity: str, include_secrets: bool = False
) -> IdentitySummary:
    """Summarise a session's base64 ``UserIdentity``.

    By default only the identity *type* is exposed (e.g. ``AnonymousUserIdentity``
    or ``UserNameIdentityToken``). Pass ``include_secrets=True`` to also decode
    and return the contained fields -- which may include credentials.
    """
    xml_text = _decode_identity_bytes(user_identity)
    if xml_text is None:
        return IdentitySummary(identity_type="Unknown", masked=not include_secrets)

    try:
        root = ET.fromstring(xml_text.strip())
    except ET.ParseError:
        return IdentitySummary(identity_type="Unknown", masked=not include_secrets)

    tag = root.tag.rsplit("}", 1)[-1]
    summary = IdentitySummary(
        identity_type=tag,
        is_anonymous=tag.lower() == "anonymoususeridentity",
        masked=not include_secrets,
        decoded_xml=xml_text.strip() if include_secrets else "",
    )
    if include_secrets:
        for child in root:
            key = child.tag.rsplit("}", 1)[-1]
            summary.fields[key] = (child.text or "").strip()
    return summary
