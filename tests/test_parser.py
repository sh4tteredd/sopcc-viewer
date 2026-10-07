"""Tests for :mod:`sopcc.parser`."""

from __future__ import annotations

import unittest
from pathlib import Path

from sopcc.parser import SopccError, load_project, parse_string, pretty_xml

FIXTURES = Path(__file__).parent / "fixtures"
REAL_FILE = FIXTURES / "3047_SoftingOPCProject.sopcc"
MULTI_FILE = FIXTURES / "multi_session.sopcc"


class RealFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = load_project(REAL_FILE)

    def test_top_level_counts(self) -> None:
        self.assertEqual(self.project.version, "1.44.0.7154")
        self.assertEqual(len(self.project.sessions), 1)
        self.assertEqual(self.project.subscription_count, 10)
        self.assertEqual(self.project.item_count, 138)

    def test_session_fields(self) -> None:
        session = self.project.sessions[0]
        self.assertEqual(session.session_name, "dataFEED OPC UA Client 1")
        self.assertEqual(session.url, "opc.tcp://uagate3194:4840/")
        self.assertEqual(session.encoding, "Binary")
        self.assertEqual(session.security_mode, "None")
        self.assertIsNotNone(session.browse_options)
        self.assertEqual(session.browse_options.reference_type_id, "ns=0;i=33")

    def test_subscriptions(self) -> None:
        first = self.project.sessions[0].subscriptions[0]
        self.assertEqual(first.display_name, "Washing_tank")
        self.assertEqual(first.publishing_interval, "1000")
        self.assertEqual(len(first.items), 11)

        item = first.items[0]
        self.assertEqual(item.display_name, "Temperature_Is")
        self.assertEqual(item.attribute_id, "Value")
        self.assertEqual(item.node_id, "ns=2;s=S7-1.IDB_Temp_WT.Static.OP_IST_TEMP")
        self.assertEqual(item.sampling_interval, "1000")

    def test_no_warnings_and_raw_xml_kept(self) -> None:
        self.assertEqual(self.project.warnings, [])
        self.assertIn("Sessions", self.project.raw_xml)

    def test_total_items_matches_subscription_sum(self) -> None:
        session = self.project.sessions[0]
        self.assertEqual(session.item_count, sum(len(s.items) for s in session.subscriptions))


class SyntheticFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = load_project(MULTI_FILE)

    def test_multiple_sessions(self) -> None:
        self.assertEqual(len(self.project.sessions), 2)
        self.assertEqual(self.project.sessions[0].session_name, "Line A")
        self.assertEqual(self.project.sessions[1].session_name, "Line B")
        self.assertEqual(self.project.sessions[1].item_count, 0)

    def test_unknown_elements_preserved_and_warned(self) -> None:
        self.assertTrue(any("FutureTopLevel" in w for w in self.project.warnings))
        item = self.project.sessions[0].subscriptions[0].items[0]
        self.assertEqual(item.extra.get("FutureField"), "keep me")

    def test_bom_is_handled(self) -> None:
        # The fixture begins with a UTF-8 BOM; parsing must still succeed.
        self.assertEqual(self.project.version, "1.44.0.7154")


class ErrorHandlingTests(unittest.TestCase):
    def test_malformed_xml_raises(self) -> None:
        with self.assertRaises(SopccError):
            parse_string("<Sessions><Session>")

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_project(FIXTURES / "does_not_exist.sopcc")

    def test_unexpected_root_warns(self) -> None:
        project = parse_string("<Wrong/>")
        self.assertTrue(any("root" in w for w in project.warnings))

    def test_namespaced_document(self) -> None:
        xml = (
            '<Sessions xmlns="urn:softing" Version="9">'
            '<Session><SessionName>NS</SessionName></Session></Sessions>'
        )
        project = parse_string(xml)
        self.assertEqual(project.version, "9")
        self.assertEqual(project.sessions[0].session_name, "NS")


class PrettyXmlTests(unittest.TestCase):
    def test_pretty_xml_adds_newlines(self) -> None:
        raw = load_project(REAL_FILE).raw_xml
        pretty = pretty_xml(raw)
        self.assertGreater(pretty.count("\n"), 10)
        self.assertIn("<MonitoredItem>", pretty)


if __name__ == "__main__":
    unittest.main()
