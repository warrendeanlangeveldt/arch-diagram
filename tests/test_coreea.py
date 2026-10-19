"""CoreEA as one metamodel of ealib, and the 1.x coreea_lib API on top of it."""
import json
import os
import subprocess
import tempfile
import unittest

from helpers import EXAMPLES, clone, example
import coreea_lib
from ealib import ModelError, View, load_metamodel, validate


class CoreEA(unittest.TestCase):
    def test_example_is_a_1x_model_file(self):
        m = example("coreea")
        self.assertNotIn("metamodel", m)
        self.assertEqual(validate(m)["metamodel"], "CoreEA")

    def test_rules(self):
        mm = load_metamodel("coreea")
        self.assertEqual(len(mm.types), 22)
        self.assertTrue(mm.allowed("realises", "Application", "Capability"))
        self.assertTrue(mm.allowed("realises", "Control", "Requirement"))
        self.assertFalse(mm.allowed("realises", "Application", "Requirement"))
        self.assertTrue(mm.allowed("categorised as", "Technology", "Technology Category"))
        self.assertFalse(mm.allowed("categorised as", "Application", "Technology Category"))
        m = clone(example("coreea"))
        m["relationships"].append({"from": "APP-01", "type": "realises", "to": "INT-01"})
        with self.assertRaises(ModelError) as cm:
            validate(m)
        self.assertIn("'realises' does not join Application -> Interface", str(cm.exception))

    def test_1x_api(self):
        self.assertEqual(coreea_lib.TYPE_PREFIX["Application"], "APP")
        self.assertEqual(coreea_lib.VERB_PAIRS["supports"],
                         {("Capability", "Objective"), ("Application", "Process")})
        self.assertIn("Interface", coreea_lib.VERBS["applies to"][1])
        th = coreea_lib.make_theme(layers={"Application": ("#1d4ed8", "#eff6ff")})
        self.assertEqual(th["layers"]["Application"], ("#1d4ed8", "#eff6ff"))
        self.assertEqual(th["layers"]["Data"], ("#3b6a8f", "#edf3f8"))
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "m.json")
            with open(p, "w") as f:
                json.dump(example("coreea"), f)
            model = coreea_lib.load_model(p)
            coreea_lib.validate(model, extra_verbs={"governs": (["Organization"], ["Principle"])})
            v = coreea_lib.View(model, "T", title="t", theme=th)
            v.node("APP-01", 16, 16, 180)
            v.edge([(10, 10), (20, 20)], "parent", check=[("APP-02", "parent", "APP-01")])
            v.save(80, d, render=False)
            with open(os.path.join(d, "T.objects.json")) as f:
                self.assertEqual(json.load(f), ["APP-01"])
            objs, rels = coreea_lib.catalogue_rows(model)
            self.assertEqual(rels[0]["relationship"], "uses")
            with self.assertRaises(ModelError):
                coreea_lib.validate(example("togaf"))

    def test_crud_matrix_from_reads_and_writes(self):
        m = clone(example("coreea"))
        m["objects"].append({"id": "DAT-01", "type": "Data Entity", "name": "Case"})
        m["relationships"] += [{"from": "APP-03", "type": "writes", "to": "DAT-01"},
                               {"from": "APP-03", "type": "reads", "to": "DAT-01"},
                               {"from": "APP-02", "type": "reads", "to": "DAT-01"}]
        validate(m)
        v = View(m, "CRUD", viewpoint="CRUD matrix")
        cells = v.cells_from({"writes": "CU", "reads": "R"}, ["DAT-01"], ["APP-02", "APP-03"])
        self.assertEqual(cells, {("DAT-01", "APP-03"): "CRU", ("DAT-01", "APP-02"): "R"})

    def test_cli_validates_1x_file(self):
        here = os.path.dirname(os.path.abspath(__file__))
        ea = os.path.join(here, "..", "skills", "arch-diagram", "scripts", "ea.py")
        r = subprocess.run(["python3", ea, "validate", os.path.join(EXAMPLES, "coreea", "model.json")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("CoreEA", r.stdout)


if __name__ == "__main__":
    unittest.main()
