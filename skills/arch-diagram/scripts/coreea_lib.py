"""CoreEA notation helper for arch-diagram.

Draws CoreEA views (OrbusInfinity-style enterprise-architecture viewpoints)
as print-grade SVG in the house design system. Every view is drawn from ONE
object model (objects + relationships, see model_schema.json), so the same
object has the same id, name and type in every view and the model exports
as a catalogue.

    from coreea_lib import load_model, validate, View
    model = load_model("model.json")
    validate(model)                      # raises ModelError listing every problem
    v = View(model, "V1")
    a = v.node("APP-01", 16, 16, 180)
    ...
    v.legend(y); v.save(height, outdir)  # writes V1.svg / V1.html / V1.png

Notation (see references/coreea.md):
- node: rect r4, layer stroke/fill; type label top-left (7.5px small caps,
  700, letter-spacing 0.6, layer colour); name centred (10.5px 600 ink);
  optional sub-line (8.5px muted); id bottom-right (7px).
- not-built objects (status Proposed / Designed / Not started) are dashed.
- edge: 1.2px body colour, canonical arrowhead, verb label 8.5px italic.
- legend lists only the types drawn, plus "dashed" when used; key_line()
  states what nesting means in this view.

The View refuses to draw an object that is not in the model, and an edge
whose (from, verb, to) triple is not a model relationship (or a `parent`
link when verb == "parent").
"""
import copy
import json
import os
import subprocess
from xml.sax.saxutils import escape

import shutil

# Headless Chrome renders the PNGs. Set CHROME_PATH to override the lookup.
def _find_chrome():
    if os.environ.get("CHROME_PATH"):
        return os.environ["CHROME_PATH"]
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.exists(mac):
        return mac
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return mac


CHROME = _find_chrome()

# ---------------------------------------------------------------- metamodel

TYPE_PREFIX = {
    "Driver": "DRV", "Goal": "GOL", "Objective": "OBJ", "Requirement": "REQ",
    "Principle": "PRN", "Capability": "CAP", "Value Stream": "VST",
    "Process": "PRC", "Organization": "ORG", "Actor": "ACT", "Role": "ROL",
    "Application": "APP", "Application Category": "APC", "Interface": "INT",
    "Data Entity": "DAT", "Data Category": "DTC", "Technology": "TEC",
    "Technology Category": "TCC", "Location": "LOC", "Project": "PRJ",
    "Risk": "RSK", "Control": "CTL",
}

TYPE_LAYER = {}
for _t in ["Driver", "Goal", "Objective", "Requirement", "Principle"]:
    TYPE_LAYER[_t] = "Motivation"
for _t in ["Capability", "Value Stream", "Process", "Organization", "Actor", "Role"]:
    TYPE_LAYER[_t] = "Business"
for _t in ["Application", "Application Category", "Interface"]:
    TYPE_LAYER[_t] = "Application"
for _t in ["Data Entity", "Data Category"]:
    TYPE_LAYER[_t] = "Data"
for _t in ["Technology", "Technology Category", "Location"]:
    TYPE_LAYER[_t] = "Technology"
TYPE_LAYER.update({"Risk": "Risk", "Control": "Control", "Project": "Project"})

# Legend order follows the metamodel.
TYPE_ORDER = [
    "Driver", "Goal", "Objective", "Requirement", "Principle",
    "Capability", "Value Stream", "Process", "Organization", "Actor", "Role",
    "Application", "Application Category", "Interface",
    "Data Entity", "Data Category",
    "Technology", "Technology Category", "Location",
    "Risk", "Control", "Project",
]

_APP_TEC = ["Application", "Technology"]
# verb -> (allowed source types, allowed target types)
VERBS = {
    "realises": (["Application", "Control"], ["Capability", "Requirement"]),
    "supports": (["Capability", "Application"], ["Objective", "Process"]),
    "motivates": (["Driver"], ["Goal"]),
    "achieved by": (["Goal"], ["Objective"]),
    "owns": (["Organization"], ["Application", "Data Entity", "Technology"]),
    "performs": (["Role"], ["Process"]),
    "assigned to": (["Actor"], ["Role"]),
    "uses": (["Actor", "Role", "Application"], ["Application", "Interface"]),
    "exposes": (["Application"], ["Interface"]),
    "consumes": (["Application"], ["Interface"]),
    "reads": (["Application"], ["Data Entity"]),
    "writes": (["Application"], ["Data Entity"]),
    "relates to": (["Data Entity"], ["Data Entity"]),
    "classified as": (["Data Entity"], ["Data Category"]),
    "hosted on": (["Application"], ["Technology"]),
    "located in": (["Technology"], ["Location"]),
    "categorised as": (["Application", "Technology"],
                       ["Application Category", "Technology Category"]),
    "satisfies": (_APP_TEC, ["Requirement"]),
    "constrains": (["Principle"], _APP_TEC),
    "mitigates": (["Control"], ["Risk"]),
    "applies to": (["Control"], ["Application", "Data Entity", "Technology", "Interface"]),
    "threatens": (["Risk"], ["Application", "Data Entity"]),
    "delivers": (["Project"], _APP_TEC),
    "depends on": (_APP_TEC, _APP_TEC),
    "supported by": (["Application"], ["Organization", "Role"]),
}
# Pairings narrower than the cross product above.
VERB_PAIRS = {
    "realises": {("Application", "Capability"), ("Control", "Requirement")},
    "supports": {("Capability", "Objective"), ("Application", "Process")},
    "categorised as": {("Application", "Application Category"),
                       ("Technology", "Technology Category")},
}

STATUSES = {"Built", "Built in UAT", "Designed", "Proposed", "Not started", "Retired"}
NOT_BUILT = {"Proposed", "Designed", "Not started"}

# ---------------------------------------------------------------- theme

DEFAULT_THEME = {
    "font": "-apple-system, 'Helvetica Neue', Arial, sans-serif",
    "width": 740,
    "ink": "#0f172a",      # names
    "body": "#475569",     # edges, legend text
    "muted": "#64748b",    # sub-lines, verb labels
    "id": "#94a3b8",       # object ids
    "rule": "#e2e8f0",     # legend divider
    "paper": "#ffffff",
    "tag": ("#b4443c", "#fbeeed"),
    "layers": {            # layer -> (stroke, fill)
        "Motivation": ("#734c74", "#f4eef4"),
        "Business": ("#b46a12", "#fdf3e6"),
        "Application": ("#3f7f8c", "#eef6f8"),
        "Data": ("#3b6a8f", "#edf3f8"),
        "Technology": ("#4f7d3a", "#eff5ea"),
        "Risk": ("#b4443c", "#fbeeed"),
        "Control": ("#475569", "#f1f5f9"),
        "Project": ("#64748b", "#f8fafc"),
    },
}


def make_theme(**overrides):
    """Copy of DEFAULT_THEME with overrides; `layers` merges per layer."""
    t = copy.deepcopy(DEFAULT_THEME)
    layers = overrides.pop("layers", None)
    t.update(overrides)
    if layers:
        t["layers"].update(layers)
    return t


# ---------------------------------------------------------------- model

class ModelError(ValueError):
    pass


def load_model(path):
    with open(path) as f:
        return json.load(f)


def validate(model, extra_verbs=None, strict_prefix=True):
    """Check the model; raise ModelError listing every problem, else return
    a summary dict. `extra_verbs` adds {verb: (sources, targets)} for a
    project that has agreed further verbs with its architecture office."""
    verbs = dict(VERBS)
    verbs.update(extra_verbs or {})
    errs = []
    objs = model.get("objects")
    rels = model.get("relationships")
    if not isinstance(objs, list) or not isinstance(rels, list):
        raise ModelError("model needs 'objects' and 'relationships' arrays")
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
        if t not in TYPE_PREFIX:
            errs.append(f"{where}: unknown type '{t}'")
        elif strict_prefix and not oid.startswith(TYPE_PREFIX[t] + "-"):
            errs.append(f"{where}: type {t} needs an id starting '{TYPE_PREFIX[t]}-'")
        st = o.get("status")
        if st is not None and st not in STATUSES:
            errs.append(f"{where}: status '{st}' not one of {sorted(STATUSES)}")
    for o in objs:
        p = o.get("parent")
        if p is None:
            continue
        if p not in byid:
            errs.append(f"{o.get('id')}: parent {p} is not in the model")
        elif byid[p].get("type") != o.get("type"):
            errs.append(f"{o.get('id')}: parent {p} is a {byid[p].get('type')}, "
                        f"parent links join objects of one type")
    # parent cycles
    for o in objs:
        seen, cur = set(), o.get("id")
        while cur in byid and byid[cur].get("parent"):
            if cur in seen:
                errs.append(f"{o.get('id')}: parent chain loops")
                break
            seen.add(cur)
            cur = byid[cur]["parent"]
    seen_rel = set()
    for i, r in enumerate(rels):
        f, v, t = r.get("from"), r.get("type"), r.get("to")
        where = f"relationships[{i}] {f} -{v}-> {t}"
        if (f, v, t) in seen_rel:
            errs.append(f"{where}: duplicate")
        seen_rel.add((f, v, t))
        if f not in byid:
            errs.append(f"{where}: source not in model")
        if t not in byid:
            errs.append(f"{where}: target not in model")
        if v not in verbs:
            errs.append(f"{where}: unknown verb (allowed: {', '.join(sorted(verbs))})")
            continue
        if f in byid and t in byid:
            ft, tt = byid[f]["type"], byid[t]["type"]
            src, tgt = verbs[v]
            pairs = VERB_PAIRS.get(v) if v not in (extra_verbs or {}) else None
            ok = (ft, tt) in pairs if pairs else (ft in src and tt in tgt)
            if not ok:
                errs.append(f"{where}: '{v}' does not join {ft} -> {tt}")
    if errs:
        raise ModelError(f"{len(errs)} model problem(s):\n  " + "\n  ".join(errs))
    return {"objects": len(objs), "relationships": len(rels)}


def catalogue_rows(model):
    """Flat rows for an OrbusInfinity / spreadsheet import: one per object,
    then one per relationship, names resolved."""
    byid = {o["id"]: o for o in model["objects"]}
    objects = [{"id": o["id"], "type": o["type"], "name": o["name"],
                "description": o.get("description", ""), "status": o.get("status", ""),
                "owner": o.get("owner", ""), "ref": o.get("ref", ""),
                "parent": o.get("parent", "")} for o in model["objects"]]
    relationships = [{"from": r["from"], "fromName": byid[r["from"]]["name"],
                      "relationship": r["type"], "to": r["to"],
                      "toName": byid[r["to"]]["name"], "note": r.get("note", "")}
                     for r in model["relationships"]]
    return objects, relationships


# ---------------------------------------------------------------- text

def esc(s):
    return escape(str(s), {'"': "&quot;"})


def text_width(s, size, bold=False):
    """Estimated rendered width of sans-serif text."""
    w = 0.0
    for ch in str(s):
        if ch in "il.,:;|!'·":
            f = 0.26
        elif ch in "fjrtI() -/":
            f = 0.34
        elif ch in "mwMW":
            f = 0.84
        elif ch.isupper() or ch.isdigit():
            f = 0.66
        else:
            f = 0.54
        w += f
    return w * size * (1.06 if bold else 1.0)


def wrap(s, size, maxw, bold=False):
    lines, cur = [], ""
    for word in str(s).split(" "):
        cand = (cur + " " + word).strip()
        if cur and text_width(cand, size, bold) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def _box(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h, "r": x + w, "b": y + h,
            "cx": x + w / 2, "cy": y + h / 2}


# ---------------------------------------------------------------- view

class View:
    NAME = 10.5
    SUB = 8.5
    PILL_H = 22

    def __init__(self, model, vid, theme=None, title=None):
        self.model = model
        self.obj = {o["id"]: o for o in model["objects"]}
        self.rels = model["relationships"]
        self.vid = vid
        self.title = title or vid
        self.t = theme or DEFAULT_THEME
        self.W = self.t["width"]
        self.parts, self.drawn, self.types = [], [], set()
        self.used_dashed = False
        self.marker = "arr-" + "".join(c for c in vid.lower() if c.isalnum())

    # ---- lookups
    def colours(self, otype):
        return self.t["layers"][TYPE_LAYER[otype]]

    def not_built(self, oid):
        return self.obj[oid].get("status") in NOT_BUILT

    def rel_exists(self, f, verb, to):
        if verb == "parent":
            return self.obj.get(f, {}).get("parent") == to
        return any(r["from"] == f and r["type"] == verb and r["to"] == to for r in self.rels)

    def related(self, frm=None, verb=None, to=None):
        return [r for r in self.rels
                if (frm is None or r["from"] == frm) and (verb is None or r["type"] == verb)
                and (to is None or r["to"] == to)]

    def children(self, oid):
        return [o["id"] for o in self.model["objects"] if o.get("parent") == oid]

    def _mark(self, oid):
        if oid not in self.obj:
            raise KeyError(f"{self.vid}: object {oid} is not in the model")
        if oid not in self.drawn:
            self.drawn.append(oid)
        self.types.add(self.obj[oid]["type"])

    # ---- primitives
    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, size=9, fill=None, anchor="start", weight=None,
             italic=False, spacing=None, halo=False):
        a = [f'x="{x:.1f}"', f'y="{y:.1f}"', f'font-size="{size}"',
             f'fill="{fill or self.t["muted"]}"']
        if anchor != "start":
            a.append(f'text-anchor="{anchor}"')
        if weight:
            a.append(f'font-weight="{weight}"')
        if italic:
            a.append('font-style="italic"')
        if spacing:
            a.append(f'letter-spacing="{spacing}"')
        if halo:
            a.append(f'stroke="{self.t["paper"]}" stroke-width="3" stroke-linejoin="round" '
                     'paint-order="stroke"')
        self.add(f'<text {" ".join(a)}>{esc(s)}</text>')

    def _rect(self, x, y, w, h, rx, fill, stroke, dashed, extra=""):
        dash = ' stroke-dasharray="4 3"' if dashed else ""
        if dashed:
            self.used_dashed = True
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
                 f'fill="{fill}"{extra} stroke="{stroke}" stroke-width="1.2"{dash}/>')

    def _subs(self, sub, w):
        if not sub:
            return []
        out = []
        for s in ([sub] if isinstance(sub, str) else sub):
            out.extend(wrap(s, self.SUB, w - 14))
        return out

    def _block_height(self, title, w, sub, name_size):
        n = len(wrap(title, name_size, w - 14, True))
        subs = self._subs(sub, w)
        return 24 + (n - 1) * (name_size + 2) + len(subs) * (self.SUB + 2.5) + (18 if subs else 12)

    def _centred_block(self, x, y, w, h, title, sub, name_size):
        names = wrap(title, name_size, w - 14, True)
        subs = self._subs(sub, w)
        block = (len(names) - 1) * (name_size + 2) + len(subs) * (self.SUB + 2.5)
        ty = y + 14 + max(0, (h - (32 if subs else 26) - block - name_size) / 2) + name_size - 1
        cx = x + w / 2
        for ln in names:
            self.text(cx, ty, ln, name_size, self.t["ink"], anchor="middle", weight=600)
            ty += name_size + 2
        ty += 0.5
        for ln in subs:
            self.text(cx, ty, ln, self.SUB, self.t["muted"], anchor="middle")
            ty += self.SUB + 2.5

    # ---- nodes
    def node_height(self, oid, w, sub=None, name_size=None):
        return self._block_height(self.obj[oid]["name"], w, sub, name_size or self.NAME)

    def node(self, oid, x, y, w, h=None, sub=None, dashed=None, name_size=None,
             type_label=None):
        """One model object as a box. Returns its box dict."""
        self._mark(oid)
        o = self.obj[oid]
        ns = name_size or self.NAME
        stroke, fill = self.colours(o["type"])
        if h is None:
            h = self.node_height(oid, w, sub, ns)
        self._rect(x, y, w, h, 4, fill, stroke, self.not_built(oid) if dashed is None else dashed)
        self.text(x + 6, y + 10, (type_label or o["type"]).upper(), 7.5, stroke,
                  weight=700, spacing=0.6)
        self._centred_block(x, y, w, h, o["name"], sub, ns)
        self.text(x + w - 5, y + h - 4, oid, 7, self.t["id"], anchor="end")
        return _box(x, y, w, h)

    def group_height(self, title, w, sub=None):
        return self._block_height(title, w, sub, self.NAME)

    def group(self, otype, title, members, x, y, w, h=None, sub=None, ids=None):
        """One box standing for several objects of one type: type label
        carries the count (REQUIREMENT ×7), the id slot lists the ids.
        Dashed only when every member is not built."""
        if not members:
            raise ValueError(f"{self.vid}: group '{title}' has no members")
        for m in members:
            self._mark(m)
            if self.obj[m]["type"] != otype:
                raise ValueError(f"{self.vid}: {m} is a {self.obj[m]['type']}, not a {otype}")
        stroke, fill = self.colours(otype)
        if h is None:
            h = self.group_height(title, w, sub)
        self._rect(x, y, w, h, 4, fill, stroke, all(self.not_built(m) for m in members))
        self.text(x + 6, y + 10, f"{otype.upper()} ×{len(members)}", 7.5, stroke,
                  weight=700, spacing=0.6)
        self._centred_block(x, y, w, h, title, sub, self.NAME)
        label = ids or (members[0] if len(members) == 1 else f"{members[0]}–{members[-1]}")
        self.text(x + w - 5, y + h - 4, label, 7, self.t["id"], anchor="end")
        return _box(x, y, w, h)

    def container_header(self, oid, w, name_size=None):
        """(height, lines) taken by a container's type label and name."""
        ns = name_size or self.NAME
        lines = wrap(self.obj[oid]["name"], ns, w - 16, True)
        return 16 + len(lines) * (ns + 2.5) + 2, lines

    def container(self, oid, x, y, w, h, sub=None, name_size=None, fill_opacity=0.45):
        """A model object drawn as a box holding other objects (children by
        parent, members of a category, technology in a location). Returns
        (box, content_top)."""
        self._mark(oid)
        o = self.obj[oid]
        ns = name_size or self.NAME
        stroke, fill = self.colours(o["type"])
        self._rect(x, y, w, h, 5, fill, stroke, self.not_built(oid),
                   extra=f' fill-opacity="{fill_opacity}"')
        self.text(x + 7, y + 11, o["type"].upper(), 7.5, stroke, weight=700, spacing=0.6)
        self.text(x + w - 6, y + 11, oid, 7, self.t["id"], anchor="end")
        hh, lines = self.container_header(oid, w, ns)
        ty = y + 14 + ns
        for ln in lines:
            self.text(x + 7, ty, ln, ns, self.t["ink"], weight=600)
            ty += ns + 2.5
        top = y + hh
        for ln in (wrap(sub, self.SUB, w - 14) if sub else []):
            self.text(x + 7, ty - 1, ln, self.SUB, self.t["muted"])
            ty += 11
            top += 11
        return _box(x, y, w, h), top

    def frame(self, x, y, w, h, label, colour=None, dashed=False):
        """A plain visual grouping (not a model object): thin frame and an
        UPPERCASE label. Use for 'External', 'No category in the model'."""
        colour = colour or self.t["muted"]
        dash = ' stroke-dasharray="4 3"' if dashed else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="6" '
                 f'fill="none" stroke="{colour}" stroke-width="1"{dash}/>')
        self.text(x + 8, y + 13, label.upper(), 8, colour, weight=700, spacing=0.5)
        return _box(x, y, w, h)

    def pill_height(self, oid, w):
        return self.PILL_H if self._pill_fits(oid, w) else self.PILL_H + 10

    def _pill_fits(self, oid, w):
        idw = text_width(oid, 7) + 4
        return text_width(self.obj[oid]["name"], 7.75, True) * 1.08 <= w - 18 - idw

    def pill_width(self, oid):
        return text_width(self.obj[oid]["name"], 8.5, True) + text_width(oid, 7) + 26

    def pill(self, oid, x, y, w=None):
        """An Interface as a pill (r11) at top-left (x, y): on the edge of the
        application that exposes it, or inside it. Name and id on one line
        when they fit, else id drops to a second line."""
        self._mark(oid)
        o = self.obj[oid]
        if o["type"] != "Interface":
            raise ValueError(f"{self.vid}: pill() is for Interfaces, {oid} is a {o['type']}")
        stroke, _ = self.colours("Interface")
        w = w or self.pill_width(oid)
        h = self.pill_height(oid, w)
        self._rect(x, y, w, h, 11, self.t["paper"], stroke, self.not_built(oid))
        size = 8.5
        if h == self.PILL_H:
            idw = text_width(oid, 7) + 4
            while text_width(o["name"], size, True) * 1.08 > w - 18 - idw and size > 7.75:
                size -= 0.25
            self.text(x + 9, y + 14.5, o["name"], size, self.t["ink"], weight=600)
            self.text(x + w - 9, y + 14.5, oid, 7, self.t["id"], anchor="end")
        else:
            while text_width(o["name"], size, True) * 1.1 > w - 26 and size > 7.25:
                size -= 0.25
            self.text(x + 9, y + 13, o["name"], size, self.t["ink"], weight=600)
            self.text(x + w - 10, y + 25, oid, 7, self.t["id"], anchor="end")
        return _box(x, y, w, h)

    def tag(self, x, y, s, anchor="start"):
        """Small status tag (e.g. NOT BUILT). An annotation, not an object."""
        stroke, fill = self.t["tag"]
        w = text_width(s, 7.5, True) + 10 + len(s) * 0.4
        x = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="14" rx="7" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="1" stroke-dasharray="3 2"/>')
        self.text(x + w / 2, y + 10, s, 7.5, stroke, anchor="middle", weight=700, spacing=0.4)
        return w

    # ---- edges
    def edge(self, points, verb, label=None, check=None, dashed=False,
             label_anchor="middle", arrow=True, label_text=None):
        """Orthogonal edge through `points` (stop 2px short of the target).
        `check` lists the (from, verb, to) triples the edge stands for; each
        must be in the model. `label` is the (x, y) of the verb label."""
        for (f, v, t) in (check or []):
            if not self.rel_exists(f, v, t):
                raise ValueError(f"{self.vid}: relationship {f} -{v}-> {t} not in the model")
        pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in points)
        dash = ' stroke-dasharray="4 3"' if dashed else ""
        mk = f' marker-end="url(#{self.marker})"' if arrow else ""
        self.add(f'<polyline points="{pts}" fill="none" stroke="{self.t["body"]}" '
                 f'stroke-width="1.2"{dash}{mk}/>')
        if label is not None:
            self.text(label[0], label[1], label_text or verb, self.SUB, self.t["muted"],
                      anchor=label_anchor, italic=True, halo=True)

    # ---- legend and key
    def legend(self, y):
        """Legend row: only the types drawn, plus dashed meaning when used.
        Returns the y below it."""
        W = self.W
        self.add(f'<line x1="16" y1="{y:.1f}" x2="{W - 16}" y2="{y:.1f}" '
                 f'stroke="{self.t["rule"]}" stroke-width="1"/>')
        y += 12
        x = 16
        entries = [("type", t) for t in TYPE_ORDER if t in self.types]
        if self.used_dashed:
            entries.append(("dashed", "Proposed / designed / not started"))
        for kind, label in entries:
            lw = text_width(label, 8.5) + 26
            if x + lw > W - 16:
                x, y = 16, y + 18
            if kind == "type":
                stroke, fill = self.colours(label)
                self.add(f'<rect x="{x}" y="{y:.1f}" width="16" height="10" rx="2" '
                         f'fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
            else:
                self.add(f'<rect x="{x}" y="{y:.1f}" width="16" height="10" rx="2" '
                         f'fill="{self.t["paper"]}" stroke="{self.t["body"]}" '
                         f'stroke-width="1.2" stroke-dasharray="3 2"/>')
            self.text(x + 21, y + 8.5, label, 8.5, self.t["body"])
            x += lw + 10
        return y + 18

    def key_line(self, y, notes):
        """Plain-text key under the legend saying what nesting / pills mean
        in this view. Returns the y below it."""
        x = 16
        for n in notes:
            tw = text_width(n, 8.5)
            if x + tw > self.W - 16:
                x, y = 16, y + 14
            self.text(x, y + 8.5, n, 8.5, self.t["body"])
            x += tw + 18
        return y + 18

    # ---- output
    def svg(self, height):
        W, b = self.W, self.t["body"]
        defs = (f'<defs><marker id="{self.marker}" viewBox="0 0 10 10" refX="9" refY="5" '
                f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                f'<path d="M 0 1 L 9 5 L 0 9 z" fill="{b}"/></marker></defs>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height:.0f}" '
                f'font-family="{esc(self.t["font"])}">\n'
                f'<title>{esc(self.title)}</title>\n'
                f'<rect x="0" y="0" width="{W}" height="{height:.0f}" fill="{self.t["paper"]}"/>\n'
                f'{defs}\n' + "\n".join(self.parts) + "\n</svg>\n")

    def save(self, height, outdir, render=True, scale=2):
        """Write <vid>.svg, <vid>.html, <vid>.objects.json (ids drawn, for
        traceability back to the catalogue) and, with render, <vid>.png via
        headless Chrome. Returns the paths written."""
        height = int(round(height))
        os.makedirs(outdir, exist_ok=True)
        base = os.path.join(os.path.abspath(outdir), self.vid)
        svg = self.svg(height)
        with open(base + ".svg", "w") as f:
            f.write(svg)
        with open(base + ".html", "w") as f:
            f.write('<!doctype html>\n<html><head><meta charset="utf-8">'
                    f'<title>{esc(self.title)}</title><style>html,body{{margin:0;padding:0;'
                    f'background:{self.t["paper"]}}}svg{{display:block;width:{self.W}px;'
                    'height:auto}</style></head>\n<body>\n' + svg + '</body></html>\n')
        with open(base + ".objects.json", "w") as f:
            json.dump(self.drawn, f, indent=1)
            f.write("\n")
        out = [base + ".svg", base + ".html", base + ".objects.json"]
        if render:
            subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                            f"--force-device-scale-factor={scale}", "--virtual-time-budget=3000",
                            f"--window-size={self.W},{height}",
                            f"--screenshot={base}.png", f"file://{base}.html"],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            out.append(base + ".png")
        return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        sys.exit("usage: python3 coreea_lib.py model.json   # validate a model")
    try:
        print(validate(load_model(sys.argv[1])))
    except ModelError as e:
        sys.exit(str(e))
