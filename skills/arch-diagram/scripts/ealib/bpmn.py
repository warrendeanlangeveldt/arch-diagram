"""BPMN 2.0: process models, the BPMN notation and BPMN 2.0 XML with
diagram interchange (BPMNDI), which Camunda Modeler, bpmn.io, Signavio,
Bizagi, ARIS, Sparx EA and most process tools import.

Model ("metamodel": "bpmn"): the same objects / relationships file.

objects
  participant                         a pool; one process each
  lane                                parent: participant or lane
  task userTask serviceTask sendTask receiveTask manualTask scriptTask
  businessRuleTask callActivity subProcess
  startEvent endEvent intermediateCatchEvent intermediateThrowEvent
  boundaryEvent                       "trigger": message | timer | error |
                                      signal | escalation | conditional |
                                      compensation | terminate | link | cancel
                                      boundary: "attachedTo", "interrupting"
  exclusiveGateway parallelGateway inclusiveGateway eventBasedGateway
  complexGateway
  dataObject dataStore textAnnotation
  Flow nodes, data and annotations take "parent": the lane, pool or
  subProcess they sit in. A model without participants is one process.

relationships
  sequenceFlow   within one process scope; "condition", "default": true
  messageFlow    between pools (pool or node ends)
  association    text annotation to anything
  dataInput      data -> activity / throw event
  dataOutput     activity / catch event -> data
"""
import os
import re
from xml.sax.saxutils import escape, quoteattr

from .common import HOUSE, NOT_BUILT, Canvas, box, text_width, wrap
from .metamodel import NCNAME, Metamodel, ModelError, relationship_id

ACTIVITIES = ["task", "userTask", "serviceTask", "sendTask", "receiveTask", "manualTask",
              "scriptTask", "businessRuleTask", "callActivity", "subProcess"]
EVENTS = ["startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent", "boundaryEvent"]
GATEWAYS = ["exclusiveGateway", "parallelGateway", "inclusiveGateway", "eventBasedGateway",
            "complexGateway"]
DATA = ["dataObject", "dataStore"]
CONTAINERS = ["participant", "lane"]
ARTIFACTS = ["textAnnotation"]
FLOW_NODES = ACTIVITIES + EVENTS + GATEWAYS
ALL_TYPES = CONTAINERS + FLOW_NODES + DATA + ARTIFACTS
RELS = ["sequenceFlow", "messageFlow", "association", "dataInput", "dataOutput"]

TRIGGERS = {
    "startEvent": {"none", "message", "timer", "conditional", "signal", "error", "escalation",
                   "compensation"},
    "endEvent": {"none", "message", "error", "escalation", "signal", "terminate", "compensation", "cancel"},
    "intermediateCatchEvent": {"message", "timer", "conditional", "signal", "link"},
    "intermediateThrowEvent": {"none", "message", "escalation", "signal", "compensation", "link"},
    "boundaryEvent": {"message", "timer", "error", "signal", "escalation", "conditional",
                      "compensation", "cancel"},
}
CATCHING = {"startEvent", "intermediateCatchEvent", "boundaryEvent"}
LABEL = {
    "task": "Task", "userTask": "User task", "serviceTask": "Service task", "sendTask": "Send task",
    "receiveTask": "Receive task", "manualTask": "Manual task", "scriptTask": "Script task",
    "businessRuleTask": "Business rule task", "callActivity": "Call activity", "subProcess": "Sub-process",
    "startEvent": "Start event", "endEvent": "End event",
    "intermediateCatchEvent": "Intermediate catch event", "intermediateThrowEvent": "Intermediate throw event",
    "boundaryEvent": "Boundary event", "exclusiveGateway": "Exclusive gateway",
    "parallelGateway": "Parallel gateway", "inclusiveGateway": "Inclusive gateway",
    "eventBasedGateway": "Event-based gateway", "complexGateway": "Complex gateway",
    "dataObject": "Data object", "dataStore": "Data store", "textAnnotation": "Text annotation",
    "participant": "Pool", "lane": "Lane",
}

BPMN_METAMODEL = Metamodel({
    "key": "bpmn", "name": "BPMN 2.0", "notation": "bpmn",
    "source": "OMG Business Process Model and Notation 2.0.2: process, collaboration and "
              "diagram interchange (BPMNDI).",
    "layer_order": ["Process"],
    "layers": {"Process": ["#475569", "#ffffff"]},
    "types": {t: {"layer": "Process", "class": t} for t in ALL_TYPES},
    "relationships": {r: {"pairs": [], "xml": r} for r in RELS},
})


# ------------------------------------------------------------------ model

def _an(t):
    s = LABEL.get(t, t).lower()
    return ("an " if s[0] in "aeiou" else "a ") + s


class _Scope:
    def __init__(self, model):
        self.objs = model["objects"]
        self.byid = {o["id"]: o for o in self.objs if o.get("id")}

    def parent(self, oid):
        o = self.byid[oid]
        if o["type"] == "boundaryEvent" and o.get("attachedTo") in self.byid:
            return self.byid[o["attachedTo"]].get("parent")
        return o.get("parent")

    def ancestors(self, oid):
        out, cur, seen = [], self.parent(oid), set()
        while cur and cur in self.byid and cur not in seen:
            seen.add(cur)
            out.append(cur)
            cur = self.parent(cur)
        return out

    def participant(self, oid):
        if self.byid[oid]["type"] == "participant":
            return oid
        for a in self.ancestors(oid):
            if self.byid[a]["type"] == "participant":
                return a
        return None

    def scope(self, oid):
        """Nearest subProcess or participant (None: the implicit process)."""
        for a in self.ancestors(oid):
            if self.byid[a]["type"] in ("subProcess", "participant"):
                return a
        return None

    def lane(self, oid):
        for a in self.ancestors(oid):
            t = self.byid[a]["type"]
            if t == "lane":
                return a
            if t in ("subProcess", "participant"):
                return None
        return None


def validate_bpmn(model):
    """Errors raise ModelError; structural smells come back as warnings."""
    errs, warns = [], []
    objs, rels = model.get("objects"), model.get("relationships")
    if not isinstance(objs, list) or not isinstance(rels, list):
        raise ModelError("model needs 'objects' and 'relationships' arrays")
    byid = {}
    for i, o in enumerate(objs):
        oid, t = o.get("id"), o.get("type")
        where = f"objects[{i}] {oid or '?'}"
        if not oid or not t or (not o.get("name") and t not in EVENTS + GATEWAYS + ["lane"]):
            errs.append(f"{where}: id, type and name are required (events and gateways may omit name)")
            if not oid or not t:
                continue
        if oid in byid:
            errs.append(f"{where}: duplicate id")
        byid[oid] = o
        if not NCNAME.match(oid):
            errs.append(f"{where}: id must be an XML identifier (letter or _ first; letters, digits, - _ .)")
        if t not in ALL_TYPES:
            errs.append(f"{where}: unknown BPMN type '{t}' (known: {', '.join(ALL_TYPES)})")
            continue
        if t in TRIGGERS:
            trig = o.get("trigger", "none")
            if trig not in TRIGGERS[t]:
                errs.append(f"{where}: {t} cannot have trigger '{trig}' (allowed: {', '.join(sorted(TRIGGERS[t]))})")
        elif o.get("trigger"):
            errs.append(f"{where}: only events have a trigger")
        if t == "boundaryEvent":
            if not o.get("attachedTo"):
                errs.append(f"{where}: boundaryEvent needs attachedTo (an activity)")
            if o.get("parent"):
                errs.append(f"{where}: a boundaryEvent takes its activity's place; drop parent")
        elif o.get("attachedTo"):
            errs.append(f"{where}: only boundary events are attachedTo an activity")
    sc = _Scope(model)
    has_pools = any(o.get("type") == "participant" for o in objs)
    for o in objs:
        oid, t = o.get("id"), o.get("type")
        if oid not in byid or t not in ALL_TYPES:
            continue
        p = o.get("parent")
        if t == "boundaryEvent":
            a = o.get("attachedTo")
            if a and (a not in byid or byid[a]["type"] not in ACTIVITIES):
                errs.append(f"{oid}: attachedTo {a} is not an activity in the model")
            continue
        if p is not None and p not in byid:
            errs.append(f"{oid}: parent {p} is not in the model")
            continue
        pt = byid[p]["type"] if p else None
        if t == "participant" and p:
            errs.append(f"{oid}: a pool has no parent")
        elif t == "lane" and pt not in ("participant", "lane"):
            errs.append(f"{oid}: a lane's parent is a pool or a lane")
        elif t in FLOW_NODES + DATA + ARTIFACTS and p and pt not in ("participant", "lane", "subProcess"):
            errs.append(f"{oid}: parent must be a pool, lane or subProcess, not a {pt}")
        if t in FLOW_NODES and has_pools and not sc.participant(oid):
            errs.append(f"{oid}: the model has pools, so every flow node sits in one")
        if t in FLOW_NODES and pt == "participant" and any(
                x.get("type") == "lane" and x.get("parent") == p for x in objs):
            errs.append(f"{oid}: pool {p} has lanes; put the node in one of them")
    for o in objs:
        seen, cur = set(), o.get("id")
        while cur in byid and byid[cur].get("parent"):
            if cur in seen:
                errs.append(f"{o.get('id')}: parent chain loops")
                break
            seen.add(cur)
            cur = byid[cur]["parent"]
    incoming, outgoing, defaults = {}, {}, {}
    seen_rel = set()
    for i, r in enumerate(rels):
        f, v, t = r.get("from"), r.get("type"), r.get("to")
        where = f"relationships[{i}] {f} -{v}-> {t}"
        if (f, v, t) in seen_rel:
            errs.append(f"{where}: duplicate")
        seen_rel.add((f, v, t))
        if v not in RELS:
            errs.append(f"{where}: unknown relationship (allowed: {', '.join(RELS)})")
            continue
        if f not in byid or t not in byid:
            errs.append(f"{where}: " + ("source" if f not in byid else "target") + " not in model")
            continue
        ft, tt = byid[f]["type"], byid[t]["type"]
        if v == "sequenceFlow":
            if ft not in FLOW_NODES or tt not in FLOW_NODES:
                errs.append(f"{where}: sequence flow joins flow nodes (activities, events, gateways)")
                continue
            if sc.scope(f) != sc.scope(t):
                errs.append(f"{where}: sequence flow stays inside one pool / sub-process; "
                            "use a message flow between pools")
            if ft == "endEvent":
                errs.append(f"{where}: an end event has no outgoing sequence flow")
            if tt in ("startEvent", "boundaryEvent"):
                errs.append(f"{where}: {_an(tt)} has no incoming sequence flow")
            if ft == "eventBasedGateway" and not (
                    tt == "receiveTask" or (tt == "intermediateCatchEvent"
                                            and byid[t].get("trigger") in ("message", "timer", "signal", "conditional"))):
                errs.append(f"{where}: an event-based gateway leads to catch events or receive tasks")
            if r.get("default"):
                if ft not in ("exclusiveGateway", "inclusiveGateway", "complexGateway") + tuple(ACTIVITIES):
                    errs.append(f"{where}: only exclusive/inclusive/complex gateways and activities have a default flow")
                if f in defaults:
                    errs.append(f"{where}: {f} already has a default flow")
                defaults[f] = i
            outgoing.setdefault(f, []).append(i)
            incoming.setdefault(t, []).append(i)
        elif v == "messageFlow":
            ok_ends = set(ACTIVITIES) | set(EVENTS) | {"participant"}
            if ft not in ok_ends or tt not in ok_ends:
                errs.append(f"{where}: message flow joins pools, activities or events (not gateways or data)")
                continue
            if sc.participant(f) is None or sc.participant(f) == sc.participant(t):
                errs.append(f"{where}: message flow runs between two different pools")
            if ft in ("startEvent", "intermediateCatchEvent", "boundaryEvent"):
                errs.append(f"{where}: {_an(ft)} receives messages; it cannot send one")
            if tt in ("endEvent", "intermediateThrowEvent"):
                errs.append(f"{where}: {_an(tt)} sends messages; it cannot receive one")
        elif v == "association":
            if "textAnnotation" not in (ft, tt):
                errs.append(f"{where}: an association links a text annotation")
        elif v == "dataInput":
            if ft not in DATA or tt not in ACTIVITIES + ["endEvent", "intermediateThrowEvent"]:
                errs.append(f"{where}: dataInput runs from a data object/store to an activity or throw event")
        elif v == "dataOutput":
            if tt not in DATA or ft not in ACTIVITIES + list(CATCHING):
                errs.append(f"{where}: dataOutput runs from an activity or catch event to a data object/store")
    for o in objs:
        oid, t = o.get("id"), o.get("type")
        n_in, n_out = len(incoming.get(oid, [])), len(outgoing.get(oid, []))
        if t == "startEvent" and n_out == 0:
            warns.append(f"{oid}: start event leads nowhere")
        elif t == "endEvent" and n_in == 0:
            warns.append(f"{oid}: nothing reaches this end event")
        elif t in GATEWAYS and n_in + n_out and not (n_in > 1 or n_out > 1):
            warns.append(f"{oid}: gateway neither splits nor joins")
        elif t in ACTIVITIES and n_in == 0 and sc.scope(oid) is not None and any(
                byid[x]["type"] == "startEvent" and sc.scope(x) == sc.scope(oid) for x in byid) \
                and not o.get("isForCompensation"):
            warns.append(f"{oid}: activity is never reached by a sequence flow")
        if t in GATEWAYS and n_out > 1 and t in ("exclusiveGateway", "inclusiveGateway"):
            unnamed = [i for i in outgoing[oid] if not rels[i].get("condition") and not rels[i].get("name")
                       and not rels[i].get("default")]
            if unnamed:
                warns.append(f"{oid}: outgoing flows of a decision should be named or conditioned")
    if errs:
        raise ModelError(f"{len(errs)} model problem(s):\n  " + "\n  ".join(errs))
    return {"metamodel": "BPMN 2.0", "objects": len(objs), "relationships": len(rels),
            "warnings": warns}


# ------------------------------------------------------------------ view

TASK_W, TASK_H, EVENT_R, GW = 112, 64, 16, 21


class BpmnView(Canvas):
    """Hand-placed BPMN diagram. Positions are recorded for BPMNDI export.

        v = BpmnView(model, "ORDER", title="…")
        pool = v.pool("P-CUST", 16, 16, 708, 120)
        t = v.task("T-1", 100, 40)            # top-left; returns box
        e = v.event("E-1", 60, 72)            # centre
        g = v.gateway("G-1", 300, 72)         # centre
        v.flow([(e["r"], e["cy"]), (t["x"] - 2, t["cy"])], check=("E-1", "sequenceFlow", "T-1"))
    """

    def __init__(self, model, vid, title=None, theme=None):
        if model.get("metamodel") != "bpmn":
            raise ValueError("BpmnView draws BPMN models")
        th = dict(theme or HOUSE)
        th.setdefault("task", ("#334155", "#ffffff"))
        th.setdefault("pool", ("#475569", "#f8fafc"))
        th.setdefault("event_start", "#15803d")
        th.setdefault("event_end", "#b4443c")
        th.setdefault("event_mid", "#b46a12")
        super().__init__(vid, th, title)
        self.model = model
        self.obj = {o["id"]: o for o in model["objects"]}
        self.rels = model["relationships"]
        self.sc = _Scope(model)
        self.shapes = {}        # id -> (box, extra)
        self.edges = []         # (rel index, points)
        self.kinds = []         # legend entries drawn
        self.flow_kinds = []
        self.used_dashed = False
        self.arrow = self.define("arr", '<marker id="{id}" viewBox="0 0 10 10" refX="9" refY="5" '
                                 'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                                 f'<path d="M 0 1 L 9 5 L 0 9 z" fill="{th["body"]}"/></marker>')

    def _get(self, oid, types):
        o = self.obj.get(oid)
        if o is None:
            raise KeyError(f"{self.vid}: object {oid} is not in the model")
        if o["type"] not in types:
            raise ValueError(f"{self.vid}: {oid} is a {o['type']}, not one of {', '.join(types)}")
        return o

    def _kind(self, k):
        if k not in self.kinds:
            self.kinds.append(k)

    def _dash(self, oid):
        if self.obj[oid].get("status") in NOT_BUILT:
            self.used_dashed = True
            return ' stroke-dasharray="4 3"'
        return ""

    # ---- containers
    def pool(self, pid, x, y, w, h):
        o = self._get(pid, ["participant"])
        stroke, fill = self.t["pool"]
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{self.t["paper"]}" '
                 f'stroke="{stroke}" stroke-width="1.3"{self._dash(pid)}/>')
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="30" height="{h:.1f}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="1.3"/>')
        self._vlabel(x + 15, y + h / 2, o["name"], h - 12, 10, 700)
        self.shapes[pid] = (box(x, y, w, h), {"isHorizontal": "true"})
        return box(x + 30, y, w - 30, h)

    def lane(self, lid, x, y, w, h):
        o = self._get(lid, ["lane"])
        stroke, fill = self.t["pool"]
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="none" '
                 f'stroke="{stroke}" stroke-width="0.9"/>')
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="24" height="{h:.1f}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="0.9"/>')
        if o.get("name"):
            self._vlabel(x + 12, y + h / 2, o["name"], h - 10, 9, 600)
        self.shapes[lid] = (box(x, y, w, h), {"isHorizontal": "true"})
        return box(x + 24, y, w - 24, h)

    def _vlabel(self, cx, cy, s, maxw, size, weight):
        lines = wrap(s, size, maxw, True)[:2]
        off = (len(lines) - 1) * (size + 1) / 2
        for i, ln in enumerate(lines):
            lx = cx - off + i * (size + 1) + size * 0.35
            self.text(lx, cy, ln, size, self.t["ink"], anchor="middle", weight=weight, rotate=-90)

    def subprocess(self, sid, x, y, w, h):
        """An expanded sub-process: rounded frame, name top-left. Returns box."""
        o = self._get(sid, ["subProcess"])
        stroke, fill = self.t["task"]
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="10" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="1.3"{self._dash(sid)}/>')
        self.text(x + 9, y + 15, o["name"], 9.5, self.t["ink"], weight=600)
        self.shapes[sid] = (box(x, y, w, h), {"isExpanded": "true"})
        self._kind("subProcess")
        return box(x, y, w, h)

    # ---- activities
    def task(self, tid, x, y, w=TASK_W, h=TASK_H):
        o = self._get(tid, ACTIVITIES)
        t = o["type"]
        stroke, fill = self.t["task"]
        sw = 3 if t == "callActivity" else 1.3
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="9" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{self._dash(tid)}/>')
        self.add(self._task_marker(t, x + 6, y + 5, stroke))
        bottom = 12 if t in ("subProcess", "callActivity") else 4
        lines = wrap(o["name"], 9.5, w - 12, True)[:4]
        ty = y + (h - bottom) / 2 - (len(lines) - 1) * 6 + 4 + (3 if t != "task" else 0)
        for ln in lines:
            self.text(x + w / 2, ty, ln, 9.5, self.t["ink"], anchor="middle", weight=600)
            ty += 12
        if t in ("subProcess", "callActivity") and o.get("collapsed", True):
            mx, my = x + w / 2 - 6, y + h - 15
            self.add(f'<rect x="{mx:.1f}" y="{my:.1f}" width="12" height="12" fill="none" stroke="{stroke}" '
                     f'stroke-width="1"/><path d="M{mx + 6:.1f} {my + 3:.1f}v6M{mx + 3:.1f} {my + 6:.1f}h6" '
                     f'stroke="{stroke}" stroke-width="1.2"/>')
        self.shapes[tid] = (box(x, y, w, h), {"isExpanded": "false"} if t == "subProcess" else {})
        self._kind(t)
        return box(x, y, w, h)

    def _task_marker(self, t, x, y, c):
        g = (f'<g transform="translate({x:.1f} {y:.1f})" fill="none" stroke="{c}" stroke-width="1" '
             'stroke-linecap="round" stroke-linejoin="round">')
        body = {
            "userTask": '<circle cx="7" cy="4" r="3"/><path d="M1.5 13c0-3.5 2.5-5.5 5.5-5.5s5.5 2 5.5 5.5z"/>',
            "serviceTask": '<circle cx="7" cy="7" r="2.2"/><path d="M7 1v2M7 11v2M1 7h2M11 7h2M2.8 2.8l1.4 1.4'
                           'M9.8 9.8l1.4 1.4M2.8 11.2l1.4-1.4M9.8 4.2l1.4-1.4"/><circle cx="7" cy="7" r="4.4"/>',
            "sendTask": f'<rect x="0.5" y="2.5" width="13" height="9" fill="{c}"/>'
                        '<path d="M0.5 2.5l6.5 5 6.5-5" stroke="#fff"/>',
            "receiveTask": '<rect x="0.5" y="2.5" width="13" height="9"/><path d="M0.5 2.5l6.5 5 6.5-5"/>',
            "manualTask": '<path d="M1 6.5h7.5a1 1 0 0 1 0 2H6M1 6.5V12h8a1 1 0 0 0 0-2M6 8.5h4a1 1 0 0 1 0 2'
                          'M1 6.5l3-4h6a1 1 0 0 1 0 2H6"/>',
            "scriptTask": '<path d="M3 1h9c-2 2-2 4 0 6s2 4 0 6H3c2-2 2-4 0-6S1 3 3 1z"/><path d="M5 4.5h4M5 7h4'
                          'M5 9.5h4"/>',
            "businessRuleTask": '<rect x="0.5" y="1.5" width="13" height="10"/><path d="M0.5 4.5h13M0.5 8h13'
                                'M4.5 4.5v7" />',
        }.get(t)
        return g + body + "</g>" if body else ""

    # ---- events
    def event(self, eid, cx, cy, r=EVENT_R, label="below"):
        o = self._get(eid, EVENTS)
        t, trig = o["type"], o.get("trigger", "none")
        colour = {"startEvent": self.t["event_start"], "endEvent": self.t["event_end"]}.get(t, self.t["event_mid"])
        sw = {"startEvent": 1.4, "endEvent": 3.2}.get(t, 1.2)
        dash = ' stroke-dasharray="3.5 2.5"' if t == "boundaryEvent" and o.get("interrupting") is False else ""
        dash = dash or self._dash(eid)
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{self.t["paper"]}" stroke="{colour}" '
                 f'stroke-width="{sw}"{dash}/>')
        if t in ("intermediateCatchEvent", "intermediateThrowEvent", "boundaryEvent"):
            self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r - 3}" fill="none" stroke="{colour}" '
                     f'stroke-width="1.1"{dash}/>')
        filled = t in ("endEvent", "intermediateThrowEvent")
        self.add(self._trigger(trig, cx, cy, r, colour, filled))
        if o.get("name") and label:
            # label: below | above | right | left | below-right | below-left
            lines = wrap(o["name"], 8.5, 104, True)
            lx, anchor = cx, "middle"
            if label in ("right", "left"):
                ly = cy + 3 - (len(lines) - 1) * 5
                lx, anchor = (cx + r + 5, "start") if label == "right" else (cx - r - 5, "end")
            elif label in ("below-right", "below-left"):
                ly = cy + r + 11
                lx, anchor = (cx + 5, "start") if label == "below-right" else (cx - 5, "end")
            else:
                ly = cy + r + 11 if label == "below" else cy - r - 5 - (len(lines) - 1) * 10
            for ln in lines:
                self.text(lx, ly, ln, 8.5, self.t["ink"], anchor=anchor, weight=600, halo=True)
                ly += 10
        self.shapes[eid] = (box(cx - r, cy - r, 2 * r, 2 * r), {})
        self._kind(f"{t}:{trig}" if trig != "none" else t)
        return box(cx - r, cy - r, 2 * r, 2 * r)

    def _trigger(self, trig, cx, cy, r, c, filled):
        s = r / 16
        f = c if filled else "none"
        g = (f'<g transform="translate({cx:.1f} {cy:.1f}) scale({s:.3f})" fill="{f}" stroke="{c}" '
             'stroke-width="1.2" stroke-linejoin="round" stroke-linecap="round">')
        body = {
            "message": '<rect x="-7" y="-5" width="14" height="10"/><path d="M-7 -5l7 5.5 7-5.5" stroke="'
                       + ("#fff" if filled else c) + '"/>',
            "timer": '<circle r="8.5" fill="none"/><path d="M0 -5.5V0l3.5 2.5" fill="none"/>',
            "error": '<path d="M-6 6l2.5-10 4 6 3.5-8-2 12-4-6z"/>',
            "signal": '<path d="M0 -7.5l7 12.5h-14z"/>',
            "escalation": '<path d="M0 -8l5.5 13-5.5-5-5.5 5z"/>',
            "conditional": '<rect x="-6" y="-7.5" width="12" height="15" fill="none"/><path d="M-3.5 -4h7M-3.5 -1h7'
                           'M-3.5 2h7M-3.5 5h7" fill="none"/>',
            "compensation": '<path d="M-8 0l7 -5v10zM0 0l7-5v10z"/>',
            "terminate": f'<circle r="8" fill="{c}"/>',
            "link": '<path d="M-7 -3h7v-4l7 7-7 7v-4h-7z"/>',
            "cancel": '<path d="M-6 -4l2 -2 4 4 4-4 2 2-4 4 4 4-2 2-4-4-4 4-2-2 4-4z"/>',
        }.get(trig)
        return g + body + "</g>" if body else ""

    # ---- gateways
    def gateway(self, gid, cx, cy, label="above", s=GW):
        o = self._get(gid, GATEWAYS)
        t, c = o["type"], self.t["body"]
        self.add(f'<path d="M{cx:.1f} {cy - s:.1f}L{cx + s:.1f} {cy:.1f}L{cx:.1f} {cy + s:.1f}'
                 f'L{cx - s:.1f} {cy:.1f}Z" fill="{self.t["paper"]}" stroke="{c}" stroke-width="1.3"'
                 f'{self._dash(gid)}/>')
        m = {
            "exclusiveGateway": f'<path d="M{cx - 6:.1f} {cy - 6:.1f}l12 12M{cx + 6:.1f} {cy - 6:.1f}l-12 12" '
                                f'stroke="{c}" stroke-width="3" stroke-linecap="round"/>',
            "parallelGateway": f'<path d="M{cx:.1f} {cy - 9:.1f}v18M{cx - 9:.1f} {cy:.1f}h18" stroke="{c}" '
                               'stroke-width="3" stroke-linecap="round"/>',
            "inclusiveGateway": f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="8" fill="none" stroke="{c}" stroke-width="2.6"/>',
            "eventBasedGateway": f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="10" fill="none" stroke="{c}" stroke-width="1"/>'
                                 f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="8" fill="none" stroke="{c}" stroke-width="1"/>'
                                 f'<path d="M{cx:.1f} {cy - 5:.1f}l4.8 3.5-1.8 5.5h-6l-1.8-5.5z" fill="none" '
                                 f'stroke="{c}" stroke-width="1"/>',
            "complexGateway": f'<path d="M{cx:.1f} {cy - 9:.1f}v18M{cx - 9:.1f} {cy:.1f}h18M{cx - 6.4:.1f} '
                              f'{cy - 6.4:.1f}l12.8 12.8M{cx + 6.4:.1f} {cy - 6.4:.1f}l-12.8 12.8" stroke="{c}" '
                              'stroke-width="2.4" stroke-linecap="round"/>',
        }[t]
        self.add(m)
        if o.get("name") and label:
            # label: above | below | above-right | above-left | below-right | below-left
            lines = wrap(o["name"], 8.5, 110, True)
            up = label.startswith("above")
            ly = cy - s - 6 - (len(lines) - 1) * 10 if up else cy + s + 12
            side = label.split("-")[1] if "-" in label else None
            lx = {"right": cx + 8, "left": cx - 8}.get(side, cx)
            if side:
                ly = cy - s / 2 - 4 - (len(lines) - 1) * 10 if up else cy + s / 2 + 12
                lx = cx + s / 2 + 4 if side == "right" else cx - s / 2 - 4
            anchor = {"right": "start", "left": "end"}.get(side, "middle")
            for ln in lines:
                self.text(lx, ly, ln, 8.5, self.t["ink"], anchor=anchor, weight=600, halo=True)
                ly += 10
        self.shapes[gid] = (box(cx - s, cy - s, 2 * s, 2 * s), {"isMarkerVisible": "true"}
                            if t == "exclusiveGateway" else {})
        self._kind(t)
        return box(cx - s, cy - s, 2 * s, 2 * s)

    # ---- data and artifacts
    def data(self, did, x, y):
        o = self._get(did, DATA)
        c = self.t["body"]
        if o["type"] == "dataObject":
            w, h = 30, 38
            self.add(f'<path d="M{x:.1f} {y:.1f}h{w - 9}l9 9v{h - 9}h-{w}z M{x + w - 9:.1f} {y:.1f}v9h9" '
                     f'fill="{self.t["paper"]}" stroke="{c}" stroke-width="1.2"{self._dash(did)}/>')
        else:
            w, h = 44, 38
            self.add(f'<path d="M{x:.1f} {y + 6:.1f}v{h - 12}a{w / 2} 6 0 0 0 {w} 0v-{h - 12}" '
                     f'fill="{self.t["paper"]}" stroke="{c}" stroke-width="1.2"/>'
                     f'<ellipse cx="{x + w / 2:.1f}" cy="{y + 6:.1f}" rx="{w / 2}" ry="6" fill="{self.t["paper"]}" '
                     f'stroke="{c}" stroke-width="1.2"/><path d="M{x:.1f} {y + 10:.1f}a{w / 2} 6 0 0 0 {w} 0" '
                     f'fill="none" stroke="{c}" stroke-width="1"/>')
        ly = y + h + 11
        for ln in wrap(o["name"], 8.5, 100, True):
            self.text(x + w / 2, ly, ln, 8.5, self.t["ink"], anchor="middle", weight=600, halo=True)
            ly += 10
        self.shapes[did] = (box(x, y, w, h), {})
        self._kind(o["type"])
        return box(x, y, w, h)

    def annotation(self, aid, x, y, w=150):
        o = self._get(aid, ARTIFACTS)
        lines = wrap(o["name"], 8.5, w - 10)
        h = 10 + len(lines) * 11
        c = self.t["muted"]
        self.add(f'<path d="M{x + 10:.1f} {y:.1f}H{x:.1f}V{y + h:.1f}H{x + 10:.1f}" fill="none" '
                 f'stroke="{c}" stroke-width="1.2"/>')
        ty = y + 14
        for ln in lines:
            self.text(x + 6, ty, ln, 8.5, self.t["body"])
            ty += 11
        self.shapes[aid] = (box(x, y, w, h), {})
        return box(x, y, w, h)

    # ---- flows
    def flow(self, points, check, label=None, label_anchor="middle"):
        """A connector through `points`; `check` is the (from, type, to)
        relationship it draws, which must be in the model."""
        f, v, t = check
        ri = next((i for i, r in enumerate(self.rels)
                   if r["from"] == f and r["type"] == v and r["to"] == t), None)
        if ri is None:
            raise ValueError(f"{self.vid}: relationship {f} -{v}-> {t} not in the model")
        r = self.rels[ri]
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        c = self.t["body"]
        a = [f'points="{pts}"', 'fill="none"', f'stroke="{c}"', 'stroke-width="1.2"']
        if v == "sequenceFlow":
            a.append(f'marker-end="url(#{self.arrow})"')
            src = self.obj[f]["type"]
            if r.get("default"):
                a.append(f'marker-start="url(#{self._mk("default")})"')
            elif r.get("condition") and src in ACTIVITIES:
                a.append(f'marker-start="url(#{self._mk("conditional")})"')
            kind = "sequenceFlow"
        elif v == "messageFlow":
            a += ['stroke-dasharray="5 3"', f'marker-start="url(#{self._mk("msg-start")})"',
                  f'marker-end="url(#{self._mk("msg-end")})"']
            kind = "messageFlow"
        elif v == "association":
            a.append('stroke-dasharray="1.5 2.5"')
            kind = None
        else:
            a += ['stroke-dasharray="1.5 2.5"', f'marker-end="url(#{self._mk("data-end")})"']
            kind = "dataAssociation"
        self.add(f'<polyline {" ".join(a)}/>')
        text = r.get("name") or r.get("condition")
        if label is not None and text:
            self.text(label[0], label[1], text, 8.5, self.t["muted"], anchor=label_anchor,
                      italic=True, halo=True)
        self.edges.append((ri, list(points)))
        if kind and kind not in self.flow_kinds:
            self.flow_kinds.append(kind)

    def _mk(self, kind):
        c, p = self.t["body"], self.t["paper"]
        defs = {
            "default": f'<marker id="{{id}}" viewBox="0 0 12 12" refX="0" refY="6" markerWidth="10" '
                       f'markerHeight="10" orient="auto"><path d="M5 2L9 10" stroke="{c}" stroke-width="1.4"/></marker>',
            "conditional": f'<marker id="{{id}}" viewBox="0 0 16 10" refX="0" refY="5" markerWidth="13" '
                           f'markerHeight="8" orient="auto"><path d="M1 5L8 1L15 5L8 9z" fill="{p}" '
                           f'stroke="{c}" stroke-width="1"/></marker>',
            "msg-start": f'<marker id="{{id}}" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" '
                         f'markerHeight="6" orient="auto"><circle cx="5" cy="5" r="3.5" fill="{p}" '
                         f'stroke="{c}" stroke-width="1.2"/></marker>',
            "msg-end": f'<marker id="{{id}}" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="9" '
                       f'markerHeight="9" orient="auto"><path d="M1 1L11 6L1 11z" fill="{p}" stroke="{c}" '
                       f'stroke-width="1.1"/></marker>',
            "data-end": f'<marker id="{{id}}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
                        f'markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="{c}" '
                        f'stroke-width="1.2"/></marker>',
        }
        return self.define(kind, defs[kind])

    # ---- legend
    def legend(self, y):
        """Key of the BPMN symbols drawn. Returns the y below it."""
        W = self.W
        self.add(f'<line x1="16" y1="{y:.1f}" x2="{W - 16}" y2="{y:.1f}" stroke="{self.t["rule"]}"/>')
        y += 12
        x = 16
        entries = list(self.kinds) + list(self.flow_kinds)
        if self.used_dashed:
            entries.append("dashed")
        saved = self.shapes.copy(), list(self.kinds)
        for k in entries:
            base, _, trig = k.partition(":")
            text = LABEL.get(base, {"sequenceFlow": "Sequence flow", "messageFlow": "Message flow",
                                    "dataAssociation": "Data association",
                                    "dashed": "Proposed / not built"}.get(base, base))
            if trig:
                text = f"{trig.capitalize()} {text[0].lower()}{text[1:]}"
            lw = text_width(text, 8.5) + 34
            if x + lw > W - 16:
                x, y = 16, y + 22
            self._legend_symbol(base, trig, x, y)
            self.text(x + 28, y + 9, text, 8.5, self.t["body"])
            x += lw + 8
        self.shapes, self.kinds = saved
        return y + 22

    def _legend_symbol(self, base, trig, x, y):
        c = self.t["body"]
        cy = y + 5.5
        if base in EVENTS:
            colour = {"startEvent": self.t["event_start"], "endEvent": self.t["event_end"]}.get(base, self.t["event_mid"])
            sw = {"startEvent": 1.2, "endEvent": 2.6}.get(base, 1)
            self.add(f'<circle cx="{x + 11}" cy="{cy}" r="7.5" fill="{self.t["paper"]}" stroke="{colour}" '
                     f'stroke-width="{sw}"/>')
            if base in ("intermediateCatchEvent", "intermediateThrowEvent", "boundaryEvent"):
                self.add(f'<circle cx="{x + 11}" cy="{cy}" r="5.5" fill="none" stroke="{colour}" stroke-width="0.9"/>')
            if trig:
                self.add(self._trigger(trig, x + 11, cy, 7.5, colour, base in ("endEvent", "intermediateThrowEvent")))
        elif base in GATEWAYS:
            self.add(f'<path d="M{x + 11} {cy - 8}l8 8-8 8-8-8z" fill="{self.t["paper"]}" stroke="{c}"/>')
            if base == "exclusiveGateway":
                self.add(f'<path d="M{x + 8.5} {cy - 2.5}l5 5M{x + 13.5} {cy - 2.5}l-5 5" stroke="{c}" stroke-width="1.6"/>')
            elif base == "parallelGateway":
                self.add(f'<path d="M{x + 11} {cy - 4}v8M{x + 7} {cy}h8" stroke="{c}" stroke-width="1.6"/>')
            elif base == "inclusiveGateway":
                self.add(f'<circle cx="{x + 11}" cy="{cy}" r="3.5" fill="none" stroke="{c}" stroke-width="1.4"/>')
            else:
                self.add(f'<circle cx="{x + 11}" cy="{cy}" r="3.8" fill="none" stroke="{c}" stroke-width="0.9"/>')
        elif base in ACTIVITIES:
            sw = 2.2 if base == "callActivity" else 1
            self.add(f'<rect x="{x}" y="{cy - 7}" width="22" height="14" rx="3.5" fill="{self.t["paper"]}" '
                     f'stroke="{self.t["task"][0]}" stroke-width="{sw}"/>')
            m = self._task_marker(base, x + 4, cy - 5, self.t["task"][0])
            if m:
                self.add(f'<g transform="translate({x + 4} {cy - 5}) scale(0.65) translate({-(x + 4)} {-(cy - 5)})">{m}</g>')
        elif base == "dataObject":
            self.add(f'<path d="M{x + 5} {cy - 7}h8l4 4v10h-12z" fill="{self.t["paper"]}" stroke="{c}"/>')
        elif base == "dataStore":
            self.add(f'<path d="M{x + 3} {cy - 4}v9a8 2.5 0 0 0 16 0v-9" fill="{self.t["paper"]}" stroke="{c}"/>'
                     f'<ellipse cx="{x + 11}" cy="{cy - 4}" rx="8" ry="2.5" fill="{self.t["paper"]}" stroke="{c}"/>')
        elif base == "sequenceFlow":
            self.add(f'<line x1="{x}" y1="{cy}" x2="{x + 22}" y2="{cy}" stroke="{c}" stroke-width="1.2" '
                     f'marker-end="url(#{self.arrow})"/>')
        elif base == "messageFlow":
            self.add(f'<line x1="{x + 2}" y1="{cy}" x2="{x + 22}" y2="{cy}" stroke="{c}" stroke-width="1.2" '
                     f'stroke-dasharray="4 2.5" marker-start="url(#{self._mk("msg-start")})" '
                     f'marker-end="url(#{self._mk("msg-end")})"/>')
        elif base == "dataAssociation":
            self.add(f'<line x1="{x}" y1="{cy}" x2="{x + 22}" y2="{cy}" stroke="{c}" stroke-width="1.2" '
                     f'stroke-dasharray="1.5 2.5" marker-end="url(#{self._mk("data-end")})"/>')
        elif base == "dashed":
            self.add(f'<rect x="{x}" y="{cy - 6}" width="22" height="12" rx="3" fill="{self.t["paper"]}" '
                     f'stroke="{c}" stroke-dasharray="3 2"/>')

    def manifest(self):
        return {"view": self.vid, "title": self.title, "metamodel": "bpmn",
                "objects": list(self.shapes), "relationships": [relationship_id(self.rels[i]) for i, _ in self.edges],
                "warnings": self.warnings}


# ------------------------------------------------------------------ XML

NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc": "http://www.omg.org/spec/DD/20100524/DC",
    "di": "http://www.omg.org/spec/DD/20100524/DI",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}


def _a(**kw):
    return "".join(f" {k}={quoteattr(str(v))}" for k, v in kw.items() if v is not None)


def to_bpmn_xml(model, view=None):
    """BPMN 2.0 XML (semantic model + BPMNDI from `view` when given)."""
    validate_bpmn(model)
    objs, rels = model["objects"], model["relationships"]
    sc = _Scope(model)
    byid = sc.byid
    rid = [relationship_id(r) for r in rels]
    slug = re.sub(r"[^A-Za-z0-9_]", "_", model.get("name", "model")) or "model"
    pools = [o for o in objs if o["type"] == "participant"]
    proc_of = {p["id"]: f"Process_{p['id']}" for p in pools}
    implicit = f"Process_{slug}"

    def proc(oid):
        p = sc.participant(oid)
        return proc_of[p] if p else implicit

    seq_in, seq_out = {}, {}
    for i, r in enumerate(rels):
        if r["type"] == "sequenceFlow":
            seq_out.setdefault(r["from"], []).append(rid[i])
            seq_in.setdefault(r["to"], []).append(rid[i])
    default_of = {r["from"]: rid[i] for i, r in enumerate(rels) if r["type"] == "sequenceFlow" and r.get("default")}
    inputs = {}
    outputs = {}
    for i, r in enumerate(rels):
        if r["type"] == "dataInput":
            inputs.setdefault(r["to"], []).append(i)
        elif r["type"] == "dataOutput":
            outputs.setdefault(r["from"], []).append(i)

    out = ['<?xml version="1.0" encoding="UTF-8"?>\n',
           f'<bpmn:definitions xmlns:bpmn="{NS["bpmn"]}" xmlns:bpmndi="{NS["bpmndi"]}" '
           f'xmlns:dc="{NS["dc"]}" xmlns:di="{NS["di"]}" xmlns:xsi="{NS["xsi"]}" '
           f'id="Definitions_{slug}" targetNamespace="urn:arch-diagram:{slug}" '
           'exporter="arch-diagram" exporterVersion="2.0">\n']
    collab = f"Collaboration_{slug}"
    if pools:
        out.append(f'  <bpmn:collaboration id="{collab}">\n')
        for p in pools:
            out.append(f'    <bpmn:participant{_a(id=p["id"], name=p["name"], processRef=proc_of[p["id"]])}/>\n')
        for i, r in enumerate(rels):
            if r["type"] == "messageFlow":
                out.append(f'    <bpmn:messageFlow{_a(id=rid[i], name=r.get("name"), sourceRef=r["from"], targetRef=r["to"])}/>\n')
        out.append("  </bpmn:collaboration>\n")

    def doc(o, pad):
        return f'{pad}<bpmn:documentation>{escape(o["description"])}</bpmn:documentation>\n' if o.get("description") else ""

    def node_xml(o, pad):
        t, oid = o["type"], o["id"]
        attrs = {"id": oid, "name": o.get("name")}
        if t in ("exclusiveGateway", "inclusiveGateway", "complexGateway") or t in ACTIVITIES:
            attrs["default"] = default_of.get(oid)
        if t == "boundaryEvent":
            attrs["attachedToRef"] = o["attachedTo"]
            if o.get("interrupting") is False:
                attrs["cancelActivity"] = "false"
        if t == "subProcess" and o.get("triggeredByEvent"):
            attrs["triggeredByEvent"] = "true"
        s = [f"{pad}<bpmn:{t}{_a(**attrs)}>\n", doc(o, pad + "  ")]
        s += [f"{pad}  <bpmn:incoming>{f}</bpmn:incoming>\n" for f in seq_in.get(oid, [])]
        s += [f"{pad}  <bpmn:outgoing>{f}</bpmn:outgoing>\n" for f in seq_out.get(oid, [])]
        if t in ACTIVITIES:
            for i in inputs.get(oid, []):
                s.append(f'{pad}  <bpmn:property id="Property_{rid[i]}" name="__targetRef_placeholder"/>\n')
            for i in inputs.get(oid, []):
                s.append(f'{pad}  <bpmn:dataInputAssociation id="{rid[i]}">\n{pad}    <bpmn:sourceRef>{rels[i]["from"]}'
                         f'</bpmn:sourceRef>\n{pad}    <bpmn:targetRef>Property_{rid[i]}</bpmn:targetRef>\n'
                         f'{pad}  </bpmn:dataInputAssociation>\n')
            for i in outputs.get(oid, []):
                s.append(f'{pad}  <bpmn:dataOutputAssociation id="{rid[i]}">\n{pad}    <bpmn:targetRef>'
                         f'{rels[i]["to"]}</bpmn:targetRef>\n{pad}  </bpmn:dataOutputAssociation>\n')
        if t in EVENTS:
            if t in CATCHING:
                for i in outputs.get(oid, []):
                    s.append(f'{pad}  <bpmn:dataOutputAssociation id="{rid[i]}">\n{pad}    <bpmn:targetRef>'
                             f'{rels[i]["to"]}</bpmn:targetRef>\n{pad}  </bpmn:dataOutputAssociation>\n')
            else:
                ins = inputs.get(oid, [])
                for i in ins:
                    s.append(f'{pad}  <bpmn:dataInput id="DataInput_{rid[i]}"/>\n')
                for i in ins:
                    s.append(f'{pad}  <bpmn:dataInputAssociation id="{rid[i]}">\n{pad}    <bpmn:sourceRef>'
                             f'{rels[i]["from"]}</bpmn:sourceRef>\n{pad}    <bpmn:targetRef>DataInput_{rid[i]}'
                             f'</bpmn:targetRef>\n{pad}  </bpmn:dataInputAssociation>\n')
                if ins:
                    s.append(f'{pad}  <bpmn:inputSet>' + "".join(
                        f"<bpmn:dataInputRefs>DataInput_{rid[i]}</bpmn:dataInputRefs>" for i in ins)
                        + "</bpmn:inputSet>\n")
            trig = o.get("trigger", "none")
            if trig != "none":
                ed = {"compensation": "compensate"}.get(trig, trig) + "EventDefinition"
                eid = f"{oid}_ed"
                if trig == "conditional":
                    s.append(f'{pad}  <bpmn:{ed} id="{eid}"><bpmn:condition xsi:type="bpmn:tFormalExpression">'
                             f'{escape(o.get("condition", o.get("name", "condition")))}</bpmn:condition></bpmn:{ed}>\n')
                elif trig == "link":
                    s.append(f'{pad}  <bpmn:{ed}{_a(id=eid, name=o.get("link", o.get("name", oid)))}/>\n')
                elif trig == "timer" and o.get("timer"):
                    s.append(f'{pad}  <bpmn:{ed} id="{eid}"><bpmn:timeDuration xsi:type="bpmn:tFormalExpression">'
                             f'{escape(o["timer"])}</bpmn:timeDuration></bpmn:{ed}>\n')
                else:
                    s.append(f'{pad}  <bpmn:{ed} id="{eid}"/>\n')
        if t == "subProcess":
            s += scope_xml(oid, pad + "  ")
        s.append(f"{pad}</bpmn:{t}>\n")
        return s

    def in_scope(o, scope_id):
        if o["type"] == "boundaryEvent":
            return sc.scope(o["attachedTo"]) == scope_id if o.get("attachedTo") in byid else False
        return sc.scope(o["id"]) == scope_id

    def scope_xml(scope_id, pad, process=None):
        s = []
        members = [o for o in objs if o["type"] in FLOW_NODES + DATA + ARTIFACTS and in_scope(o, scope_id)]
        if process and scope_id is None:
            members = [o for o in objs if o["type"] in FLOW_NODES + DATA + ARTIFACTS
                       and sc.participant(o["id"]) is None and in_scope(o, None)]
        if scope_id is not None and byid[scope_id]["type"] == "participant":
            members += [o for o in objs if o["type"] in ("dataStore", "textAnnotation") and not o.get("parent")
                        and scope_id == (pools[0]["id"] if pools else None)]
        ids = {o["id"] for o in members}
        for o in members:
            if o["type"] in FLOW_NODES:
                s += node_xml(o, pad)
            elif o["type"] == "dataObject":
                s.append(f'{pad}<bpmn:dataObject id="DataObject_{o["id"]}"/>\n')
                s.append(f'{pad}<bpmn:dataObjectReference{_a(id=o["id"], name=o["name"], dataObjectRef="DataObject_" + o["id"])}/>\n')
            elif o["type"] == "dataStore":
                s.append(f'{pad}<bpmn:dataStoreReference{_a(id=o["id"], name=o["name"], dataStoreRef="DataStore_" + o["id"])}/>\n')
        for i, r in enumerate(rels):
            if r["type"] == "sequenceFlow" and r["from"] in ids:
                attrs = _a(id=rid[i], name=r.get("name"), sourceRef=r["from"], targetRef=r["to"])
                if r.get("condition"):
                    s.append(f'{pad}<bpmn:sequenceFlow{attrs}><bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">'
                             f'{escape(r["condition"])}</bpmn:conditionExpression></bpmn:sequenceFlow>\n')
                else:
                    s.append(f"{pad}<bpmn:sequenceFlow{attrs}/>\n")
        for o in members:
            if o["type"] == "textAnnotation":
                s.append(f'{pad}<bpmn:textAnnotation id="{o["id"]}"><bpmn:text>{escape(o["name"])}</bpmn:text>'
                         "</bpmn:textAnnotation>\n")
        for i, r in enumerate(rels):
            note = r["from"] if byid[r["from"]]["type"] == "textAnnotation" else r["to"]
            if r["type"] == "association" and note in ids:
                s.append(f'{pad}<bpmn:association{_a(id=rid[i], sourceRef=r["from"], targetRef=r["to"])}/>\n')
        return s

    def lanes_xml(parent, pad):
        kids = [o for o in objs if o["type"] == "lane" and o.get("parent") == parent]
        if not kids:
            return []
        s = []
        for ln in kids:
            s.append(f'{pad}<bpmn:lane{_a(id=ln["id"], name=ln.get("name"))}>\n')
            for o in objs:
                if o["type"] in FLOW_NODES and (ln["id"] in sc.ancestors(o["id"])) and \
                        sc.scope(o["id"]) == sc.participant(ln["id"]):
                    s.append(f'{pad}  <bpmn:flowNodeRef>{o["id"]}</bpmn:flowNodeRef>\n')
            sub = lanes_xml(ln["id"], pad + "    ")
            if sub:
                s.append(f'{pad}  <bpmn:childLaneSet id="LaneSet_{ln["id"]}">\n')
                s += sub
                s.append(f"{pad}  </bpmn:childLaneSet>\n")
            s.append(f"{pad}</bpmn:lane>\n")
        return s

    for o in objs:
        if o["type"] == "dataStore":
            out.append(f'  <bpmn:dataStore{_a(id="DataStore_" + o["id"], name=o["name"])}/>\n')
    if pools:
        for p in pools:
            out.append(f'  <bpmn:process{_a(id=proc_of[p["id"]], name=p["name"], isExecutable="false")}>\n')
            ln = lanes_xml(p["id"], "      ")
            if ln:
                out.append(f'    <bpmn:laneSet id="LaneSet_{p["id"]}">\n')
                out += ln
                out.append("    </bpmn:laneSet>\n")
            out += scope_xml(p["id"], "    ")
            out.append("  </bpmn:process>\n")
    else:
        out.append(f'  <bpmn:process{_a(id=implicit, name=model.get("name"), isExecutable="false")}>\n')
        out += scope_xml(None, "    ", process=True)
        out.append("  </bpmn:process>\n")

    if view is not None:
        plane = collab if pools else implicit
        out.append(f'  <bpmndi:BPMNDiagram id="Diagram_{view.slug}"{_a(name=view.title)}>\n'
                   f'    <bpmndi:BPMNPlane id="Plane_{view.slug}" bpmnElement="{plane}">\n')
        for oid, (b, extra) in view.shapes.items():
            out.append(f'      <bpmndi:BPMNShape id="{oid}_di" bpmnElement="{oid}"{_a(**extra)}>\n'
                       f'        <dc:Bounds x="{b["x"]:.0f}" y="{b["y"]:.0f}" width="{b["w"]:.0f}" '
                       f'height="{b["h"]:.0f}"/>\n      </bpmndi:BPMNShape>\n')
        for ri, pts in view.edges:
            out.append(f'      <bpmndi:BPMNEdge id="{rid[ri]}_di" bpmnElement="{rid[ri]}">\n')
            for x, y in pts:
                out.append(f'        <di:waypoint x="{x:.0f}" y="{y:.0f}"/>\n')
            out.append("      </bpmndi:BPMNEdge>\n")
        out.append("    </bpmndi:BPMNPlane>\n  </bpmndi:BPMNDiagram>\n")
    out.append("</bpmn:definitions>\n")
    return "".join(out)


def write_bpmn_xml(model, path, view=None):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_bpmn_xml(model, view))
    return path
