"""Reader and viewer for Softing dataFEED OPC Suite project files (``.sopcc``).

The public entry points are :func:`sopcc.parser.load_project` for parsing a
file into the dataclasses in :mod:`sopcc.model`, and the ``sopcc.gui`` package
for the Tkinter viewer.
"""

from __future__ import annotations

from .model import (
    BrowseOptions,
    MonitoredItem,
    Project,
    SessionInfo,
    Subscription,
)
from .parser import load_project

__all__ = [
    "BrowseOptions",
    "MonitoredItem",
    "Project",
    "SessionInfo",
    "Subscription",
    "load_project",
]

__version__ = "0.1.0"
