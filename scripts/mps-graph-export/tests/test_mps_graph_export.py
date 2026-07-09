#!/usr/bin/env python3
"""Self-contained tests for mps_graph_export (stdlib unittest, no deps)."""

import io
import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mps_graph_export as mge  # noqa: E402

SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample.mps")
MODEL_UUID = "11111111-1111-4111-8111-111111111111"
OTHER_UUID = "22222222-2222-4222-8222-222222222222"


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.graph = mge.build_graph(
            [SAMPLE], edges="both", with_properties=True, model_nodes=True)

    def test_model_ref_parsing(self):
        uuid, name = mge._parse_model_ref("r:11111111-1111-4111-8111-111111111111(demo.model)")
        self.assertEqual(uuid, MODEL_UUID)
        self.assertEqual(name, "demo.model")

    def test_concept_and_role_resolution(self):
        root = self.graph.nodes[f"{MODEL_UUID}:root1"]
        self.assertEqual(root.concept, "Root")
        self.assertEqual(root.label, "MyRoot")
        item = self.graph.nodes[f"{MODEL_UUID}:itemA"]
        self.assertEqual(item.concept, "Item")
        self.assertEqual(item.role, "items")   # containment role resolved

    def test_containment_edges(self):
        cont = [e for e in self.graph.edges if e.kind == "containment"]
        pairs = {(e.source, e.target, e.role) for e in cont}
        # model -> root
        self.assertIn((MODEL_UUID, f"{MODEL_UUID}:root1", "root"), pairs)
        # root -> items
        self.assertIn((f"{MODEL_UUID}:root1", f"{MODEL_UUID}:itemA", "items"), pairs)
        self.assertIn((f"{MODEL_UUID}:root1", f"{MODEL_UUID}:itemB", "items"), pairs)

    def test_same_model_reference(self):
        refs = [e for e in self.graph.edges if e.kind == "reference"]
        local = [e for e in refs if e.source == f"{MODEL_UUID}:itemA"]
        self.assertEqual(len(local), 1)
        self.assertEqual(local[0].target, f"{MODEL_UUID}:itemB")
        self.assertEqual(local[0].role, "target")

    def test_cross_model_reference_creates_external(self):
        target_gid = f"{OTHER_UUID}:externalItem"
        self.assertIn(target_gid, self.graph.nodes)
        self.assertEqual(self.graph.nodes[target_gid].kind, "external")
        refs = [e for e in self.graph.edges
                if e.source == f"{MODEL_UUID}:itemB" and e.target == target_gid]
        self.assertEqual(len(refs), 1)

    def test_properties_carried(self):
        item = self.graph.nodes[f"{MODEL_UUID}:itemA"]
        self.assertEqual(item.properties.get("name"), "Alpha")

    def test_edge_filtering(self):
        cont_only = mge.build_graph([SAMPLE], edges="containment",
                                    with_properties=False, model_nodes=True)
        self.assertTrue(all(e.kind == "containment" for e in cont_only.edges))
        ref_only = mge.build_graph([SAMPLE], edges="references",
                                   with_properties=False, model_nodes=True)
        self.assertTrue(all(e.kind == "reference" for e in ref_only.edges))
        self.assertEqual(len(ref_only.edges), 2)


class WriterTest(unittest.TestCase):
    def setUp(self):
        self.graph = mge.build_graph(
            [SAMPLE], edges="both", with_properties=True, model_nodes=True)

    def test_graphml_is_well_formed(self):
        buf = io.StringIO()
        mge.write_graphml(self.graph, buf, with_properties=True)
        root = ET.fromstring(buf.getvalue())  # raises on malformed XML
        ns = "{http://graphml.graphdrawing.org/xmlns}"
        graph_el = root.find(f"{ns}graph")
        self.assertIsNotNone(graph_el)
        self.assertEqual(len(graph_el.findall(f"{ns}node")), len(self.graph.nodes))
        self.assertEqual(len(graph_el.findall(f"{ns}edge")), len(self.graph.edges))

    def test_graphml_key_ids_unique(self):
        buf = io.StringIO()
        mge.write_graphml(self.graph, buf, with_properties=True)
        root = ET.fromstring(buf.getvalue())
        ns = "{http://graphml.graphdrawing.org/xmlns}"
        ids = [k.get("id") for k in root.findall(f"{ns}key")]
        self.assertEqual(len(ids), len(set(ids)), f"duplicate key ids: {ids}")
        # Every edge <data key=...> must reference a declared key.
        for edge in root.iter(f"{ns}edge"):
            for data in edge.findall(f"{ns}data"):
                self.assertIn(data.get("key"), ids)

    def test_json_roundtrip(self):
        import json
        buf = io.StringIO()
        mge.write_json(self.graph, buf, with_properties=True)
        data = json.loads(buf.getvalue())
        self.assertTrue(data["directed"])
        self.assertEqual(len(data["nodes"]), len(self.graph.nodes))
        self.assertEqual(len(data["links"]), len(self.graph.edges))

    def test_dot_and_gml_render(self):
        for writer in (mge.write_dot, mge.write_gml):
            buf = io.StringIO()
            writer(self.graph, buf, with_properties=False)
            self.assertTrue(buf.getvalue().strip())

    def test_dot_uses_single_backslash_newline(self):
        buf = io.StringIO()
        mge.write_dot(self.graph, buf, with_properties=False)
        text = buf.getvalue()
        # DOT label newline must be "\n", not a doubled "\\n".
        self.assertIn(r'label="Root\nMyRoot"', text)
        self.assertNotIn(r"\\n", text)

    def test_xml_escaping(self):
        self.assertEqual(mge._xml_escape('a<b>&"c'), "a&lt;b&gt;&amp;&quot;c")


if __name__ == "__main__":
    unittest.main()
