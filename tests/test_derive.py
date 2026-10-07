"""Tests for :mod:`sopcc.derive` and :mod:`sopcc.export`."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sopcc.derive import (
    build_symbol_tree,
    identity_summary,
    parse_node_id,
    project_stats,
    subscription_stats,
)
from sopcc.export import export_csv, export_json, item_rows, project_to_dict
from sopcc.parser import load_project

FIXTURES = Path(__file__).parent / "fixtures"
REAL_FILE = FIXTURES / "3047_SoftingOPCProject.sopcc"
MULTI_FILE = FIXTURES / "multi_session.sopcc"


class NodeIdTests(unittest.TestCase):
    def test_string_node_id(self) -> None:
        info = parse_node_id("ns=2;s=S7-1.IDB_Temp_WT.Static.OP_IST_TEMP")
        self.assertEqual(info.namespace_index, 2)
        self.assertEqual(info.identifier_type, "s")
        self.assertEqual(info.identifier_type_name, "String")
        self.assertEqual(
            info.symbol_parts, ["S7-1", "IDB_Temp_WT", "Static", "OP_IST_TEMP"]
        )

    def test_numeric_node_id(self) -> None:
        info = parse_node_id("ns=0;i=33")
        self.assertEqual(info.namespace_index, 0)
        self.assertEqual(info.identifier_type, "i")
        self.assertEqual(info.identifier_type_name, "Numeric")
        self.assertEqual(info.symbol_parts, [])

    def test_bare_node_id(self) -> None:
        info = parse_node_id("i=85")
        self.assertIsNone(info.namespace_index)
        self.assertEqual(info.identifier, "85")


class SymbolTreeTests(unittest.TestCase):
    def test_tree_groups_by_symbol_path(self) -> None:
        project = load_project(REAL_FILE)
        root = build_symbol_tree(project)
        self.assertIn("S7-1", root.children)
        s7 = root.children["S7-1"]
        self.assertIn("IDB_Temp_WT", s7.children)
        self.assertEqual(root.subtree_item_count, 138)

        temp_wt = s7.children["IDB_Temp_WT"]
        self.assertGreater(temp_wt.subtree_item_count, 0)

    def test_non_symbolic_items_grouped(self) -> None:
        project = load_project(MULTI_FILE)
        root = build_symbol_tree(project)
        self.assertIn("<non-symbolic>", root.children)


class StatsTests(unittest.TestCase):
    def test_project_stats(self) -> None:
        project = load_project(REAL_FILE)
        stats = project_stats(project)
        self.assertEqual(stats["sessions"], 1)
        self.assertEqual(stats["subscriptions"], 10)
        self.assertEqual(stats["items"], 138)
        self.assertEqual(stats["namespaces"].get(2), 138)
        self.assertEqual(stats["sampling_intervals"].get("1000"), 138)

    def test_subscription_stats(self) -> None:
        project = load_project(REAL_FILE)
        stats = subscription_stats(project.sessions[0].subscriptions[0])
        self.assertEqual(stats["item_count"], 11)
        self.assertEqual(stats["intervals"], {"1000": 11})


class IdentityTests(unittest.TestCase):
    def test_anonymous_identity_from_real_file(self) -> None:
        project = load_project(REAL_FILE)
        summary = identity_summary(project.sessions[0].user_identity)
        self.assertTrue(summary.is_anonymous)
        self.assertEqual(summary.identity_type, "AnonymousUserIdentity")

    def test_username_identity_masked_by_default(self) -> None:
        project = load_project(MULTI_FILE)
        summary = identity_summary(project.sessions[0].user_identity)
        self.assertEqual(summary.identity_type, "UserNameIdentityToken")
        self.assertTrue(summary.masked)
        self.assertEqual(summary.fields, {})
        self.assertEqual(summary.decoded_xml, "")

    def test_username_identity_revealed_on_request(self) -> None:
        project = load_project(MULTI_FILE)
        summary = identity_summary(
            project.sessions[0].user_identity, include_secrets=True
        )
        self.assertFalse(summary.masked)
        self.assertEqual(summary.fields.get("UserName"), "operator")
        self.assertEqual(summary.fields.get("Password"), "secret")


class ExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = load_project(REAL_FILE)

    def test_item_rows(self) -> None:
        rows = item_rows(self.project)
        self.assertEqual(len(rows), 138)
        self.assertEqual(rows[0]["subscription"], "Washing_tank")
        self.assertEqual(rows[0]["namespace_index"], "2")
        self.assertEqual(rows[0]["identifier_type"], "String")

    def test_export_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "items.csv"
            count = export_csv(self.project, str(out))
            self.assertEqual(count, 138)
            lines = out.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 139)  # header + 138 rows
            self.assertIn("node_id", lines[0])

    def test_export_json_masks_identity(self) -> None:
        project = load_project(MULTI_FILE)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "project.json"
            export_json(project, str(out))
            data = json.loads(out.read_text(encoding="utf-8"))
            identity = data["sessions"][0]["identity"]
            self.assertTrue(identity["masked"])
            self.assertEqual(identity["fields"], {})

    def test_project_to_dict_counts(self) -> None:
        data = project_to_dict(self.project)
        self.assertEqual(len(data["sessions"]), 1)
        self.assertEqual(len(data["sessions"][0]["subscriptions"]), 10)


if __name__ == "__main__":
    unittest.main()
