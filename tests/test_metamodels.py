import unittest

from helpers import clone, example  # noqa: F401  (sets sys.path)
from ealib import ModelError, load_metamodel, validate


class MetamodelFiles(unittest.TestCase):
    def test_archimate_table_covers_every_type(self):
        mm = load_metamodel("archimate")
        self.assertEqual(len(mm.types), 62)
        codes = {r["code"] for r in mm.relationships.values()}
        for t in mm.types:
            self.assertIn(t, mm.rules, t)
            for tgt, rel in mm.rules[t].items():
                self.assertIn(tgt, mm.types)
                self.assertTrue(set(rel) <= codes, (t, tgt, rel))

    def test_archimate_spot_checks_against_the_standard(self):
        mm = load_metamodel("archimate")
        self.assertTrue(mm.allowed("serving", "Application Service", "Business Process"))
        self.assertTrue(mm.allowed("assignment", "Business Actor", "Business Role"))
        self.assertTrue(mm.allowed("realization", "Application Component", "Application Service"))
        self.assertTrue(mm.allowed("access", "Application Process", "Data Object"))
        self.assertFalse(mm.allowed("access", "Data Object", "Application Process"))
        self.assertFalse(mm.allowed("triggering", "Business Actor", "Data Object"))
        self.assertTrue(mm.allowed("influence", "Driver", "Goal"))

    def test_every_viewpoint_type_exists(self):
        for key in ("archimate", "togaf", "essential", "coreea"):
            mm = load_metamodel(key)
            for name, vp in mm.viewpoints.items():
                for t in vp["types"]:
                    self.assertIn(t, mm.types, f"{key} {name}: {t}")
                for k in ("rows", "columns"):
                    if k in vp:
                        self.assertIn(vp[k], mm.types)
                if "verb" in vp:
                    self.assertIn(vp["verb"], mm.relationships)

    def test_box_metamodel_pairs_name_real_types(self):
        for key in ("togaf", "essential", "coreea"):
            mm = load_metamodel(key)
            prefixes = [d["prefix"] for d in mm.types.values()]
            self.assertEqual(len(prefixes), len(set(prefixes)), f"{key}: duplicate prefixes")
            for verb, rel in mm.relationships.items():
                self.assertTrue(rel["pairs"], verb)
                for src, tgt in rel["pairs"]:
                    for t in src + tgt:
                        self.assertIn(t, mm.types, f"{key} {verb}: {t}")
            for d in mm.types.values():
                self.assertIn(d["layer"], mm.layers)


class Validation(unittest.TestCase):
    def assertProblems(self, model, *fragments):
        with self.assertRaises(ModelError) as cm:
            validate(model)
        for f in fragments:
            self.assertIn(f, str(cm.exception))

    def test_examples_validate(self):
        for name in ("coreea", "archimate", "togaf", "essential", "bpmn"):
            validate(example(name))

    def test_archimate_rejects_disallowed_relationship_with_hint(self):
        m = clone(example("archimate"))
        m["relationships"].append({"from": "DOBJ-01", "type": "serving", "to": "BPRC-01"})
        self.assertProblems(m, "'serving' does not join Data Object -> Business Process")

    def test_archimate_rejects_parent_and_bad_prefix_together(self):
        m = clone(example("archimate"))
        m["objects"][2]["parent"] = "ACMP-01"
        m["objects"][0]["id"] = "XX-1"
        self.assertProblems(m, "ArchiMate has no parent field", "needs an id starting 'BACT-'",
                            "source not in model")

    def test_archimate_access_attribute(self):
        m = clone(example("archimate"))
        m["relationships"][0]["access"] = "read"
        self.assertProblems(m, "on access relationships only")

    def test_junction_keeps_one_relationship_type(self):
        m = clone(example("archimate"))
        m["objects"].append({"id": "JAND-1", "type": "And Junction", "name": "and"})
        m["relationships"] += [{"from": "ACMP-02", "type": "serving", "to": "JAND-1"},
                               {"from": "JAND-1", "type": "flow", "to": "ACMP-03"}]
        self.assertProblems(m, "JAND-1: relationships through one junction must be of one type")

    def test_togaf_pairs_and_extra_verbs(self):
        m = clone(example("togaf"))
        m["relationships"].append({"from": "DAT-01", "type": "is hosted on", "to": "PTC-01"})
        self.assertProblems(m, "'is hosted on' does not join Data Entity -> Physical Technology Component")
        m = clone(example("togaf"))
        m["relationships"].append({"from": "ROL-01", "type": "approves", "to": "DAT-01"})
        validate(m, extra_verbs={"approves": (["Role"], ["Data Entity"])})

    def test_parent_must_share_type_and_not_loop(self):
        m = clone(example("essential"))
        m["objects"][2]["parent"] = "ACP-01"
        self.assertProblems(m, "parent links join objects of one type")
        m = clone(example("essential"))
        m["objects"][1]["parent"] = "BCP-02"
        self.assertProblems(m, "parent chain loops")


class BpmnValidation(unittest.TestCase):
    def problems(self, m):
        with self.assertRaises(ModelError) as cm:
            validate(m)
        return str(cm.exception)

    def test_sequence_flow_cannot_cross_pools(self):
        m = clone(example("bpmn"))
        m["objects"].append({"id": "T-X", "type": "task", "name": "Customer task", "parent": "P-CUST"})
        m["relationships"].append({"from": "T-REG", "type": "sequenceFlow", "to": "T-X"})
        self.assertIn("sequence flow stays inside one pool", self.problems(m))

    def test_message_flow_needs_two_pools_and_right_ends(self):
        m = clone(example("bpmn"))
        m["relationships"] += [{"from": "T-REG", "type": "messageFlow", "to": "T-ASSESS"},
                               {"from": "P-CUST", "type": "messageFlow", "to": "E-END"}]
        p = self.problems(m)
        self.assertIn("message flow runs between two different pools", p)
        self.assertIn("an end event sends messages", p)

    def test_event_rules(self):
        m = clone(example("bpmn"))
        m["relationships"].append({"from": "E-END", "type": "sequenceFlow", "to": "T-REG"})
        m["objects"][4]["trigger"] = "terminate"
        p = self.problems(m)
        self.assertIn("an end event has no outgoing sequence flow", p)
        self.assertIn("startEvent cannot have trigger 'terminate'", p)

    def test_boundary_and_lanes(self):
        m = clone(example("bpmn"))
        b = next(o for o in m["objects"] if o["id"] == "B-SLA")
        del b["attachedTo"]
        m["objects"].append({"id": "T-Y", "type": "task", "name": "Loose", "parent": "P-SVC"})
        p = self.problems(m)
        self.assertIn("boundaryEvent needs attachedTo", p)
        self.assertIn("pool P-SVC has lanes; put the node in one of them", p)

    def test_warnings_for_smells(self):
        m = clone(example("bpmn"))
        m["objects"].append({"id": "G-LONE", "type": "exclusiveGateway", "parent": "L-SYS"})
        m["relationships"] = [r for r in m["relationships"] if r["to"] != "E-END"]
        m["relationships"] += [{"from": "T-NOTIFY", "type": "sequenceFlow", "to": "G-LONE"},
                               {"from": "G-LONE", "type": "sequenceFlow", "to": "E-END"}]
        w = validate(m)["warnings"]
        self.assertTrue(any("G-LONE: gateway neither splits nor joins" in x for x in w), w)


if __name__ == "__main__":
    unittest.main()
