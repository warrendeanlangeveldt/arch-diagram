"""Automatic layout for views written in the view language (ealib.dsl).

EA views (ArchiMate, TOGAF, Essential, CoreEA)
- Layer bands, top to bottom in the metamodel's band order (Business above
  Application above Technology …). Within a band, relationships marked
  "layout": "up" in the metamodel put their target above their source
  (realises, provides), "down" below it (composition, hosted on); every
  other relationship runs across the row.
- Containers lay out their children the same way, inside the box, before the
  container is placed as one block.
- Rows are ordered to reduce crossings, then each box is pulled over the
  boxes it connects to (isotonic placement keeps the order and the gaps), so
  most lines come out straight. Rows wider than the page wrap.
- Lines are routed orthogonally on a grid that keeps them CLEAR px off every
  box they don't belong to, with penalties for bends, shared segments and
  crossings. Labels go where they collide with nothing.

BPMN views
- Pools stacked in model order, lanes inside them; flow nodes in columns by
  their longest sequence-flow distance from a start, and in tracks within
  their lane; boundary events on their activity's lower edge; data and
  annotations beside what they're associated with.
"""
import heapq

from .common import box, text_width, wrap
from .metamodel import metamodel_of
from .views import View, make_theme

GAP_X, GAP_Y = 40, 44
PAD, PAD_TOP, PAD_BOTTOM = 16, 10, 14
CLEAR = 8                     # lines keep this far from boxes
EPS = 0.2
BEND, OVERLAP, CROSS, PORT_USED = 40, 5.0, 14, 70
PILL_OVERHANG = 14


class LayoutError(ValueError):
    pass


# ================================================================== routing

def _ports(r, kind="box"):
    """Candidate ports of rect r=(x, y, w, h): (px, py, nx, ny, cost), on
    the same 0.1px grid as the routing lines."""
    return [(round(px, 1), round(py, 1), nx, ny, c) for px, py, nx, ny, c in _raw_ports(r, kind)]


def _raw_ports(r, kind):
    x, y, w, h = r
    if kind == "side":
        kind = "box"
    cx, cy = x + w / 2, y + h / 2
    out = [(cx, y, 0, -1, 0), (cx, y + h, 0, 1, 0), (x, cy, -1, 0, 0), (x + w, cy, 1, 0, 0)]
    if kind == "box":
        if w >= 90:
            for f in (0.3, 0.7):
                out += [(x + w * f, y, 0, -1, 6), (x + w * f, y + h, 0, 1, 6)]
        if h >= 70:
            for f in (0.3, 0.7):
                out += [(x, y + h * f, -1, 0, 6), (x + w, y + h * f, 1, 0, 6)]
    return out


class Router:
    """Orthogonal connector routing over a sparse grid built from the boxes'
    clearance lines, ports and the channels between them."""

    def __init__(self, width, height, boxes):
        self.W, self.H = width, height
        self.boxes = boxes                  # every box drawn, for channel lines
        self.used_h, self.used_v = {}, {}   # (y, x0, x1) / (x, y0, y1) grid segments
        self.pts_h, self.pts_v = set(), set()
        self.ports = {}

    def _lines(self, rects, extra):
        xs, ys = set(), set()
        for (x, y, w, h) in rects:
            xs |= {x - CLEAR, x + w + CLEAR}
            ys |= {y - CLEAR, y + h + CLEAR}
        for px, py in extra:
            xs.add(px)
            ys.add(py)

        def fill(vals, lo, hi):
            vals = sorted(v for v in vals if lo <= v <= hi)
            out = set(vals)
            for a, b in zip(vals, vals[1:]):
                if b - a > 2 * CLEAR:
                    out.add((a + b) / 2)
                if b - a > 6 * CLEAR:
                    out |= {a + (b - a) / 3, a + 2 * (b - a) / 3}
            return sorted({round(v, 1) for v in out})

        return fill(xs, 4, self.W - 4), fill(ys, 4, self.H - 4)

    def route(self, sbox, tbox, obstacles, skind="box", tkind="box", soft=(), forbid=()):
        """Points from sbox's border to tbox's border avoiding `obstacles`
        (rects); sbox and tbox are avoided too, apart from their ports.
        `soft` rects (the containers the line has to leave or enter) may be
        crossed but not run along. Ports at the points in `forbid` aren't
        used."""
        obs = [o for o in obstacles] + [sbox, tbox]
        sp = [p for p in _ports(sbox, skind)]
        tp = [p for p in _ports(tbox, tkind)]
        for ports, b, kind in ((sp, sbox, skind), (tp, tbox, tkind)):
            if kind == "side":           # a pool: anywhere along its top or bottom
                x, y, w, h = b
                for k in range(1, int(w // 24)):
                    px = round(x + 24 * k, 1)
                    ports += [(px, round(y, 1), 0, -1, 2), (px, round(y + h, 1), 0, 1, 2)]
        # where the boxes face each other, a straight pair of ports
        (sx, sy, sw, sh), (tx, ty, tw, th) = [tuple(round(v, 1) for v in b) for b in (sbox, tbox)]
        if skind == "box" and tkind == "box":
            lo, hi = max(sy, ty) + 6, min(sy + sh, ty + th) - 6
            if hi >= lo:
                m = round((lo + hi) / 2, 1)
                if sx + sw <= tx:
                    sp.append((sx + sw, m, 1, 0, 0))
                    tp.append((tx, m, -1, 0, 0))
                elif tx + tw <= sx:
                    sp.append((sx, m, -1, 0, 0))
                    tp.append((tx + tw, m, 1, 0, 0))
            lo, hi = max(sx, tx) + 10, min(sx + sw, tx + tw) - 10
            if hi >= lo:
                m = round((lo + hi) / 2, 1)
                if sy + sh <= ty:
                    sp.append((m, sy + sh, 0, 1, 0))
                    tp.append((m, ty, 0, -1, 0))
                elif ty + th <= sy:
                    sp.append((m, sy, 0, -1, 0))
                    tp.append((m, ty + th, 0, 1, 0))
        if forbid:
            sp = [p for p in sp if (p[0], p[1]) not in forbid]
            tp = [p for p in tp if (p[0], p[1]) not in forbid]
        stub = lambda p: (round(p[0] + p[2] * CLEAR, 1), round(p[1] + p[3] * CLEAR, 1))  # noqa: E731
        extra = [stub(p) for p in sp + tp] + [(p[0], p[1]) for p in sp + tp]
        xs, ys = self._lines(self.boxes + obs, extra)
        xi = {v: i for i, v in enumerate(xs)}
        yi = {v: i for i, v in enumerate(ys)}

        # grid values are rounded to 0.1px, so the clearance test allows for it
        def inside(px, py):
            for (x, y, w, h) in obs:
                if (x - CLEAR + EPS < px < x + w + CLEAR - EPS
                        and y - CLEAR + EPS < py < y + h + CLEAR - EPS):
                    return True
            return False

        blocked_cache = {}

        def along(a, b):
            for (x, y, w, h) in soft:
                if a[1] == b[1]:
                    lo, hi = min(a[0], b[0]), max(a[0], b[0])
                    if hi > x and lo < x + w and (abs(a[1] - y) < CLEAR - EPS or abs(a[1] - y - h) < CLEAR - EPS):
                        return True
                else:
                    lo, hi = min(a[1], b[1]), max(a[1], b[1])
                    if hi > y and lo < y + h and (abs(a[0] - x) < CLEAR - EPS or abs(a[0] - x - w) < CLEAR - EPS):
                        return True
            return False

        def blocked(a, b):
            k = (a, b)
            if k not in blocked_cache:
                blocked_cache[k] = (inside((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) or inside(*b)
                                    or along(a, b))
            return blocked_cache[k]

        goals = {}
        for p in tp:
            s = stub(p)
            if s[0] in xi and s[1] in yi and not self._outside(s):
                cost = p[4] + PORT_USED * self.ports.get((round(p[0], 1), round(p[1], 1)), 0)
                goals.setdefault(s, []).append((p, cost))
        if not goals:
            return None

        def h(pt):
            return min(abs(pt[0] - g[0]) + abs(pt[1] - g[1]) for g in goals)

        heap, best, came = [], {}, {}
        n = 0
        for p in sp:
            s = stub(p)
            if s[0] not in xi or s[1] not in yi or self._outside(s):
                continue
            g = p[4] + PORT_USED * self.ports.get((round(p[0], 1), round(p[1], 1)), 0)
            d = (p[2], p[3])
            st = (s, d)
            if g < best.get(st, 1e18):
                best[st] = g
                came[st] = ("start", p)
                n += 1
                heapq.heappush(heap, (g + h(s), n, g, s, d))
        done = None
        while heap:
            f, _, g, pt, d = heapq.heappop(heap)
            if pt == "goal":
                done = d
                break
            if g > best.get((pt, d), 1e18):
                continue
            if pt in goals:
                for p, cost in goals[pt]:
                    final = g + cost + (0 if d == (-p[2], -p[3]) else BEND)
                    if (-p[2], -p[3]) == (-d[0], -d[1]):
                        continue            # would arrive backwards
                    n += 1
                    heapq.heappush(heap, (final, n, final, "goal", ((pt, d), p)))
            i, j = xi[pt[0]], yi[pt[1]]
            for nd in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if nd == (-d[0], -d[1]):
                    continue
                ni, nj = i + nd[0], j + nd[1]
                if not (0 <= ni < len(xs) and 0 <= nj < len(ys)):
                    continue
                q = (xs[ni], ys[nj])
                if blocked(pt, q):
                    continue
                length = abs(q[0] - pt[0]) + abs(q[1] - pt[1])
                cost = length + (BEND if nd != d else 0)
                if nd[1] == 0:
                    key = (pt[1], min(pt[0], q[0]), max(pt[0], q[0]))
                    cost += OVERLAP * length * self.used_h.get(key, 0)
                    if q in self.pts_v:
                        cost += CROSS
                else:
                    key = (pt[0], min(pt[1], q[1]), max(pt[1], q[1]))
                    cost += OVERLAP * length * self.used_v.get(key, 0)
                    if q in self.pts_h:
                        cost += CROSS
                ng = g + cost
                st = (q, nd)
                if ng < best.get(st, 1e18):
                    best[st] = ng
                    came[st] = (pt, d)
                    n += 1
                    heapq.heappush(heap, (ng + h(q), n, ng, q, nd))
        if done is None:
            return None
        (last, d), tport = done
        path = [(tport[0], tport[1]), last]
        st = (last, d)
        while True:
            prev = came[st]
            if prev[0] == "start":
                sport = prev[1]
                break
            path.append(prev[0])
            st = prev
        path.append((sport[0], sport[1]))
        path.reverse()
        self.last = (path, [(round(p[0], 1), round(p[1], 1)) for p in (sport, tport)])
        self.occupy(self.last, 1)
        return _simplify(path)

    def occupy(self, footprint, sign):
        """Add (sign 1) or remove (sign -1) a routed path's use of the grid
        and its ports."""
        path, ports = footprint
        for k in ports:
            self.ports[k] = self.ports.get(k, 0) + sign
        for a, b in zip(path[1:-1], path[2:-1]):
            if a[1] == b[1]:
                k = (a[1], min(a[0], b[0]), max(a[0], b[0]))
                self.used_h[k] = self.used_h.get(k, 0) + sign
            else:
                k = (a[0], min(a[1], b[1]), max(a[1], b[1]))
                self.used_v[k] = self.used_v.get(k, 0) + sign
        pts = set(path[1:-1])
        if sign > 0:
            for a, b in zip(path[1:-1], path[2:-1]):
                (self.pts_h if a[1] == b[1] else self.pts_v).update((a, b))
        else:
            self.pts_h = {q for q in self.pts_h if q not in pts or self._still_used(q, "h")}
            self.pts_v = {q for q in self.pts_v if q not in pts or self._still_used(q, "v")}

    def _still_used(self, q, axis):
        used = self.used_h if axis == "h" else self.used_v
        for k, n in used.items():
            if n <= 0:
                continue
            if axis == "h" and k[0] == q[1] and k[1] <= q[0] <= k[2]:
                return True
            if axis == "v" and k[0] == q[0] and k[1] <= q[1] <= k[2]:
                return True
        return False

    def _outside(self, pt):
        return not (0 < pt[0] < self.W and 0 < pt[1] < self.H)


def _crossings(p, q):
    """Points where two orthogonal polylines cross (not just touch)."""
    n = 0
    for a, b in zip(p, p[1:]):
        for c, d in zip(q, q[1:]):
            if a[1] == b[1] and c[0] == d[0]:
                h, v = (a, b), (c, d)
            elif a[0] == b[0] and c[1] == d[1]:
                h, v = (c, d), (a, b)
            else:
                continue
            x0, x1 = sorted((h[0][0], h[1][0]))
            y0, y1 = sorted((v[0][1], v[1][1]))
            if x0 < v[0][0] < x1 and y0 < h[0][1] < y1:
                n += 1
    return n


def route_all(router, jobs):
    """Route `jobs` [(key, sbox, tbox, obstacles, skind, tkind, soft)] in
    order, then untangle two lines that share a box and cross. Routing one
    line at a time, the first takes the port that suits it and can leave the
    second only a port it has to cross to reach, whichever goes first. So
    the pair is routed again three ways: in the other order, and with each
    line in turn kept off the port it used on the shared box (it goes
    first, the other line routes around it). The way that crosses least is
    kept, if it crosses less than before. Returns ({key: points}, [keys the
    grid found no route for, drawn as a plain elbow])."""
    out, prints = {}, {}

    def one(job, forbid=()):
        key, sbox, tbox, obstacles, sk, tk, soft = job
        pts = router.route(sbox, tbox, obstacles, sk, tk, soft, forbid)
        if pts is None:
            return _fallback(sbox, tbox), None
        return pts, router.last

    for job in jobs:
        out[job[0]], prints[job[0]] = one(job)

    def total(keys):
        return sum(_crossings(out[a], out[b]) for i, a in enumerate(keys) for b in keys[i + 1:])

    keys = [j[0] for j in jobs]
    byk = {j[0]: j for j in jobs}
    for _ in range(3):
        changed = False
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                ja, jb = byk[a], byk[b]
                share = {tuple(ja[1]), tuple(ja[2])} & {tuple(jb[1]), tuple(jb[2])}
                if not share or not _crossings(out[a], out[b]):
                    continue
                before = total(keys) + len(keys) * sum(prints[k] is None for k in keys)
                saved = {k: (out[k], prints[k]) for k in (a, b)}
                shared = [r for r in share]
                tries = [((b, ()), (a, ()))]
                for first, second in ((a, b), (b, a)):
                    used = _ports_on(prints[first], shared)
                    if used:
                        tries.append(((first, used), (second, ())))
                best = None
                for attempt in tries:
                    for k in (a, b):
                        if prints[k]:
                            router.occupy(prints[k], -1)
                    for k, forbid in attempt:
                        out[k], prints[k] = one(byk[k], forbid)
                    score = total(keys) + len(keys) * sum(prints[k] is None for k in keys)
                    if score < before and (best is None or score < best[0]):
                        best = (score, {k: (out[k], prints[k]) for k in (a, b)})
                    for k in (a, b):
                        if prints[k]:
                            router.occupy(prints[k], -1)
                    for k in (a, b):
                        out[k], prints[k] = saved[k]
                        if prints[k]:
                            router.occupy(prints[k], 1)
                if best is None:
                    continue
                for k in (a, b):
                    if prints[k]:
                        router.occupy(prints[k], -1)
                for k in (a, b):
                    out[k], prints[k] = best[1][k]
                    if prints[k]:
                        router.occupy(prints[k], 1)
                changed = True
        if not changed:
            break
    return out, [k for k in keys if prints[k] is None]


def _ports_on(footprint, rects):
    """The ports of a routed line (its footprint) that sit on one of `rects`."""
    if not footprint:
        return ()
    out = []
    for px, py in footprint[1]:
        for x, y, w, h in rects:
            if x - EPS <= px <= x + w + EPS and y - EPS <= py <= y + h + EPS:
                out.append((px, py))
    return tuple(out)


def crossing_pairs(lines):
    """[(key a, key b)] for every two lines {key: points} that cross."""
    keys = list(lines)
    return [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:]
            if _crossings(lines[a], lines[b])]


def _simplify(pts):
    out = [pts[0]]
    for p in pts[1:]:
        if p == out[-1]:
            continue
        if len(out) >= 2:
            a, b = out[-2], out[-1]
            if (a[0] == b[0] == p[0]) or (a[1] == b[1] == p[1]):
                out[-1] = p
                continue
        out.append(p)
    return out


def _shorten(pts, end=2.0, start=0.0):
    pts = [list(p) for p in pts]
    for idx, amount in ((-1, end), (0, start)):
        if not amount or len(pts) < 2:
            continue
        a, b = pts[idx], pts[idx - 1 if idx == -1 else 1]
        dx, dy = a[0] - b[0], a[1] - b[1]
        L = abs(dx) + abs(dy)
        if L > amount * 2:
            a[0] -= amount * (dx / L)
            a[1] -= amount * (dy / L)
    return [tuple(p) for p in pts]


def _overlap(a, b):
    return not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])


def _seg_hits(rect, seg):
    (x1, y1), (x2, y2) = seg
    sx, sy = min(x1, x2), min(y1, y2)
    return _overlap(rect, (sx - 0.5, sy - 0.5, abs(x2 - x1) + 1, abs(y2 - y1) + 1))


def place_label(text, size, pts, solid, labels, segments, own, W, H):
    """Where to put an edge label: (x, y, anchor, rect, clean) beside one of
    the edge's segments, avoiding boxes (`solid`), other labels and other
    lines. `clean` is False when every spot touches a box or another label,
    or runs off the page."""
    tw = text_width(text, size) * 1.05
    th = size + 2
    best, best_score = None, None
    segs = list(zip(pts, pts[1:]))
    for k, (a, b) in enumerate(segs):
        L = abs(b[0] - a[0]) + abs(b[1] - a[1])
        if a[1] == b[1]:
            if L < 18:
                continue
            for f in (0.5, 0.3, 0.7):
                mx = a[0] + (b[0] - a[0]) * f
                for dy, anchor in ((-5, "middle"), (12 + size * 0.1, "middle")):
                    ly = a[1] + dy
                    rect = (mx - tw / 2, ly - size, tw, th)
                    cand = (mx, ly, anchor, rect, L, f, 0 if dy < 0 else 4)
                    best, best_score = _better(cand, best, best_score, tw, solid, labels, segments, own, W, H)
        else:
            if L < 22:
                continue
            for f in (0.5, 0.3, 0.7):
                my = a[1] + (b[1] - a[1]) * f + size * 0.35
                for dx, anchor in ((5, "start"), (-5, "end")):
                    lx = a[0] + dx
                    rx = lx if anchor == "start" else lx - tw
                    rect = (rx, my - size, tw, th)
                    cand = (lx, my, anchor, rect, L, f, 0 if dx > 0 else 3)
                    best, best_score = _better(cand, best, best_score, tw, solid, labels, segments, own, W, H)
    if best is None:
        a, b = segs[len(segs) // 2] if segs else (pts[0], pts[0])
        return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 5, "middle", None, False
    lx, ly, anchor, rect = best[:4]
    labels.append(rect)
    return lx, ly, anchor, rect, best_score < 500


def _better(cand, best, best_score, tw, solid, labels, segments, own, W, H):
    lx, ly, anchor, rect, L, f, side = cand
    score = side + abs(f - 0.5) * 10 - min(L, 200) * 0.02
    if rect[0] < 2 or rect[1] < 2 or rect[0] + rect[2] > W - 2 or rect[1] + rect[3] > H - 2:
        score += 1000
    for s in solid:
        if _overlap(rect, s):
            score += 1000
    for lb in labels:
        if _overlap(rect, lb):
            score += 1000
    for seg in segments:
        if seg not in own and _seg_hits(rect, seg):
            score += 120
    if best_score is None or score < best_score:
        return cand, score
    return best, best_score


# ================================================================== EA views

class _Stack:
    """Boxes stacked in one column inside a row (the row was too wide)."""
    kind = "stack"
    GAP = 24

    def __init__(self, children):
        self.children = children
        self.pills = []
        self.w = max(c.w for c in children)
        self.h = sum(c.h for c in children) + self.GAP * (len(children) - 1)
        self.x = self.y = 0.0

    def expand(self):
        y = self.y
        for c in self.children:
            c.x = self.x + (self.w - c.w) / 2
            c.y = y
            y += c.h + self.GAP


class _Edge:
    def __init__(self, src, tgt, verb, triples, label, explicit):
        self.src, self.tgt, self.verb = src, tgt, verb
        self.triples, self.label, self.explicit = triples, label, explicit
        self.points = None


def draw(model, spec):
    """Lay out and draw one parsed view. Returns (view, height)."""
    if spec.script:
        return _run_script(model, spec)
    mm = metamodel_of(model)
    if mm.key == "bpmn":
        return BpmnLayout(model, spec).run()
    theme = make_theme(width=spec.width) if spec.width else make_theme()
    v = View(model, spec.vid, title=spec.title, viewpoint=spec.viewpoint, theme=theme)
    if spec.matrices:
        return _draw_matrix(v, spec)
    L = _EaLayout(v, model, mm, spec)
    return L.run()


def _run_script(model, spec):
    """A view placed by hand: load the script and call its draw(model, vid)."""
    import importlib.util
    from .dsl import DslError
    name = "_ead_view_" + "".join(c if c.isalnum() else "_" for c in spec.script)
    loader = importlib.util.spec_from_file_location(name, spec.script)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    fn = getattr(module, "draw", None)
    if not callable(fn):
        raise DslError(f"view {spec.vid}: {spec.script} has no draw(model, vid) function")
    try:
        out = fn(model, spec.vid)
    except KeyError as e:
        raise DslError(f"view {spec.vid}: {spec.script} can't draw it ({e})")
    if not (isinstance(out, tuple) and len(out) == 2 and hasattr(out[0], "save")):
        raise DslError(f"view {spec.vid}: draw() in {spec.script} has to return (view, height)")
    if out[0].vid != spec.vid:
        raise DslError(f"view {spec.vid}: {spec.script} drew view {out[0].vid} instead")
    return out


def _draw_matrix(v, spec):
    y = 16
    for m in spec.matrices:
        row_w = m.get("row_w", 200)
        cols = m["cols"]
        col_w = m.get("col_w")
        need = 16 + row_w + len(cols) * (col_w or 96) + 16
        if need > v.W:
            v.W = v.t["width"] = int(need)
        cells = v.cells_from(m["verb"], m["rows"], cols, **({"mark": m["mark"]} if "mark" in m else {}))
        y = v.matrix(16, y, m["rows"], cols, cells, row_w=row_w, col_w=col_w, title=m.get("title")) + 20
    y -= 10
    if spec.keys:
        y = v.key_line(y, spec.keys)
    return v, y + 4


NODE_ATTRS = {"icon", "sub", "w", "h", "type_label", "dashed", "name_size"}
CONTAINER_ATTRS = {"icon", "sub", "w", "fill_opacity", "name_size"}
FRAME_ATTRS = {"icon", "dashed", "colour"}
GROUP_ATTRS = {"w", "sub", "ids"}


class _EaLayout:
    def __init__(self, v, model, mm, spec):
        self.v, self.model, self.mm, self.spec = v, model, mm, spec
        self.objs = {o["id"]: o for o in model["objects"]}
        bands = spec.bands if spec.bands is not None else (mm.data.get("bands") or mm.layer_order)
        self.band_of_layer = {b: i for i, b in enumerate(bands)}
        self.banded = spec.bands != []
        self.item_of = {}
        self.attached = {}            # pill oid -> (pill item, host item)
        self.errors = []

    def fail(self, line, msg):
        self.errors.append(f"line {line}: {msg}")

    def warn(self, msg):
        warn_layout(self.v, msg)

    # -------------------------------------------------- set-up
    def run(self):
        spec, v = self.spec, self.v
        for top in spec.items:
            for it in top.walk():
                self._check_attrs(it)
                if it.kind == "group":
                    for m in it.members:
                        self.item_of[m] = it
                elif it.oid:
                    self.item_of[it.oid] = it
        from .dsl import Item
        for pill, host, line, attrs in spec.attached:
            p = Item("pill", pill, line, attrs)
            p.host = self.item_of[host]
            p.host.pills.append(p)
            self.attached[pill] = p
            self.item_of[pill] = p
        edges = self._edges()
        if self.errors:
            from .dsl import DslError
            raise DslError(f"view {spec.vid}:\n  " + "\n  ".join(self.errors))
        self.edges = edges
        avail = v.W - 32
        root_w, root_h = self._block(None, spec.items, avail)
        W = max(v.W, int(root_w + 32 + 0.5))
        if W > v.W:
            self.warn(f"the view is {W}px wide, wider than the {v.W}px page "
                      "(a row can't be narrower)")
        v.W = v.t["width"] = W
        ox = 16 + max(0, (W - 32 - root_w) / 2)
        top_hang = PILL_OVERHANG if any(i.pills for i in spec.items) else 0
        self._absolute(spec.items, ox, 16 + top_hang)
        for it in self._all():
            if it.pills:
                self._pill_geometry(it)
        bottom = max([it.y + it.h for it in self._all()] or [16])
        H = bottom + 60
        self._draw_boxes()
        self._route(W, H)
        y = bottom + 20
        if spec.legend:
            y = v.legend(y)
            y -= 2
        if spec.keys:
            y = v.key_line(y, spec.keys)
        return v, y + 4

    def _check_attrs(self, it):
        allowed = {"node": NODE_ATTRS, "pill": {"w"}, "junction": set(), "container": CONTAINER_ATTRS,
                   "frame": FRAME_ATTRS, "group": GROUP_ATTRS}[it.kind]
        for k in it.attrs:
            if k not in allowed:
                self.fail(it.line, f"{k}= doesn't apply to a {it.kind}"
                          + (f" (it takes {', '.join(sorted(allowed))})" if allowed else ""))
        for k in ("w", "h", "name_size"):
            if k in it.attrs:
                try:
                    it.attrs[k] = float(it.attrs[k])
                except ValueError:
                    self.fail(it.line, f"{k}= must be a number")
        if "fill_opacity" in it.attrs:
            try:
                it.attrs["fill_opacity"] = float(it.attrs["fill_opacity"])
            except ValueError:
                self.fail(it.line, "fill_opacity= must be a number")

    def _all(self):
        for top in self.spec.items:
            yield from top.walk()

    # -------------------------------------------------- which edges
    def _edges(self):
        spec, mm = self.spec, self.mm
        rels = self.model["relationships"]
        drawn = self.item_of
        notation_box = mm.notation != "archimate"
        explicit = {}
        for f, verb, t, label, line in spec.edges:
            found = [i for i, r in enumerate(rels)
                     if r["from"] == f and r["to"] == t and (verb is None or r["type"] == verb)]
            if verb is not None and verb not in mm.relationships:
                self.fail(line, f"{verb} is not a {mm.name} relationship")
                continue
            if not found:
                self.fail(line, f"the model has no relationship {f} -[{verb or '…'}]-> {t}")
                continue
            if verb is None and len(found) > 1:
                kinds = ", ".join(rels[i]["type"] for i in found)
                self.fail(line, f"{f} --> {t} matches {kinds}; name the verb with -[verb]->")
                continue
            for oid in (f, t):
                if oid not in drawn:
                    self.fail(line, f"{oid} is not drawn in this view")
            explicit[found[0]] = label
        hidden = set()
        for f, verb, t, line in spec.hidden:
            found = [i for i, r in enumerate(rels)
                     if r["from"] == f and r["to"] == t and (verb is None or r["type"] == verb)]
            if not found:
                self.fail(line, f"the model has no relationship {f} -[{verb or '…'}]-> {t} to hide")
            hidden |= set(found)
        if spec.edges_mode == "explicit":
            chosen = sorted(explicit)
        else:
            chosen = [i for i, r in enumerate(rels) if r["from"] in drawn and r["to"] in drawn]
        merged = {}
        for i in chosen:
            if i in hidden:
                continue
            r = rels[i]
            a, b = drawn[r["from"]], drawn[r["to"]]
            if a is b:
                continue
            if i not in explicit and self._implied(a, b):
                continue
            key = (id(a), id(b), r["type"])
            if key in merged:
                merged[key].triples.append((r["from"], r["type"], r["to"]))
                continue
            label = explicit.get(i)
            if label is None:
                if spec.labels == "verb":
                    label = r["type"]
                elif spec.labels == "text":
                    label = r.get("name") or r.get("note") or (r["type"] if notation_box else None)
                    if not notation_box and r["type"] == "influence" and not label:
                        label = r.get("modifier")
            merged[key] = _Edge(a, b, r["type"], [(r["from"], r["type"], r["to"])], label, i in explicit)
        return list(merged.values())

    def _implied(self, a, b):
        """Nesting or a pill on its host already says this relationship."""
        if getattr(a, "host", None) is b or getattr(b, "host", None) is a:
            return True
        return a.parent is b or b.parent is a

    # -------------------------------------------------- sizes
    def _band(self, it):
        if not self.banded:
            return 0
        if it.kind == "frame":
            bands = [self._band(c) for c in it.children]
            return min(bands) if bands else 0
        otype = it.otype if it.kind == "group" else self.objs[it.oid]["type"]
        return self.band_of_layer.get(self.mm.layer(otype), len(self.band_of_layer))

    def _leaf_size(self, it):
        v, a = self.v, it.attrs
        if it.kind == "junction":
            it.w = it.h = 10
        elif it.kind == "pill":
            it.w = a.get("w") or v.pill_width(it.oid)
            it.h = v.pill_height(it.oid, it.w)
        elif it.kind == "group":
            it.w = a.get("w") or 190
            it.h = v.group_height(it.label, it.w, a.get("sub"))
        else:
            it.w = a.get("w") or max(self._node_width(it), self._pill_room(it))
            it.h = a.get("h") or v.node_height(it.oid, it.w, a.get("sub"), a.get("name_size"), a.get("icon"))

    def _pill_room(self, it):
        """Width a box needs so the pills on its top edge clear its type label
        (box notation) or type symbol (ArchiMate)."""
        if not it.pills:
            return 0
        pills = sum(self.v.pill_width(p.oid) + 8 for p in it.pills)
        if self.mm.notation == "archimate":
            return pills + 40
        label = self.objs[it.oid]["type"].upper()
        room = text_width(label, 7.5, True) + 0.6 * len(label) + 22 + pills
        if it.kind == "container":
            room += text_width(it.oid, 7) + 12
        return room

    def _node_width(self, it):
        o = self.objs[it.oid]
        icon = 30 if it.attrs.get("icon") else 0
        name = text_width(o["name"], 10.5, True) + 34 + icon
        if self.mm.notation == "archimate":
            name += 22
            return max(150, min(210, name))
        label = o["type"].upper()
        tl = text_width(label, 7.5, True) + 0.6 * len(label) + 20
        return max(150, min(216, max(name, min(tl, 216))))

    # -------------------------------------------------- block layout
    def _child_of(self, oid_item, owner):
        it = oid_item
        if getattr(it, "host", None) is not None:
            it = it.host
        while it is not None and it.parent is not owner:
            it = it.parent
        return it

    def _block(self, owner, items, avail):
        """Lay out `items` (children of owner) inside width `avail`; set their
        x, y relative to the block and return (width, height)."""
        v = self.v
        for it in items:
            if it.kind in ("container", "frame"):
                inner = avail - 2 * PAD
                cw, ch = self._block(it, it.children, inner)
                if it.kind == "container":
                    minw = max(it.attrs.get("w") or 0, self._header_min(it), self._pill_room(it))
                    it.w = max(cw + 2 * PAD, minw)
                    hh, _ = v.container_header(it.oid, it.w, it.attrs.get("name_size"))
                    if it.attrs.get("sub"):
                        hh += 11 * len(wrap(it.attrs["sub"], v.SUB, it.w - 14))
                    it.head = hh + PAD_TOP
                else:
                    it.w = max(cw + 2 * PAD, text_width(it.label.upper(), 8, True) + 40)
                    it.head = 24
                top_hang = PILL_OVERHANG if any(c.pills for c in it.children) else 0
                it.head += top_hang
                it.h = it.head + ch + PAD_BOTTOM
                it.inner_off = (it.w - cw) / 2
            else:
                self._leaf_size(it)
        if not items:
            return 0, 0
        index = {id(it): k for k, it in enumerate(items)}
        # lifted edges between children of this block
        lifted = []
        for e in self.edges:
            a, b = self._child_of(e.src, owner), self._child_of(e.tgt, owner)
            if a is not None and b is not None and a is not b and id(a) in index and id(b) in index:
                lifted.append((a, b, e))
        rows = self._rows(owner, items, lifted, avail)
        return self._place(rows, lifted, avail, owner)

    def _header_min(self, it):
        o = self.objs[it.oid]
        w = text_width(o["name"], it.attrs.get("name_size") or 10.5, True) + 40
        if self.mm.notation != "archimate":
            label = o["type"].upper()
            w = max(w, text_width(label, 7.5, True) + 0.6 * len(label) + text_width(it.oid, 7) + 36)
        else:
            w += 24
        return min(w, 260)

    def _rows(self, owner, items, lifted, avail):
        spec = self.spec
        # union-find for `same`
        parent = {id(it): id(it) for it in items}

        def find(k):
            while parent[k] != k:
                parent[k] = parent[parent[k]]
                k = parent[k]
            return k

        band = {id(it): self._band(it) for it in items}
        for ids, line in spec.same:
            members = []
            for oid in ids:
                c = self._child_of(self.item_of[oid], owner) if oid in self.item_of else None
                if c is not None and id(c) in parent:
                    members.append(c)
            for c in members[1:]:
                parent[find(id(c))] = find(id(members[0]))
        groups = {}
        for it in items:
            groups.setdefault(find(id(it)), []).append(it)
        gband = {g: min(band[id(i)] for i in its) for g, its in groups.items()}
        # constraints: u above v
        above = set()
        for a, b, e in lifted:
            d = self.mm.relationships.get(e.verb, {}).get("layout")
            ga, gb = find(id(a)), find(id(b))
            if ga == gb or gband[ga] != gband[gb]:
                continue
            if d == "up":
                above.add((gb, ga))
            elif d == "down":
                above.add((ga, gb))
        for up, low, line in spec.above:
            if up not in self.item_of or low not in self.item_of:
                continue
            a, b = self._child_of(self.item_of[up], owner), self._child_of(self.item_of[low], owner)
            if a is None or b is None or id(a) not in parent or id(b) not in parent:
                continue
            ga, gb = find(id(a)), find(id(b))
            if gband[ga] > gband[gb]:
                from .dsl import DslError
                raise DslError(f"view {spec.vid}: line {line}: {up} is in a lower layer band than {low}; "
                               "use 'bands' to change the band order or 'bands off'")
            if gband[ga] == gband[gb] and ga != gb:
                above.add((ga, gb))
        rank = _longest_path(list(groups), above, order=[find(id(it)) for it in items])
        # a box with nothing above or below it in its band sits in the row of
        # the boxes it connects across to
        tied = {u for pair in above for u in pair}
        for _ in range(3):
            for g in groups:
                if g in tied:
                    continue
                near = [rank[find(id(b if find(id(a)) == g else a))] for a, b, e in lifted
                        if g in (find(id(a)), find(id(b))) and find(id(a)) != find(id(b))
                        and gband[find(id(a))] == gband[find(id(b))]]
                if near:
                    rank[g] = max(set(near), key=near.count)
        keyed = sorted({(gband[g], rank[g]) for g in groups})
        row_of = {k: n for n, k in enumerate(keyed)}
        rows = [[] for _ in keyed]
        for it in items:
            g = find(id(it))
            rows[row_of[(gband[g], rank[g])]].append(it)
        return rows

    def _gap(self, a, b, lifted):
        """Space between neighbours in a row: room for the label of a line
        running across between them."""
        am = a.children if a.kind == "stack" else [a]
        bm = b.children if b.kind == "stack" else [b]
        gap = GAP_X
        for x, y, e in lifted:
            if (x in am and y in bm) or (x in bm and y in am):
                if e.label:
                    gap = max(gap, text_width(e.label, 8.5) * 1.05 + 28)
                else:
                    gap = max(gap, 48)
        return gap

    def _packed(self, row, lifted):
        return sum(it.w for it in row) + sum(self._gap(a, b, lifted) for a, b in zip(row, row[1:]))

    def _wrap(self, rows, lifted, avail):
        """Rows wider than the block: first try stacking the trailing boxes in
        a column beside a taller one (an application with its neighbours on
        its right), else carry them onto a new row."""
        out = []
        for row in rows:
            if self._packed(row, lifted) <= avail:
                out.append(row)
                continue
            done = False
            for cut in range(len(row) - 1, 0, -1):
                head, tail = row[:cut], row[cut:]
                if len(tail) < 2:
                    continue
                st = _Stack(tail)
                tall = max(it.h for it in head)
                if self._packed(head + [st], lifted) <= avail and st.h <= tall + 40:
                    out.append(head + [st])
                    done = True
                    break
            if done:
                continue
            cur, moved = [], []
            for it in row:
                if cur and self._packed(cur + [it], lifted) > avail:
                    out.append(cur)
                    cur = []
                    moved.append(it)
                elif moved:
                    moved.append(it)
                cur.append(it)
            out.append(cur)
            if moved:
                self.warn("a row is too wide for the page, so "
                          + ", ".join(_name(it) for it in moved) + " moved to a row below")
        return [r for r in out if r]

    def _rel_cx(self, d, top):
        """Centre of `d` (a descendant of `top`, or top itself) measured from
        top's left edge, while the block is still in relative coordinates."""
        if getattr(d, "host", None) is not None:
            d = d.host
        off = d.w / 2
        while d is not top and d.parent is not None:
            off += d.x + d.parent.inner_off
            d = d.parent
        return off

    def _place(self, rows, lifted, avail, owner):
        # same height for plain boxes in a row, unless sized by hand
        for row in rows:
            nodes = [it for it in row if it.kind == "node" and "h" not in it.attrs]
            if len(nodes) > 1:
                hmax = max(it.h for it in nodes)
                for it in nodes:
                    it.h = hmax
        rows = self._wrap(_order(rows, lifted), lifted, avail)
        slot = {}
        for r in rows:
            for it in r:
                slot[id(it)] = it
                for c in getattr(it, "children", []) if it.kind == "stack" else []:
                    slot[id(c)] = it
        gaps = [[self._gap(a, b, lifted) for a, b in zip(r, r[1:])] for r in rows]
        packed = [sum(it.w for it in r) + sum(g) for r, g in zip(rows, gaps)]
        W = max(packed)
        for r, g, pw in zip(rows, gaps, packed):
            x = (W - pw) / 2
            for k, it in enumerate(r):
                it.x = x
                x += it.w + (g[k] if k < len(g) else 0)
        row_index = {id(it): n for n, r in enumerate(rows) for it in r}
        neigh = {}
        for a, b, e in lifted:
            sa, sb = slot[id(a)], slot[id(b)]
            if row_index[id(sa)] == row_index[id(sb)]:
                continue
            oa = self._rel_cx(e.src, a) + (sa.w - a.w) / 2 * (sa is not a)
            ob = self._rel_cx(e.tgt, b) + (sb.w - b.w) / 2 * (sb is not b)
            neigh.setdefault(id(sa), []).append((sb, ob, oa))
            neigh.setdefault(id(sb), []).append((sa, oa, ob))
        order = list(range(len(rows)))
        for sweep in range(8):
            seq = order if sweep % 2 == 0 else order[::-1]
            for n in seq:
                r, g = rows[n], gaps[n]
                desired = []
                for it in r:
                    nb = neigh.get(id(it))
                    if nb:
                        desired.append(sum(o.x + off_o - off_me for o, off_o, off_me in nb) / len(nb))
                    else:
                        desired.append(it.x)
                xs = _isotonic_place([it.w for it in r], g, desired, W)
                for it, x in zip(r, xs):
                    it.x = x
        y = 0
        for n, r in enumerate(rows):
            if n > 0:
                jogs = 0
                for a, b, e in lifted:
                    ra, rb = row_index[id(slot[id(a)])], row_index[id(slot[id(b)])]
                    if {ra, rb} == {n - 1, n} and abs((a.x + a.w / 2) - (b.x + b.w / 2)) > 3:
                        jogs += 1
                hang = PILL_OVERHANG if any(it.pills for it in r) else 0
                y += GAP_Y + 8 * min(max(jogs - 1, 0), 3) + hang
            rh = max(it.h for it in r)
            for it in r:
                it.y = y + (rh - it.h) / 2
            y += rh
        for r in rows:
            for it in r:
                if it.kind == "stack":
                    it.expand()
        return W, y

    # -------------------------------------------------- absolute positions
    def _absolute(self, items, ox, oy):
        for it in items:
            it.x += ox
            it.y += oy
            if it.kind in ("container", "frame"):
                self._absolute(it.children, it.x + it.inner_off, it.y + it.head)

    def _pill_geometry(self, host):
        v = self.v
        right = host.x + host.w - 10
        if self.mm.notation == "archimate":
            right -= 18
        elif host.kind == "container":
            right -= text_width(host.oid, 7) + 12
        for p in host.pills:
            p.w = p.attrs.get("w") or v.pill_width(p.oid)
            p.h = v.pill_height(p.oid, p.w)
            p.x = right - p.w
            p.y = host.y - 11
            right = p.x - 8

    # -------------------------------------------------- drawing
    def _draw_boxes(self):
        v = self.v
        for top in self.spec.items:
            for it in top.walk():
                if it.kind == "container":
                    a = it.attrs
                    kw = {k: a[k] for k in ("icon", "sub", "fill_opacity", "name_size") if k in a}
                    v.container(it.oid, it.x, it.y, it.w, it.h, **kw)
                elif it.kind == "frame":
                    a = it.attrs
                    v.frame(it.x, it.y, it.w, it.h, it.label, colour=a.get("colour"),
                            dashed=a.get("dashed") is True, icon=a.get("icon"))
        for top in self.spec.items:
            for it in top.walk():
                a = it.attrs
                if it.kind == "node":
                    tl = a.get("type_label")
                    tl = False if tl == "off" else tl
                    kw = {k: a[k] for k in ("sub", "icon", "name_size") if k in a}
                    if "dashed" in a:
                        kw["dashed"] = a["dashed"] is True
                    if tl is not None:
                        kw["type_label"] = tl
                    v.node(it.oid, it.x, it.y, it.w, it.h, **kw)
                elif it.kind == "pill":
                    v.pill(it.oid, it.x, it.y, it.w)
                elif it.kind == "group":
                    v.group(it.otype, it.label, it.members, it.x, it.y, it.w, it.h,
                            sub=a.get("sub"), ids=a.get("ids"))
                elif it.kind == "junction":
                    v.junction(it.oid, it.x + 5, it.y + 5)
        for it in self._all():
            for p in it.pills:
                v.pill(p.oid, p.x, p.y, p.w)

    def _rect(self, it):
        return (it.x, it.y, it.w, it.h)

    def _ancestors(self, it):
        """Boxes an edge from `it` may cross: the containers around it (for
        a pill on a box's edge, the containers around that box)."""
        out = set()
        cur = it.host.parent if getattr(it, "host", None) is not None else it.parent
        while cur is not None:
            out.add(id(cur))
            cur = cur.parent
        return out

    def _route(self, W, H):
        v = self.v
        leaves = [it for it in self._all() if it.kind not in ("container", "frame")]
        leaves += list(self.attached.values())
        boxes = [self._rect(it) for it in self._all()] + [self._rect(p) for p in self.attached.values()]
        router = Router(W, H, boxes)

        def key(e):
            a, b = e.src, e.tgt
            dx = abs((a.x + a.w / 2) - (b.x + b.w / 2))
            dy = abs((a.y + a.h / 2) - (b.y + b.h / 2))
            straight = (a.x < b.x + b.w and b.x < a.x + a.w) or (a.y < b.y + b.h and b.y < a.y + a.h)
            return (0 if straight else 1, dx + dy)

        archimate = self.mm.notation == "archimate"
        heads = self._header_rects()
        jobs = []
        for n, e in enumerate(sorted(self.edges, key=key)):
            anc = self._ancestors(e.src) | self._ancestors(e.tgt)
            obstacles, soft = [], []
            for it in self._all():
                if it is e.src or it is e.tgt:
                    continue
                (soft if id(it) in anc else obstacles).append(self._rect(it))
            for p in self.attached.values():
                if p is not e.src and p is not e.tgt:
                    obstacles.append(self._rect(p))
            obstacles += [r for it, r in heads if it is not e.src and it is not e.tgt]
            jobs.append((id(e), self._rect(e.src), self._rect(e.tgt), obstacles,
                         self._port_kind(e.src), self._port_kind(e.tgt), soft))
        routed, failed = route_all(router, jobs)
        byid = {id(e): e for e in self.edges}
        for k in failed:
            self.warn(f"no clear route for {_edge_name(byid[k])}; "
                      "drawn as a plain elbow that may cross boxes")
        for a, b in crossing_pairs({k: routed[k] for k in byid}):
            self.warn(f"lines {_edge_name(byid[a])} and {_edge_name(byid[b])} cross")
        for e in self.edges:
            start_gap = 0
            if archimate:
                rd = self.mm.relationships.get(e.verb, {})
                if rd.get("start") or e.verb == "access":
                    start_gap = 2
            e.points = _shorten(routed[id(e)], 2, start_gap)
        solid = [self._rect(it) for it in leaves] + [r for _, r in heads]
        for it in self._all():
            if it.kind in ("container", "frame"):
                x, y, w, h = self._rect(it)
                solid += [(x - 1, y - 1, w + 2, 2), (x - 1, y + h - 1, w + 2, 2),
                          (x - 1, y - 1, 2, h + 2), (x + w - 1, y - 1, 2, h + 2)]
        labels = []
        segments = [seg for e in self.edges for seg in zip(e.points, e.points[1:])]
        for e in self.edges:
            label = None
            if e.label:
                own = set(zip(e.points, e.points[1:]))
                lx, ly, anchor, rect, clean = place_label(e.label, v.SUB, e.points, solid,
                                                          labels, segments, own, W, H)
                label = (lx, ly)
                if not clean:
                    self.warn(f"no free spot for the label \"{e.label}\" on {_edge_name(e)}; "
                              "it touches a box or another label")
            kw = {}
            if label:
                kw = {"label": label, "label_anchor": anchor, "label_text": e.label}
            v.edge(e.points, e.verb, check=e.triples, **kw)

    def _header_rects(self):
        """The text in container and frame headers (type label, name, id,
        ArchiMate symbol), which lines entering the box must not cross."""
        v, out = self.v, []
        for it in self._all():
            if it.kind == "frame":
                out.append((it, (it.x + 4, it.y + 3, text_width(it.label.upper(), 8, True) + 14, 13)))
            if it.kind != "container":
                continue
            o = self.objs[it.oid]
            ns = it.attrs.get("name_size") or v.NAME
            hh, lines = v.container_header(it.oid, it.w, ns)
            tx = it.x + (28 if it.attrs.get("icon") else 7)
            tw = max([text_width(ln, ns, True) for ln in lines] or [0])
            if v.type_labels:
                label = o["type"].upper()
                tw = max(tw, text_width(label, 7.5, True) + 0.6 * len(label))
                idw = text_width(it.oid, 7)
                out.append((it, (it.x + it.w - idw - 8, it.y + 3, idw + 4, 10)))
            else:
                out.append((it, (it.x + it.w - 22, it.y + 3, 18, 14)))
            out.append((it, (it.x + 3, it.y + 2, tx - it.x + tw + 2, hh - 4)))
        return out

    def _port_kind(self, it):
        return "pill" if it.kind in ("pill", "junction") else "box"


def warn_layout(v, msg):
    """Record a layout problem on the view: the automatic layout drew it, but
    not cleanly. They print when the view is saved and go in its manifest."""
    w = f"{v.vid}: layout: {msg}"
    if w not in v.layout_warnings:
        v.layout_warnings.append(w)
        v.warnings.append(w)


def _name(it):
    if it.kind == "stack":
        return ", ".join(_name(c) for c in it.children)
    return it.oid or it.label


def _edge_name(e):
    return f"{_name(e.src)} -[{e.verb}]-> {_name(e.tgt)}"


def _fallback(a, b):
    """A plain elbow when the grid has no route (boxes packed too tight)."""
    ax, ay = a[0] + a[2] / 2, a[1] + a[3]
    bx, by = b[0] + b[2] / 2, b[1]
    if by < ay:
        ay, by = a[1], b[1] + b[3]
    my = (ay + by) / 2
    return [(ax, ay), (ax, my), (bx, my), (bx, by)]


def _longest_path(nodes, above, order):
    """Rank = longest chain of `above` pairs ending at the node. Cycles are
    broken by ignoring the pair that closes them (in declaration order)."""
    succ = {n: [] for n in nodes}
    for u, w in above:
        succ[u].append(w)
    pos = {n: k for k, n in enumerate(dict.fromkeys(order))}
    state, topo, back = {}, [], set()

    def dfs(u):
        state[u] = 1
        for w in sorted(succ[u], key=lambda n: pos.get(n, 0)):
            if state.get(w) == 1:
                back.add((u, w))
            elif w not in state:
                dfs(w)
        state[u] = 2
        topo.append(u)

    for n in sorted(nodes, key=lambda n: pos.get(n, 0)):
        if n not in state:
            dfs(n)
    rank = {n: 0 for n in nodes}
    for u in reversed(topo):
        for w in succ[u]:
            if (u, w) not in back:
                rank[w] = max(rank[w], rank[u] + 1)
    return rank


def _order(rows, lifted):
    """Barycentre ordering, keeping the declaration order where nothing pulls."""
    pos = {}

    def refresh():
        for r in rows:
            for k, it in enumerate(r):
                pos[id(it)] = (k + 0.5) / len(r)

    refresh()
    rindex = {id(it): n for n, r in enumerate(rows) for it in r}
    adj = {}
    for a, b, e in lifted:
        if rindex[id(a)] != rindex[id(b)]:
            adj.setdefault(id(a), []).append(b)
            adj.setdefault(id(b), []).append(a)

    def crossings():
        c = 0
        es = [(a, b) for a, b, _ in lifted if rindex[id(a)] != rindex[id(b)]]
        for i in range(len(es)):
            for j in range(i + 1, len(es)):
                (a1, b1), (a2, b2) = es[i], es[j]
                if rindex[id(a1)] > rindex[id(b1)]:
                    a1, b1 = b1, a1
                if rindex[id(a2)] > rindex[id(b2)]:
                    a2, b2 = b2, a2
                if rindex[id(a1)] == rindex[id(a2)] and rindex[id(b1)] == rindex[id(b2)]:
                    if (pos[id(a1)] - pos[id(a2)]) * (pos[id(b1)] - pos[id(b2)]) < 0:
                        c += 1
        return c

    best = [list(r) for r in rows]
    best_c = crossings()
    for sweep in range(6):
        seq = range(len(rows)) if sweep % 2 == 0 else range(len(rows) - 1, -1, -1)
        for n in seq:
            r = rows[n]
            keyed = []
            for k, it in enumerate(r):
                nb = adj.get(id(it))
                bary = sum(pos[id(o)] for o in nb) / len(nb) if nb else pos[id(it)]
                keyed.append((bary, k, it))
            keyed.sort(key=lambda t: (t[0], t[1]))
            rows[n] = [t[2] for t in keyed]
            refresh()
        c = crossings()
        if c < best_c:
            best, best_c = [list(r) for r in rows], c
    return best


def _isotonic_place(widths, gaps, desired, W):
    """Left edges as close as possible (least squares) to `desired`, keeping
    the order, the gaps and the block [0, W]."""
    off = [0.0]
    for k in range(1, len(widths)):
        off.append(off[-1] + widths[k - 1] + gaps[k - 1])
    total = off[-1] + widths[-1]
    d = [desired[k] - off[k] for k in range(len(widths))]
    blocks = []
    for val in d:
        blocks.append([val, 1])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            s, c = blocks.pop()
            blocks[-1][0] += s
            blocks[-1][1] += c
    vals = []
    for s, c in blocks:
        vals += [s / c] * c
    hi = max(0.0, W - total)
    return [min(max(val, 0.0), hi) + off[k] for k, val in enumerate(vals)]


# ================================================================== BPMN

class BpmnLayout:
    """Pools stacked, lanes inside them, flow nodes in columns (longest
    sequence-flow distance) and tracks (rows within a lane)."""
    TRACK = 100
    COL_GAP = 56
    MARGIN = 22

    def __init__(self, model, spec):
        from . import bpmn
        self.b = bpmn
        self.model, self.spec = model, spec
        self.objs = {o["id"]: o for o in model["objects"]}
        self.rels = model["relationships"]
        self.sc = bpmn._Scope(model)
        self.pos = {}           # oid -> (x, y, w, h)
        self.lanes_y = {}       # lane -> (y, h)

    # -------------------------------------------------- sizes
    def _size(self, oid):
        b, o = self.b, self.objs[oid]
        t = o["type"]
        if t in b.EVENTS:
            return 2 * b.EVENT_R, 2 * b.EVENT_R
        if t in b.GATEWAYS:
            return 2 * b.GW, 2 * b.GW
        if t == "dataObject":
            return 30, 38
        if t == "dataStore":
            return 44, 38
        if t in b.ARTIFACTS:
            return 150, 10 + len(wrap(o["name"], 8.5, 140)) * 11
        if t == "subProcess" and self._children(oid):
            return self.inner[oid][0], self.inner[oid][1]
        return b.TASK_W, b.TASK_H

    def _children(self, scope):
        b = self.b
        return [o["id"] for o in self.model["objects"]
                if o["type"] in b.FLOW_NODES + b.DATA + b.ARTIFACTS and o["type"] != "boundaryEvent"
                and self.sc.scope(o["id"]) == scope
                and (scope is None or self._in_pool_or_sub(o["id"], scope))]

    def _in_pool_or_sub(self, oid, scope):
        return scope in self.sc.ancestors(oid)

    def _anchor(self, oid):
        """The flow node a data object or annotation is drawn beside."""
        for r in self.rels:
            if r["type"] == "dataInput" and r["from"] == oid:
                return r["to"]
            if r["type"] == "dataOutput" and r["to"] == oid:
                return r["from"]
            if r["type"] == "association":
                if r["from"] == oid:
                    return r["to"]
                if r["to"] == oid:
                    return r["from"]
        return None

    def _host(self, oid):
        o = self.objs[oid]
        return o.get("attachedTo") if o["type"] == "boundaryEvent" else oid

    # -------------------------------------------------- arrange one scope
    def _arrange(self, members, lane_of, lanes):
        """Columns and tracks for the members of one process scope. Returns
        ({oid: (col, lane, track)}, column widths, {lane: [track heights]})."""
        b = self.b
        flow = [m for m in members if self.objs[m]["type"] in b.FLOW_NODES]
        extra = [m for m in members if m not in flow]
        fs = set(flow)
        above = set()
        preds = {}
        for r in self.rels:
            if r["type"] != "sequenceFlow":
                continue
            u, w = self._host(r["from"]), r["to"]
            if u in fs and w in fs and u != w:
                above.add((u, w))
                preds.setdefault(w, []).append(u)
        rank = _longest_path(flow, above, order=flow)
        for m in extra:
            a = self._anchor(m)
            rank[m] = rank.get(self._host(a), 0) if a else 0
        used = {}                         # (lane, col) -> set(tracks)
        place = {}

        def take(m, lane, col, pref):
            taken = used.setdefault((lane, col), set())
            for d in range(0, 20):
                for t in ((pref + d, pref - d) if d else (pref,)):
                    if t >= 0 and t not in taken:
                        taken.add(t)
                        place[m] = (col, lane, t)
                        return

        for m in sorted(flow, key=lambda m: (rank[m], flow.index(m))):
            lane = lane_of(m)
            pref = 0
            for p in preds.get(m, []):
                if p in place and place[p][1] == lane:
                    pref = place[p][2]
                    break
            take(m, lane, rank[m], pref)
        for m in extra:
            lane = lane_of(m)
            a = self._anchor(m)
            a = self._host(a) if a else None
            pref = place[a][2] + 1 if a in place and place[a][1] == lane else 0
            take(m, lane, rank[m], pref)
        ncols = max([c for c, _, _ in place.values()] or [0]) + 1
        colw = [0] * ncols
        heights = {ln: [] for ln in lanes}
        hosts = {o.get("attachedTo") for o in self.model["objects"] if o["type"] == "boundaryEvent"}
        for m, (c, ln, t) in place.items():
            w, h = self._size(m)
            colw[c] = max(colw[c], w)
            hs = heights.setdefault(ln, [])
            while len(hs) <= t:
                hs.append(self.TRACK)
            # room under an activity for its boundary events and their flows
            hs[t] = max(hs[t], h + 48 + (56 if m in hosts else 0))
        for ln in lanes:
            if not heights.get(ln):
                heights[ln] = [self.TRACK]
        return place, colw, heights

    def _columns_x(self, colw, left, gap):
        xs, x = [], left
        for w in colw:
            xs.append(x + w / 2)
            x += w + gap
        return xs, x - gap - left

    # -------------------------------------------------- subprocess interiors
    def _measure_subprocesses(self):
        b = self.b
        self.inner = {}
        subs = [o["id"] for o in self.model["objects"] if o["type"] == "subProcess"]
        # innermost first
        subs.sort(key=lambda s: -len(self.sc.ancestors(s)))
        self.sub_layout = {}
        for s in subs:
            kids = self._children(s)
            if not kids:
                continue
            place, colw, heights = self._arrange(kids, lambda m: None, [None])
            xs, width = self._columns_x(colw, 0, 40)
            tracks = heights[None]
            self.sub_layout[s] = (place, xs, tracks)
            self.inner[s] = (width + 2 * 20, sum(tracks) + 26)

    def _place_sub(self, s, x, y):
        place, xs, tracks = self.sub_layout[s]
        tops = [y + 26 + sum(tracks[:k]) for k in range(len(tracks))]
        for m, (c, _, t) in place.items():
            w, h = self._size(m)
            cx, cy = x + 20 + xs[c], tops[t] + tracks[t] / 2
            self.pos[m] = (cx - w / 2, cy - h / 2, w, h)
            if m in self.sub_layout:
                self._place_sub(m, cx - w / 2, cy - h / 2)

    # -------------------------------------------------- pools and lanes
    def _lane_tree(self, parent):
        return [o["id"] for o in self.model["objects"] if o["type"] == "lane" and o.get("parent") == parent]

    def _leaf_lanes(self, parent, depth=0, out=None):
        out = [] if out is None else out
        for ln in self._lane_tree(parent):
            kids = self._lane_tree(ln)
            if kids:
                self._leaf_lanes(ln, depth + 1, out)
            else:
                out.append((ln, depth))
        return out

    def run(self):
        b, spec = self.b, self.spec
        self._measure_subprocesses()
        pools = spec.pools or [o["id"] for o in self.model["objects"] if o["type"] == "participant"]
        plans = []
        for p in pools or [None]:
            leaves = self._leaf_lanes(p) if p else []
            lanes = [ln for ln, _ in leaves] or [None]
            depth = max([d for _, d in leaves] or [-1]) + 1
            members = [m for m in self._children(p)] if p else self._children(None)
            first = lanes[0]

            def lane_of(m, lanes=lanes, first=first):
                ln = self.sc.lane(m) if self.objs[m]["type"] != "boundaryEvent" else None
                while ln is not None and ln not in lanes:
                    kids = self._lane_tree(ln)
                    ln = kids[0] if kids else None
                return ln if ln in lanes else first

            if members:
                place, colw, heights = self._arrange(members, lane_of, lanes)
            else:
                place, colw, heights = {}, [], {}
            plans.append((p, lanes, depth, members, place, colw, heights))
        left_band = lambda depth, p: (30 if p else 0) + 24 * depth  # noqa: E731
        need = 0
        for p, lanes, depth, members, place, colw, heights in plans:
            if colw:
                need = max(need, 16 + left_band(depth, p) + self.MARGIN * 2 + sum(colw)
                           + self.COL_GAP * (len(colw) - 1) + 16)
        W = max(spec.width or 740, int(need + 0.5))
        theme = make_theme(width=W)
        v = b.BpmnView(self.model, spec.vid, title=spec.title, theme=theme)
        self.v = v
        if W > (spec.width or 740):
            warn_layout(v, f"the process is {W}px wide, wider than the {spec.width or 740}px page")
        y = 16
        drawn_pools = []
        for p, lanes, depth, members, place, colw, heights in plans:
            lb = left_band(depth, p)
            inner_w = W - 32 - lb - 2 * self.MARGIN
            gap = self.COL_GAP
            if colw and len(colw) > 1:
                spare = inner_w - sum(colw) - gap * (len(colw) - 1)
                gap = min(110, gap + max(0, spare) / (len(colw) - 1))
            xs, width = self._columns_x(colw, 16 + lb + self.MARGIN, gap)
            if colw:
                shift = max(0, (inner_w - width) / 2)
                xs = [x + shift for x in xs]
            if p and not members:
                h = 60
                drawn_pools.append((p, (16, y, W - 32, h), []))
                y += h + 40
                continue
            lane_boxes, ly = [], y
            for ln in lanes:
                hs = heights.get(ln, [self.TRACK])
                lh = max(110, sum(hs))
                lane_boxes.append((ln, ly, lh, hs))
                ly += lh
            for m, (c, ln, t) in place.items():
                _, top, lh, hs = next(lb_ for lb_ in lane_boxes if lb_[0] == ln)
                pad = (lh - sum(hs)) / 2
                cy = top + pad + sum(hs[:t]) + hs[t] / 2
                w, h = self._size(m)
                self.pos[m] = (xs[c] - w / 2, cy - h / 2, w, h)
                if m in self.sub_layout:
                    self._place_sub(m, xs[c] - w / 2, cy - h / 2)
            drawn_pools.append((p, (16, y, W - 32, ly - y), lane_boxes))
            y = ly + 40
        # boundary events on their activity's lower edge
        bounds = {}
        for o in self.model["objects"]:
            if o["type"] == "boundaryEvent" and o.get("attachedTo") in self.pos:
                bounds.setdefault(o["attachedTo"], []).append(o["id"])
        for host, evs in bounds.items():
            hx, hy, hw, hh = self.pos[host]
            for k, e in enumerate(evs):
                cx = hx + hw * (0.3 + 0.4 * k / max(1, len(evs) - 1)) if len(evs) > 1 else hx + hw * 0.3
                r = b.EVENT_R
                self.pos[e] = (cx - r, hy + hh - r, 2 * r, 2 * r)
        pool_rects = {p: r for p, r, _ in drawn_pools if p}
        self.bands = [r for _, r, _ in drawn_pools]
        for p, (x, _, w, _), lane_boxes in drawn_pools:
            self.bands += [(x, top, w, lh) for ln, top, lh, _ in lane_boxes if ln is not None]
        flows = self._route(W, y + 40, pool_rects)
        self._draw(drawn_pools, flows)
        y -= 20
        if spec.legend:
            y = v.legend(y)
        if spec.keys:
            y = v.key_line(y, spec.keys) if hasattr(v, "key_line") else y
        return v, y + 4

    # -------------------------------------------------- routing
    def _kind(self, oid):
        t = self.objs[oid]["type"]
        return "pill" if t in self.b.EVENTS + self.b.GATEWAYS else "box"

    def _route(self, W, H, pool_rects):
        b = self.b
        boxes = list(self.pos.values())
        router = Router(W, H, boxes)
        flows, jobs = {}, []
        order = sorted(range(len(self.rels)), key=lambda i: (self.rels[i]["type"] != "sequenceFlow", i))
        for i in order:
            r = self.rels[i]
            f, t = r["from"], r["to"]
            if f in pool_rects or t in pool_rects:
                pts = self._message_straight(f, t, pool_rects)
                if pts:
                    flows[i] = pts
                    continue
            if (f not in self.pos and f not in pool_rects) or (t not in self.pos and t not in pool_rects):
                continue
            fr = self.pos.get(f) or pool_rects[f]
            tr = self.pos.get(t) or pool_rects[t]
            skip = {f, t}
            soft = [self.pos[s_] for s_ in self.sub_layout
                    if s_ in self.pos and (s_ in self.sc.ancestors(f) or s_ in self.sc.ancestors(t))]
            obstacles = [rect for oid, rect in self.pos.items()
                         if oid not in skip and rect not in soft]
            soft = soft + [b_ for b_ in self.bands if b_ not in (fr, tr)]
            sk = self._kind(f) if f in self.pos else "side"
            tk = self._kind(t) if t in self.pos else "side"
            jobs.append((i, fr, tr, obstacles, sk, tk, soft))
        routed, failed = route_all(router, jobs)
        for i in failed:
            warn_layout(self.v, f"no clear route for {self._flow_name(i)}; "
                        "drawn as a plain elbow that may cross shapes")
        for i, j in crossing_pairs(routed):
            warn_layout(self.v, f"flows {self._flow_name(i)} and {self._flow_name(j)} cross")
        for i, pts in routed.items():
            flows[i] = _shorten(pts, 2 if self.rels[i]["type"] != "association" else 0)
        return sorted(flows.items())

    def _flow_name(self, i):
        r = self.rels[i]
        return f"{r['from']} -[{r['type']}]-> {r['to']}"

    def _message_straight(self, f, t, pool_rects):
        """A message flow between a pool and a node: straight up or down at
        the node's centre."""
        node, pool = (t, f) if f in pool_rects else (f, t)
        if node in pool_rects or node not in self.pos:
            return None
        nx, ny, nw, nh = self.pos[node]
        px, py, pw, ph = pool_rects[pool]
        cx = nx + nw / 2
        if py + ph <= ny:
            a, bpt = (cx, ny), (cx, py + ph)
        else:
            a, bpt = (cx, ny + nh), (cx, py)
        for oid, (x, y, w, h) in self.pos.items():
            if oid == node:
                continue
            lo, hi = min(a[1], bpt[1]), max(a[1], bpt[1])
            if x - 4 < cx < x + w + 4 and y < hi and y + h > lo:
                return None
        pts = [a, bpt] if node == f else [bpt, a]
        return _shorten(pts, 2)

    # -------------------------------------------------- drawing
    def _label_rect(self, oid, where):
        b, o = self.b, self.objs[oid]
        x, y, w, h = self.pos[oid]
        cx, cy = x + w / 2, y + h / 2
        if o["type"] in b.EVENTS:
            lines = wrap(o["name"], 8.5, 104, True)
            tw = max(text_width(ln, 8.5, True) for ln in lines)
            lh = len(lines) * 10
            r = w / 2
            if where == "below":
                return (cx - tw / 2, cy + r + 3, tw, lh)
            if where == "above":
                return (cx - tw / 2, cy - r - 5 - lh + 2, tw, lh)
            if where == "right":
                return (cx + r + 5, cy - lh / 2, tw, lh)
            if where == "below-right":
                return (cx + 5, cy + r + 3, tw, lh)
            if where == "below-left":
                return (cx - 5 - tw, cy + r + 3, tw, lh)
            return (cx - r - 5 - tw, cy - lh / 2, tw, lh)
        lines = wrap(o["name"], 8.5, 110, True)
        tw = max(text_width(ln, 8.5, True) for ln in lines)
        lh = len(lines) * 10
        s = b.GW
        up = where.startswith("above")
        side = where.split("-")[1] if "-" in where else None
        if side:
            ly = cy - s / 2 - 12 - lh + 10 if up else cy + s / 2 + 3
            lx = cx + s / 2 + 4 if side == "right" else cx - s / 2 - 4 - tw
        else:
            ly = cy - s - 14 - lh + 10 if up else cy + s + 3
            lx = cx - tw / 2
        return (lx, ly, tw, lh)

    def _choose_label(self, oid, options, segments, taken):
        best, best_score = options[0], None
        for k, where in enumerate(options):
            rect = self._label_rect(oid, where)
            score = k
            for seg in segments:
                if _seg_hits(rect, seg):
                    score += 100
            for other, r in self.pos.items():
                if other != oid and _overlap(rect, r):
                    score += 100
            for r in taken:
                if _overlap(rect, r):
                    score += 100
            if best_score is None or score < best_score:
                best, best_score = where, score
        taken.append(self._label_rect(oid, best))
        if best_score >= 100:
            warn_layout(self.v, f"no free spot for the name of {oid}; it touches a flow, "
                        "a shape or another label")
        return best

    def _draw(self, pools, flows):
        b, v = self.b, self.v
        for p, rect, lane_boxes in pools:
            if p:
                inner = v.pool(p, *rect)
                self._draw_lanes(p, inner["x"], lane_boxes)
        segments = [s for _, pts in flows for s in zip(pts, pts[1:])]
        for p, (x, y, w, h), lane_boxes in pools:
            edges = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
            segments += list(zip(edges, edges[1:]))
            for ln, top, lh, _ in lane_boxes:
                if ln is not None:
                    segments.append(((x, top + lh), (x + w, top + lh)))
        taken = []
        order = sorted(self.pos, key=lambda m: (self.objs[m]["type"] == "boundaryEvent",
                                                 -len(self.sc.ancestors(m))))
        order.sort(key=lambda m: (self.objs[m]["type"] == "boundaryEvent",
                                  not (self.objs[m]["type"] == "subProcess" and m in self.sub_layout)))
        for m in order:
            x, y, w, h = self.pos[m]
            t = self.objs[m]["type"]
            if t == "subProcess" and m in self.sub_layout:
                v.subprocess(m, x, y, w, h)
            elif t in b.ACTIVITIES:
                v.task(m, x, y, w, h)
            elif t in b.EVENTS:
                label = None
                if self.objs[m].get("name"):
                    opts = ["below", "above", "right", "left"]
                    if t == "boundaryEvent":
                        opts = ["below-right", "below-left", "right", "left", "below"]
                    label = self._choose_label(m, opts, segments, taken)
                v.event(m, x + w / 2, y + h / 2, label=label)
            elif t in b.GATEWAYS:
                label = None
                if self.objs[m].get("name"):
                    label = self._choose_label(m, ["above", "above-right", "above-left", "below",
                                                   "below-right", "below-left"], segments, taken)
                v.gateway(m, x + w / 2, y + h / 2, label=label)
            elif t in b.DATA:
                v.data(m, x, y)
                taken.append((x - 30, y + h, w + 60, 12 * len(wrap(self.objs[m]["name"], 8.5, 100, True))))
            elif t in b.ARTIFACTS:
                v.annotation(m, x, y, w)
        solid = list(self.pos.values()) + taken
        labels = []
        for i, pts in flows:
            r = self.rels[i]
            text = r.get("name") or r.get("condition")
            kw = {}
            if text and r["type"] in ("sequenceFlow", "messageFlow"):
                own = set(zip(pts, pts[1:]))
                lx, ly, anchor, _, clean = place_label(text, 8.5, pts, solid, labels, segments, own,
                                                       v.W, 10 ** 5)
                kw = {"label": (lx, ly), "label_anchor": anchor}
                if not clean:
                    warn_layout(v, f"no free spot for the label \"{text}\" on {self._flow_name(i)}; "
                                "it touches a shape or another label")
            v.flow(pts, (r["from"], r["type"], r["to"]), **kw)

    def _draw_lanes(self, parent, x, lane_boxes):
        """Draw the lane tree under `parent`: parent lanes span their leaves."""
        spans = {ln: (top, lh) for ln, top, lh, _ in lane_boxes}

        def span(ln):
            if ln in spans:
                return spans[ln]
            kids = [span(k) for k in self._lane_tree(ln)]
            kids = [k for k in kids if k]
            if not kids:
                return None
            top = min(k[0] for k in kids)
            return (top, max(k[0] + k[1] for k in kids) - top)

        def draw(par, lx):
            for ln in self._lane_tree(par):
                sp = span(ln)
                if not sp:
                    continue
                self.v.lane(ln, lx, sp[0], self.v.W - 16 - lx, sp[1])
                draw(ln, lx + 24)

        if lane_boxes and lane_boxes[0][0] is not None:
            draw(parent, x)
