import os
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

from helpers import EXAMPLES, clone, example, schema
from ealib import View, catalogue_rows, write_catalogue
from ealib.bpmn import BpmnView, to_bpmn_xml
from ealib.exchange import to_archimate_xml, xsd_check

A = "{http://www.opengroup.org/xsd/archimate/3.0/}"
XSI = "{http://www.w3.org/2001/XMLSchema-instance}type"
B = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"


def archimate_view(model):
    v = View(model, "T1", title="test", viewpoint="Layered")
    plat, top = v.container("ACMP-01", 16, 16, 400, 120)
    a = v.node("ACMP-02", 32, top + 8, 150, 50)
    b = v.node("ACMP-03", 240, top + 8, 150, 50)
    v.edge([(b["x"], b["cy"]), (240 - 20, b["cy"]), (240 - 20, a["cy"] + 5), (a["r"] + 2, a["cy"] + 5)],
           "serving", check=[("ACMP-03", "serving", "ACMP-02")])
    return v


class ArchimateExchange(unittest.TestCase):
    def test_structure_and_references(self):
        model = example("archimate")
        xml = to_archimate_xml(model, [archimate_view(model)])
        root = ET.fromstring(xml)
        elements = {e.get("identifier"): e.get(XSI) for e in root.iter(A + "element")}
        self.assertEqual(len(elements), len(model["objects"]))
        self.assertEqual(elements["ACMP-01"], "ApplicationComponent")
        rels = list(root.iter(A + "relationship"))
        self.assertEqual(len(rels), len(model["relationships"]))
        acc = [r for r in rels if r.get(XSI) == "Access"][0]
        self.assertEqual(acc.get("accessType"), "Write")
        ids = set(elements) | {r.get("identifier") for r in rels}
        for r in rels:
            self.assertIn(r.get("source"), ids)
            self.assertIn(r.get("target"), ids)
        view = next(root.iter(A + "view"))
        self.assertEqual(view.get("viewpoint"), "Layered")
        outer = [n for n in view.findall(A + "node")]
        self.assertEqual([n.get("elementRef") for n in outer], ["ACMP-01"])
        self.assertEqual(sorted(n.get("elementRef") for n in outer[0].findall(A + "node")), ["ACMP-02", "ACMP-03"])
        conn = view.find(A + "connection")
        self.assertEqual(len(conn.findall(A + "bendpoint")), 2)

    def test_schema_valid(self):
        xsd = schema("archimate")
        if not xsd:
            self.skipTest("xmllint or network unavailable")
        model = example("archimate")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "m.xml")
            with open(p, "w") as f:
                f.write(to_archimate_xml(model, [archimate_view(model)]))
            ok, msg = xsd_check(p, xsd)
            self.assertTrue(ok, msg)
            m2 = clone(model)
            m2["objects"].append({"id": "JOR-1", "type": "Or Junction", "name": "or"})
            m2["relationships"] += [{"from": "ACMP-02", "type": "flow", "to": "JOR-1"},
                                    {"from": "JOR-1", "type": "flow", "to": "ACMP-NOTIFY"},
                                    {"from": "BACT-01", "type": "association", "to": "ACMP-02", "directed": True}]
            with open(p, "w") as f:
                f.write(to_archimate_xml(m2))
            ok, msg = xsd_check(p, xsd)
            self.assertTrue(ok, msg)

    def test_refuses_other_metamodels(self):
        with self.assertRaises(ValueError):
            to_archimate_xml(example("togaf"))


class BpmnXml(unittest.TestCase):
    def view(self, model):
        v = BpmnView(model, "B1")
        v.pool("P-CUST", 16, 16, 700, 60)
        v.pool("P-SVC", 16, 100, 700, 300)
        v.lane("L-AGENT", 46, 100, 670, 150)
        v.lane("L-SYS", 46, 250, 670, 150)
        e = v.event("E-START", 100, 320)
        t = v.task("T-REG", 140, 288)
        v.flow([(e["r"], 320), (t["x"] - 2, 320)], ("E-START", "sequenceFlow", "T-REG"))
        v.flow([(100, 78), (100, e["y"] - 2)], ("P-CUST", "messageFlow", "E-START"))
        return v

    def test_structure(self):
        model = example("bpmn")
        root = ET.fromstring(to_bpmn_xml(model, self.view(model)))
        procs = list(root.iter(B + "process"))
        self.assertEqual(len(procs), 2)
        parts = {p.get("id"): p.get("processRef") for p in root.iter(B + "participant")}
        self.assertEqual(set(parts.values()), {p.get("id") for p in procs})
        lanes = {l.get("id"): [r.text for r in l.findall(B + "flowNodeRef")] for l in root.iter(B + "lane")}
        self.assertIn("T-REG", lanes["L-SYS"])
        self.assertIn("T-ASSESS", lanes["L-AGENT"])
        gw = next(root.iter(B + "exclusiveGateway"))
        default = gw.get("default")
        flow = [f for f in root.iter(B + "sequenceFlow") if f.get("id") == default][0]
        self.assertEqual(flow.get("targetRef"), "T-REQ")
        b = next(root.iter(B + "boundaryEvent"))
        self.assertEqual((b.get("attachedToRef"), b.get("cancelActivity")), ("T-ASSESS", "false"))
        self.assertIsNotNone(b.find(B + "timerEventDefinition"))
        shapes = [s.get("bpmnElement") for s in root.iter("{http://www.omg.org/spec/BPMN/20100524/DI}BPMNShape")]
        self.assertIn("P-SVC", shapes)

    def test_schema_valid(self):
        xsd = schema("bpmn")
        if not xsd:
            self.skipTest("xmllint or network unavailable")
        model = example("bpmn")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "m.bpmn")
            with open(p, "w") as f:
                f.write(to_bpmn_xml(model, self.view(model)))
            ok, msg = xsd_check(p, xsd)
            self.assertTrue(ok, msg)
            # a single process without pools, with data in and out
            m = {"metamodel": "bpmn", "name": "solo", "objects": [
                {"id": "S", "type": "startEvent"}, {"id": "T", "type": "scriptTask", "name": "Run"},
                {"id": "X", "type": "intermediateThrowEvent", "trigger": "signal", "name": "Done"},
                {"id": "E", "type": "endEvent", "trigger": "terminate"},
                {"id": "D", "type": "dataStore", "name": "Ledger"},
                {"id": "C", "type": "intermediateCatchEvent", "trigger": "conditional", "name": "Ready"}],
                "relationships": [{"from": "S", "type": "sequenceFlow", "to": "C"},
                                  {"from": "C", "type": "sequenceFlow", "to": "T"},
                                  {"from": "T", "type": "sequenceFlow", "to": "X"},
                                  {"from": "X", "type": "sequenceFlow", "to": "E"},
                                  {"from": "D", "type": "dataInput", "to": "T"},
                                  {"from": "D", "type": "dataInput", "to": "X"},
                                  {"from": "T", "type": "dataOutput", "to": "D"}]}
            with open(p, "w") as f:
                f.write(to_bpmn_xml(m))
            ok, msg = xsd_check(p, xsd)
            self.assertTrue(ok, msg)


class Catalogue(unittest.TestCase):
    def test_rows_carry_framework_class(self):
        objs, rels = catalogue_rows(example("essential"))
        apr = [o for o in objs if o["id"] == "APR-01"][0]
        self.assertEqual(apr["class"], "Application_Provider")
        crud = [r for r in rels if r["relationship"] == "uses information" and r["to"] == "IRP-02"]
        self.assertEqual({r["crud"] for r in crud}, {"R", "CRUD"})
        objs, _ = catalogue_rows(example("archimate"))
        self.assertIn("classification", objs[0])

    def test_write(self):
        with tempfile.TemporaryDirectory() as d:
            paths = write_catalogue(example("togaf"), d)
            self.assertEqual([os.path.basename(p) for p in paths],
                             ["service-portal.objects.csv", "service-portal.relationships.csv"])


class Examples(unittest.TestCase):
    """Each example script runs end to end (renders PNGs when Chrome exists)."""

    def test_scripts(self):
        from ealib.common import find_chrome
        if not find_chrome():
            self.skipTest("Chrome not installed")
        for d, script in (("coreea", "app_context.py"), ("archimate", "layered.py"), ("togaf", "views.py"),
                          ("essential", "views.py"), ("bpmn", "lodgement.py")):
            p = subprocess.run(["python3", os.path.join(EXAMPLES, d, script)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertNotIn("warning", p.stderr)
            for line in p.stdout.split():
                if line.endswith((".png", ".xml", ".bpmn", ".csv", ".svg")):
                    self.assertTrue(os.path.getsize(line) > 0, line)


if __name__ == "__main__":
    unittest.main()
