#!/usr/bin/env python3
"""arch-diagram EA command line.

  ea.py validate MODEL                      check a model against its metamodel
  ea.py rules METAMODEL SOURCE_TYPE TARGET_TYPE
                                            relationships allowed between two types
                                            (METAMODEL: archimate togaf essential coreea bpmn)
  ea.py types METAMODEL                     element types (with id prefixes)
  ea.py viewpoints METAMODEL [NAME]         viewpoints / artifacts and their types
  ea.py export MODEL --format csv|archimate|bpmn [--out DIR]
                                            catalogue CSVs, ArchiMate exchange XML
                                            (no diagrams; views export from their
                                            scripts), BPMN 2.0 XML
  ea.py orbus discover [--model MODEL] [--map-out FILE] [--ledger FILE]
  ea.py orbus plan MODEL --map FILE [--ledger FILE] [--out FILE]
  ea.py orbus push PAYLOAD --map FILE --ledger FILE
                                            OrbusInfinity import (ORBUS_TOKEN, ORBUS_API_URL)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ealib import ModelError, load_metamodel, load_model, validate, write_catalogue  # noqa: E402


def _stem(model):
    import re
    return re.sub(r"[^A-Za-z0-9]+", "-", model.get("name", "model")).strip("-").lower() or "model"


def cmd_validate(a):
    try:
        res = validate(load_model(a.model))
    except ModelError as e:
        sys.exit(str(e))
    for w in res.pop("warnings", []):
        print("warning:", w)
    print(json.dumps(res))


def cmd_rules(a):
    mm = load_metamodel(a.metamodel)
    for t in (a.source, a.target):
        if t not in mm.types:
            sys.exit(f"{mm.name} has no type '{t}'")
    verbs = mm.allowed_verbs(a.source, a.target)
    print(f"{a.source} -> {a.target}: " + (", ".join(verbs) if verbs else "no relationship allowed"))


def cmd_types(a):
    mm = load_metamodel(a.metamodel)
    for t, d in mm.types.items():
        print(f"{d.get('layer', ''):<15} {t:<32} {d.get('prefix', '') or ''}")


def cmd_viewpoints(a):
    mm = load_metamodel(a.metamodel)
    for name, vp in mm.viewpoints.items():
        if a.name and name != a.name:
            continue
        kind = vp.get("kind") or vp.get("category", "")
        print(f"{name}  [{kind}]  {vp.get('purpose', '')}")
        if a.name:
            print("  types: " + ", ".join(vp["types"]))


def cmd_export(a):
    model = load_model(a.model)
    try:
        validate(model)
    except ModelError as e:
        sys.exit(str(e))
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.model)), "out")
    if a.format == "csv":
        for p in write_catalogue(model, out):
            print(p)
    elif a.format == "archimate":
        from ealib.exchange import write_archimate_xml
        print(write_archimate_xml(model, os.path.join(out, _stem(model) + ".xml")))
    elif a.format == "bpmn":
        from ealib.bpmn import write_bpmn_xml
        print(write_bpmn_xml(model, os.path.join(out, _stem(model) + ".bpmn")))


def _client(mapping):
    from ealib.orbus import Client
    return Client(os.environ.get("ORBUS_API_URL") or mapping.get("apiUrl"), os.environ.get("ORBUS_TOKEN"))


def cmd_orbus(a):
    from ealib import orbus
    try:
        if a.action == "discover":
            mapping = {}
            if a.map and os.path.exists(a.map):
                with open(a.map) as f:
                    mapping = json.load(f)
            model = load_model(a.model) if a.model else None
            found = orbus.discover(_client(mapping), model)
            print(f"{len(found['objectTypes'])} object types, {len(found['relationshipTypes'])} "
                  f"relationship types, {len(found['objects'])} objects read")
            if a.map_out and model is not None:
                with open(a.map_out, "w") as f:
                    json.dump(found["draft"], f, indent=1)
                missing = [k for k, v in list(found["draft"]["objectTypes"].items())
                           + list(found["draft"]["relationshipTypes"].items()) if not v]
                print(f"draft mapping: {a.map_out}" + (f" ({len(missing)} types to fill in: "
                                                      + ", ".join(missing) + ")" if missing else ""))
            if a.types_out:
                with open(a.types_out, "w") as f:
                    json.dump({k: found[k] for k in ("objectTypes", "relationshipTypes", "models")}, f, indent=1)
                print(f"tenant types: {a.types_out}")
            if a.ledger and model is not None:
                with open(a.map_out or a.map) as f:
                    mp = json.load(f)
                led = orbus.seed_ledger(model, mp, found["objects"], a.ledger)
                print(f"ledger: {len(led['objects'])} model objects matched to existing Orbus objects")
        elif a.action == "plan":
            with open(a.map) as f:
                mapping = json.load(f)
            model = load_model(a.model)
            payload = orbus.plan(model, mapping, orbus.load_ledger(a.ledger))
            out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.model)), "out",
                                        _stem(model) + ".orbus.json")
            orbus.write_plan(payload, out)
            print(f"{out}: {payload['counts']['create']} to create, {payload['counts']['update']} to update")
        elif a.action == "push":
            with open(a.payload) as f:
                payload = json.load(f)
            with open(a.map) as f:
                mapping = json.load(f)
            res = orbus.push(payload, _client(mapping), a.ledger)
            print(json.dumps(res))
    except (ModelError, orbus.OrbusError) as e:
        sys.exit(str(e))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("validate"); s.add_argument("model"); s.set_defaults(fn=cmd_validate)
    s = sp.add_parser("rules"); s.add_argument("metamodel"); s.add_argument("source"); s.add_argument("target")
    s.set_defaults(fn=cmd_rules)
    s = sp.add_parser("types"); s.add_argument("metamodel"); s.set_defaults(fn=cmd_types)
    s = sp.add_parser("viewpoints"); s.add_argument("metamodel"); s.add_argument("name", nargs="?")
    s.set_defaults(fn=cmd_viewpoints)
    s = sp.add_parser("export"); s.add_argument("model")
    s.add_argument("--format", required=True, choices=["csv", "archimate", "bpmn"]); s.add_argument("--out")
    s.set_defaults(fn=cmd_export)
    s = sp.add_parser("orbus"); o = s.add_subparsers(dest="action", required=True)
    d = o.add_parser("discover"); d.add_argument("--model"); d.add_argument("--map")
    d.add_argument("--map-out"); d.add_argument("--types-out"); d.add_argument("--ledger")
    d = o.add_parser("plan"); d.add_argument("model"); d.add_argument("--map", required=True)
    d.add_argument("--ledger"); d.add_argument("--out")
    d = o.add_parser("push"); d.add_argument("payload"); d.add_argument("--map", required=True)
    d.add_argument("--ledger", required=True)
    s.set_defaults(fn=cmd_orbus)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
