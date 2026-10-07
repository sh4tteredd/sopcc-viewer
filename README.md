# SOPCC Viewer

A read-only reader and desktop viewer for **Softing dataFEED OPC Suite project
files** (`.sopcc`).

A `.sopcc` file is a single-line XML document (usually UTF-8, often with a BOM)
rooted at `<Sessions>`. Each `<Session>` describes one saved OPC UA client
connection and contains zero or more `<Subscription>` elements, each holding
`<MonitoredItem>` elements. SOPCC Viewer parses those files into plain Python
dataclasses and presents them through a clean Tkinter GUI — or lets you script
against the parsed model directly.

The tool is strictly **read-only**: it never writes back to a `.sopcc` file.
It can, however, *decode and reveal* the stored user identity (which may include
credentials), so treat the source files as sensitive.

## Features

- **Tolerant parser** — no assumptions about field order, namespaces, element
  count, or document version. Unknown elements are preserved instead of being
  dropped, and a warning is recorded rather than raising.
- **Overview tab** — connection metadata plus project-level statistics
  (sessions, subscriptions, items, namespaces, sampling intervals, target
  states).
- **Items tab** — every monitored item in a sortable, striped table with a
  case-insensitive search filter.
- **Details tab** — full field view of the selected monitored item, including
  any preserved unknown fields.
- **Symbol tree tab** — a hierarchy derived from the dot-separated symbol path
  of string NodeIds (e.g. `ns=2;s=S7-1.IDB.Static.OP` → `S7-1` → `IDB` →
  `Static` → `OP`). Non-symbolic NodeIds are grouped under `<non-symbolic>`.
- **Raw XML tab** — pretty-printed document view, with the `<UserIdentity>`
  block masked by default.
- **Identity handling** — the base64 `UserIdentity` blob is decoded and
  summarised; credentials stay masked until explicitly revealed.
- **Export** — flatten monitored items to CSV, or export the whole project to
  JSON.
- **Light and dark themes.**

## Requirements

- Python 3.10 or newer
- Tkinter (bundled with most Python installs; on macOS with Homebrew Python it
  is a separate package — see below)

The core parser and exports have **no third-party dependencies**.

### Installing Tkinter

If `import tkinter` fails, the GUI cannot start. The command-line entry point
prints a hint and exits. On macOS with a Homebrew Python:

```sh
brew install python-tk
```

On Debian/Ubuntu:

```sh
sudo apt-get install python3-tk
```

On Arch Linux:

```sh
sudo pacman -S tk
```

## Running

There is no package metadata in this repository, so run the viewer from the
repository root. Launch the GUI with no argument (use the **Open…** button from
there), or pass a file to open on startup:

```sh
python -m sopcc
python -m sopcc path/to/project.sopcc
```

You can also launch it directly through the entry point:

```sh
python -c "from sopcc.gui.app import main; main()"
```

To make it importable system-wide, add the repository root to `PYTHONPATH` or
install the `sopcc` package directory into your environment.

## Using the GUI

The window is split into a structure sidebar on the left (sessions →
subscriptions → items) and a tabbed content area on the right.

| Tab | Contents |
| --- | --- |
| **Overview** | Connection fields for the selected session and a project summary |
| **Items** | Sortable table of all monitored items; click a column heading to sort |
| **Details** | All fields of the selected item, including preserved extra fields |
| **Symbol tree** | NodeId symbol hierarchy, with per-branch item counts |
| **Raw XML** | Pretty-printed source, identity masked unless revealed |

Toolbar and menu actions:

- **Open…** / `Cmd+O` — choose a `.sopcc` file.
- **Reload** / `Cmd+R` — re-read the current file from disk.
- **Export CSV** — write one row per monitored item.
- **Export JSON** — write the nested project representation.
- **Search** — filters the sidebar tree and items table as you type.
- **Reveal identity** (View menu or toolbar) — toggles decoding of the
  `<UserIdentity>` blob. When enabled, the identity fields (and the raw XML
  block) are shown in clear text.
- **Light / Dark theme** — switch palettes (`Cmd+D` toggles).

## Programmatic use

The parser is a plain library. Load a file and walk the dataclasses:

```python
from sopcc import load_project
from sopcc.derive import parse_node_id, project_stats

project = load_project("project.sopcc")

print(project.version)
print(project_stats(project))

for session in project.sessions:
    print(session.session_name, session.url, session.item_count)
    for subscription in session.subscriptions:
        for item in subscription.items:
            info = parse_node_id(item.node_id)
            print(f"  {item.display_name}: {info.identifier_type_name} "
                  f"ns={info.namespace_index}")
```

Key entry points:

- `sopcc.parser.load_project(path)` → `Project`
- `sopcc.parser.parse_string(text, source_path="")` → `Project`
- `sopcc.parser.pretty_xml(text)` → indented XML for display
- `sopcc.parser.SopccError` — raised when a file is not well-formed XML
- `sopcc.model` — `Project`, `SessionInfo`, `Subscription`, `MonitoredItem`,
  `BrowseOptions`
- `sopcc.derive` — `parse_node_id`, `build_symbol_tree`, `project_stats`,
  `subscription_stats`, `identity_summary`, `IdentitySummary`, `SymbolNode`
- `sopcc.export` — `item_rows`, `export_csv`, `project_to_dict`, `export_json`

### Exporting

```python
from sopcc import load_project
from sopcc.export import export_csv, export_json

project = load_project("project.sopcc")
export_csv(project, "items.csv")                       # one row per item
export_json(project, "project.json")                   # identity masked
export_json(project, "project.json", include_secrets=True)  # reveals credentials
```

## Security: user identities

Sessions may store a base64-encoded UTF-16LE XML fragment describing the OPC UA
user identity. This can contain a username and password in clear text once
decoded.

- The GUI masks the `<UserIdentity>` block until you enable **Reveal identity**.
- `identity_summary(user_identity)` returns only the identity *type* by default.
- `export_json(..., include_secrets=False)` (the default) omits the secret
  fields.
- Passing `include_secrets=True` (to `identity_summary` or `export_json`)
  decodes and exposes the credentials — only do this when you intend to.

Treat exported JSON or revealed values as secrets.

## Project layout

```
sopcc/
  __init__.py      # public API and version
  __main__.py      # `python -m sopcc` entry point
  model.py         # dataclasses for Project / Session / Subscription / Item
  parser.py        # tolerant, namespace-agnostic .sopcc parser
  derive.py        # NodeId parsing, symbol tree, stats, identity summary
  export.py        # CSV and JSON exporters
  gui/
    app.py         # main Tkinter window and wiring
    views.py       # reusable panels (overview, details, symbol tree, text)
    filters.py     # search predicates
    theme.py       # light/dark palettes and ttk restyling
tests/
  test_parser.py   # parser behaviour and error handling
  test_derive.py   # derive helpers, identity handling, exports
  fixtures/
    multi_session.sopcc
```

## Testing

Run the suite with `unittest` from the repository root:

```sh
python -m unittest discover -s tests
```

> **Note:** `tests/test_parser.py` and `tests/test_derive.py` reference a
> fixture named `3047_SoftingOPCProject.sopcc`, which is **not included** in
> this repository (it is a real customer-style project file). Tests that depend
> on it will fail unless you drop that file into `tests/fixtures/`. The
> synthetic `multi_session.sopcc` fixture is included and covers multiple
> sessions, BOM handling, unknown-element preservation, and identity masking.

## Scope and limitations

- Read-only: no editing or saving of `.sopcc` files.
- The parser recognises the elements documented in `sopcc/parser.py`; anything
  else is kept under each object's `extra` mapping and reported as a warning.
- Not affiliated with Softing; it is an independent viewer for the file format.
