"""Metamodels and the object model.

A model is one JSON file per solution:

    {"metamodel": "archimate" | "togaf" | "essential" | "coreea" | "bpmn",
     "name": "…",
     "objects": [{"id", "type", "name", "description", "status", "owner",
                  "ref", "parent", "category", "doc", "sad", "properties"}],
     "relationships": [{"id", "from", "type", "to", "name", "note", …}]}

validate(model) checks it against its metamodel and raises ModelError
listing every problem at once. Every view and every export reads the same
validated model, so an object has the same id, type and name everywhere.
"""
import csv
import json
import os
import re

from .common import SCRIPTS, STATUSES

METAMODEL_DIR = os.path.join(SCRIPTS, "metamodels")
METAMODELS = ("archimate", "togaf", "essential", "coreea", "bpmn")
NCNAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


class ModelError(ValueError):
    pass


class Metamodel:
    """Types, layers, relationships, rules and viewpoints of one framework."""

    def __init__(self, data):
        self.data = data
        self.key = data["key"]
        self.name = data["name"]
        self.notation = data["notation"]
        self.source = data.get("source", "")
        self.types = data["types"]
        self.layers = {k: tuple(v) for k, v in data["layers"].items()}
        self.layer_order = data["layer_order"]
        self.relationships = data["relationships"]
        self.rules = data.get("rules")          # ArchiMate: src -> tgt -> codes
        self.viewpoints = data.get("viewpoints", {})
        self.type_order = list(self.types)
        self._code = {r.get("code"): k for k, r in self.relationships.items() if r.get("code")}

    def layer(self, otype):
        return self.types[otype]["layer"]

    def colours(self, otype, theme_layers=None):
        layer = self.layer(otype)
        if theme_layers and layer in theme_layers:
            return tuple(theme_layers[layer])
        return self.layers[layer]

    def prefix(self, otype):
        return self.types[otype].get("prefix")

    def allowed(self, verb, src, tgt, extra=None):
        if extra and verb in extra:
            s, t = extra[verb]
            return src in s and tgt in t
        rel = self.relationships.get(verb)
        if rel is None:
            return False
        if self.rules is not None:
            return rel["code"] in self.rules.get(src, {}).get(tgt, "")
        return any(src in s and tgt in t for s, t in rel["pairs"])

    def allowed_verbs(self, src, tgt):
        if self.rules is not None:
            return [self._code[c] for c in self.rules.get(src, {}).get(tgt, "")]
        return [v for v in self.relationships if self.allowed(v, src, tgt)]

    def viewpoint(self, name):
        if name not in self.viewpoints:
            raise KeyError(f"{self.name} has no viewpoint '{name}'. Known: "
                           + ", ".join(self.viewpoints))
        return self.viewpoints[name]


_CACHE = {}


def load_metamodel(key):
    """The Metamodel for 'archimate', 'togaf', 'essential' or 'coreea'. BPMN's rules
    are structural and live in ealib.bpmn."""
    if key == "bpmn":
        from .bpmn import BPMN_METAMODEL
        return BPMN_METAMODEL
    if key not in _CACHE:
        path = os.path.join(METAMODEL_DIR, f"{key}.json")
        if not os.path.exists(path):
            raise ModelError(f"unknown metamodel '{key}' (known: {', '.join(METAMODELS)})")
        with open(path) as f:
            _CACHE[key] = Metamodel(json.load(f))
    return _CACHE[key]


def load_model(path):
    """A model from model.json, or the model a view-language file (.ead)
    declares or imports."""
    if str(path).endswith(".ead"):
        from .dsl import load_document
        return load_document(path).model
    with open(path) as f:
        return json.load(f)


def metamodel_of(model):
    """The model's metamodel. A model without a 'metamodel' field is CoreEA,
    as every 1.x model file was."""
    return load_metamodel(model.get("metamodel") or "coreea")


def _common_object_checks(objs, errs, mm, strict_prefix):
    byid = {}
    for i, o in enumerate(objs):
        oid, t = o.get("id"), o.get("type")
        where = f"objects[{i}] {oid or '?'}"
        if not oid or not o.get("name") or not t:
            errs.append(f"{where}: id, type and name are required")
            continue
        if oid in byid:
            errs.append(f"{where}: duplicate id")
        byid[oid] = o
        if not NCNAME.match(oid):
            errs.append(f"{where}: id must start with a letter or _ and use only letters, "
                        "digits, '-', '_' or '.' (it becomes an XML identifier)")
        if t not in mm.types:
            errs.append(f"{where}: unknown {mm.name} type '{t}'")
        elif strict_prefix and mm.prefix(t) and not oid.startswith(mm.prefix(t) + "-"):
            errs.append(f"{where}: type {t} needs an id starting '{mm.prefix(t)}-'")
        st = o.get("status")
        if st is not None and st not in STATUSES:
            errs.append(f"{where}: status '{st}' not one of {STATUSES}")
        props = o.get("properties")
        if props is not None and not isinstance(props, dict):
            errs.append(f"{where}: properties must be an object of name: value")
    return byid


def _parent_checks(objs, byid, errs, same_type=True):
    for o in objs:
        p = o.get("parent")
        if p is None:
            continue
        if p not in byid:
            errs.append(f"{o.get('id')}: parent {p} is not in the model")
        elif same_type and byid[p].get("type") != o.get("type"):
            errs.append(f"{o.get('id')}: parent {p} is a {byid[p].get('type')}; "
                        "parent links join objects of one type")
    for o in objs:
        seen, cur = set(), o.get("id")
        while cur in byid and byid[cur].get("parent"):
            if cur in seen:
                errs.append(f"{o.get('id')}: parent chain loops")
                break
            seen.add(cur)
            cur = byid[cur]["parent"]


def validate(model, extra_verbs=None, strict_prefix=True):
    """Check the model against its metamodel; raise ModelError listing every
    problem, else return a summary dict. `extra_verbs` adds
    {verb: (sources, targets)} that a project has agreed with its
    architecture office (TOGAF, Essential and CoreEA; ArchiMate's table is
    fixed)."""
    mm = metamodel_of(model)
    if mm.key == "bpmn":
        from .bpmn import validate_bpmn
        return validate_bpmn(model)
    errs = []
    objs = model.get("objects")
    rels = model.get("relationships")
    if not isinstance(objs, list) or not isinstance(rels, list):
        raise ModelError("model needs 'objects' and 'relationships' arrays")
    byid = _common_object_checks(objs, errs, mm, strict_prefix)
    if mm.key == "archimate":
        for o in objs:
            if o.get("parent") is not None:
                errs.append(f"{o.get('id')}: ArchiMate has no parent field; nest with a "
                            "composition, aggregation, assignment or realization relationship")
    else:
        _parent_checks(objs, byid, errs)
    if extra_verbs and mm.key == "archimate":
        errs.append("extra_verbs: ArchiMate's relationships are fixed by the standard")
    seen_rel, rel_ids = set(), set()
    junction_types = {}
    for i, r in enumerate(rels):
        f, v, t = r.get("from"), r.get("type"), r.get("to")
        where = f"relationships[{i}] {f} -{v}-> {t}"
        rid = r.get("id")
        if rid is not None:
            if rid in rel_ids or rid in byid:
                errs.append(f"{where}: id {rid} is already used")
            elif not NCNAME.match(rid):
                errs.append(f"{where}: id {rid} is not a valid identifier")
            rel_ids.add(rid)
        if (f, v, t, r.get("name")) in seen_rel:
            errs.append(f"{where}: duplicate")
        seen_rel.add((f, v, t, r.get("name")))
        if f not in byid:
            errs.append(f"{where}: source not in model")
        if t not in byid:
            errs.append(f"{where}: target not in model")
        known = set(mm.relationships) | set(extra_verbs or {})
        if v not in known:
            errs.append(f"{where}: unknown relationship (allowed: {', '.join(sorted(known))})")
            continue
        if f in byid and t in byid:
            ft, tt = byid[f]["type"], byid[t]["type"]
            if ft in mm.types and tt in mm.types and not mm.allowed(v, ft, tt, extra_verbs):
                ok = mm.allowed_verbs(ft, tt)
                hint = f" (allowed {ft} -> {tt}: {', '.join(ok)})" if ok else f" (no relationship joins {ft} -> {tt})"
                errs.append(f"{where}: '{v}' does not join {ft} -> {tt}{hint}")
            for end in (f, t):
                if byid[end]["type"] in ("And Junction", "Or Junction"):
                    junction_types.setdefault(end, set()).add(v)
        if mm.key == "archimate":
            acc = r.get("access")
            if acc is not None and (v != "access" or acc not in ("access", "read", "write", "readwrite")):
                errs.append(f"{where}: 'access' is read / write / readwrite / access, on access relationships only")
            mod = r.get("modifier")
            if mod is not None and v != "influence":
                errs.append(f"{where}: 'modifier' belongs on influence relationships")
            if r.get("directed") is not None and v != "association":
                errs.append(f"{where}: 'directed' belongs on association relationships")
    for j, verbs in junction_types.items():
        if len(verbs) > 1:
            errs.append(f"{j}: relationships through one junction must be of one type, found "
                        + ", ".join(sorted(verbs)))
    if errs:
        raise ModelError(f"{len(errs)} model problem(s):\n  " + "\n  ".join(errs))
    return {"metamodel": mm.name, "objects": len(objs), "relationships": len(rels)}


def relationship_id(r, i=None):
    """Stable identifier for a relationship: its own id, else derived."""
    if r.get("id"):
        return r["id"]
    raw = f"R-{r['from']}-{r['type']}-{r['to']}"
    rid = re.sub(r"[^A-Za-z0-9_.-]", "_", raw)
    if r.get("name"):
        rid += "-" + re.sub(r"[^A-Za-z0-9_.-]", "_", r["name"])
    return rid


def catalogue_rows(model):
    """Flat rows, names resolved: one per object, then one per relationship.
    `class` carries the framework's own type name (ArchiMate exchange type,
    Essential meta-class)."""
    mm = metamodel_of(model)
    byid = {o["id"]: o for o in model["objects"]}
    prop_keys = sorted({k for o in model["objects"] for k in (o.get("properties") or {})})
    objects = []
    for o in model["objects"]:
        td = mm.types.get(o["type"], {})
        row = {"id": o["id"], "type": o["type"],
               "class": td.get("class") or td.get("xml") or o["type"],
               "layer": td.get("layer", ""), "name": o["name"],
               "description": o.get("description", ""), "status": o.get("status", ""),
               "owner": o.get("owner", ""), "ref": o.get("ref", ""),
               "parent": o.get("parent", ""), "category": o.get("category", ""),
               "doc": o.get("doc") or o.get("sad", "")}
        for k in prop_keys:
            row[k] = (o.get("properties") or {}).get(k, "")
        objects.append(row)
    relationships = []
    for i, r in enumerate(model["relationships"]):
        rd = mm.relationships.get(r["type"], {})
        relationships.append({
            "id": relationship_id(r, i), "from": r["from"], "fromName": byid[r["from"]]["name"],
            "fromType": byid[r["from"]]["type"], "relationship": r["type"],
            "class": rd.get("xml") or rd.get("essential") or r["type"],
            "to": r["to"], "toName": byid[r["to"]]["name"], "toType": byid[r["to"]]["type"],
            "name": r.get("name", ""), "note": r.get("note", ""),
            "crud": r.get("crud", ""), "access": r.get("access", "")})
    return objects, relationships


def write_catalogue(model, outdir, stem=None):
    """Write <stem>.objects.csv and <stem>.relationships.csv. Returns paths."""
    os.makedirs(outdir, exist_ok=True)
    stem = stem or re.sub(r"[^A-Za-z0-9]+", "-", model.get("name", "model")).strip("-").lower() or "model"
    objects, rels = catalogue_rows(model)
    paths = []
    for name, rows in (("objects", objects), ("relationships", rels)):
        p = os.path.join(outdir, f"{stem}.{name}.csv")
        with open(p, "w", newline="") as f:
            if rows:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
        paths.append(p)
    return paths
