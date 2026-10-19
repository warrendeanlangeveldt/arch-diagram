"""Views drawn from one validated model.

    from ealib import load_model, validate, View
    model = load_model("model.json"); validate(model)
    v = View(model, "V1", title="…", viewpoint="Application Cooperation")
    a = v.node("ACMP-01", 16, 16, 180)            # returns a box: x y w h r b cx cy
    v.edge([(a["r"], a["cy"]), (300, a["cy"])], "serving",
           check=[("ACMP-01", "serving", "ACMP-02")])
    y = v.legend(bottom + 20); y = v.key_line(y, ["…"]); v.save(y + 4, "out")

Notation follows the model's metamodel:
- archimate: ArchiMate 3.2 rectangle notation. Square corners for structure,
  rounded for behaviour, cut corners for motivation, header band on
  business/data objects; the type symbol sits top-right. Each relationship
  type has its own line and ends (composition diamond, realization dashed
  with hollow triangle, serving open arrow …) and the legend shows the ones
  drawn.
- box (TOGAF, Essential): the house EA box. Layer colour stroke and fill,
  type label top-left in small caps, name centred, id bottom-right; every
  edge is the canonical arrow with its verb as the label.

Both: objects whose status is Proposed / Designed / Not started are dashed;
the view refuses an object that is not in the model and an edge whose
(from, verb, to) is not a model relationship; the legend lists only what
was drawn.
"""
import copy
import sys

from . import archimate_icons
from .common import HOUSE, NOT_BUILT, Canvas, box, esc, text_width, wrap
from .metamodel import metamodel_of, relationship_id

DASH = {"solid": None, "dashed": "5 3", "dotted": "1.5 2.2", "dashed-long": "7 3"}

MARKERS = {
    "arrow-filled": ('viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7"',
                     '<path d="M 0 1 L 9 5 L 0 9 z" fill="{body}"/>'),
    "arrow-open": ('viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8"',
                   '<path d="M 1 1 L 9 5 L 1 9" fill="none" stroke="{body}" stroke-width="1.2"/>'),
    "arrow-open-small": ('viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6"',
                         '<path d="M 2 2 L 9 5 L 2 8" fill="none" stroke="{body}" stroke-width="1.4"/>'),
    "triangle-hollow": ('viewBox="0 0 12 12" refX="11" refY="6" markerWidth="10" markerHeight="10"',
                        '<path d="M 1 1 L 11 6 L 1 11 z" fill="{paper}" stroke="{body}" stroke-width="1"/>'),
    "diamond-filled": ('viewBox="0 0 14 10" refX="13" refY="5" markerWidth="11" markerHeight="8"',
                       '<path d="M 1 5 L 7 1 L 13 5 L 7 9 z" fill="{body}"/>'),
    "diamond-hollow": ('viewBox="0 0 14 10" refX="13" refY="5" markerWidth="11" markerHeight="8"',
                       '<path d="M 1 5 L 7 1 L 13 5 L 7 9 z" fill="{paper}" stroke="{body}" stroke-width="1"/>'),
    "dot": ('viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6"',
            '<circle cx="5" cy="5" r="3" fill="{body}"/>'),
}


def make_theme(base=None, **overrides):
    """Copy of the house theme with overrides. `layers` merges per layer:
    make_theme(layers={"Application": ("#1d4ed8", "#eff6ff")})."""
    t = copy.deepcopy(base or HOUSE)
    t.setdefault("layers", {})
    layers = overrides.pop("layers", None)
    t.update(overrides)
    if layers:
        t["layers"].update(layers)
    return t


class View(Canvas):
    NAME = 10.5
    SUB = 8.5
    PILL_H = 22

    def __init__(self, model, vid, title=None, viewpoint=None, theme=None, type_labels=None):
        self.mm = metamodel_of(model)
        if self.mm.key == "bpmn":
            raise ValueError("BPMN models are drawn with ealib.bpmn.BpmnView")
        super().__init__(vid, theme or make_theme(), title)
        self.model = model
        self.obj = {o["id"]: o for o in model["objects"]}
        self.rels = model["relationships"]
        self.archimate = self.mm.notation == "archimate"
        # ArchiMate identifies types by symbol; box notation prints the type.
        self.type_labels = (not self.archimate) if type_labels is None else type_labels
        self.viewpoint = viewpoint
        self.vp_types = set(self.mm.viewpoint(viewpoint)["types"]) if viewpoint else None
        self.drawn, self.types, self.rel_types = [], [], []
        self.placed = {}          # oid -> (box, kind) for exchange-format export
        self.edges = []           # (relationship index, points) for export
        self.warnings = []
        self.used_dashed = False
        self.marker = self.define("arr", self._marker_svg("arrow-filled"))

    # ---- lookups
    def colours(self, otype):
        return self.mm.colours(otype, self.t.get("layers"))

    def not_built(self, oid):
        return self.obj[oid].get("status") in NOT_BUILT

    def rel_index(self, f, verb, to):
        if verb == "parent":
            return -1 if self.obj.get(f, {}).get("parent") == to else None
        for i, r in enumerate(self.rels):
            if r["from"] == f and r["type"] == verb and r["to"] == to:
                return i
        return None

    def rel_exists(self, f, verb, to):
        return self.rel_index(f, verb, to) is not None

    def related(self, frm=None, verb=None, to=None):
        return [r for r in self.rels
                if (frm is None or r["from"] == frm) and (verb is None or r["type"] == verb)
                and (to is None or r["to"] == to)]

    def children(self, oid):
        return [o["id"] for o in self.model["objects"] if o.get("parent") == oid]

    def _mark(self, oid, bx=None, kind="node"):
        if oid not in self.obj:
            raise KeyError(f"{self.vid}: object {oid} is not in the model")
        if oid not in self.drawn:
            self.drawn.append(oid)
        t = self.obj[oid]["type"]
        if t not in self.types:
            self.types.append(t)
        if self.vp_types is not None and t not in self.vp_types:
            w = f"{self.vid}: {t} {oid} is outside the {self.viewpoint} viewpoint"
            if w not in self.warnings:
                self.warnings.append(w)
        if bx is not None:
            self.placed[oid] = (bx, kind)

    # ---- shapes
    def _dash(self, dashed):
        if dashed:
            self.used_dashed = True
            return ' stroke-dasharray="4 3"'
        return ""

    def _rect(self, x, y, w, h, rx, fill, stroke, dashed, extra=""):
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
                 f'fill="{fill}"{extra} stroke="{stroke}" stroke-width="1.2"{self._dash(dashed)}/>')

    def _shape(self, otype, x, y, w, h, fill, stroke, dashed, extra="", container=False):
        """Element outline in the metamodel's notation."""
        shape = self.mm.types[otype].get("shape", "rect") if self.archimate else "box"
        if shape == "round":
            self._rect(x, y, w, h, 7, fill, stroke, dashed, extra)
        elif shape == "cut":
            c = 6
            pts = (f"{x + c:.1f},{y:.1f} {x + w - c:.1f},{y:.1f} {x + w:.1f},{y + c:.1f} "
                   f"{x + w:.1f},{y + h - c:.1f} {x + w - c:.1f},{y + h:.1f} {x + c:.1f},{y + h:.1f} "
                   f"{x:.1f},{y + h - c:.1f} {x:.1f},{y + c:.1f}")
            self.add(f'<polygon points="{pts}" fill="{fill}"{extra} stroke="{stroke}" '
                     f'stroke-width="1.2"{self._dash(dashed)}/>')
        elif shape in ("object", "contract"):
            self._rect(x, y, w, h, 0, fill, stroke, dashed, extra)
            self.add(f'<line x1="{x:.1f}" y1="{y + 13:.1f}" x2="{x + w:.1f}" y2="{y + 13:.1f}" '
                     f'stroke="{stroke}" stroke-width="1"/>')
            if shape == "contract":
                self.add(f'<line x1="{x:.1f}" y1="{y + h - 9:.1f}" x2="{x + w:.1f}" '
                         f'y2="{y + h - 9:.1f}" stroke="{stroke}" stroke-width="1"/>')
        elif shape == "grouping":
            self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="none" '
                     f'stroke="{stroke}" stroke-width="1.2" stroke-dasharray="5 3"/>')
        elif shape == "box":
            self._rect(x, y, w, h, 5 if container else 4, fill, stroke, dashed, extra)
        else:
            self._rect(x, y, w, h, 0 if self.archimate else 4, fill, stroke, dashed, extra)

    def _symbol(self, otype, x, y, w):
        if not self.archimate:
            return
        kind = self.mm.types[otype].get("icon")
        if kind:
            stroke, _ = self.colours(otype)
            self.add(archimate_icons.icon(kind, x + w - 20, y + 4, stroke))

    def _platform_icon(self, ref, x, y, size, colour):
        from .icons import inline
        self.add(inline(ref, x, y, size, colour=colour))

    def _subs(self, sub, w):
        if not sub:
            return []
        out = []
        for s in ([sub] if isinstance(sub, str) else sub):
            out.extend(wrap(s, self.SUB, w - 14))
        return out

    def _block_height(self, title, w, sub, name_size, icon=False):
        n = len(wrap(title, name_size, w - 14 - (30 if icon else 0), True))
        subs = self._subs(sub, w - (30 if icon else 0))
        h = 24 + (n - 1) * (name_size + 2) + len(subs) * (self.SUB + 2.5) + (18 if subs else 12)
        return max(h, 46) if icon else h

    def _centred_block(self, x, y, w, h, title, sub, name_size, top=14):
        names = wrap(title, name_size, w - 14, True)
        subs = self._subs(sub, w)
        block = (len(names) - 1) * (name_size + 2) + len(subs) * (self.SUB + 2.5)
        ty = y + top + max(0, (h - top - (18 if subs else 12) - block - name_size) / 2) + name_size - 1
        cx = x + w / 2
        for ln in names:
            self.text(cx, ty, ln, name_size, self.t["ink"], anchor="middle", weight=600)
            ty += name_size + 2
        ty += 0.5
        for ln in subs:
            self.text(cx, ty, ln, self.SUB, self.t["muted"], anchor="middle")
            ty += self.SUB + 2.5

    def _type_label(self, x, y, label, colour, maxw):
        """Type label in small caps, tightened to fit `maxw`."""
        label = label.upper()
        size, spacing = 7.5, 0.6
        while (text_width(label, size, True) + spacing * len(label)) > maxw and size > 6:
            if spacing > 0.15:
                spacing = round(spacing - 0.15, 2)
            else:
                size -= 0.25
        self.text(x, y, label, size, colour, weight=700, spacing=spacing)

    # ---- nodes
    def node_height(self, oid, w, sub=None, name_size=None, icon=None):
        return self._block_height(self.obj[oid]["name"], w, sub, name_size or self.NAME, bool(icon))

    def node(self, oid, x, y, w, h=None, sub=None, dashed=None, name_size=None,
             type_label=None, icon=None):
        """One model object as a box. `icon` is a platform or generic icon
        reference ("aws:amazon-simple-storage-service", "S3", "generic:queue"),
        drawn 20px at the left. Returns its box dict."""
        o = self.obj.get(oid)
        if o is None:
            raise KeyError(f"{self.vid}: object {oid} is not in the model")
        if o["type"] in ("And Junction", "Or Junction"):
            raise ValueError(f"{self.vid}: {oid} is a junction; draw it with junction()")
        ns = name_size or self.NAME
        stroke, fill = self.colours(o["type"])
        if h is None:
            h = self.node_height(oid, w, sub, ns, icon)
        self._mark(oid, box(x, y, w, h))
        self._shape(o["type"], x, y, w, h, fill, stroke,
                    self.not_built(oid) if dashed is None else dashed)
        show_type = self.type_labels if type_label is None else bool(type_label)
        if show_type:
            label = type_label if isinstance(type_label, str) else o["type"]
            self._type_label(x + 6, y + 10, label, stroke, w - 12 - (22 if self.archimate else 0))
        self._symbol(o["type"], x, y, w)
        top = 16 if self.archimate and self.mm.types[o["type"]].get("shape") in ("object", "contract") else 14
        if icon:
            self._platform_icon(icon, x + 8, y + (h - 20) / 2 + (4 if show_type else 0), 20, stroke)
            self._centred_block(x + 30, y, w - 30, h, o["name"], sub, ns, top)
        else:
            self._centred_block(x, y, w, h, o["name"], sub, ns, top)
        self.text(x + w - 5, y + h - 4, oid, 7, self.t["id"], anchor="end")
        return box(x, y, w, h)

    def group_height(self, title, w, sub=None):
        return self._block_height(title, w, sub, self.NAME)

    def group(self, otype, title, members, x, y, w, h=None, sub=None, ids=None):
        """One box standing for several objects of one type: the type label
        carries the count (REQUIREMENT ×7), the id slot the range. Dashed only
        when every member is unbuilt. The catalogue still lists each."""
        if not members:
            raise ValueError(f"{self.vid}: group '{title}' has no members")
        for m in members:
            self._mark(m)
            if self.obj[m]["type"] != otype:
                raise ValueError(f"{self.vid}: {m} is a {self.obj[m]['type']}, not a {otype}")
        stroke, fill = self.colours(otype)
        if h is None:
            h = self.group_height(title, w, sub)
        self._shape(otype, x, y, w, h, fill, stroke, all(self.not_built(m) for m in members))
        self._type_label(x + 6, y + 10, f"{otype} ×{len(members)}", stroke,
                         w - 12 - (22 if self.archimate else 0))
        self._symbol(otype, x, y, w)
        self._centred_block(x, y, w, h, title, sub, self.NAME)
        label = ids or (members[0] if len(members) == 1 else f"{members[0]}–{members[-1]}")
        self.text(x + w - 5, y + h - 4, label, 7, self.t["id"], anchor="end")
        return box(x, y, w, h)

    def container_header(self, oid, w, name_size=None):
        """(height, lines) taken by a container's type label and name."""
        ns = name_size or self.NAME
        lines = wrap(self.obj[oid]["name"], ns, w - 16 - (20 if self.archimate else 0), True)
        top = 16 if self.type_labels else 6
        return top + len(lines) * (ns + 2.5) + 2, lines

    def container(self, oid, x, y, w, h, sub=None, name_size=None, fill_opacity=0.45, icon=None):
        """A model object drawn as a box holding others. Box notation: its
        children (parent), category members or located technology. ArchiMate:
        whatever the relationships say it composes, aggregates, is assigned
        or realizes; say which in the key line. Returns (box, content_top)."""
        o = self.obj.get(oid)
        if o is None:
            raise KeyError(f"{self.vid}: object {oid} is not in the model")
        self._mark(oid, box(x, y, w, h), "container")
        ns = name_size or self.NAME
        stroke, fill = self.colours(o["type"])
        self._shape(o["type"], x, y, w, h, fill, stroke, self.not_built(oid),
                    extra=f' fill-opacity="{fill_opacity}"', container=True)
        hh, lines = self.container_header(oid, w, ns)
        tx = x + 7
        if icon:
            self._platform_icon(icon, x + 7, y + 6, 16, stroke)
            tx = x + 28
        if self.type_labels:
            self._type_label(tx, y + 11, o["type"], stroke, w - (tx - x) - 14 - text_width(oid, 7))
            self.text(x + w - 6, y + 11, oid, 7, self.t["id"], anchor="end")
            ty = y + 14 + ns
        else:
            self._symbol(o["type"], x, y, w)
            self.text(x + w - 6, y + h - 5, oid, 7, self.t["id"], anchor="end")
            ty = y + 4 + ns
        for ln in lines:
            self.text(tx, ty, ln, ns, self.t["ink"], weight=600)
            ty += ns + 2.5
        top = y + hh
        for ln in (wrap(sub, self.SUB, w - 14) if sub else []):
            self.text(tx, ty - 1, ln, self.SUB, self.t["muted"])
            ty += 11
            top += 11
        return box(x, y, w, h), top

    def frame(self, x, y, w, h, label, colour=None, dashed=False, icon=None):
        """A plain visual grouping that is not a model object: thin frame and
        an UPPERCASE label ('External', 'AWS Cloud'). `icon` puts a platform
        group icon (e.g. aws:virtual-private-cloud-vpc) at its top-left."""
        colour = colour or self.t["muted"]
        dash = ' stroke-dasharray="4 3"' if dashed else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="6" '
                 f'fill="none" stroke="{colour}" stroke-width="1"{dash}/>')
        lx = x + 8
        if icon:
            self._platform_icon(icon, x + 1, y + 1, 18, colour)
            lx = x + 24
        self.text(lx, y + 13, label.upper(), 8, colour, weight=700, spacing=0.5)
        return box(x, y, w, h)

    def junction(self, oid, cx, cy, r=5):
        """An ArchiMate And (filled) or Or (hollow) junction."""
        o = self.obj.get(oid)
        if o is None or o["type"] not in ("And Junction", "Or Junction"):
            raise ValueError(f"{self.vid}: {oid} is not a junction in the model")
        self._mark(oid, box(cx - r, cy - r, 2 * r, 2 * r))
        fill = self.t["body"] if o["type"] == "And Junction" else self.t["paper"]
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}" '
                 f'stroke="{self.t["body"]}" stroke-width="1.2"/>')
        return box(cx - r, cy - r, 2 * r, 2 * r)

    def _pill_ok(self, otype):
        if self.archimate:
            return otype.endswith("Interface")
        return self.mm.types[otype].get("shape") == "pill"

    def pill_height(self, oid, w):
        return self.PILL_H if self._pill_fits(oid, w) else self.PILL_H + 10

    def _pill_fits(self, oid, w):
        idw = text_width(oid, 7) + 4
        return text_width(self.obj[oid]["name"], 7.75, True) * 1.08 <= w - 18 - idw

    def pill_width(self, oid):
        return text_width(self.obj[oid]["name"], 8.5, True) + text_width(oid, 7) + 26

    def pill(self, oid, x, y, w=None):
        """A service or interface as a pill (r11) at top-left (x, y), on the
        edge of the element that provides it or listed inside it."""
        o = self.obj.get(oid)
        if o is None:
            raise KeyError(f"{self.vid}: object {oid} is not in the model")
        if not self._pill_ok(o["type"]):
            raise ValueError(f"{self.vid}: pill() is for service / interface types; {oid} is a {o['type']}")
        stroke, _ = self.colours(o["type"])
        w = w or self.pill_width(oid)
        h = self.pill_height(oid, w)
        self._mark(oid, box(x, y, w, h))
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
        return box(x, y, w, h)

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
    def _marker_svg(self, kind):
        attrs, body = MARKERS[kind]
        body = body.replace("{body}", self.t["body"]).replace("{paper}", self.t["paper"])
        return f'<marker id="{{id}}" {attrs} orient="auto-start-reverse">{body}</marker>'

    def _marker(self, kind):
        return self.define(kind, self._marker_svg(kind))

    def edge(self, points, verb, label=None, check=None, dashed=False,
             label_anchor="middle", arrow=True, label_text=None):
        """Orthogonal edge through `points` (stop 2px short of the target, and
        of the source when that end carries a symbol). `check` lists the
        (from, verb, to) triples the edge stands for; each must be in the
        model. `label` is the (x, y) of the label. Box notation labels with
        the verb; ArchiMate draws the relationship's own line style and
        labels with its name (or label_text) only when a position is given."""
        found = []
        for (f, v, t) in (check or []):
            i = self.rel_index(f, v, t)
            if i is None:
                raise ValueError(f"{self.vid}: relationship {f} -{v}-> {t} not in the model")
            found.append(i)
        pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in points)
        if found and found[0] >= 0:
            self.edges.append((found[0], list(points)))
        if self.archimate and verb in self.mm.relationships:
            rd = self.mm.relationships[verb]
            if verb not in self.rel_types:
                self.rel_types.append(verb)
            rel = self.rels[found[0]] if found and found[0] >= 0 else {}
            start, end = rd["start"], rd["end"]
            if verb == "access":
                acc = rel.get("access", "write")
                start = "arrow-open-small" if acc in ("read", "readwrite") else None
                end = "arrow-open-small" if acc in ("write", "readwrite") else None
            if verb == "association" and rel.get("directed"):
                end = "arrow-open-small"
            dash = DASH[rd["line"]]
            a = [f'points="{pts}"', 'fill="none"', f'stroke="{self.t["body"]}"', 'stroke-width="1.1"']
            if dash:
                a.append(f'stroke-dasharray="{dash}"')
            if start:
                a.append(f'marker-start="url(#{self._marker(start)})"')
            if end:
                a.append(f'marker-end="url(#{self._marker(end)})"')
            self.add(f'<polyline {" ".join(a)}/>')
            if label is not None:
                text = label_text or rel.get("name") or (rel.get("modifier") if verb == "influence" else None) or verb
                self.text(label[0], label[1], text, self.SUB, self.t["muted"],
                          anchor=label_anchor, italic=True, halo=True)
            return
        dash = ' stroke-dasharray="4 3"' if dashed else ""
        mk = f' marker-end="url(#{self.marker})"' if arrow else ""
        self.add(f'<polyline points="{pts}" fill="none" stroke="{self.t["body"]}" '
                 f'stroke-width="1.2"{dash}{mk}/>')
        if label is not None:
            self.text(label[0], label[1], label_text or verb, self.SUB, self.t["muted"],
                      anchor=label_anchor, italic=True, halo=True)

    # ---- matrix (TOGAF matrices, CRUD)
    def matrix(self, x, y, rows, cols, cells, row_w=170, col_w=None, title=None):
        """A catalogue matrix as a table: `rows` and `cols` are object ids,
        `cells` maps (row, col) -> text. Use cells_from() to derive the cells
        from relationships so every mark traces to the model. Returns the y
        below it."""
        for oid in list(rows) + list(cols):
            self._mark(oid)
        col_w = col_w or max(44, min(96, (self.W - 16 - x - row_w) / max(1, len(cols))))
        head_lines = max(len(wrap(self.obj[c]["name"], 8.5, col_w - 8, True)) for c in cols)
        hh = 18 + head_lines * 11
        if title:
            self.text(x, y + 10, title.upper(), 8, self.t["muted"], weight=700, spacing=0.5)
            y += 18
        W = row_w + col_w * len(cols)
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{W:.1f}" height="{hh:.1f}" fill="{self.t["band"]}" '
                 f'stroke="{self.t["rule"]}" stroke-width="1"/>')
        for j, c in enumerate(cols):
            cx = x + row_w + j * col_w
            stroke, _ = self.colours(self.obj[c]["type"])
            ty = y + 13
            for ln in wrap(self.obj[c]["name"], 8.5, col_w - 8, True):
                self.text(cx + col_w / 2, ty, ln, 8.5, self.t["ink"], anchor="middle", weight=600)
                ty += 11
            self.text(cx + col_w / 2, y + hh - 5, c, 7, self.t["id"], anchor="middle")
            self.add(f'<line x1="{cx:.1f}" y1="{y:.1f}" x2="{cx:.1f}" y2="{y + hh:.1f}" '
                     f'stroke="{self.t["rule"]}"/>')
        ry = y + hh
        for i, r in enumerate(rows):
            rh = 12 + len(wrap(self.obj[r]["name"], 9, row_w - 60, True)) * 11
            if i % 2:
                self.add(f'<rect x="{x:.1f}" y="{ry:.1f}" width="{W:.1f}" height="{rh:.1f}" '
                         f'fill="{self.t["band"]}"/>')
            ty = ry + 15
            for ln in wrap(self.obj[r]["name"], 9, row_w - 60, True):
                self.text(x + 8, ty, ln, 9, self.t["ink"], weight=600)
                ty += 11
            self.text(x + row_w - 8, ry + 15, r, 7, self.t["id"], anchor="end")
            for j, c in enumerate(cols):
                v = cells.get((r, c))
                if v:
                    self.text(x + row_w + j * col_w + col_w / 2, ry + rh / 2 + 3.5, v, 9,
                              self.t["ink"], anchor="middle", weight=700, spacing=0.6)
            self.add(f'<line x1="{x:.1f}" y1="{ry + rh:.1f}" x2="{x + W:.1f}" y2="{ry + rh:.1f}" '
                     f'stroke="{self.t["rule"]}"/>')
            ry += rh
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{W:.1f}" height="{ry - y:.1f}" fill="none" '
                 f'stroke="{self.t["frame"]}" stroke-width="1"/>')
        self.add(f'<line x1="{x + row_w:.1f}" y1="{y:.1f}" x2="{x + row_w:.1f}" y2="{ry:.1f}" '
                 f'stroke="{self.t["rule"]}"/>')
        return ry

    def cells_from(self, verb, rows, cols, mark="●"):
        """Cells for matrix(): one per relationship of `verb` between a row and
        a column (either direction). The cell shows the relationship's crud
        (Essential), access (ArchiMate) or note, else `mark`. `verb` may be a
        dict {verb: letters}, e.g. {"writes": "CU", "reads": "R"} (CoreEA), whose
        letters are merged in C R U D order."""
        verbs = verb if isinstance(verb, dict) else {verb: None}
        rs, cs = set(rows), set(cols)
        out = {}
        for r in self.rels:
            if r["type"] not in verbs:
                continue
            if r["from"] in rs and r["to"] in cs:
                key = (r["from"], r["to"])
            elif r["to"] in rs and r["from"] in cs:
                key = (r["to"], r["from"])
            else:
                continue
            fixed = verbs[r["type"]]
            text = fixed or r.get("crud") or {"read": "R", "write": "W", "readwrite": "RW"}.get(
                r.get("access"), "") or r.get("note") or mark
            if fixed and key in out:
                text = "".join(c for c in "CRUD" if c in out[key] + fixed)
            out[key] = text
        return out

    # ---- legend and key
    def _legend_swatch(self, x, y, otype):
        stroke, fill = self.colours(otype)
        if self.archimate:
            shape = self.mm.types[otype].get("shape")
            if shape == "junction":
                f = self.t["body"] if otype == "And Junction" else self.t["paper"]
                self.add(f'<circle cx="{x + 11}" cy="{y + 6}" r="4" fill="{f}" stroke="{self.t["body"]}"/>')
                return 22
            rx = 4 if shape == "round" else 0
            dash = ' stroke-dasharray="3 2"' if shape == "grouping" else ""
            fl = "none" if shape == "grouping" else fill
            self.add(f'<rect x="{x}" y="{y - 1:.1f}" width="22" height="14" rx="{rx}" fill="{fl}" '
                     f'stroke="{stroke}" stroke-width="1"{dash}/>')
            if shape in ("object", "contract"):
                self.add(f'<line x1="{x}" y1="{y + 3:.1f}" x2="{x + 22}" y2="{y + 3:.1f}" '
                         f'stroke="{stroke}" stroke-width="1"/>')
            kind = self.mm.types[otype].get("icon")
            if kind:
                self.add(f'<g transform="translate({x + 3} {y + 0.6:.1f}) scale(1)">'
                         + archimate_icons.icon(kind, 0, 0, stroke) + '</g>')
            return 22
        self.add(f'<rect x="{x}" y="{y:.1f}" width="16" height="10" rx="2" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
        return 16

    def _legend_line(self, x, y, verb):
        rd = self.mm.relationships[verb]
        a = [f'x1="{x}" y1="{y + 5:.1f}" x2="{x + 26}" y2="{y + 5:.1f}"',
             f'stroke="{self.t["body"]}" stroke-width="1.1"']
        dash = DASH[rd["line"]]
        if dash:
            a.append(f'stroke-dasharray="{dash}"')
        start, end = rd["start"], rd["end"]
        if verb == "access":
            end = "arrow-open-small"
        if start:
            a.append(f'marker-start="url(#{self._marker(start)})"')
        if end:
            a.append(f'marker-end="url(#{self._marker(end)})"')
        self.add(f'<line {" ".join(a)}/>')
        return 26

    def legend(self, y):
        """Legend: the types drawn (metamodel order), the relationship types
        drawn (ArchiMate), plus the dashed meaning when used. Returns the y
        below it."""
        W = self.W
        self.add(f'<line x1="16" y1="{y:.1f}" x2="{W - 16}" y2="{y:.1f}" '
                 f'stroke="{self.t["rule"]}" stroke-width="1"/>')
        y += 12
        x = 16
        entries = [("type", t) for t in self.mm.type_order if t in self.types]
        if self.used_dashed:
            entries.append(("dashed", "Proposed / designed / not started"))
        entries += [("rel", r) for r in self.mm.relationships if r in self.rel_types]
        row = 20 if self.archimate else 18
        for kind, label in entries:
            text = label
            sw = 22 if self.archimate else 16
            if kind == "rel":
                text = label.capitalize()
                sw = 26
            lw = text_width(text, 8.5) + sw + 10
            if x + lw > W - 16:
                x, y = 16, y + row
            if kind == "type":
                sw = self._legend_swatch(x, y, label)
            elif kind == "rel":
                sw = self._legend_line(x, y, label)
            else:
                self.add(f'<rect x="{x}" y="{y:.1f}" width="16" height="10" rx="2" '
                         f'fill="{self.t["paper"]}" stroke="{self.t["body"]}" '
                         f'stroke-width="1.2" stroke-dasharray="3 2"/>')
                sw = 16
            self.text(x + sw + 5, y + 8.5, text, 8.5, self.t["body"])
            x += lw + 10
        return y + row

    def key_line(self, y, notes):
        """Plain-text key under the legend saying what nesting and pills mean
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
    def manifest(self):
        return {"view": self.vid, "title": self.title, "metamodel": self.mm.key,
                "viewpoint": self.viewpoint, "objects": self.drawn,
                "relationships": [relationship_id(self.rels[i]) for i, _ in self.edges],
                "warnings": self.warnings}

    def save(self, height, outdir, render=True, scale=2):
        for w in self.warnings:
            print("warning:", w, file=sys.stderr)
        return super().save(height, outdir, render, scale)
