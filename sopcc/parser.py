"""Tolerant parser for Softing ``.sopcc`` project files.

The files are single-line UTF-8 XML documents (often with a BOM) rooted at
``Sessions``. This module avoids assumptions about field order, element
namespace, or the number of sessions, and never raises for an unknown element:
unrecognised children are preserved in each dataclass's ``extra`` mapping and a
warning is recorded on the project.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Any

from .model import (
    BrowseOptions,
    MonitoredItem,
    Project,
    SessionInfo,
    Subscription,
)


class SopccError(Exception):
    """Raised when a file cannot be parsed as a ``.sopcc`` document at all."""


def _local_name(tag: str) -> str:
    """Strip an ``{namespace}`` prefix from an ElementTree tag."""
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _child(element: ET.Element | None, name: str) -> ET.Element | None:
    """Return the first direct child with the given local name, or ``None``."""
    if element is None:
        return None
    for child in element:
        if _local_name(child.tag) == name:
            return child
    return None


def _text(element: ET.Element | None) -> str:
    """Return stripped text of an element, or ``""`` when absent/empty."""
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def _child_text(element: ET.Element | None, name: str) -> str:
    return _text(_child(element, name))


def _collect_extra(element: ET.Element, known: set[str]) -> dict[str, Any]:
    """Capture children whose local names are not in ``known``.

    A repeated name is stored as a list so nothing is lost.
    """
    extra: dict[str, Any] = {}
    for child in element:
        name = _local_name(child.tag)
        if name in known:
            continue
        value: Any = _text(child)
        if len(child):
            value = [_collect_extra(child, set()) | {"_tag": _local_name(c.tag)} for c in child]
        if name in extra:
            existing = extra[name]
            if not isinstance(existing, list):
                existing = [existing]
            existing.append(value)
            extra[name] = existing
        else:
            extra[name] = value
    return extra


_MONITORED_ITEM_FIELDS = {
    "DisplayName",
    "NodeId",
    "AttributeId",
    "DiscardOldest",
    "QueueSize",
    "SamplingInterval",
    "TargetState",
    "ConnectedIsSampling",
    "LogValues",
}

_SUBSCRIPTION_FIELDS = {
    "DisplayName",
    "LifeTimeCount",
    "MaxKeepAliveCount",
    "MaxNotificationsPerPublish",
    "Priority",
    "TimestampsToReturn",
    "PublishingInterval",
    "TargetState",
    "Children",
}

_BROWSE_FIELDS = {
    "BrowseDirection",
    "ContinueUntilDone",
    "IncludeSubtypes",
    "MaxReferencesReturned",
    "NodeClassMask",
    "ReferenceTypeId",
}

_SESSION_FIELDS = {
    "CheckDomain",
    "Encoding",
    "ApplicationName",
    "SecurityMode",
    "SecurityPolicy",
    "SessionName",
    "TargetState",
    "Timeout",
    "Url",
    "UserIdentity",
    "Subscriptions",
    "BrowseOptions",
}


def _parse_monitored_item(element: ET.Element, warnings: list[str]) -> MonitoredItem:
    return MonitoredItem(
        display_name=_child_text(element, "DisplayName"),
        node_id=_child_text(element, "NodeId"),
        attribute_id=_child_text(element, "AttributeId"),
        discard_oldest=_child_text(element, "DiscardOldest"),
        queue_size=_child_text(element, "QueueSize"),
        sampling_interval=_child_text(element, "SamplingInterval"),
        target_state=_child_text(element, "TargetState"),
        connected_is_sampling=_child_text(element, "ConnectedIsSampling"),
        log_values=_child_text(element, "LogValues"),
        extra=_collect_extra(element, _MONITORED_ITEM_FIELDS),
    )


def _parse_subscription(element: ET.Element, warnings: list[str]) -> Subscription:
    subscription = Subscription(
        display_name=_child_text(element, "DisplayName"),
        lifetime_count=_child_text(element, "LifeTimeCount"),
        max_keep_alive_count=_child_text(element, "MaxKeepAliveCount"),
        max_notifications_per_publish=_child_text(element, "MaxNotificationsPerPublish"),
        priority=_child_text(element, "Priority"),
        timestamps_to_return=_child_text(element, "TimestampsToReturn"),
        publishing_interval=_child_text(element, "PublishingInterval"),
        target_state=_child_text(element, "TargetState"),
        extra=_collect_extra(element, _SUBSCRIPTION_FIELDS),
    )

    children = _child(element, "Children")
    if children is not None:
        for child in children:
            if _local_name(child.tag) == "MonitoredItem":
                subscription.items.append(_parse_monitored_item(child, warnings))
            else:
                warnings.append(
                    f"Unknown element under subscription Children: {_local_name(child.tag)}"
                )
    return subscription


def _parse_browse_options(element: ET.Element) -> BrowseOptions:
    return BrowseOptions(
        browse_direction=_child_text(element, "BrowseDirection"),
        continue_until_done=_child_text(element, "ContinueUntilDone"),
        include_subtypes=_child_text(element, "IncludeSubtypes"),
        max_references_returned=_child_text(element, "MaxReferencesReturned"),
        node_class_mask=_child_text(element, "NodeClassMask"),
        reference_type_id=_child_text(element, "ReferenceTypeId"),
        extra=_collect_extra(element, _BROWSE_FIELDS),
    )


def _parse_session(element: ET.Element, warnings: list[str]) -> SessionInfo:
    session = SessionInfo(
        check_domain=_child_text(element, "CheckDomain"),
        encoding=_child_text(element, "Encoding"),
        application_name=_child_text(element, "ApplicationName"),
        security_mode=_child_text(element, "SecurityMode"),
        security_policy=_child_text(element, "SecurityPolicy"),
        session_name=_child_text(element, "SessionName"),
        target_state=_child_text(element, "TargetState"),
        timeout=_child_text(element, "Timeout"),
        url=_child_text(element, "Url"),
        user_identity=_child_text(element, "UserIdentity"),
        extra=_collect_extra(element, _SESSION_FIELDS),
    )

    subscriptions = _child(element, "Subscriptions")
    if subscriptions is not None:
        for child in subscriptions:
            if _local_name(child.tag) == "Subscription":
                session.subscriptions.append(_parse_subscription(child, warnings))
            else:
                warnings.append(
                    f"Unknown element under Subscriptions: {_local_name(child.tag)}"
                )

    browse = _child(element, "BrowseOptions")
    if browse is not None:
        session.browse_options = _parse_browse_options(browse)

    return session


def _decode_bytes(data: bytes) -> str:
    """Decode SOPCC bytes, tolerating a UTF-8 BOM and stray encodings."""
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    # latin-1 never fails, so this is unreachable in practice.
    return data.decode("utf-8", errors="replace")


def parse_string(text: str, source_path: str = "") -> Project:
    """Parse already-decoded XML text into a :class:`Project`."""
    warnings: list[str] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise SopccError(f"Not a well-formed .sopcc XML document: {exc}") from exc

    if _local_name(root.tag) != "Sessions":
        warnings.append(
            f"Unexpected root element <{_local_name(root.tag)}>; expected <Sessions>."
        )

    project = Project(
        version=root.attrib.get("Version", ""),
        source_path=source_path,
        raw_xml=text,
        warnings=warnings,
    )

    for child in root:
        if _local_name(child.tag) == "Session":
            project.sessions.append(_parse_session(child, warnings))
        else:
            warnings.append(f"Unknown element under Sessions: {_local_name(child.tag)}")

    if not project.sessions:
        warnings.append("No <Session> elements found in the document.")

    return project


def load_project(path: str | os.PathLike[str]) -> Project:
    """Load a ``.sopcc`` file from disk.

    Raises:
        FileNotFoundError: if ``path`` does not exist.
        SopccError: if the file is not well-formed XML.
    """
    path = os.fspath(path)
    with open(path, "rb") as handle:
        data = handle.read()
    return parse_string(_decode_bytes(data), source_path=path)


def pretty_xml(text: str, indent: str = "  ") -> str:
    """Return an indented version of the document for display."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return text
    _indent(root, indent)
    return ET.tostring(root, encoding="unicode")


def _indent(element: ET.Element, indent: str, level: int = 0) -> None:
    pad = "\n" + indent * level
    if len(element):
        if not (element.text or "").strip():
            element.text = pad + indent
        for child in element:
            _indent(child, indent, level + 1)
        if not (element[-1].tail or "").strip():
            element[-1].tail = pad
    if level and not (element.tail or "").strip():
        element.tail = pad
