import json
import os
import subprocess
import tempfile
import unittest

from helpers import EXAMPLES, SCRIPTS, example

EA = os.path.join(SCRIPTS, "ea.py")
ICONS = os.path.join(SCRIPTS, "icons.py")


def run(*args, env=None):
    return subprocess.run(["python3", *args], capture_output=True, text=True,
                          env=dict(os.environ, **(env or {})))


class Schema(unittest.TestCase):
    def test_examples_use_only_schema_fields(self):
        with open(os.path.join(SCRIPTS, "model_schema.json")) as f:
            sc = json.load(f)
        okeys = set(sc["properties"]["objects"]["items"]["properties"])
        rkeys = set(sc["properties"]["relationships"]["items"]["properties"])
        for name in ("coreea", "archimate", "togaf", "essential", "bpmn"):
            m = example(name)
            m.setdefault("metamodel", "coreea")
            self.assertTrue(set(m) <= set(sc["properties"]), name)
            self.assertIn(m["metamodel"], sc["properties"]["metamodel"]["enum"])
            for o in m["objects"]:
                self.assertTrue(set(o) <= okeys, (name, set(o) - okeys))
            for r in m["relationships"]:
                self.assertTrue(set(r) <= rkeys, (name, set(r) - rkeys))


class Cli(unittest.TestCase):
    def test_validate_reports_errors_and_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            m = example("archimate")
            m["relationships"].append({"from": "DOBJ-01", "type": "serving", "to": "BACT-01"})
            p = os.path.join(d, "m.json")
            with open(p, "w") as f:
                json.dump(m, f)
            r = run(EA, "validate", p)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("'serving' does not join Data Object -> Business Actor", r.stderr)
        r = run(EA, "validate", os.path.join(EXAMPLES, "bpmn", "model.json"))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_rules_types_viewpoints(self):
        self.assertIn("serving", run(EA, "rules", "archimate", "Application Service", "Business Process").stdout)
        self.assertIn("PAC", run(EA, "types", "togaf").stdout)
        self.assertIn("Business Capability to Application", run(EA, "viewpoints", "essential").stdout)

    def test_exports(self):
        with tempfile.TemporaryDirectory() as d:
            for name, fmt, ext in (("archimate", "archimate", ".xml"), ("bpmn", "bpmn", ".bpmn"),
                                   ("togaf", "csv", ".objects.csv")):
                r = run(EA, "export", os.path.join(EXAMPLES, name, "model.json"), "--format", fmt, "--out", d)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertTrue(r.stdout.strip().splitlines()[0].endswith(ext))

    def test_orbus_plan(self):
        m = example("togaf")
        mp = {"modelId": "m-1", "objectTypes": {t: f"ot-{i}" for i, t in enumerate(sorted({o["type"] for o in m["objects"]}))},
              "relationshipTypes": {t: f"rt-{i}" for i, t in enumerate(sorted({r["type"] for r in m["relationships"]}))}}
        with tempfile.TemporaryDirectory() as d:
            mpath, out = os.path.join(d, "map.json"), os.path.join(d, "payload.json")
            with open(mpath, "w") as f:
                json.dump(mp, f)
            r = run(EA, "orbus", "plan", os.path.join(EXAMPLES, "togaf", "model.json"), "--map", mpath, "--out", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out) as f:
                payload = json.load(f)
            self.assertEqual(len(payload["objects"]), len(m["objects"]))
            del mp["objectTypes"]["Driver"]
            with open(mpath, "w") as f:
                json.dump(mp, f)
            r = run(EA, "orbus", "plan", os.path.join(EXAMPLES, "togaf", "model.json"), "--map", mpath, "--out", out)
            self.assertIn("objectTypes['Driver']", r.stderr)
        r = run(EA, "orbus", "push", out, "--map", mpath, "--ledger", os.path.join(d, "l.json"),
                env={"ORBUS_TOKEN": "", "ORBUS_API_URL": ""})
        self.assertNotEqual(r.returncode, 0)

    def test_icons_cli_without_packs(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"ARCH_DIAGRAM_ICONS": d}
            r = run(ICONS, "resolve", "S3", env=env)
            self.assertEqual(json.loads(r.stdout)["ref"], "generic:bucket")
            r = run(ICONS, "fetch", "aws", env=env)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("--accept-terms", r.stderr)
            self.assertIn("<g transform", run(ICONS, "svg", "Kafka", "--x", "4", env=env).stdout)


if __name__ == "__main__":
    unittest.main()
