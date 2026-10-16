"""OrbusInfinity import: turn a validated model into the requests that load
it into an OrbusInfinity repository through its REST API, and run them.

OrbusInfinity API (OData v4, OAuth 2 bearer token), as published in its
connector reference:
    POST  /odata/Objects               {objectTypeId, modelId, name, attributeValuesFlat}
    PATCH /odata/Objects({id})         {attributeValuesFlat}
    POST  /odata/Relationships         {relationshipTypeId, modelId, leadModelItemId,
                                        memberModelItemId, relationshipTypePairId?,
                                        attributeValuesFlat?}
    GET   /odata/Objects?$expand=ObjectType,Model&$top=50&$skip=n
    GET   /odata/Relationships?$expand=RelationshipType,LeadObject,MemberObject&$top=50&$skip=n
    100 calls per 60 seconds per connection.

Object and relationship type ids belong to each tenant, so a mapping file
says which Orbus type each model type becomes:

    {"apiUrl": "https://<tenant>-api.orbusinfinity.com",
     "modelId": "<guid of the Orbus model to load into>",
     "objectTypes": {"Application Component": "<guid>", …},
     "relationshipTypes": {"serving": "<guid>" |
                           {"id": "<guid>", "pairId": "<guid>", "reverse": false}, …},
     "attributes": {"description": "Description", "status": "Lifecycle Status", …}}

`reverse` swaps lead and member for a relationship type that Orbus defines
in the other direction. `discover()` reads the tenant's types and existing
objects and drafts this file; `plan()` writes the import payload (every
request, in order, with {{id}} placeholders for GUIDs not yet known);
`push()` runs it, throttled, and keeps a ledger of model id -> Orbus GUID so
a second push updates instead of duplicating.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .metamodel import ModelError, metamodel_of, relationship_id, validate

RATE = 100            # calls per window
WINDOW = 60.0         # seconds
PAGE = 50             # the API's $top ceiling
FIELDS = ("description", "status", "owner", "ref", "category", "doc", "sad")


class OrbusError(RuntimeError):
    pass


def _ci(d, *keys):
    """Case-insensitive lookup across candidate keys (OData casing varies)."""
    if not isinstance(d, dict):
        return None
    low = {k.lower(): v for k, v in d.items()}
    for k in keys:
        if k.lower() in low:
            return low[k.lower()]
    return None


class Client:
    """Minimal OrbusInfinity OData client with throttling and retry."""

    def __init__(self, api_url, token, rate=RATE, window=WINDOW, opener=None):
        if not api_url:
            raise OrbusError("no API URL: set apiUrl in the mapping file or ORBUS_API_URL")
        if not token:
            raise OrbusError("no access token: set ORBUS_TOKEN to an OAuth 2 bearer token for the API")
        self.base = api_url.rstrip("/")
        self.token = token
        self.min_gap = window / max(1, rate - 5)
        self.last = 0.0
        self.calls = 0
        self.open = opener or urllib.request.urlopen

    def request(self, method, path, body=None, retries=4):
        url = self.base + path
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(retries + 1):
            wait = self.last + self.min_gap - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.last = time.monotonic()
            self.calls += 1
            req = urllib.request.Request(url, data=data, method=method, headers={
                "Authorization": f"Bearer {self.token}", "Accept": "application/json",
                "Content-Type": "application/json"})
            try:
                with self.open(req, timeout=60) as r:
                    raw = r.read()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:600]
                if e.code in (429, 502, 503, 504) and attempt < retries:
                    time.sleep(float(e.headers.get("Retry-After") or 2 * (attempt + 1)))
                    continue
                raise OrbusError(f"{method} {path} -> HTTP {e.code}: {detail}")
            except urllib.error.URLError as e:
                if attempt < retries:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise OrbusError(f"{method} {path} -> {e.reason}")
        raise OrbusError(f"{method} {path}: gave up after {retries} retries")

    def pages(self, path, query, limit_pages=200):
        """GET every page of an OData collection."""
        out = []
        for n in range(limit_pages):
            q = dict(query, **{"$top": PAGE, "$skip": n * PAGE})
            res = self.request("GET", f"{path}?{urllib.parse.urlencode(q, safe='$,()')}")
            rows = _ci(res, "value") or []
            out.extend(rows)
            if len(rows) < PAGE:
                break
        return out


# ------------------------------------------------------------------ discover

def discover(client, model=None, max_pages=200):
    """Read the tenant's object and relationship types and existing objects.
    Returns {"objectTypes": {name: id}, "relationshipTypes": {name: id},
    "models": {name: id}, "objects": [{id, name, objectTypeId, objectType}],
    "draft": mapping file draft for `model` (types matched by name)}."""
    objs = client.pages("/odata/Objects", {"$expand": "ObjectType,Model"}, max_pages)
    rels = client.pages("/odata/Relationships", {"$expand": "RelationshipType"}, max_pages)
    otypes, rtypes, models, existing = {}, {}, {}, []
    for o in objs:
        ot = _ci(o, "ObjectType") or {}
        tname, tid = _ci(ot, "Name", "name"), _ci(ot, "Id", "ObjectTypeId", "id")
        tid = tid or _ci(o, "ObjectTypeId")
        if tname and tid:
            otypes[tname] = tid
        m = _ci(o, "Model") or {}
        if _ci(m, "Name") and _ci(m, "Id", "ModelId"):
            models[_ci(m, "Name")] = _ci(m, "Id", "ModelId")
        existing.append({"id": _ci(o, "ObjectId", "Id"), "name": _ci(o, "Name"),
                         "objectTypeId": tid, "objectType": tname})
    for r in rels:
        rt = _ci(r, "RelationshipType") or {}
        name, rid = _ci(rt, "Name", "name"), _ci(rt, "Id", "RelationshipTypeId", "id")
        if name and rid:
            rtypes[name] = rid
    out = {"objectTypes": otypes, "relationshipTypes": rtypes, "models": models, "objects": existing}
    if model is not None:
        out["draft"] = draft_mapping(model, otypes, rtypes, client.base,
                                     next(iter(models.values()), ""))
    return out


def _norm(s):
    return "".join(c for c in str(s).lower() if c.isalnum())


def draft_mapping(model, otypes, rtypes, api_url="", model_id=""):
    """A mapping file with every type the model uses, filled where a tenant
    type has the same name (ignoring case and spaces), else empty for the
    person to complete."""
    mm = metamodel_of(model)
    on = {_norm(k): v for k, v in otypes.items()}
    rn = {_norm(k): v for k, v in rtypes.items()}
    used_o = sorted({o["type"] for o in model["objects"]})
    used_r = sorted({r["type"] for r in model["relationships"]})

    def rguess(verb):
        for cand in (verb, mm.relationships.get(verb, {}).get("xml", ""),
                     mm.relationships.get(verb, {}).get("reads", "")):
            if cand and _norm(cand) in rn:
                return rn[_norm(cand)]
        return ""

    return {"apiUrl": api_url, "modelId": model_id,
            "objectTypes": {t: on.get(_norm(t), "") for t in used_o},
            "relationshipTypes": {v: rguess(v) for v in used_r},
            "attributes": {"description": "Description"}}


# ------------------------------------------------------------------ plan

def _rel_map(entry):
    if isinstance(entry, dict):
        return entry.get("id", ""), entry.get("pairId"), bool(entry.get("reverse"))
    return entry, None, False


def plan(model, mapping, ledger=None):
    """The import payload: objects then relationships, each with its request.
    Raises ModelError listing every unmapped type at once."""
    validate(model)
    ledger = ledger or {}
    led_o, led_r = ledger.get("objects", {}), ledger.get("relationships", {})
    errs = []
    if not mapping.get("modelId"):
        errs.append("mapping: modelId is empty (the Orbus model to load into)")
    ot, rt = mapping.get("objectTypes", {}), mapping.get("relationshipTypes", {})
    for t in sorted({o["type"] for o in model["objects"]}):
        if not ot.get(t):
            errs.append(f"mapping: objectTypes['{t}'] has no Orbus object type id")
    for v in sorted({r["type"] for r in model["relationships"]}):
        if not _rel_map(rt.get(v, ""))[0]:
            errs.append(f"mapping: relationshipTypes['{v}'] has no Orbus relationship type id")
    if errs:
        raise ModelError(f"{len(errs)} mapping problem(s):\n  " + "\n  ".join(errs))
    attrs = mapping.get("attributes", {"description": "Description"})
    mid = mapping["modelId"]
    steps_o, steps_r = [], []
    for o in model["objects"]:
        flat = {}
        for f in FIELDS:
            if o.get(f) and attrs.get(f):
                flat[attrs[f]] = o[f]
        for k, v in (o.get("properties") or {}).items():
            if attrs.get(k):
                flat[attrs[k]] = v
        if o["id"] in led_o:
            req = {"method": "PATCH", "path": f"/odata/Objects({led_o[o['id']]})",
                   "body": {"attributeValuesFlat": flat}}
        else:
            body = {"objectTypeId": ot[o["type"]], "modelId": mid, "name": o["name"]}
            if flat:
                body["attributeValuesFlat"] = flat
            req = {"method": "POST", "path": "/odata/Objects", "body": body}
        steps_o.append({"key": o["id"], "type": o["type"], "name": o["name"], "request": req})
    for r in model["relationships"]:
        rid = relationship_id(r)
        tid, pair, reverse = _rel_map(rt[r["type"]])
        lead, member = (r["to"], r["from"]) if reverse else (r["from"], r["to"])
        flat = {}
        if r.get("note") and attrs.get("note"):
            flat[attrs["note"]] = r["note"]
        if r.get("name") and attrs.get("name"):
            flat[attrs["name"]] = r["name"]
        if rid in led_r:
            if not flat:
                continue
            req = {"method": "PATCH", "path": f"/odata/Relationships({led_r[rid]})",
                   "body": {"attributeValuesFlat": flat}}
        else:
            body = {"relationshipTypeId": tid, "modelId": mid,
                    "leadModelItemId": "{{%s}}" % lead, "memberModelItemId": "{{%s}}" % member}
            if pair:
                body["relationshipTypePairId"] = pair
            if flat:
                body["attributeValuesFlat"] = flat
            req = {"method": "POST", "path": "/odata/Relationships", "body": body}
        steps_r.append({"key": rid, "from": r["from"], "type": r["type"], "to": r["to"], "request": req})
    return {"target": "OrbusInfinity", "api": "OData v4: /odata/Objects, /odata/Relationships",
            "model": model.get("name", ""), "metamodel": metamodel_of(model).key,
            "modelId": mid, "objects": steps_o, "relationships": steps_r,
            "counts": {"create": sum(s["request"]["method"] == "POST" for s in steps_o + steps_r),
                       "update": sum(s["request"]["method"] == "PATCH" for s in steps_o + steps_r)}}


def write_plan(payload, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=1)
        f.write("\n")
    return path


# ------------------------------------------------------------------ push

def load_ledger(path):
    if path and os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"objects": {}, "relationships": {}}


def _save_ledger(ledger, path):
    if not path:
        return
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(ledger, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def _fill(body, ids):
    out = {}
    for k, v in body.items():
        if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
            key = v[2:-2]
            if key not in ids:
                raise OrbusError(f"no Orbus id for {key}: its object was not created")
            out[k] = ids[key]
        else:
            out[k] = v
    return out


def push(payload, client, ledger_path=None, log=print):
    """Run the payload: objects first (recording each new GUID), then the
    relationships with their ends filled in. The ledger is saved after every
    call, so an interrupted push resumes where it stopped."""
    ledger = load_ledger(ledger_path)
    ids = dict(ledger["objects"])
    done = {"created": 0, "updated": 0}
    for s in payload["objects"]:
        req = s["request"]
        if req["method"] == "POST" and s["key"] in ids:
            continue          # created by an interrupted earlier run of this payload
        res = client.request(req["method"], req["path"], req["body"])
        if req["method"] == "POST":
            oid = _ci(res, "objectId", "ObjectId", "id", "Id")
            if not oid:
                raise OrbusError(f"create {s['key']}: response had no objectId: {res}")
            ids[s["key"]] = oid
            ledger["objects"][s["key"]] = oid
            done["created"] += 1
        else:
            done["updated"] += 1
        _save_ledger(ledger, ledger_path)
        log(f"{req['method']:5} object {s['key']:<16} {s['name']}")
    for s in payload["relationships"]:
        req = s["request"]
        if req["method"] == "POST" and s["key"] in ledger["relationships"]:
            continue
        body = _fill(req["body"], ids)
        res = client.request(req["method"], req["path"], body)
        if req["method"] == "POST":
            rid = _ci(res, "relationshipId", "RelationshipId", "id", "Id")
            if not rid:
                raise OrbusError(f"create {s['key']}: response had no relationshipId: {res}")
            ledger["relationships"][s["key"]] = rid
            done["created"] += 1
        else:
            done["updated"] += 1
        _save_ledger(ledger, ledger_path)
        log(f"{req['method']:5} relationship {s['from']} -{s['type']}-> {s['to']}")
    done["calls"] = client.calls
    return done


def seed_ledger(model, mapping, existing, ledger_path=None):
    """Match the model's objects to objects already in the tenant (same name
    and mapped type) so the first push updates them instead of adding
    duplicates. `existing` is discover()["objects"]. Returns the ledger."""
    ledger = load_ledger(ledger_path)
    ot = mapping.get("objectTypes", {})
    index = {}
    for e in existing:
        if e.get("id") and e.get("name"):
            index.setdefault((str(e.get("objectTypeId")).lower(), e["name"].strip().lower()), []).append(e["id"])
    for o in model["objects"]:
        hits = index.get((str(ot.get(o["type"], "")).lower(), o["name"].strip().lower()), [])
        if len(hits) == 1 and o["id"] not in ledger["objects"]:
            ledger["objects"][o["id"]] = hits[0]
    _save_ledger(ledger, ledger_path)
    return ledger
