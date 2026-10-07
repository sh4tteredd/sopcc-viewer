"""Reusable Tkinter panels used by the ``.sopcc`` viewer."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable

from ..derive import IdentitySummary, SymbolNode
from .theme import Palette


class FieldList(ttk.Frame):
    """A simple two-column grid of ``(label, value)`` rows."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, style="Card.TFrame")
        self.columnconfigure(1, weight=1)
        self._row = 0

    def clear(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        self._row = 0

    def add(self, label: str, value: object, wrap: int = 0) -> None:
        name = ttk.Label(self, text=f"{label}:" if label else "", style="Field.TLabel")
        text = "" if value is None else str(value)
        kwargs: dict = {"text": text, "style": "Value.TLabel", "justify": "left"}
        if wrap:
            kwargs["wraplength"] = wrap
        val = ttk.Label(self, **kwargs)
        name.grid(row=self._row, column=0, sticky="nw", padx=(0, 12), pady=3)
        val.grid(row=self._row, column=1, sticky="nw", pady=3)
        self._row += 1

    def add_all(self, rows: Iterable[tuple[str, object]], wrap: int = 0) -> None:
        for label, value in rows:
            self.add(label, value, wrap=wrap)


class ScrollableText(ttk.Frame):
    """A read-only text area with scrollbars, themed to match the app."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, style="Card.TFrame")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.text = tk.Text(self, wrap="none", relief="flat", borderwidth=0, padx=14, pady=12)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.text.configure(state="disabled")

    def set_palette(self, palette: Palette, mono_family: str) -> None:
        self.text.configure(
            background=palette.editor_bg,
            foreground=palette.editor_fg,
            insertbackground=palette.editor_fg,
            selectbackground=palette.select_bg,
            selectforeground=palette.select_fg,
            font=(mono_family, 12),
        )

    def set_text(self, content: str) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.configure(state="disabled")


class OverviewPanel(ttk.Frame):
    """Session metadata plus a compact project summary, as two titled sections."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, style="Card.TFrame", padding=(20, 18))
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="Connection", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )
        ttk.Label(self, text="Summary", style="Title.TLabel").grid(
            row=0, column=1, sticky="w", pady=(0, 10)
        )

        self._left = FieldList(self)
        self._right = FieldList(self)
        self._left.grid(row=1, column=0, sticky="nw", padx=(0, 32))
        self._right.grid(row=1, column=1, sticky="nw")

    def show_session(
        self,
        session,
        identity: IdentitySummary,
        project_stats: dict,
        session_index: int,
        session_total: int,
    ) -> None:
        self._left.clear()
        self._right.clear()

        self._left.add("Session", f"{session_index + 1} of {session_total}")
        self._left.add("Name", session.session_name)
        self._left.add("Application", session.application_name)
        self._left.add("URL", session.url)
        self._left.add("Encoding", session.encoding)
        self._left.add("Timeout (ms)", session.timeout)
        self._left.add("Target state", session.target_state)
        self._left.add("Security mode", session.security_mode)
        self._left.add("Security policy", session.security_policy)
        self._left.add("Check domain", session.check_domain)

        identity_text = identity.label
        if identity.is_anonymous:
            identity_text = "Anonymous"
        elif identity.masked:
            identity_text += " (masked)"
        self._left.add("User identity", identity_text)
        if not identity.masked and identity.fields:
            for key, value in identity.fields.items():
                self._left.add(f"  {key}", value)

        self._right.add("Subscriptions", len(session.subscriptions))
        self._right.add("Monitored items", session.item_count)
        self._right.add("Project sessions", project_stats.get("sessions", 0))
        self._right.add("Project items", project_stats.get("items", 0))

        ns = project_stats.get("namespaces", {})
        self._right.add(
            "Namespaces", ", ".join(f"ns={k} ({v})" for k, v in ns.items())
        )
        intervals = project_stats.get("sampling_intervals", {})
        self._right.add(
            "Sampling intervals",
            ", ".join(f"{k or 'default'} \u00d7{v}" for k, v in intervals.items()),
        )
        states = project_stats.get("target_states", {})
        self._right.add(
            "Target states", ", ".join(f"{k or 'n/a'}: {v}" for k, v in states.items())
        )


class DetailsPanel(ttk.Frame):
    """Full field view of the selected monitored item."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, style="Card.TFrame", padding=(20, 18))
        self.columnconfigure(0, weight=1)
        self._title = ttk.Label(self, text="Monitored item", style="Title.TLabel")
        self._title.grid(row=0, column=0, sticky="w", pady=(0, 12))
        self._fields = FieldList(self)
        self._fields.grid(row=1, column=0, sticky="nw")

    def show_item(self, item, session, subscription) -> None:
        self._fields.clear()
        self._fields.add("Session", session.session_name)
        self._fields.add("URL", session.url)
        self._fields.add("Subscription", subscription.display_name)
        self._fields.add("Publishing interval", subscription.publishing_interval)
        self._fields.add("", "")
        self._fields.add_all(item.field_map().items(), wrap=560)
        if item.extra:
            self._fields.add("", "")
            for key, value in item.extra.items():
                self._fields.add(key, value, wrap=560)

    def clear(self) -> None:
        self._fields.clear()


class SymbolTreePanel(ttk.Frame):
    """Hierarchy derived from the dot-separated NodeId symbols."""

    def __init__(
        self,
        master: tk.Misc,
        on_select: Callable[[object], None] | None = None,
    ) -> None:
        super().__init__(master, style="Card.TFrame")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self._on_select = on_select
        self._node_by_iid: dict[str, SymbolNode] = {}
        self.tree = ttk.Treeview(self, show="tree", selectmode="browse")
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        vsb.grid(row=0, column=1, sticky="ns", pady=4)
        self.tree.bind("<<TreeviewSelect>>", self._handle_select)

    def populate(self, root: SymbolNode) -> None:
        self.tree.delete(*self.tree.get_children())
        self._node_by_iid.clear()
        for name in sorted(root.children):
            self._insert("", root.children[name])

    def _insert(self, parent: str, node: SymbolNode) -> str:
        label = f"{node.name}  ({node.subtree_item_count})"
        item_id = self.tree.insert(parent, "end", text=label, open=False)
        self._node_by_iid[item_id] = node
        for name in sorted(node.children):
            self._insert(item_id, node.children[name])
        return item_id

    def _handle_select(self, _event: object) -> None:
        selection = self.tree.selection()
        if not selection or self._on_select is None:
            return
        node = self._node_by_iid.get(selection[0])
        if node is not None and node.entries:
            self._on_select(node.entries[0])
