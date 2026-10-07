"""Dataclasses describing a Softing ``.sopcc`` project.

The file is a single-line XML document whose root is ``Sessions``. Each
``Session`` describes one saved OPC UA client connection and contains zero or
more ``Subscription`` elements, each of which contains ``MonitoredItem``
elements.

The dataclasses here intentionally keep an ``extra`` mapping so that fields not
known to this version of the reader are preserved rather than silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MonitoredItem:
    """A single monitored item inside a subscription."""

    display_name: str = ""
    node_id: str = ""
    attribute_id: str = ""
    discard_oldest: str = ""
    queue_size: str = ""
    sampling_interval: str = ""
    target_state: str = ""
    connected_is_sampling: str = ""
    log_values: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def field_map(self) -> dict[str, str]:
        """Return the known scalar fields as a display-order mapping."""
        return {
            "DisplayName": self.display_name,
            "NodeId": self.node_id,
            "AttributeId": self.attribute_id,
            "SamplingInterval": self.sampling_interval,
            "QueueSize": self.queue_size,
            "DiscardOldest": self.discard_oldest,
            "TargetState": self.target_state,
            "ConnectedIsSampling": self.connected_is_sampling,
            "LogValues": self.log_values,
        }


@dataclass
class Subscription:
    """A subscription grouping a set of monitored items."""

    display_name: str = ""
    lifetime_count: str = ""
    max_keep_alive_count: str = ""
    max_notifications_per_publish: str = ""
    priority: str = ""
    timestamps_to_return: str = ""
    publishing_interval: str = ""
    target_state: str = ""
    items: list[MonitoredItem] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class BrowseOptions:
    """The browse filter settings stored on a session."""

    browse_direction: str = ""
    continue_until_done: str = ""
    include_subtypes: str = ""
    max_references_returned: str = ""
    node_class_mask: str = ""
    reference_type_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionInfo:
    """One saved OPC UA client connection."""

    check_domain: str = ""
    encoding: str = ""
    application_name: str = ""
    security_mode: str = ""
    security_policy: str = ""
    session_name: str = ""
    target_state: str = ""
    timeout: str = ""
    url: str = ""
    # Base64 of a UTF-16LE XML fragment describing the user identity. May
    # contain credentials, so callers must treat it as a secret.
    user_identity: str = ""
    subscriptions: list[Subscription] = field(default_factory=list)
    browse_options: BrowseOptions | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def item_count(self) -> int:
        return sum(len(sub.items) for sub in self.subscriptions)


@dataclass
class Project:
    """A parsed ``.sopcc`` document."""

    version: str = ""
    sessions: list[SessionInfo] = field(default_factory=list)
    source_path: str = ""
    raw_xml: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def subscription_count(self) -> int:
        return sum(len(ses.subscriptions) for ses in self.sessions)

    @property
    def item_count(self) -> int:
        return sum(ses.item_count for ses in self.sessions)
