import json
import os
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

from helpers import EXAMPLES, SCRIPTS, schema
from ealib import ModelError, load_model, validate
from ealib.dsl import DslError, load_document, parse_document, tokenize
from ealib.exchange import to_archimate_xml, xsd_check
from ealib.layout import draw

EA = os.path.join(SCRIPTS, "ea.py")
FRAMEWORKS = ("coreea", "archimate", "togaf", "essential", "bpmn")


def doc_of(name):
    return load_document(os.path.join(EXAMPLES, name, "views.ead"))


def text_doc(src, base=None):
    return parse_document(src, base or EXAMPLES, "test.ead")


# ------------------------------------------------------------------ geometry checks

def inside(inner, outer, slack=0.5):
    return (inner["x"] >= outer["x"] - slack and inner["y"] >= outer["y"] - slack
            and inner["x"] + inner["w"] <= outer["x"] + outer["w"] + slack
            and inner["y"] + inner["h"] <= outer["y"] + outer["h"] + slack)


def overlap(a, b, inset=0.5):
    return not (a["x"] + a["w"] - inset <= b["x"] + inset or b["x"] + b["w"] - inset <= a["x"] + inset
                or a["y"] + a["h"] - inset <= b["y"] + inset or b["y"] + b["h"] - inset <= a["y"] + inset)


def on_border(pt, b, tol=3.0):
    x, y = pt
    within_x = b["x"] - tol <= x <= b["x"] + b["w"] + tol
    within_y = b["y"] - tol <= y <= b["y"] + b["h"] + tol
    near_v = min(abs(x - b["x"]), abs(x - b["x"] - b["w"])) <= tol
    near_h = min(abs(y - b["y"]), abs(y - b["y"] - b["h"])) <= tol
    return (within_x and within_y) and (near_v or near_h)


def crosses(seg, b, inset=1.0):
    (x1, y1), (x2, y2) = seg
    sx, ex = sorted((x1, x2))
    sy, ey = sorted((y1, y2))
    return (sx < b["x"] + b["w"] - inset and ex > b["x"] + inset
            and sy < b["y"] + b["h"] - inset and ey > b["y"] + inset)


class Geometry:
    """Invariants every auto-laid-out EA view must keep."""

    def check_view(self, model, spec, v):
        objs = {o["id"]: o for o in model["objects"]}
        placed = {oid: bx for oid, (bx, kind) in v.placed.items()}
        kinds = {oid: kind for oid, (bx, kind) in v.placed.items()}
        pills = {oid for oid in placed if v.forms.get(objs[oid]["type"]) and "pill" in v.forms[objs[oid]["type"]]
                 and placed[oid]["h"] <= v.PILL_H + 10}
        leaves = [oid for oid in placed if kinds[oid] != "container"]
        hosts = {p: h for p, h, _, _ in spec.attached}
        # no two leaves overlap, apart from a pill on its host's edge
        for i, a in enumerate(leaves):
            for b in leaves[i + 1:]:
                if hosts.get(a) == b or hosts.get(b) == a:
                    continue
                self.assertFalse(overlap(placed[a], placed[b]), f"{spec.vid}: {a} overlaps {b}")
        # every child is inside its container, and containers don't overlap siblings
        for top in spec.items:
            for it in top.walk():
                for c in it.children:
                    if it.oid and c.oid:
                        self.assertTrue(inside(placed[c.oid], placed[it.oid]),
                                        f"{spec.vid}: {c.oid} is not inside {it.oid}")
        # pills on an edge sit on their host's top edge
        for p, h in hosts.items():
            self.assertAlmostEqual(placed[p]["y"] + placed[p]["h"] / 2, placed[h]["y"], delta=0.6)
        # edges: orthogonal, end on their boxes, cross no unrelated leaf
        rels = model["relationships"]
        for ri, pts in v.edges:
            r = rels[ri]
            for a, b in zip(pts, pts[1:]):
                self.assertTrue(abs(a[0] - b[0]) < 0.01 or abs(a[1] - b[1]) < 0.01,
                                f"{spec.vid}: {r['from']}->{r['to']} has a diagonal {a}->{b}")
            ends = []
            for oid in (r["from"], r["to"]):
                end = oid if oid in placed else next(
                    (it for it in spec.items for it in [it] if it.kind == "group" and oid in it.members), None)
                ends.append(end)
            if all(isinstance(e, str) for e in ends):
                self.assertTrue(on_border(pts[0], placed[ends[0]]), f"{spec.vid}: {r} starts off its box")
                self.assertTrue(on_border(pts[-1], placed[ends[1]]), f"{spec.vid}: {r} ends off its box")
            mine = {r["from"], r["to"]}
            for oid in leaves:
                if oid in mine or hosts.get(oid) in mine or any(hosts.get(m) == oid for m in mine):
                    continue
                for seg in zip(pts, pts[1:]):
                    self.assertFalse(crosses(seg, placed[oid]),
                                     f"{spec.vid}: {r['from']} -{r['type']}-> {r['to']} crosses {oid}")
        # every relationship between drawn objects is drawn or said by nesting / a pill
        drawn = {ri for ri, _ in v.edges}
        parent = {}
        for top in spec.items:
            for it in top.walk():
                for c in it.children:
                    if c.oid:
                        parent[c.oid] = it.oid
        hidden = set()
        for f, verb, t, _ in spec.hidden:
            hidden |= {i for i, r in enumerate(rels) if r["from"] == f and r["to"] == t
                       and (verb is None or r["type"] == verb)}
        for i, r in enumerate(rels):
            if r["from"] in placed and r["to"] in placed and spec.edges_mode == "auto" and i not in hidden:
                implied = (parent.get(r["to"]) == r["from"] or parent.get(r["from"]) == r["to"]
                           or hosts.get(r["to"]) == r["from"] or hosts.get(r["from"]) == r["to"])
                self.assertTrue(i in drawn or implied, f"{spec.vid}: {r} is neither drawn nor nested")


class Parser(unittest.TestCase):
    def test_tokens(self):
        toks = tokenize('A: Application Component "Portal \\"web\\"" status=Built note="x y" # c\n'
                        'A -[serves people]-> B "n"\nC --> D;E\n')
        kinds = [(t.kind, t.value) for t in toks if t.kind != "nl"]
        self.assertIn(("string", 'Portal "web"'), kinds)
        self.assertIn(("arrow", "serves people"), kinds)
        self.assertIn(("arrow", None), kinds)
        attrs = {t.key: t.value for t in toks if t.kind == "attr"}
        self.assertEqual(attrs, {"status": "Built", "note": "x y"})
        self.assertEqual(sum(1 for t in toks if t.kind == "nl"), 5)

    def test_inline_model(self):
        d = text_doc('''
            metamodel archimate
            name "Inline"
            ACMP-1: Application Component "Portal" status=Proposed properties.classification=Internal
            ASVC-1: Application Service "Lookup"
            ACMP-1 -[realization]-> ASVC-1 "realises"
            BPRC-1: Business Process "Serve" ref=FR-1
            ASVC-1 -[serving]-> BPRC-1
            view V "Inline view" {
              ACMP-1
              ASVC-1
              BPRC-1
            }
        ''')
        m = d.model
        self.assertEqual(m["metamodel"], "archimate")
        a = next(o for o in m["objects"] if o["id"] == "ACMP-1")
        self.assertEqual(a["status"], "Proposed")
        self.assertEqual(a["properties"], {"classification": "Internal"})
        self.assertEqual(m["relationships"][0]["name"], "realises")
        validate(m)
        v, h = draw(m, d.views[0])
        self.assertEqual(len(v.edges), 2)

    def test_import_and_extend(self):
        d = text_doc('''
            model "archimate/model.json"
            ACMP-NEW: Application Component "Audit log"
            ACMP-03 -[flow]-> ACMP-NEW "audit events"
            view V { ACMP-03; ACMP-NEW }
        ''')
        validate(d.model)
        self.assertIn("ACMP-NEW", {o["id"] for o in d.model["objects"]})
        self.assertEqual(d.model["metamodel"], "archimate")

    def test_every_error_reported_with_its_line(self):
        src = '''model "archimate/model.json"
ACMP-01: Application Component "Again"
view V {
  NOPE
  ACMP-02
  ACMP-02
  ACMP-03 -[serving]-> GHOST
  edges sometimes
}
'''
        with self.assertRaises(DslError) as cm:
            text_doc(src)
        msg = str(cm.exception)
        for line, frag in ((2, "ACMP-01 is already defined"), (4, "NOPE is not in the model"),
                           (6, "ACMP-02 is already drawn"), (7, "GHOST is not in the model"),
                           (8, "edges is auto or explicit")):
            self.assertIn(f"line {line}: {frag}", msg)

    def test_structure_errors(self):
        for src, frag in (('view V {\n  A\n', "never closed"), ('}\n', "without a matching"),
                          ('A -[x]-> \n', "a relationship is"), ('A: Type Name\n', "name in quotes"),
                          ('A -[x\n', "closing ']->'"), ('view V "t" {\n  frame "F" {\n  }\n}\n', "is empty")):
            with self.assertRaises(DslError, msg=src) as cm:
                text_doc('metamodel archimate\n' + src)
            self.assertIn(frag, str(cm.exception), src)

    def test_layout_time_errors(self):
        d = text_doc('''model "archimate/model.json"
view V {
  ACMP-03 size=big
  ACMP-02
  ACMP-03 -[access]-> ACMP-02
}''')
        with self.assertRaises(DslError) as cm:
            draw(d.model, d.views[0])
        self.assertIn("line 3: size= doesn't apply to a node", str(cm.exception))
        self.assertIn("line 5: the model has no relationship ACMP-03 -[access]-> ACMP-02", str(cm.exception))

    def test_ambiguous_arrow(self):
        d = text_doc('''metamodel archimate
ACMP-A: Application Component "A"
ACMP-B: Application Component "B"
ACMP-A -[serving]-> ACMP-B
ACMP-A -[flow]-> ACMP-B
view V {
  ACMP-A
  ACMP-B
  ACMP-A --> ACMP-B
}''')
        with self.assertRaises(DslError) as cm:
            draw(d.model, d.views[0])
        self.assertIn("matches serving, flow", str(cm.exception))

    def test_pill_rules(self):
        with self.assertRaises(DslError) as cm:
            text_doc('model "coreea/model.json"\nview V {\n  APP-02 on APP-03\n  APP-03\n}')
        self.assertIn("pills are for service and interface types", str(cm.exception))
        with self.assertRaises(DslError) as cm:
            text_doc('model "coreea/model.json"\nview V {\n  INT-01 on APP-03\n}')
        self.assertIn("APP-03 has to be drawn in the view", str(cm.exception))

    def test_load_model_reads_ead(self):
        m = load_model(os.path.join(EXAMPLES, "coreea", "views.ead"))
        self.assertEqual(len(m["objects"]), 12)
        with self.assertRaises(ModelError):
            load_model(os.path.join(EXAMPLES, "missing.ead"))


class Layout(Geometry, unittest.TestCase):
    def test_examples_keep_the_invariants(self):
        for name in ("coreea", "archimate", "togaf", "essential"):
            d = doc_of(name)
            for spec in d.views:
                v, h = draw(d.model, spec)
                if spec.matrices:
                    self.assertFalse(v.placed)
                    continue
                self.check_view(d.model, spec, v)
                self.assertGreater(h, 100)
                # viewpoint warnings: none. Layout warnings are allowed here
                # (LayoutWarnings covers them); they flag a view to look at
                self.assertEqual([w for w in v.warnings if w not in v.layout_warnings], [])

    def test_bands_put_business_above_application_above_technology(self):
        d = doc_of("archimate")
        v, _ = draw(d.model, d.views[0])
        y = {oid: bx["y"] for oid, (bx, _) in v.placed.items()}
        self.assertLess(y["BPRC-01"], y["ASVC-01"])
        self.assertLess(y["ASVC-01"], y["ACMP-01"])        # realization: service above component
        self.assertLess(y["ACMP-01"], y["NODE-01"])
        self.assertAlmostEqual(y["ACMP-01"], y["ACMP-CRM"], delta=60)   # serving runs across

    def test_options(self):
        d = text_doc('''model "essential/model.json"
view V {
  bands off
  labels verb
  edges explicit
  ACP-01
  ASV-01
  ASV-02
  APR-01
  ASV-02 above ASV-01
  same ACP-01 APR-01
  APR-01 -[provides]-> ASV-01 "provides registration"
  ASV-01 -[realises]-> ACP-01
}''')
        v, _ = draw(d.model, d.views[0])
        self.check_view(d.model, d.views[0], v)
        y = {oid: bx["y"] for oid, (bx, _) in v.placed.items()}
        self.assertLess(y["ASV-02"], y["ASV-01"])
        self.assertAlmostEqual(y["ACP-01"], y["APR-01"], delta=1)
        self.assertEqual(len(v.edges), 2)                  # explicit: only the two listed
        svg = "\n".join(v.parts)
        self.assertIn(">provides registration<", svg)
        self.assertIn(">realises<", svg)

    def test_hide_group_frame_junction(self):
        d = text_doc('''metamodel archimate
ACMP-A: Application Component "Portal"
REQ-1: Requirement "R one"
REQ-2: Requirement "R two"
REQ-3: Requirement "R three"
JOR-1: Or Junction "J"
ACMP-X: Application Component "External thing"
ACMP-Y: Application Component "Other"
ACMP-A -[realization]-> REQ-1
ACMP-A -[realization]-> REQ-2
ACMP-A -[realization]-> REQ-3
ACMP-A -[flow]-> JOR-1
JOR-1 -[flow]-> ACMP-X
JOR-1 -[flow]-> ACMP-Y
ACMP-X -[serving]-> ACMP-A
view V {
  ACMP-A
  group "Requirements" REQ-1 REQ-2 REQ-3
  JOR-1
  frame "External" dashed=true {
    ACMP-X
  }
  ACMP-Y
  hide ACMP-X -[serving]-> ACMP-A
}''')
        validate(d.model)
        v, _ = draw(d.model, d.views[0])
        self.check_view(d.model, d.views[0], v)
        rels = d.model["relationships"]
        drawn = [rels[i] for i, _ in v.edges]
        self.assertFalse(any(r["type"] == "serving" for r in drawn))
        self.assertEqual(sum(1 for r in drawn if r["type"] == "realization"), 1)   # one edge to the group
        self.assertIn(">EXTERNAL<", "\n".join(v.parts))

    def test_wide_rows_wrap_and_stay_on_the_page(self):
        objs = "\n".join(f'ACMP-{i}: Application Component "Service number {i}"' for i in range(9))
        flows = "\n".join(f"ACMP-{i} -[flow]-> ACMP-{i + 1}" for i in range(8))
        d = text_doc(f"metamodel archimate\n{objs}\n{flows}\nview V {{\n"
                     + "\n".join(f"  ACMP-{i}" for i in range(9)) + "\n}")
        v, _ = draw(d.model, d.views[0])
        self.check_view(d.model, d.views[0], v)
        for bx, _ in v.placed.values():
            self.assertLessEqual(bx["x"] + bx["w"], v.W - 15)
        self.assertGreater(len({round(bx["y"]) for bx, _ in v.placed.values()}), 1)

    def test_same_type_same_colour_across_views(self):
        d = doc_of("essential")
        v1, _ = draw(d.model, d.views[0])
        v2, _ = draw(d.model, d.views[1])
        self.assertEqual(v1.colours("Application Provider"), v2.colours("Application Provider"))


class Bpmn(unittest.TestCase):
    def check(self, model, v):
        shapes = {k: s[0] for k, s in v.shapes.items()}
        objs = {o["id"]: o for o in model["objects"]}
        nodes = [k for k in shapes if objs[k]["type"] not in ("participant", "lane", "subProcess")
                 and objs[k]["type"] != "boundaryEvent"]
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                self.assertFalse(overlap(shapes[a], shapes[b]), f"{a} overlaps {b}")
        for k in nodes:
            par = objs[k].get("parent")
            if par in shapes:
                self.assertTrue(inside(shapes[k], shapes[par]), f"{k} is outside {par}")
        for k, o in objs.items():
            if o["type"] == "boundaryEvent" and k in shapes:
                host = shapes[o["attachedTo"]]
                cy = shapes[k]["y"] + shapes[k]["h"] / 2
                self.assertAlmostEqual(cy, host["y"] + host["h"], delta=0.6)
        rels = model["relationships"]
        for ri, pts in v.edges:
            for a, b in zip(pts, pts[1:]):
                self.assertTrue(abs(a[0] - b[0]) < 0.01 or abs(a[1] - b[1]) < 0.01, rels[ri])
            r = rels[ri]
            for seg in zip(pts, pts[1:]):
                for k in nodes:
                    if k in (r["from"], r["to"]) or objs[r["from"]].get("attachedTo") == k:
                        continue
                    self.assertFalse(crosses(seg, shapes[k]), f"{r} crosses {k}")
        self.assertEqual({ri for ri, _ in v.edges}, set(range(len(rels))))

    def test_example(self):
        d = doc_of("bpmn")
        v, _ = draw(d.model, d.views[0])
        self.check(d.model, v)
        x = {k: s[0]["x"] for k, s in v.shapes.items()}
        self.assertLess(x["E-START"], x["T-REG"])
        self.assertLess(x["T-REG"], x["G-TRIAGE"])
        self.assertLess(x["G-TRIAGE"], x["T-ASSESS"])

    def test_no_pools_nested_lanes_and_subprocess(self):
        d = text_doc('''metamodel bpmn
name "Nested"
P: participant "Org"
L1: lane "Front office" parent=P
L1a: lane "Desk" parent=L1
L1b: lane "Phone" parent=L1
L2: lane "Back office" parent=P
S: startEvent "Go" parent=L1a
T: userTask "Take call" parent=L1b
SP: subProcess "Handle" parent=L2
S2: startEvent "In" parent=SP
T2: serviceTask "Work" parent=SP
E2: endEvent "Out" parent=SP
E: endEvent "Done" parent=L2
S -[sequenceFlow]-> T
T -[sequenceFlow]-> SP
SP -[sequenceFlow]-> E
S2 -[sequenceFlow]-> T2
T2 -[sequenceFlow]-> E2
view V { }
''')
        validate(d.model)
        v, _ = draw(d.model, d.views[0])
        self.check(d.model, v)
        for k in ("S2", "T2", "E2"):
            self.assertTrue(inside(v.shapes[k][0], v.shapes["SP"][0]), k)
        solo = text_doc('''metamodel bpmn
S: startEvent "Go"
T: scriptTask "Run"
G: parallelGateway "Split"
A: task "A"
B: task "B"
J: parallelGateway "Join"
E: endEvent "End"
S -[sequenceFlow]-> T
T -[sequenceFlow]-> G
G -[sequenceFlow]-> A
G -[sequenceFlow]-> B
A -[sequenceFlow]-> J
B -[sequenceFlow]-> J
J -[sequenceFlow]-> E
view V { }
''')
        validate(solo.model)
        v, _ = draw(solo.model, solo.views[0])
        self.check(solo.model, v)
        self.assertNotAlmostEqual(v.shapes["A"][0]["y"], v.shapes["B"][0]["y"])


class Exports(unittest.TestCase):
    def test_archimate_exchange_carries_the_laid_out_view(self):
        d = doc_of("archimate")
        v, _ = draw(d.model, d.views[0])
        xml = to_archimate_xml(d.model, [v])
        root = ET.fromstring(xml)
        A = "{http://www.opengroup.org/xsd/archimate/3.0/}"
        view = next(root.iter(A + "view"))
        refs = {n.get("elementRef") for n in view.iter(A + "node")}
        self.assertTrue({"ACMP-01", "ACMP-02", "SSW-01", "LOC-01"} <= refs)
        self.assertGreater(len(list(view.iter(A + "connection"))), 5)
        xsd = schema("archimate")
        if xsd:
            with tempfile.TemporaryDirectory() as t:
                p = os.path.join(t, "m.xml")
                with open(p, "w") as f:
                    f.write(xml)
                ok, msg = xsd_check(p, xsd)
                self.assertTrue(ok, msg)

    def test_bpmn_carries_the_laid_out_view(self):
        from ealib.bpmn import to_bpmn_xml
        d = doc_of("bpmn")
        v, _ = draw(d.model, d.views[0])
        xml = to_bpmn_xml(d.model, v)
        root = ET.fromstring(xml)
        DI = "{http://www.omg.org/spec/BPMN/20100524/DI}"
        shapes = {s.get("bpmnElement") for s in root.iter(DI + "BPMNShape")}
        self.assertTrue({"P-SVC", "L-AGENT", "T-ASSESS", "B-SLA"} <= shapes)
        self.assertEqual(len(list(root.iter(DI + "BPMNEdge"))), len(d.model["relationships"]))
        xsd = schema("bpmn")
        if xsd:
            with tempfile.TemporaryDirectory() as t:
                p = os.path.join(t, "m.bpmn")
                with open(p, "w") as f:
                    f.write(xml)
                ok, msg = xsd_check(p, xsd)
                self.assertTrue(ok, msg)


class Cli(unittest.TestCase):
    def run_ea(self, *args):
        return subprocess.run(["python3", EA, *args], capture_output=True, text=True)

    def test_render_validate_export(self):
        with tempfile.TemporaryDirectory() as out:
            r = self.run_ea("render", os.path.join(EXAMPLES, "archimate", "views.ead"), "--out", out,
                            "--no-png", "--export", "archimate", "--export", "csv")
            self.assertEqual(r.returncode, 0, r.stderr)
            files = set(os.listdir(out))
            self.assertTrue({"LAYERED.svg", "LAYERED.html", "LAYERED.objects.json", "service-portal.xml",
                             "service-portal.objects.csv"} <= files, files)
            self.assertNotIn("LAYERED.png", files)
            with open(os.path.join(out, "LAYERED.objects.json")) as f:
                self.assertIn("ACMP-03", json.load(f)["objects"])
            r = self.run_ea("render", os.path.join(EXAMPLES, "essential", "views.ead"), "--out", out,
                            "--no-png", "--view", "V2")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("V2.svg", os.listdir(out))
            self.assertNotIn("V1.svg", os.listdir(out))
            r = self.run_ea("export", os.path.join(EXAMPLES, "bpmn", "views.ead"), "--format", "bpmn",
                            "--out", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(out, "case-lodgement.bpmn")) as f:
                self.assertIn("BPMNShape", f.read())
        r = self.run_ea("validate", os.path.join(EXAMPLES, "togaf", "views.ead"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout.splitlines()[-1])["views"], 2)

    def test_errors_exit_non_zero(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "bad.ead")
            with open(p, "w") as f:
                f.write('metamodel coreea\nAPP-1: Application "A"\nview V {\n  APP-2\n}\n')
            r = self.run_ea("render", p, "--no-png")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("line 4: APP-2 is not in the model", r.stderr)
            r = self.run_ea("render", os.path.join(EXAMPLES, "coreea", "views.ead"), "--no-png",
                            "--view", "NOPE", "--out", d)
            self.assertIn("no view NOPE", r.stderr)



class LayoutWarnings(unittest.TestCase):
    def test_wrapped_row_and_wide_page_are_reported(self):
        objs = "\n".join(f'ACMP-{i}: Application Component "Service number {i}"' for i in range(9))
        flows = "\n".join(f"ACMP-{i} -[flow]-> ACMP-{i + 1}" for i in range(8))
        ids = "\n".join(f"  ACMP-{i}" for i in range(9))
        d = text_doc(f"metamodel archimate\n{objs}\n{flows}\nview V {{\n{ids}\n}}")
        v, _ = draw(d.model, d.views[0])
        self.assertTrue(any("moved to a row below" in w for w in v.layout_warnings), v.layout_warnings)
        self.assertTrue(set(v.layout_warnings) <= set(v.warnings))
        self.assertEqual(v.manifest()["warnings"], v.warnings)
        # a box wider than the page can't wrap: the page widens, and says so
        d = text_doc('metamodel archimate\nACMP-1: Application Component "A"\n'
                     'view V {\n  ACMP-1 w=900\n}')
        v, _ = draw(d.model, d.views[0])
        self.assertTrue(any("wider than the 740px page" in w for w in v.layout_warnings), v.layout_warnings)

    def test_clean_layout_has_no_warnings(self):
        d = doc_of("essential")
        for spec in d.views:
            v, _ = draw(d.model, spec)
            self.assertEqual(v.layout_warnings, [], spec.vid)

    def test_crossings_and_label_spots(self):
        from ealib.layout import crossing_pairs, place_label
        lines = {"a": [(0, 50), (100, 50)], "b": [(50, 0), (50, 100)], "c": [(200, 0), (200, 100)]}
        self.assertEqual(crossing_pairs(lines), [("a", "b")])
        pts = [(0, 50), (200, 50)]
        *_, clean = place_label("label", 8.5, pts, [], [], [], set(pts), 400, 400)
        self.assertTrue(clean)
        *_, clean = place_label("label", 8.5, pts, [(-10, -10, 420, 420)], [], [], set(pts), 400, 400)
        self.assertFalse(clean)

    def test_bpmn_reports_crossing_flows(self):
        d = doc_of("bpmn")
        v, _ = draw(d.model, d.views[0])
        self.assertTrue(all(w.startswith("LODGEMENT: layout: ") for w in v.layout_warnings))
        self.assertEqual(v.manifest()["warnings"], v.warnings)


class ScriptViews(unittest.TestCase):
    """view ID script="file.py": a view placed by hand, drawn by the script's
    draw(model, vid), alongside views the layout places."""

    def ead(self, d, body, framework="togaf"):
        p = os.path.join(d, "v.ead")
        with open(p, "w") as f:
            f.write(f'model "{os.path.join(EXAMPLES, framework, "model.json")}"\n{body}')
        return p

    def test_script_view_draws_what_the_script_draws(self):
        script = os.path.join(EXAMPLES, "togaf", "views.py")
        with tempfile.TemporaryDirectory() as d:
            doc = load_document(self.ead(d, f'view V1 script="{script}"\n'
                                            'view V2 "Application/Data matrix" {\n'
                                            '  matrix "operates on" rows "Data Entity" cols "Physical Application Component"\n}\n'))
            self.assertEqual([v.script for v in doc.views], [script, None])
            v1, h1 = draw(doc.model, doc.views[0])
            import importlib.util
            spec = importlib.util.spec_from_file_location("togaf_views", script)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            ref, href = mod.draw(doc.model, "V1")
            self.assertEqual(v1.svg(h1), ref.svg(href))
            self.assertEqual(v1.layout_warnings, [])
            v2, _ = draw(doc.model, doc.views[1])
            self.assertTrue(v2.forms)

    def test_script_view_exports(self):
        script = os.path.join(EXAMPLES, "archimate", "layered.py")
        with tempfile.TemporaryDirectory() as d:
            doc = load_document(self.ead(d, f'view LAYERED script="{script}"\n', "archimate"))
            v, _ = draw(doc.model, doc.views[0])
            self.assertIn("SSW-01", v.placed)
            xml = to_archimate_xml(doc.model, views=[v])
            self.assertIn('<view identifier="v-layered"', xml)
            self.assertIn('elementRef="SSW-01"', xml)

    def test_script_view_errors(self):
        script = os.path.join(EXAMPLES, "togaf", "views.py")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(DslError) as e:
                load_document(self.ead(d, f'view V1 "Title" script="{script}"\n'
                                          'view V2 script="nope.py"\n'
                                          f'view V3 script="{script}" width=900\n'
                                          f'view V4 script="{script}" {{\n  PAC-01\n}}\n'
                                          'view V5\n'))
            msg = str(e.exception)
            for want in ("line 2: a hand-placed view is", "line 3: no script nope.py",
                         "line 4: a hand-placed view takes only script= (not width=)",
                         "line 5: a view placed by a script has no { … } block",
                         "line 8: a view is"):
                self.assertIn(want, msg)
            doc = load_document(self.ead(d, f'view V9 script="{script}"\n'))
            with self.assertRaises(DslError) as e:
                draw(doc.model, doc.views[0])
            self.assertIn("can't draw it", str(e.exception))
            other = os.path.join(d, "other.py")
            with open(other, "w") as f:
                f.write("x = 1\n")
            doc = load_document(self.ead(d, 'view V1 script="other.py"\n'))
            with self.assertRaises(DslError) as e:
                draw(doc.model, doc.views[0])
            self.assertIn("has no draw(model, vid) function", str(e.exception))
            with open(other, "w") as f:
                f.write(f"import importlib.util\n"
                        f"s = importlib.util.spec_from_file_location('t', {script!r})\n"
                        "m = importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
                        "def draw(model, vid):\n    return m.draw(model, 'V2')\n")
            with self.assertRaises(DslError) as e:
                draw(doc.model, doc.views[0])
            self.assertIn("drew view V2 instead", str(e.exception))

    def test_cli_hint_and_validate_warnings(self):
        r = subprocess.run(["python3", EA, "validate", os.path.join(EXAMPLES, "archimate", "views.ead")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("warning: LAYERED: layout: a row is too wide", r.stdout)
        self.assertEqual(json.loads(r.stdout.splitlines()[-1])["views"], 1)
        with tempfile.TemporaryDirectory() as out:
            r = subprocess.run(["python3", EA, "render", os.path.join(EXAMPLES, "archimate", "views.ead"),
                                "--no-png", "--out", out], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("place the view by hand", r.stderr)
            r = subprocess.run(["python3", EA, "render", os.path.join(EXAMPLES, "essential", "views.ead"),
                                "--no-png", "--out", out], capture_output=True, text=True)
            self.assertNotIn("place the view by hand", r.stderr)


if __name__ == "__main__":
    unittest.main()
