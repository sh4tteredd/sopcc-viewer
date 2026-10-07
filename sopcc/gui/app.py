"""Main Tkinter application window for viewing ``.sopcc`` projects."""

from __future__ import annotations

import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .. import __version__
from ..derive import (
    build_symbol_tree,
    identity_summary,
    parse_node_id,
    project_stats,
)
from ..export import export_csv, export_json
from ..model import Project
from ..parser import SopccError, load_project, pretty_xml
from . import theme
from .filters import item_matches, subscription_matches
from .views import DetailsPanel, OverviewPanel, ScrollableText, SymbolTreePanel

_USER_IDENTITY_RE = re.compile(r"(<UserIdentity>).*?(</UserIdentity>)", re.DOTALL)

_ITEM_COLUMNS = [
    ("subscription", "Subscription", 150),
    ("display_name", "Display Name", 190),
    ("node_id", "NodeId", 340),
    ("attribute_id", "Attribute", 90),
    ("sampling_interval", "Sampling (ms)", 110),
    ("queue_size", "Queue", 70),
    ("discard_oldest", "Discard Oldest", 110),
    ("target_state", "State", 90),
    ("log_values", "Log", 70),
]

_TABS = ["Overview", "Items", "Details", "Symbol tree", "Raw XML"]


class SopccApp(tk.Tk):
    """The application window."""

    def __init__(self, initial_path: str | None = None) -> None:
        super().__init__()
        self.title("SOPCC Viewer")
        self.geometry("1240x780")
        self.minsize(960, 600)

        self.project: Project | None = None
        self.current_path: str | None = None
        self.include_secrets = tk.BooleanVar(value=False)
        self.filter_text = tk.StringVar(value="")
        self.status_text = tk.StringVar(value="Open a .sopcc file to begin.")
        self.structure_text = tk.StringVar(value="No file loaded")
        self.header_file = tk.StringVar(value="No file loaded")
        self.theme_name = tk.StringVar(value="light")

        self.fonts = theme.Fonts(ui="Helvetica", mono="Courier")
        self.palette = theme.get_palette("light")

        self._tree_refs: dict[str, tuple] = {}
        self._row_refs: dict[str, tuple] = {}
        self._sort_column: str | None = None
        self._sort_reverse = False
        self.tab_buttons: dict[str, ttk.Button] = {}

        self._build_menu()
        self._build_layout()
        self._apply_theme("light")

        self.filter_text.trace_add("write", lambda *_: self._refresh_tree_and_table())

        if initial_path:
            self.after(50, lambda: self._load_path(initial_path))

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Open…", accelerator="Cmd+O", command=self.open_file)
        file_menu.add_command(label="Reload", accelerator="Cmd+R", command=self.reload)
        file_menu.add_separator()
        file_menu.add_command(label="Export items as CSV…", command=self.export_csv)
        file_menu.add_command(label="Export project as JSON…", command=self.export_json)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", accelerator="Cmd+Q", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=False)
        view_menu.add_checkbutton(
            label="Reveal user identity",
            variable=self.include_secrets,
            command=self._secrets_changed,
        )
        view_menu.add_separator()
        view_menu.add_radiobutton(
            label="Light theme",
            variable=self.theme_name,
            value="light",
            command=lambda: self._apply_theme("light"),
        )
        view_menu.add_radiobutton(
            label="Dark theme",
            variable=self.theme_name,
            value="dark",
            command=lambda: self._apply_theme("dark"),
        )
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menubar)
        self.bind_all("<Command-o>", lambda _e: self.open_file())
        self.bind_all("<Command-r>", lambda _e: self.reload())
        self.bind_all("<Command-d>", lambda _e: self._toggle_theme())

    def _build_layout(self) -> None:
        self._build_header()
        self._build_toolbar()

        body = ttk.Frame(self, style="Body.TFrame")
        body.pack(side="top", fill="both", expand=True)

        paned = ttk.PanedWindow(body, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=14, pady=(4, 12))

        paned.add(self._build_sidebar(paned), weight=1)
        paned.add(self._build_content(paned), weight=4)

        status = ttk.Frame(self, style="Divider.TFrame", height=1)
        status.pack(side="bottom", fill="x")
        ttk.Label(
            self,
            textvariable=self.status_text,
            style="Status.TLabel",
            anchor="w",
            padding=(14, 6),
        ).pack(side="bottom", fill="x")

    def _build_header(self) -> None:
        header = ttk.Frame(self, style="Header.TFrame")
        header.pack(side="top", fill="x")

        left = ttk.Frame(header, style="Header.TFrame")
        left.pack(side="left", padx=(20, 0), pady=16)
        ttk.Label(left, text="SOPCC Viewer", style="HeaderTitle.TLabel").pack(
            side="left"
        )
        ttk.Label(left, textvariable=self.header_file, style="HeaderSub.TLabel").pack(
            side="left", padx=(14, 0), pady=(6, 0)
        )

        right = ttk.Frame(header, style="Header.TFrame")
        right.pack(side="right", padx=(0, 18), pady=14)
        self._theme_buttons: dict[str, ttk.Button] = {}
        for name in ("light", "dark"):
            button = ttk.Button(
                right,
                text=name.capitalize(),
                width=6,
                style="Tab.TButton",
                command=lambda n=name: self._apply_theme(n),
            )
            button.pack(side="left", padx=2)
            self._theme_buttons[name] = button

        ttk.Frame(self, style="Accent.TFrame", height=3).pack(side="top", fill="x")

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self, style="Toolbar.TFrame", padding=(14, 12))
        toolbar.pack(side="top", fill="x")

        ttk.Button(
            toolbar, text="Open…", style="Accent.TButton", command=self.open_file
        ).pack(side="left")
        ttk.Button(
            toolbar, text="Reload", style="Flat.TButton", command=self.reload
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            toolbar, text="Export CSV", style="Flat.TButton", command=self.export_csv
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            toolbar, text="Export JSON", style="Flat.TButton", command=self.export_json
        ).pack(side="left", padx=(8, 0))

        self.reveal_button = ttk.Button(
            toolbar,
            text="Reveal identity",
            style="Flat.TButton",
            command=self._toggle_secrets,
        )
        self.reveal_button.pack(side="right")

        search = ttk.Frame(toolbar, style="Toolbar.TFrame")
        search.pack(side="right", padx=(0, 18))
        ttk.Label(search, text="Search", style="Card.TLabel").pack(side="left")
        ttk.Entry(search, textvariable=self.filter_text, width=26).pack(
            side="left", padx=(8, 0)
        )

        ttk.Frame(self, style="Divider.TFrame", height=1).pack(side="top", fill="x")

    def _build_sidebar(self, parent: tk.Misc) -> ttk.Frame:
        sidebar = ttk.Frame(parent, style="Surface.TFrame", padding=(14, 14))
        sidebar.rowconfigure(2, weight=1)
        sidebar.columnconfigure(0, weight=1)

        ttk.Label(sidebar, text="Structure", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            sidebar,
            textvariable=self.structure_text,
            style="Field.TLabel",
            wraplength=210,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        tree_wrap = ttk.Frame(sidebar, style="Surface.TFrame")
        tree_wrap.grid(row=2, column=0, sticky="nsew")
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(tree_wrap, show="tree", selectmode="browse")
        tree_vsb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_vsb.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda _e: self._select_tab("Details"))
        return sidebar

    def _build_content(self, parent: tk.Misc) -> ttk.Frame:
        content = ttk.Frame(parent, style="Surface.TFrame", padding=(0, 0))
        content.rowconfigure(1, weight=1)
        content.columnconfigure(0, weight=1)

        tabbar = ttk.Frame(content, style="Surface.TFrame", padding=(12, 12, 12, 0))
        tabbar.grid(row=0, column=0, sticky="ew")
        for name in _TABS:
            button = ttk.Button(
                tabbar,
                text=name,
                style="Tab.TButton",
                command=lambda n=name: self._select_tab(n),
            )
            button.pack(side="left", padx=(0, 6))
            self.tab_buttons[name] = button

        container = ttk.Frame(content, style="Surface.TFrame")
        container.grid(row=1, column=0, sticky="nsew")

        self.panels: dict[str, tk.Widget] = {
            "Overview": OverviewPanel(container),
            "Items": self._build_items_tab(container),
            "Details": DetailsPanel(container),
            "Symbol tree": SymbolTreePanel(container, on_select=self._on_symbol_select),
            "Raw XML": ScrollableText(container),
        }
        self.symbol_panel: SymbolTreePanel = self.panels["Symbol tree"]  # type: ignore[assignment]
        self.overview: OverviewPanel = self.panels["Overview"]  # type: ignore[assignment]
        self.details: DetailsPanel = self.panels["Details"]  # type: ignore[assignment]
        self.raw_panel: ScrollableText = self.panels["Raw XML"]  # type: ignore[assignment]

        self._select_tab("Overview")
        return content

    def _build_items_tab(self, parent: tk.Misc) -> ttk.Frame:
        frame = ttk.Frame(parent, style="Surface.TFrame")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.items_table = ttk.Treeview(
            frame,
            columns=[c[0] for c in _ITEM_COLUMNS],
            show="headings",
            selectmode="browse",
        )
        for key, label, width in _ITEM_COLUMNS:
            self.items_table.heading(
                key, text=label, command=lambda k=key: self._sort_items_by(k)
            )
            self.items_table.column(
                key, width=width, anchor="w", stretch=(key == "node_id")
            )
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.items_table.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.items_table.xview)
        self.items_table.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.items_table.grid(row=0, column=0, sticky="nsew", padx=(12, 0), pady=(12, 0))
        vsb.grid(row=0, column=1, sticky="ns", pady=(12, 0))
        hsb.grid(row=1, column=0, sticky="ew", padx=(12, 0))
        self.items_table.bind("<<TreeviewSelect>>", self._on_table_select)
        self.items_table.bind("<Double-1>", lambda _e: self._select_tab("Details"))
        return frame

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_theme(self, name: str) -> None:
        self.theme_name.set(name)
        self.palette = theme.get_palette(name)
        self.fonts = theme.apply_theme(self, self.palette)
        theme.configure_row_tags(self.items_table, self.palette)

        self.raw_panel.set_palette(self.palette, self.fonts.mono)

        for key, button in getattr(self, "_theme_buttons", {}).items():
            button.configure(
                style="TabActive.TButton" if key == name else "Tab.TButton"
            )
        self._update_reveal_button()
        self._select_tab(self._active_tab)

        if self.project is not None:
            self._populate_table()
            self._populate_symbol_tree()

    def _toggle_theme(self) -> None:
        self._apply_theme("dark" if self.theme_name.get() == "light" else "light")

    def _select_tab(self, name: str) -> None:
        if name not in self.panels:
            return
        self._active_tab = name
        for widget in self.panels.values():
            widget.pack_forget()
        self.panels[name].pack(fill="both", expand=True)
        for tab_name, button in self.tab_buttons.items():
            button.configure(
                style="TabActive.TButton" if tab_name == name else "Tab.TButton"
            )

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open .sopcc file",
            filetypes=[("Softing OPC project", "*.sopcc"), ("All files", "*.*")],
        )
        if path:
            self._load_path(path)

    def _load_path(self, path: str) -> None:
        try:
            project = load_project(path)
        except FileNotFoundError:
            messagebox.showerror("SOPCC Viewer", f"File not found:\n{path}")
            return
        except SopccError as exc:
            messagebox.showerror("SOPCC Viewer", str(exc))
            return

        self.project = project
        self.current_path = path
        base = os.path.basename(path)
        self.title(f"SOPCC Viewer \u2014 {base}")
        self.header_file.set(base)
        self._refresh_all()

    def reload(self) -> None:
        if self.current_path:
            self._load_path(self.current_path)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _refresh_all(self) -> None:
        self._populate_symbol_tree()
        self._refresh_tree_and_table()
        self._refresh_raw_xml()
        self._refresh_overview()

    def _populate_symbol_tree(self) -> None:
        if self.project is not None:
            self.symbol_panel.populate(build_symbol_tree(self.project))

    def _refresh_raw_xml(self) -> None:
        if self.project is None:
            self.raw_panel.set_text("")
            return
        text = pretty_xml(self.project.raw_xml)
        if not self.include_secrets.get():
            text = _USER_IDENTITY_RE.sub(
                r"\1<masked - enable View ▸ Reveal user identity>\2", text
            )
        self.raw_panel.set_text(text)

    def _refresh_overview(self) -> None:
        if self.project is None or not self.project.sessions:
            return
        session = self.project.sessions[0]
        self.overview.show_session(
            session,
            identity_summary(session.user_identity, self.include_secrets.get()),
            project_stats(self.project),
            0,
            len(self.project.sessions),
        )

    def _refresh_tree_and_table(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._tree_refs.clear()
        query = self.filter_text.get().strip()

        if self.project is None:
            self._populate_table()
            self.status_text.set("Open a .sopcc file to begin.")
            return

        for s_index, session in enumerate(self.project.sessions):
            ses_id = self.tree.insert(
                "",
                "end",
                text=f"{session.session_name or 'Session'}  ({session.item_count} items)",
                open=True,
            )
            self._tree_refs[ses_id] = ("session", s_index, None, None)

            visible = 0
            for sub in session.subscriptions:
                if not subscription_matches(sub, query):
                    continue
                sub_id = self.tree.insert(
                    ses_id,
                    "end",
                    text=f"{sub.display_name or '(subscription)'}  ({len(sub.items)})",
                    open=bool(query),
                )
                self._tree_refs[sub_id] = ("subscription", s_index, sub, None)
                for item in sub.items:
                    if not item_matches(item, query):
                        continue
                    item_id = self.tree.insert(
                        sub_id,
                        "end",
                        text=item.display_name or item.node_id or "(item)",
                    )
                    self._tree_refs[item_id] = ("item", s_index, sub, item)
                    visible += 1
        self._populate_table()
        self.status_text.set(
            f"{len(self.project.sessions)} session(s), "
            f"{self.project.subscription_count} subscription(s), "
            f"{self.project.item_count} item(s)"
            + (f" \u2014 {visible} match filter" if query else "")
        )
        self.structure_text.set(
            f"{self.project.subscription_count} subscriptions, "
            f"{self.project.item_count} items"
            + (f" \u2014 {visible} match" if query else "")
        )

    def _populate_table(self) -> None:
        self.items_table.delete(*self.items_table.get_children())
        self._row_refs.clear()
        if self.project is None:
            return
        query = self.filter_text.get().strip()

        rows: list[tuple] = []
        for session in self.project.sessions:
            for sub in session.subscriptions:
                for item in sub.items:
                    if not item_matches(item, query):
                        continue
                    info = parse_node_id(item.node_id)
                    values = {
                        "subscription": sub.display_name,
                        "display_name": item.display_name,
                        "node_id": item.node_id,
                        "attribute_id": item.attribute_id,
                        "sampling_interval": item.sampling_interval,
                        "queue_size": item.queue_size,
                        "discard_oldest": item.discard_oldest,
                        "target_state": item.target_state,
                        "log_values": item.log_values,
                        "_ns": info.namespace_index,
                    }
                    rows.append((session, sub, item, values))

        if self._sort_column:
            key = self._sort_column
            rows.sort(
                key=lambda r: _sort_key(r[3].get(key, "")),
                reverse=self._sort_reverse,
            )

        for index, (session, sub, item, values) in enumerate(rows):
            row_id = self.items_table.insert(
                "",
                "end",
                values=[values[c[0]] for c in _ITEM_COLUMNS],
                tags=("odd" if index % 2 else "even",),
            )
            self._row_refs[row_id] = (session, sub, item)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_tree_select(self, _event: object) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        ref = self._tree_refs.get(selection[0])
        if ref is None:
            return
        kind, s_index, sub, item = ref
        if kind == "item":
            self.details.show_item(item, self.project.sessions[s_index], sub)
        else:
            self._show_session_overview(s_index)

    def _show_session_overview(self, s_index: int) -> None:
        if self.project is None:
            return
        session = self.project.sessions[s_index]
        self.overview.show_session(
            session,
            identity_summary(session.user_identity, self.include_secrets.get()),
            project_stats(self.project),
            s_index,
            len(self.project.sessions),
        )

    def _on_table_select(self, _event: object) -> None:
        selection = self.items_table.selection()
        if not selection:
            return
        ref = self._row_refs.get(selection[0])
        if ref is None:
            return
        session, sub, item = ref
        self.details.show_item(item, session, sub)

    def _on_symbol_select(self, entry: object) -> None:
        session, sub, item = entry  # type: ignore[misc]
        self.details.show_item(item, session, sub)

    def _sort_items_by(self, column: str) -> None:
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False
        self._populate_table()

    def _toggle_secrets(self) -> None:
        self.include_secrets.set(not self.include_secrets.get())
        self._secrets_changed()

    def _secrets_changed(self) -> None:
        self._update_reveal_button()
        self._refresh_raw_xml()
        self._refresh_overview()

    def _update_reveal_button(self) -> None:
        on = self.include_secrets.get()
        self.reveal_button.configure(
            style="Accent.TButton" if on else "Flat.TButton",
            text="Reveal identity: On" if on else "Reveal identity",
        )

    # ------------------------------------------------------------------
    # Export & misc
    # ------------------------------------------------------------------

    def export_csv(self) -> None:
        if self.project is None:
            messagebox.showinfo("SOPCC Viewer", "Open a .sopcc file first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export items as CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=self._default_export_name(".csv"),
        )
        if not path:
            return
        count = export_csv(self.project, path)
        self.status_text.set(f"Exported {count} item(s) to {path}")

    def export_json(self) -> None:
        if self.project is None:
            messagebox.showinfo("SOPCC Viewer", "Open a .sopcc file first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export project as JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=self._default_export_name(".json"),
        )
        if not path:
            return
        export_json(self.project, path, include_secrets=self.include_secrets.get())
        self.status_text.set(f"Exported project to {path}")

    def _default_export_name(self, ext: str) -> str:
        if self.current_path:
            base = os.path.splitext(os.path.basename(self.current_path))[0]
            return base + ext
        return "export" + ext

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About SOPCC Viewer",
            f"SOPCC Viewer {__version__}\n\n"
            "Loads and visualises Softing dataFEED OPC Suite project files "
            "(.sopcc).\nRead-only: use View \u25b8 Reveal user identity to "
            "decode the stored credential.",
        )


def _sort_key(value: str):
    """Sort numerically when possible, otherwise case-insensitively."""
    text = str(value)
    try:
        return (0, float(text), text.casefold())
    except (TypeError, ValueError):
        return (1, 0.0, text.casefold())


def main(initial_path: str | None = None) -> None:
    app = SopccApp(initial_path=initial_path)
    app.mainloop()
