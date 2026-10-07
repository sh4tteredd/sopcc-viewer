"""Export a parsed project to CSV or JSON."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from typing import Any

from .derive import identity_summary, parse_node_id
from .model import MonitoredItem, Project, SessionInfo, Subscription

ITEM_COLUMNS = [
    "session_name",
    "url",
    "subscription",
    "display_name",
    "node_id",
    "namespace_index",
    "identifier_type",
    "attribute_id",
    "sampling_interval",
    "queue_size",
    "discard_oldest",
    "target_state",
    "log_values",
]


def item_rows(project: Project) -> list[dict[str, str]]:
    """Flatten every monitored item into one row per item."""
    rows: list[dict[str, str]] = []
    for session in project.sessions:
        for subscription in session.subscriptions:
            for item in subscription.items:
                info = parse_node_id(item.node_id)
                rows.append(
                    {
                        "session_name": session.session_name,
                        "url": session.url,
                        "subscription": subscription.display_name,
                        "display_name": item.display_name,
                        "node_id": item.node_id,
                        "namespace_index": (
                            "" if info.namespace_index is None else str(info.namespace_index)
                        ),
                        "identifier_type": info.identifier_type_name,
                        "attribute_id": item.attribute_id,
                        "sampling_interval": item.sampling_interval,
                        "queue_size": item.queue_size,
                        "discard_oldest": item.discard_oldest,
                        "target_state": item.target_state,
                        "log_values": item.log_values,
                    }
                )
    return rows


def export_csv(project: Project, path: str) -> int:
    """Write one row per monitored item to ``path``; return the row count."""
    rows = item_rows(project)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ITEM_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _item_to_dict(item: MonitoredItem) -> dict[str, Any]:
    data = asdict(item)
    data.pop("extra", None)
    return data


def _subscription_to_dict(subscription: Subscription) -> dict[str, Any]:
    return {
        "display_name": subscription.display_name,
        "lifetime_count": subscription.lifetime_count,
        "max_keep_alive_count": subscription.max_keep_alive_count,
        "max_notifications_per_publish": subscription.max_notifications_per_publish,
        "priority": subscription.priority,
        "timestamps_to_return": subscription.timestamps_to_return,
        "publishing_interval": subscription.publishing_interval,
        "target_state": subscription.target_state,
        "items": [_item_to_dict(item) for item in subscription.items],
    }


def project_to_dict(project: Project, include_secrets: bool = False) -> dict[str, Any]:
    """Return a JSON-serialisable nested representation of the project."""
    sessions: list[dict[str, Any]] = []
    for session in project.sessions:
        identity = identity_summary(session.user_identity, include_secrets=include_secrets)
        browse = None
        if session.browse_options is not None and is_dataclass(session.browse_options):
            browse = {
                key: value
                for key, value in asdict(session.browse_options).items()
                if key != "extra"
            }
        sessions.append(
            {
                "check_domain": session.check_domain,
                "encoding": session.encoding,
                "application_name": session.application_name,
                "security_mode": session.security_mode,
                "security_policy": session.security_policy,
                "session_name": session.session_name,
                "target_state": session.target_state,
                "timeout": session.timeout,
                "url": session.url,
                "identity": {
                    "type": identity.label,
                    "is_anonymous": identity.is_anonymous,
                    "masked": identity.masked,
                    "fields": identity.fields,
                },
                "subscriptions": [
                    _subscription_to_dict(sub) for sub in session.subscriptions
                ],
                "browse_options": browse,
            }
        )
    return {
        "version": project.version,
        "source_path": project.source_path,
        "sessions": sessions,
    }


def export_json(project: Project, path: str, include_secrets: bool = False) -> None:
    """Write the nested project representation to ``path``."""
    data = project_to_dict(project, include_secrets=include_secrets)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
