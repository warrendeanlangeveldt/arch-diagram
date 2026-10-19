"""OrbusInfinity import, exercised against a local HTTP server that follows
the published API contract (/odata/Objects, /odata/Relationships, OData
paging, 429 throttling). It checks request order, bodies and idempotency;
it is not a substitute for a trial push into a real tenant."""
import json
import os
import re
import tempfile
import threading
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from helpers import clone, example
from ealib import ModelError
from ealib import orbus


class FakeOrbus:
    def __init__(self):
        self.objects, self.rels, self.log = {}, {}, []
        self.throttle_next = 0
        self.types = {"Application Component": str(uuid.uuid4()), "Business Actor": str(uuid.uuid4())}
        self.model_id = str(uuid.uuid4())
        for i in range(60):   # existing content, more than one page
            oid = str(uuid.uuid4())
            self.objects[oid] = {"ObjectId": oid, "Name": "CRM" if i == 0 else f"Existing {i}",
                                 "ObjectTypeId": self.types["Application Component"],
                                 "ObjectType": {"Id": self.types["Application Component"], "Name": "Application Component"},
                                 "Model": {"Id": self.model_id, "Name": "Enterprise"}}
        self.rtid = str(uuid.uuid4())
        self.rels["seed"] = {"RelationshipId": "seed", "RelationshipType": {"Id": self.rtid, "Name": "Serving"}}

    def handler(fake):
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body=None, headers=None):
                data = json.dumps(body).encode() if body is not None else b""
                self.send_response(code)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _body(self):
                n = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(n)) if n else None

            def handle_one(self, method):
                body = self._body()
                fake.log.append((method, self.path, body))
                if self.headers.get("Authorization") != "Bearer t0ken":
                    return self._send(401, {"error": "unauthorised"})
                if fake.throttle_next:
                    fake.throttle_next -= 1
                    return self._send(429, {"error": "slow down"}, {"Retry-After": "0"})
                path, _, query = self.path.partition("?")
                q = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
                if method == "GET" and path == "/odata/Objects":
                    rows = list(fake.objects.values())
                    s, t = int(q.get("%24skip", q.get("$skip", 0))), int(q.get("%24top", q.get("$top", 50)))
                    return self._send(200, {"value": rows[s:s + t]})
                if method == "GET" and path == "/odata/Relationships":
                    return self._send(200, {"value": list(fake.rels.values())})
                if method == "POST" and path == "/odata/Objects":
                    for k in ("objectTypeId", "modelId", "name"):
                        if not body.get(k):
                            return self._send(400, {"error": f"{k} required"})
                    oid = str(uuid.uuid4())
                    fake.objects[oid] = dict(body, ObjectId=oid)
                    return self._send(200, {"name": body["name"], "objectId": oid, "modelId": body["modelId"],
                                            "objectTypeId": body["objectTypeId"]})
                m = re.match(r"/odata/(Objects|Relationships)\(([^)]+)\)$", path)
                if method == "PATCH" and m:
                    store = fake.objects if m.group(1) == "Objects" else fake.rels
                    if m.group(2) not in store:
                        return self._send(404, {"error": "not found"})
                    store[m.group(2)].update(body)
                    return self._send(200, {"objectId": m.group(2)})
                if method == "POST" and path == "/odata/Relationships":
                    for k in ("leadModelItemId", "memberModelItemId"):
                        if body.get(k) not in fake.objects:
                            return self._send(400, {"error": f"{k} unknown"})
                    rid = str(uuid.uuid4())
                    fake.rels[rid] = dict(body, RelationshipId=rid)
                    return self._send(200, {"relationshipId": rid, "leadObjectId": body["leadModelItemId"],
                                            "memberObjectId": body["memberModelItemId"]})
                return self._send(404, {"error": "no route"})

            def do_GET(self):
                self.handle_one("GET")

            def do_POST(self):
                self.handle_one("POST")

            def do_PATCH(self):
                self.handle_one("PATCH")
        return H


class OrbusImport(unittest.TestCase):
    def setUp(self):
        self.fake = FakeOrbus()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), self.fake.handler())
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        self.tmp = tempfile.TemporaryDirectory()
        self.model = example("archimate")

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()

    def client(self):
        return orbus.Client(self.url, "t0ken", rate=10000)

    def mapping(self):
        types = {t: str(uuid.uuid4()) for t in {o["type"] for o in self.model["objects"]}}
        types["Application Component"] = self.fake.types["Application Component"]
        rels = {v: str(uuid.uuid4()) for v in {r["type"] for r in self.model["relationships"]}}
        rels["serving"] = {"id": self.fake.rtid, "reverse": True, "pairId": "pair-1"}
        return {"apiUrl": self.url, "modelId": self.fake.model_id, "objectTypes": types,
                "relationshipTypes": rels,
                "attributes": {"description": "Description", "status": "Lifecycle Status",
                               "classification": "Classification", "name": "Label"}}

    def test_plan_lists_every_missing_mapping(self):
        m = self.mapping()
        del m["objectTypes"]["Node"]
        m["relationshipTypes"]["flow"] = ""
        m["modelId"] = ""
        with self.assertRaises(ModelError) as cm:
            orbus.plan(self.model, m)
        msg = str(cm.exception)
        for frag in ("modelId is empty", "objectTypes['Node']", "relationshipTypes['flow']"):
            self.assertIn(frag, msg)

    def test_plan_bodies(self):
        p = orbus.plan(self.model, self.mapping())
        self.assertEqual(p["counts"], {"create": 27, "update": 0})
        crm = [s for s in p["objects"] if s["key"] == "ACMP-CRM"][0]["request"]
        self.assertEqual(crm["body"]["attributeValuesFlat"],
                         {"Description": "Defined in the CRM solution architecture.", "Lifecycle Status": "Built"})
        dobj = [s for s in p["objects"] if s["key"] == "DOBJ-01"][0]["request"]["body"]
        self.assertEqual(dobj["attributeValuesFlat"], {"Classification": "Confidential"})
        srv = [s for s in p["relationships"] if s["type"] == "serving" and s["from"] == "ASVC-01"][0]
        b = srv["request"]["body"]
        self.assertEqual((b["leadModelItemId"], b["memberModelItemId"]), ("{{BPRC-01}}", "{{ASVC-01}}"))
        self.assertEqual(b["relationshipTypePairId"], "pair-1")
        flow = [s for s in p["relationships"] if s["type"] == "flow"][0]["request"]["body"]
        self.assertEqual(flow["attributeValuesFlat"], {"Label": "case events"})

    def test_discover_drafts_mapping_and_seeds_ledger(self):
        found = orbus.discover(self.client(), self.model)
        self.assertEqual(len(found["objects"]), 60)          # paged past 50
        draft = found["draft"]
        self.assertEqual(draft["objectTypes"]["Application Component"], self.fake.types["Application Component"])
        self.assertEqual(draft["objectTypes"]["Node"], "")
        self.assertEqual(draft["relationshipTypes"]["serving"], self.fake.rtid)
        self.assertEqual(draft["modelId"], self.fake.model_id)
        ledger = os.path.join(self.tmp.name, "ledger.json")
        led = orbus.seed_ledger(self.model, self.mapping(), found["objects"], ledger)
        crm_id = [k for k, v in self.fake.objects.items() if v.get("Name") == "CRM"][0]
        self.assertEqual(led["objects"], {"ACMP-CRM": crm_id})

    def test_push_then_repush_updates(self):
        ledger = os.path.join(self.tmp.name, "ledger.json")
        before = len(self.fake.objects)
        self.fake.throttle_next = 2
        res = orbus.push(orbus.plan(self.model, self.mapping()), self.client(), ledger, log=lambda *_: None)
        self.assertEqual(res["created"], 27)
        self.assertEqual(len(self.fake.objects), before + 13)
        posts = [p for m, p, _ in self.fake.log if m == "POST"]
        first_rel = posts.index("/odata/Relationships")
        self.assertNotIn("/odata/Objects", posts[first_rel:], "objects go first")
        self.assertEqual(len(posts), 27 + 2, "27 creates plus the 2 throttled retries")
        with open(ledger) as f:
            led = json.load(f)
        lead = [r for r in self.fake.rels.values() if r.get("relationshipTypePairId") == "pair-1"
                and r["memberModelItemId"] == led["objects"]["ASVC-01"]][0]
        self.assertEqual(lead["leadModelItemId"], led["objects"]["BPRC-01"])
        # second push: nothing new is created
        self.fake.log.clear()
        m2 = clone(self.model)
        m2["objects"][3]["description"] = "Now documented"
        p2 = orbus.plan(m2, self.mapping(), orbus.load_ledger(ledger))
        self.assertEqual(p2["counts"]["create"], 0)
        res2 = orbus.push(p2, self.client(), ledger, log=lambda *_: None)
        self.assertEqual(res2["created"], 0)
        self.assertEqual(len(self.fake.objects), before + 13)
        self.assertEqual(self.fake.objects[led["objects"]["ACMP-01"]]["attributeValuesFlat"]["Description"],
                         "Now documented")
        self.assertTrue(all(m == "PATCH" for m, _, _ in self.fake.log))

    def test_interrupted_push_resumes(self):
        ledger = os.path.join(self.tmp.name, "ledger.json")
        payload = orbus.plan(self.model, self.mapping())
        bad = clone(payload)
        bad["relationships"][4]["request"]["body"]["relationshipTypeId"] = None
        bad["relationships"][4]["request"]["body"]["leadModelItemId"] = "{{NOPE}}"
        with self.assertRaises(orbus.OrbusError):
            orbus.push(bad, self.client(), ledger, log=lambda *_: None)
        n = len(self.fake.objects)
        res = orbus.push(payload, self.client(), ledger, log=lambda *_: None)
        self.assertEqual(len(self.fake.objects), n, "objects are not created twice")
        self.assertEqual(res["created"], len(payload["relationships"]) - 4)

    def test_bad_token(self):
        c = orbus.Client(self.url, "wrong", rate=10000)
        with self.assertRaises(orbus.OrbusError) as cm:
            c.request("GET", "/odata/Objects")
        self.assertIn("HTTP 401", str(cm.exception))

    def test_bpmn_model_plans_too(self):
        m = example("bpmn")
        mp = {"modelId": "m", "objectTypes": {t: "x" for t in {o["type"] for o in m["objects"]}},
              "relationshipTypes": {t: "y" for t in {r["type"] for r in m["relationships"]}}}
        p = orbus.plan(m, mp)
        self.assertEqual(len(p["objects"]), len(m["objects"]))


if __name__ == "__main__":
    unittest.main()
