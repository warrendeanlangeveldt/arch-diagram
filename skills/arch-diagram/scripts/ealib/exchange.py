"""ArchiMate Model Exchange File Format (The Open Group, 3.1 schema, used by
ArchiMate 3.2 tools): the model's elements, relationships and properties,
plus every View passed in as a diagram with its node positions, nesting and
bendpoints. Archi, Sparx EA, BiZZdesign, BOC ADOIT, MEGA and other
ArchiMate tools import it.

    from ealib.exchange import write_archimate_xml
    write_archimate_xml(model, "out/model.xml", views=[v1, v2])
"""
import os
import re
import shutil
import subprocess
from xml.sax.saxutils import escape, quoteattr

from .metamodel import ModelError, metamodel_of, relationship_id, validate

NS = "http://www.opengroup.org/xsd/archimate/3.0/"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA = "http://www.opengroup.org/xsd/archimate/3.1/archimate3_Diagram.xsd"
FIELDS = [("status", "Status"), ("owner", "Owner"), ("ref", "Source reference"),
          ("category", "Category"), ("doc", "Document section"), ("sad", "SAD section")]


def _txt(tag, s, lang, ind):
    return f'{ind}<{tag} xml:lang="{lang}">{escape(str(s))}</{tag}>\n'


def _pid(key):
    return "pd-" + re.sub(r"[^A-Za-z0-9_.-]", "_", key)


def _contains(outer, inner):
    return (outer["x"] <= inner["x"] + 0.5 and outer["y"] <= inner["y"] + 0.5
            and outer["r"] >= inner["r"] - 0.5 and outer["b"] >= inner["b"] - 0.5)


def _view_xml(view, rel_ids, lang, out, ind="      "):
    placed = view.placed
    parent = {}
    for oid, (bx, _) in placed.items():
        best = None
        for cid, (cb, kind) in placed.items():
            if cid == oid or kind != "container" or not _contains(cb, bx):
                continue
            if best is None or cb["w"] * cb["h"] < placed[best][0]["w"] * placed[best][0]["h"]:
                best = cid
        parent[oid] = best
    nid = {oid: f"n-{view.slug}-{oid}" for oid in placed}
    vp = view.viewpoint
    vpa = f' viewpoint={quoteattr(vp)}' if vp else ""
    out.append(f'{ind}<view identifier="v-{view.slug}" xsi:type="Diagram"{vpa}>\n')
    out.append(_txt("name", view.title, lang, ind + "  "))

    def emit(oid, depth):
        bx, _ = placed[oid]
        pad = ind + "  " * (depth + 1)
        x, y = max(0, int(round(bx["x"]))), max(0, int(round(bx["y"])))
        w, h = max(1, int(round(bx["w"]))), max(1, int(round(bx["h"])))
        kids = [k for k in placed if parent[k] == oid]
        head = (f'{pad}<node identifier="{nid[oid]}" elementRef="{oid}" xsi:type="Element" '
                f'x="{x}" y="{y}" w="{w}" h="{h}"')
        if not kids:
            out.append(head + "/>\n")
            return
        out.append(head + ">\n")
        for k in kids:
            emit(k, depth + 1)
        out.append(f"{pad}</node>\n")

    for oid in placed:
        if parent[oid] is None:
            emit(oid, 0)
    for n, (ri, pts) in enumerate(view.edges):
        r = view.rels[ri]
        if r["from"] not in nid or r["to"] not in nid:
            continue
        pad = ind + "  "
        out.append(f'{pad}<connection identifier="c-{view.slug}-{n}" relationshipRef="{rel_ids[ri]}" '
                   f'xsi:type="Relationship" source="{nid[r["from"]]}" target="{nid[r["to"]]}"')
        bends = pts[1:-1]
        if not bends:
            out.append("/>\n")
            continue
        out.append(">\n")
        for bx, by in bends:
            out.append(f'{pad}  <bendpoint x="{max(0, int(round(bx)))}" y="{max(0, int(round(by)))}"/>\n')
        out.append(f"{pad}</connection>\n")
    out.append(f"{ind}</view>\n")


def to_archimate_xml(model, views=(), lang="en"):
    """The model (and views) as an ArchiMate exchange document (str)."""
    mm = metamodel_of(model)
    if mm.key != "archimate":
        raise ModelError(f"the ArchiMate exchange format needs an ArchiMate model, not {mm.name}")
    validate(model)
    for v in views:
        if v.model is not model and v.model.get("objects") != model.get("objects"):
            raise ModelError(f"view {v.vid} was drawn from a different model")
    keys = [k for k, _ in FIELDS if any(o.get(k) for o in model["objects"])]
    extra = sorted({k for o in model["objects"] for k in (o.get("properties") or {})})
    labels = dict(FIELDS)
    out = ['<?xml version="1.0" encoding="UTF-8"?>\n',
           f'<model xmlns="{NS}" xmlns:xsi="{XSI}" xsi:schemaLocation="{NS} {SCHEMA}" '
           f'identifier="id-{re.sub(r"[^A-Za-z0-9_.-]", "-", model.get("name", "model")).lower()}">\n',
           _txt("name", model.get("name", "Model"), lang, "  ")]
    if model.get("description"):
        out.append(_txt("documentation", model["description"], lang, "  "))
    out.append("  <elements>\n")
    for o in model["objects"]:
        t = mm.types[o["type"]]["xml"]
        out.append(f'    <element identifier="{o["id"]}" xsi:type="{t}">\n')
        if mm.types[o["type"]]["aspect"] != "junction":
            out.append(_txt("name", o["name"], lang, "      "))
        if o.get("description"):
            out.append(_txt("documentation", o["description"], lang, "      "))
        props = [(k, o[k]) for k in keys if o.get(k)] + \
                [(k, v) for k, v in sorted((o.get("properties") or {}).items()) if v not in (None, "")]
        if props:
            out.append("      <properties>\n")
            for k, v in props:
                out.append(f'        <property propertyDefinitionRef="{_pid(k)}">\n'
                           + _txt("value", v, lang, "          ") + "        </property>\n")
            out.append("      </properties>\n")
        out.append("    </element>\n")
    out.append("  </elements>\n")
    rel_ids = [relationship_id(r) for r in model["relationships"]]
    if model["relationships"]:
        out.append("  <relationships>\n")
        for r, rid in zip(model["relationships"], rel_ids):
            a = [f'identifier="{rid}"', f'source="{r["from"]}"', f'target="{r["to"]}"',
                 f'xsi:type="{mm.relationships[r["type"]]["xml"]}"']
            if r["type"] == "access":
                a.append('accessType="%s"' % {"read": "Read", "write": "Write", "readwrite": "ReadWrite",
                                             "access": "Access"}[r.get("access", "write")])
            if r["type"] == "influence" and r.get("modifier"):
                a.append(f'modifier={quoteattr(str(r["modifier"]))}')
            if r["type"] == "association" and r.get("directed"):
                a.append('isDirected="true"')
            body = ""
            if r.get("name"):
                body += _txt("name", r["name"], lang, "      ")
            if r.get("note"):
                body += _txt("documentation", r["note"], lang, "      ")
            out.append(f'    <relationship {" ".join(a)}' + (f">\n{body}    </relationship>\n" if body else "/>\n"))
        out.append("  </relationships>\n")
    if keys or extra:
        out.append("  <propertyDefinitions>\n")
        for k in keys + extra:
            out.append(f'    <propertyDefinition identifier="{_pid(k)}" type="string">\n'
                       + _txt("name", labels.get(k, k), lang, "      ") + "    </propertyDefinition>\n")
        out.append("  </propertyDefinitions>\n")
    if views:
        out.append("  <views>\n    <diagrams>\n")
        for v in views:
            _view_xml(v, rel_ids, lang, out)
        out.append("    </diagrams>\n  </views>\n")
    out.append("</model>\n")
    return "".join(out)


def write_archimate_xml(model, path, views=(), lang="en"):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_archimate_xml(model, views, lang))
    return path


def xsd_check(xml_path, xsd_path):
    """Validate with xmllint against a local copy of the schema. Returns
    (ok, message); (None, reason) when xmllint is not installed."""
    if not shutil.which("xmllint"):
        return None, "xmllint not installed"
    p = subprocess.run(["xmllint", "--noout", "--nonet", "--schema", xsd_path, xml_path],
                       capture_output=True, text=True)
    return p.returncode == 0, (p.stderr or p.stdout).strip()
