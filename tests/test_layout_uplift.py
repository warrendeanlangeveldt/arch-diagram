"""2.2 layout and language: box sizing, same, packing, columns, direction,
joined lines, repeated boxes, field pairing, icons, scale and platform."""
import os
import unittest
import xml.etree.ElementTree as ET

from helpers import EXAMPLES  # noqa: F401  (puts scripts/ on the path)
from ealib.dsl import DslError, load_document
from ealib.exchange import to_archimate_xml
from ealib.layout import draw
from test_dsl import Geometry, text_doc

NS = "{http://www.opengroup.org/xsd/archimate/3.0/}"


def first(src):
    d = text_doc(src)
    return d, draw(d.model, d.views[0])[0]


def ys(v):
    return {oid: bx["y"] for oid, (bx, _) in v.placed.items()}


def xs(v):
    return {oid: bx["x"] for oid, (bx, _) in v.placed.items()}


ACTORS = ["Team admins", "Business users", "Platform admins", "EAI support engineers",
          "External systems and partners", "External validation harness"]

STRATEGY = """DRV-1: Driver "Costs rise"
DRV-2: Driver "Customers leave"
GOL-1: Goal "Keep customers"
OBJ-1: Objective "Answer in a day"
OBJ-2: Objective "Fix it first time"
DRV-1 -[motivates]-> GOL-1
DRV-2 -[motivates]-> GOL-1
GOL-1 -[achieved by]-> OBJ-1
GOL-1 -[achieved by]-> OBJ-2
view V {
  viewpoint "Business Strategy Diagram"
  OPTION
  DRV-1
  DRV-2
  GOL-1
  OBJ-1
  OBJ-2
}"""

COPIES = """LOC-D: Location "Dev subscription"
LOC-P: Location "Prod subscription"
TEC-S: Technology "Shared services"
TEC-H: Technology "Hub network"
TEC-S -[located in]-> LOC-D
TEC-S -[depends on]-> TEC-H
view V {
  LOC-D {
    TEC-S#dev
  }
  LOC-P {
    TEC-S#prod
  }
  TEC-H
}"""

PAIRS = """CAP-Z: Capability "Zone"
CAP-A: Capability "Core"
CAP-Z1: Capability "Vend" parent=CAP-Z
CAP-Z2: Capability "Isolate" parent=CAP-Z
CAP-Z3: Capability "Route" parent=CAP-Z
CAP-A1: Capability "Subscription vending" parent=CAP-A buildsOn=CAP-Z1
CAP-A2: Capability "Hub transit" parent=CAP-A buildsOn=CAP-Z3
view V {
  same by=buildsOn
  CAP-Z {
    CAP-Z1
    CAP-Z2
    CAP-Z3
  }
  CAP-A {
    CAP-A1
    CAP-A2
  }
}"""


class Defaults(unittest.TestCase):
    def test_box_notation_labels_with_the_verb(self):
        src = ('APP-1: Application "A"\nAPP-2: Application "B"\n'
               'APP-1 -[depends on]-> APP-2 note=DEP-001\nview V {\n  OPTION\n  APP-1\n  APP-2\n}')
        _, v = first(src.replace("OPTION", ""))
        svg = "\n".join(v.parts)
        self.assertIn(">depends on<", svg)
        self.assertNotIn(">DEP-001<", svg)
        _, v = first(src.replace("OPTION", "labels text"))
        self.assertIn(">DEP-001<", "\n".join(v.parts))

    def test_dense_view_warns(self):
        objs = "\n".join(f'APP-{i}: Application "App {i}"' for i in range(4))
        rels = "\n".join(f"APP-{a} -[depends on]-> APP-{b}" for a in range(4) for b in range(4) if a != b)
        boxes = "\n".join(f"  APP-{i}" for i in range(4))
        _, v = first(f"{objs}\n{rels}\nview V {{\n{boxes}\n}}")
        self.assertTrue(any("12 lines between 4 boxes" in w for w in v.layout_warnings), v.layout_warnings)
        _, v = first(f"{objs}\n{rels}\nview V {{\n  edges explicit\n  APP-0 --> APP-1\n{boxes}\n}}")
        self.assertFalse(any("lines between" in w for w in v.layout_warnings))


class Sizing(Geometry, unittest.TestCase):
    def test_same_keeps_its_row_by_narrowing_names(self):
        objs = "\n".join(f'ACT-{i}: Actor "{n}"' for i, n in enumerate(ACTORS))
        boxes = "\n".join(f"  ACT-{i}" for i in range(6))
        ids = " ".join(f"ACT-{i}" for i in range(6))
        d, v = first(f"{objs}\nview V {{\n{boxes}\n  same {ids}\n}}")
        self.check_view(d.model, d.views[0], v)
        self.assertEqual(len({round(y) for y in ys(v).values()}), 1)
        self.assertEqual(v.layout_warnings, [])
        self.assertEqual(v.W, 740)
        self.assertLess(max(bx["w"] for bx, _ in v.placed.values()), 150)

    def test_same_that_cannot_fit_widens_the_page_and_says_so(self):
        objs = "\n".join(f'ACT-{i}: Actor "Somebody with a long role name {i}"' for i in range(12))
        boxes = "\n".join(f"  ACT-{i}" for i in range(12))
        ids = " ".join(f"ACT-{i}" for i in range(12))
        _, v = first(f"{objs}\nview V {{\n{boxes}\n  same {ids}\n}}")
        self.assertEqual(len({round(y) for y in ys(v).values()}), 1)
        self.assertTrue(any("can't share a row" in w for w in v.layout_warnings), v.layout_warnings)
        self.assertGreater(v.W, 740)

    def test_two_sames_too_wide_together_get_a_row_each(self):
        objs = "\n".join(f'APP-{i}: Application "Application number {i}"' for i in range(8))
        boxes = "\n".join(f"  APP-{i}" for i in range(8))
        _, v = first(f"{objs}\nview V {{\n{boxes}\n  same APP-0 APP-1 APP-2 APP-3\n"
                     "  same APP-4 APP-5 APP-6 APP-7\n}")
        y = ys(v)
        self.assertEqual(len({round(y[f"APP-{i}"]) for i in range(4)}), 1)
        self.assertEqual(len({round(y[f"APP-{i}"]) for i in range(4, 8)}), 1)
        self.assertLess(y["APP-0"], y["APP-4"])

    def test_container_children_pack_into_one_row(self):
        objs = 'APP-P: Application "Platform"\n' + "\n".join(
            f'APP-{i}: Application "Part {i}" parent=APP-P' for i in range(4))
        kids = "\n".join(f"    APP-{i}" for i in range(4))
        d, v = first(f"{objs}\nview V {{\n  APP-P {{\n{kids}\n  }}\n}}")
        self.check_view(d.model, d.views[0], v)
        self.assertEqual(len({round(ys(v)[f"APP-{i}"]) for i in range(4)}), 1)
        self.assertEqual(v.layout_warnings, [])

    def test_containers_with_no_lines_flow_into_columns(self):
        cats = "\n".join(f'DTC-{c}: Data Category "Category {c}"' for c in range(6))
        ents = "\n".join(f'DAT-{c}{e}: Data Entity "Entity {c}.{e} with a longer name"'
                         for c in range(6) for e in range(c % 3 + 1))
        cls = "\n".join(f"DAT-{c}{e} -[classified as]-> DTC-{c}" for c in range(6) for e in range(c % 3 + 1))
        body = "\n".join(f"  DTC-{c} {{\n" + "\n".join(f"    DAT-{c}{e}" for e in range(c % 3 + 1)) + "\n  }"
                         for c in range(6))
        d = text_doc(f"{cats}\n{ents}\n{cls}\nview V {{\n{body}\n}}")
        v, h = draw(d.model, d.views[0])
        self.check_view(d.model, d.views[0], v)
        self.assertLess(len({round(ys(v)[f"DTC-{c}"]) for c in range(6)}), 6)
        self.assertEqual(v.W, 740)
        self.assertLess(h, 1.6 * v.W)
        self.assertEqual(len({round(bx["w"]) for oid, (bx, _) in v.placed.items() if oid.startswith("DAT-2")}), 1)


class Direction(Geometry, unittest.TestCase):
    def test_viewpoint_default_reads_left_to_right_with_joined_lines(self):
        d, v = first(STRATEGY.replace("OPTION", "join both"))
        self.check_view(d.model, d.views[0], v)
        x, y = xs(v), ys(v)
        self.assertLess(x["DRV-1"], x["GOL-1"])
        self.assertLess(x["GOL-1"], x["OBJ-1"])
        self.assertEqual(round(x["DRV-1"]), round(x["DRV-2"]))
        self.assertLess(y["OBJ-1"], y["OBJ-2"])
        self.assertEqual(v.layout_warnings, [])
        rels = d.model["relationships"]
        starts = {tuple(pts[0]) for ri, pts in v.edges if rels[ri]["from"] == "GOL-1"}
        self.assertEqual(len(starts), 1)                   # one trunk out of GOL-1
        ends = {tuple(pts[-1]) for ri, pts in v.edges if rels[ri]["to"] == "GOL-1"}
        self.assertEqual(len(ends), 1)                     # one arrowhead into it
        svg = "\n".join(v.parts)
        self.assertEqual(svg.count(">achieved by<"), 1)
        self.assertEqual(svg.count(">motivates<"), 1)

    def test_direction_tb_overrides_the_viewpoint(self):
        _, v = first(STRATEGY.replace("OPTION", "direction tb"))
        self.assertLess(ys(v)["DRV-1"], ys(v)["GOL-1"])
        with self.assertRaises(DslError) as e:
            text_doc(STRATEGY.replace("OPTION", "direction up"))
        self.assertIn("direction is tb or lr", str(e.exception))

    def test_before_overrides_the_relationship_order(self):
        src = ('APP-1: Application "Runs it"\nREQ-1: Requirement "Must run"\nAPP-1 -[satisfies]-> REQ-1\n'
               'view V {\n  bands off\n  APP-1\n  REQ-1\n  OPTION\n}')
        _, v = first(src.replace("OPTION", ""))
        self.assertLess(ys(v)["REQ-1"], ys(v)["APP-1"])    # satisfies: the requirement above
        _, v = first(src.replace("OPTION", "APP-1 before REQ-1"))
        self.assertLess(ys(v)["APP-1"], ys(v)["REQ-1"])


class Copies(unittest.TestCase):
    def test_an_object_drawn_twice(self):
        d, v = first(COPIES)
        self.assertIn("TEC-S", v.placed)
        self.assertIn("TEC-S#2", v.placed)
        rels = d.model["relationships"]
        self.assertEqual(sum(1 for ri, _ in v.edges if rels[ri]["type"] == "depends on"), 2)
        self.assertEqual(sum(1 for ri, _ in v.edges if rels[ri]["type"] == "located in"), 0)

    def test_copy_errors(self):
        with self.assertRaises(DslError) as e:
            text_doc(COPIES.replace("TEC-S#prod", "TEC-S#dev"))
        self.assertIn("a second box for it needs a tag", str(e.exception))
        with self.assertRaises(DslError) as e:
            text_doc(COPIES.replace("TEC-S#prod", "TEC-S#"))
        self.assertIn("needs a tag after the #", str(e.exception))

    def test_copies_export_as_separate_nodes(self):
        d, v = first("""metamodel archimate
NODE-1: Node "Dev"
NODE-2: Node "Prod"
SSW-1: System Software "Runtime"
ACMP-1: Application Component "App"
NODE-1 -[composition]-> SSW-1
NODE-2 -[composition]-> SSW-1
ACMP-1 -[serving]-> SSW-1
view V {
  NODE-1 {
    SSW-1#a
  }
  NODE-2 {
    SSW-1#b
  }
  ACMP-1
}""")
        root = ET.fromstring(to_archimate_xml(d.model, [v]))
        nodes = {n.get("identifier") for n in root.iter(NS + "node") if n.get("elementRef") == "SSW-1"}
        self.assertEqual(len(nodes), 2)
        targets = {c.get("target") for c in root.iter(NS + "connection")}
        self.assertEqual(targets & nodes, nodes)           # a serving line to each copy


class Pairing(Geometry, unittest.TestCase):
    def test_same_by_field_lines_up_boxes_across_containers(self):
        d, v = first(PAIRS)
        self.check_view(d.model, d.views[0], v)
        y = ys(v)
        self.assertAlmostEqual(y["CAP-Z1"], y["CAP-A1"], delta=0.5)
        self.assertAlmostEqual(y["CAP-Z3"], y["CAP-A2"], delta=0.5)
        self.assertLess(y["CAP-Z2"], y["CAP-Z3"])
        with self.assertRaises(DslError):
            text_doc(PAIRS.replace("same by=buildsOn", "same CAP-Z1 by=buildsOn"))


class IconsAndOutput(unittest.TestCase):
    def test_group_icon_and_icons_in_narrow_boxes(self):
        _, v = first('TEC-1: Technology "Key vault one"\nTEC-2: Technology "Key vault two"\n'
                     'TEC-3: Technology "Application gateway and web application firewall"\n'
                     'view V {\n  group "Key vaults" TEC-1 TEC-2 icon=generic:key\n'
                     '  TEC-3 icon=generic:waf w=110\n}')
        svg = "\n".join(v.parts)
        self.assertEqual(svg.count("scale(0.8333)"), 1)    # 20px: the group's, beside its name
        self.assertEqual(svg.count("scale(0.4583)"), 1)    # 11px: the narrow box's, in its label row

    def test_icon_ids_are_the_same_every_time(self):
        d = load_document(os.path.join(EXAMPLES, "togaf", "views.ead"))
        a, ha = draw(d.model, d.views[0])
        b, hb = draw(d.model, d.views[0])
        self.assertEqual(a.svg(ha), b.svg(hb))

    def test_scale_and_platform_statements(self):
        d = text_doc('scale 3\nAPP-1: Application "A"\nview V {\n  platform azure\n  APP-1\n}')
        self.assertEqual(d.scale, 3)
        self.assertEqual(d.views[0].platform, "azure")
        self.assertEqual(draw(d.model, d.views[0])[0].platform, "azure")
        for bad, msg in (("scale big\n", "scale is a number"), ("scale 20\n", "between 0.5 and 8")):
            with self.assertRaises(DslError) as e:
                text_doc(bad + 'APP-1: Application "A"\nview V {\n  APP-1\n}')
            self.assertIn(msg, str(e.exception))
        with self.assertRaises(DslError) as e:
            text_doc('APP-1: Application "A"\nview V {\n  platform oracle\n  APP-1\n}')
        self.assertIn("platform is aws or azure or gcp", str(e.exception))


if __name__ == "__main__":
    unittest.main()
