"""Shared search/filter predicates for the GUI."""

from __future__ import annotations

from ..model import MonitoredItem, Subscription

ITEM_SEARCH_FIELDS = (
    "display_name",
    "node_id",
    "attribute_id",
    "sampling_interval",
    "target_state",
    "log_values",
)


def item_matches(item: MonitoredItem, query: str) -> bool:
    """Case-insensitive substring match across the item's searchable fields."""
    if not query:
        return True
    needle = query.casefold()
    return any(
        needle in str(getattr(item, field)).casefold() for field in ITEM_SEARCH_FIELDS
    )


def subscription_matches(subscription: Subscription, query: str) -> bool:
    """True when the subscription name matches or any of its items match."""
    if not query:
        return True
    if query.casefold() in subscription.display_name.casefold():
        return True
    return any(item_matches(item, query) for item in subscription.items)
