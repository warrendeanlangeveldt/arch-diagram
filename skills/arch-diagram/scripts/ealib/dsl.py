"""The view language: one text file holds the model (or points at a
model.json) and the views, and `ea.py render` lays them out and draws them.
Positions are worked out, not written, so adding an object or a
relationship is a one-line change. references/dsl.md is the full reference.

    metamodel archimate
    name "Service Portal"
    model "model.json"                  # optional: objects and relationships from a file

    ACMP-01: Application Component "Service Portal" status=Built
    ACMP-02: Application Component "Portal web app"
    ACMP-01 -[composition]-> ACMP-02

    view V1 "Application cooperation" {
      viewpoint "Application Cooperation"
      ACMP-01 {                         # nesting: the box holds its parts
        ACMP-02
      }
      ACMP-03 icon=EKS
      ACMP-03 -[flow]-> ACMP-NOTIFY "case events"
      key "Box in a box: composition"
    }

    from ealib.dsl import load_document, render_document
    doc = load_document("views.ead")
    render_document(doc, "out")
"""
import json
import os

from .metamodel import ModelError, metamodel_of

KEYWORDS_VIEW = {"viewpoint", "width", "edges", "labels", "legend", "key", "bands", "same",
                 "frame", "group", "pill", "hide", "matrix", "pools"}


class DslError(ModelError):
    """Every problem in a view-language file, one per line, with its line number."""


# ------------------------------------------------------------------ lexer

class Tok:
    __slots__ = ("kind", "value", "line", "key")

    def __init__(self, kind, value, line, key=None):
        self.kind, self.value, self.line, self.key = kind, value, line, key

    def __repr__(self):
        return f"{self.kind}:{self.value!r}@{self.line}"


def _string(src, i, line):
    """Read a "…" string starting at src[i] == '"'. Returns (text, next i)."""
    out, i = [], i + 1
    while i < len(src):
        c = src[i]
        if c == "\\" and i + 1 < len(src):
            out.append({"n": "\n", "t": "\t"}.get(src[i + 1], src[i + 1]))
            i += 2
            continue
        if c == '"':
            return "".join(out), i + 1
        if c == "\n":
            break
        out.append(c)
        i += 1
    raise DslError(f"line {line}: string not closed")


def tokenize(src):
    """Tokens: word, string, attr (key=value), arrow (verb or None), {, }, ;
    and nl. '#' starts a comment where a token could start."""
    toks, i, line = [], 0, 1
    while i < len(src):
        c = src[i]
        if c == "\n":
            toks.append(Tok("nl", None, line))
            line += 1
            i += 1
        elif c in " \t\r":
            i += 1
        elif c == "#":
            while i < len(src) and src[i] != "\n":
                i += 1
        elif c in "{};":
            toks.append(Tok(c if c != ";" else "nl", c, line))
            i += 1
        elif c == '"':
            s, i = _string(src, i, line)
            toks.append(Tok("string", s, line))
        elif src.startswith("-[", i):
            j = src.find("]->", i)
            if j < 0 or "\n" in src[i:j]:
                raise DslError(f"line {line}: '-[' needs a closing ']->' on the same line")
            toks.append(Tok("arrow", src[i + 2:j].strip(), line))
            i = j + 3
        elif src.startswith("-->", i):
            toks.append(Tok("arrow", None, line))
            i += 3
        else:
            j = i
            while j < len(src) and src[j] not in " \t\r\n{};\"#":
                j += 1
            word = src[i:j]
            i = j
            if "=" in word and not word.startswith("="):
                key, val = word.split("=", 1)
                if val == "" and i < len(src) and src[i] == '"':
                    val, i = _string(src, i, line)
                toks.append(Tok("attr", val, line, key))
            else:
                toks.append(Tok("word", word, line))
    toks.append(Tok("nl", None, line))
    return toks


# ------------------------------------------------------------------ parser

class Stmt:
    """One statement: its tokens (without attrs), its attrs, an optional
    block of child statements, and the line it starts on."""

    def __init__(self, toks, attrs, line, block=None):
        self.toks, self.attrs, self.line, self.block = toks, attrs, line, block

    def words(self):
        return [t.value for t in self.toks]


def parse(src):
    toks = tokenize(src)
    pos = 0

    def statements(depth, open_line):
        nonlocal pos
        out = []
        cur, attrs = [], {}
        while pos < len(toks):
            t = toks[pos]
            pos += 1
            if t.kind == "nl":
                if cur or attrs:
                    out.append(Stmt(cur, attrs, cur[0].line if cur else t.line))
                    cur, attrs = [], {}
            elif t.kind == "{":
                if not cur:
                    raise DslError(f"line {t.line}: '{{' must follow a statement")
                block = statements(depth + 1, t.line)
                out.append(Stmt(cur, attrs, cur[0].line, block))
                cur, attrs = [], {}
            elif t.kind == "}":
                if depth == 0:
                    raise DslError(f"line {t.line}: '}}' without a matching '{{'")
                if cur or attrs:
                    out.append(Stmt(cur, attrs, cur[0].line if cur else t.line))
                return out
            elif t.kind == "attr":
                attrs[t.key] = t.value
            else:
                cur.append(t)
        if depth:
            raise DslError(f"line {open_line}: '{{' is never closed")
        return out

    return statements(0, 0)


def _value(v):
    if v in ("true", "false"):
        return v == "true"
    return v


def _set_attr(d, key, val):
    """key=value onto an object or relationship; dotted keys nest
    (properties.classification=Confidential)."""
    parts = key.split(".")
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = _value(val)


# ------------------------------------------------------------------ document

class ViewSpec:
    """A parsed view: its items (a tree), edges, constraints and options."""

    def __init__(self, vid, title, line):
        self.vid, self.title, self.line = vid, title, line
        self.viewpoint = None
        self.width = None
        self.edges_mode = "auto"
        self.labels = "text"
        self.legend = True
        self.keys = []
        self.bands = None            # None: metamodel order; []: off; list: this order
        self.items = []              # top-level Items
        self.edges = []              # explicit (from, verb|None, to, label|None, line)
        self.hidden = []             # (from, verb|None, to, line)
        self.same = []               # ([ids], line)
        self.above = []              # (upper, lower, line)
        self.matrices = []           # dicts
        self.pools = None            # BPMN: participants to draw, in order
        self.attached = []           # (pill, host, line, attrs): pills on a box's top edge
        self.script = None           # a hand-placed view: path of the script that draws it


class Item:
    """One thing a view draws. kind: node, pill, group, junction, container,
    frame. Containers and frames hold children; `pills` are interface or
    service pills drawn on this item's top edge."""

    def __init__(self, kind, oid=None, line=0, attrs=None, label=None):
        self.kind, self.oid, self.line = kind, oid, line
        self.attrs = attrs or {}
        self.label = label           # frame label, group title
        self.children = []
        self.members = []            # group members
        self.pills = []              # attached pill oids
        self.parent = None
        self.x = self.y = self.w = self.h = 0.0

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def __repr__(self):
        return f"Item({self.kind} {self.oid or self.label})"


class Document:
    def __init__(self, path, model, views):
        self.path, self.model, self.views = path, model, views


def load_document(path):
    """Parse a .ead file: the model it declares or imports, and its views.
    Raises DslError listing every problem found."""
    try:
        with open(path) as f:
            src = f.read()
    except OSError as e:
        raise DslError(f"can't read {path}: {e.strerror}")
    return parse_document(src, os.path.dirname(os.path.abspath(path)), path)


def parse_document(src, base_dir=".", path="<text>"):
    errs = []
    try:
        stmts = parse(src)
    except DslError as e:
        raise DslError(f"{path}: {e}")
    header, objects, rels, views = {}, [], [], []
    imported = None
    for s in stmts:
        try:
            w = s.words()
            kinds = [t.kind for t in s.toks]
            if s.block is not None:
                if "script" in s.attrs and w[:1] == ["view"]:
                    raise DslError(f"line {s.line}: a view placed by a script has no {{ … }} block")
                if w[:1] != ["view"]:
                    raise DslError(f"line {s.line}: only 'view' takes a {{ … }} block at the top level")
                views.append(s)
            elif w[:1] == ["view"]:
                if "script" not in s.attrs:
                    raise DslError(f"line {s.line}: a view is  view ID \"Title\" {{ … }}, "
                                   "or  view ID script=\"file.py\"  for one placed by hand")
                views.append(s)
            elif w and w[0] in ("metamodel", "name", "description", "model"):
                if len(w) != 2:
                    raise DslError(f"line {s.line}: {w[0]} takes one value")
                if w[0] == "model":
                    if imported is not None:
                        raise DslError(f"line {s.line}: one 'model' import per file")
                    imported = (w[1], s.line)
                else:
                    header[w[0]] = w[1]
            elif len(w) >= 3 and kinds[0] == "word" and w[0].endswith(":"):
                if kinds[-1] != "string":
                    raise DslError(f"line {s.line}: an object is  ID: Type \"Name\"  (the name in quotes)")
                o = {"id": w[0][:-1], "type": " ".join(w[1:-1]), "name": w[-1]}
                for k, v in s.attrs.items():
                    _set_attr(o, k, v)
                o["_line"] = s.line
                objects.append(o)
            elif "arrow" in kinds:
                rels.append(_relationship(s))
            else:
                raise DslError(f"line {s.line}: don't know what '{' '.join(map(str, w))}' means here")
        except DslError as e:
            errs.append(str(e))

    model = {}
    if imported:
        p = os.path.join(base_dir, imported[0])
        try:
            with open(p) as f:
                model = json.load(f)
        except (OSError, ValueError) as e:
            errs.append(f"line {imported[1]}: can't read model {imported[0]}: {e}")
    if "metamodel" in header:
        if model.get("metamodel") and model["metamodel"] != header["metamodel"]:
            errs.append(f"metamodel {header['metamodel']} but {imported[0]} is {model['metamodel']}")
        model["metamodel"] = header["metamodel"]
    for k in ("name", "description"):
        if k in header:
            model[k] = header[k]
    model.setdefault("objects", [])
    model.setdefault("relationships", [])
    known = {o.get("id") for o in model["objects"]}
    for o in objects:
        line = o.pop("_line")
        if o["id"] in known:
            errs.append(f"line {line}: {o['id']} is already defined"
                        + (f" in {imported[0]}" if imported else ""))
            continue
        known.add(o["id"])
        model["objects"].append(o)
    for r in rels:
        r.pop("_line")
        model["relationships"].append(r)

    try:
        mm = metamodel_of(model)
    except ModelError as e:
        raise DslError(f"{path}:\n  " + "\n  ".join(errs + [str(e)]))
    parsed = []
    for s in views:
        try:
            parsed.append(_script_view(s, base_dir) if s.block is None else _view(s, model, mm, errs))
        except DslError as e:
            errs.append(str(e))
    ids = [v.vid for v in parsed]
    for vid in {v for v in ids if ids.count(v) > 1}:
        errs.append(f"view {vid} is defined more than once")
    if errs:
        raise DslError(f"{path}:\n  " + "\n  ".join(errs))
    return Document(path, model, parsed)


def _relationship(s):
    toks = s.toks
    if len(toks) not in (3, 4) or toks[1].kind != "arrow" or toks[1].value is None:
        raise DslError(f"line {s.line}: a relationship is  FROM -[verb]-> TO  (optionally \"name\")")
    r = {"from": toks[0].value, "type": toks[1].value, "to": toks[2].value}
    if len(toks) == 4:
        if toks[3].kind != "string":
            raise DslError(f"line {s.line}: put the relationship's name in quotes")
        r["name"] = toks[3].value
    for k, v in s.attrs.items():
        _set_attr(r, k, v)
    r["_line"] = s.line
    return r


# ------------------------------------------------------------------ views

def _script_view(s, base_dir):
    """view ID script="file.py": a view placed by hand. The script defines
    draw(model, vid) and returns (view, height); render calls it with this
    file's model."""
    w = s.words()
    if len(w) != 2 or s.toks[1].kind != "word":
        raise DslError(f"line {s.line}: a hand-placed view is  view ID script=\"file.py\"  "
                       "(the script sets the title)")
    extra = sorted(set(s.attrs) - {"script"})
    if extra:
        raise DslError(f"line {s.line}: a hand-placed view takes only script= (not {', '.join(extra)}=)")
    path = os.path.join(base_dir, str(s.attrs["script"]))
    if not os.path.isfile(path):
        raise DslError(f"line {s.line}: no script {s.attrs['script']}")
    v = ViewSpec(w[1], None, s.line)
    v.script = path
    return v


def _view(s, model, mm, errs):
    w = s.words()
    if len(w) < 2 or s.toks[1].kind != "word":
        raise DslError(f"line {s.line}: a view is  view ID \"Title\" {{ … }}")
    if len(w) > 3 or (len(w) == 3 and s.toks[2].kind != "string"):
        raise DslError(f"line {s.line}: put the view title in quotes")
    v = ViewSpec(w[1], w[2] if len(w) == 3 else None, s.line)
    for k, val in s.attrs.items():
        if k == "viewpoint":
            v.viewpoint = val
        elif k == "width":
            v.width = _int(val, s.line, "width")
        else:
            errs.append(f"line {s.line}: unknown view setting {k}=")
    objs = {o["id"]: o for o in model["objects"]}
    seen = {}
    bpmn = mm.key == "bpmn"
    for st in s.block:
        try:
            _view_stmt(st, v, None, objs, mm, seen, bpmn)
        except DslError as e:
            errs.append(str(e))
    boxes = {i.oid for it in v.items for i in it.walk() if i.oid and i.kind != "junction"}
    for pill, host, line, _ in v.attached:
        if host not in boxes:
            errs.append(f"line {line}: {host} has to be drawn in the view for {pill} to sit on it")
    if v.matrices and v.items:
        errs.append(f"line {v.matrices[0]['line']}: a matrix view holds only the matrix (and key)")
    return v


def _int(val, line, what):
    try:
        return int(float(val))
    except ValueError:
        raise DslError(f"line {line}: {what} must be a number, not {val}")


def _need(oid, objs, line):
    if oid not in objs:
        raise DslError(f"line {line}: {oid} is not in the model")
    return objs[oid]


def _place(item, v, parent, seen):
    oid = item.oid
    if oid:
        if oid in seen:
            raise DslError(f"line {item.line}: {oid} is already drawn in this view (line {seen[oid]})")
        seen[oid] = item.line
    item.parent = parent
    (parent.children if parent else v.items).append(item)


def _view_stmt(st, v, parent, objs, mm, seen, bpmn):
    w, kinds, line = st.words(), [t.kind for t in st.toks], st.line
    head = w[0] if w else None
    if not w:
        raise DslError(f"line {line}: settings need a statement ({', '.join(st.attrs)})")
    if bpmn and head not in ("width", "legend", "key", "pools", "viewpoint"):
        raise DslError(f"line {line}: a BPMN view takes width, pools, legend and key; "
                       "the process itself comes from the model")
    if head in KEYWORDS_VIEW and kinds[0] == "word" and not (len(w) > 1 and kinds[1] == "arrow"):
        if parent is not None and head not in ("frame", "group", "pill"):
            raise DslError(f"line {line}: {head} belongs at the top of the view, not inside a box")
        if head == "viewpoint":
            v.viewpoint = _one(w, line)
        elif head == "width":
            v.width = _int(_one(w, line), line, "width")
        elif head == "edges":
            v.edges_mode = _choice(_one(w, line), ("auto", "explicit"), line, "edges")
        elif head == "labels":
            v.labels = _choice(_one(w, line), ("text", "verb", "none"), line, "labels")
        elif head == "legend":
            v.legend = _choice(_one(w, line), ("on", "off"), line, "legend") == "on"
        elif head == "key":
            if len(w) < 2 or any(k != "string" for k in kinds[1:]):
                raise DslError(f"line {line}: key takes one or more \"quoted\" notes")
            v.keys.extend(w[1:])
        elif head == "bands":
            if w[1:] == ["off"]:
                v.bands = []
            else:
                bad = [b for b in w[1:] if b not in mm.layers]
                if bad or len(w) < 2:
                    raise DslError(f"line {line}: bands takes 'off' or layer names "
                                   f"({', '.join(mm.layers)}); not {', '.join(bad) or 'nothing'}")
                v.bands = w[1:]
        elif head == "same":
            if len(w) < 3:
                raise DslError(f"line {line}: same needs two or more ids")
            for oid in w[1:]:
                _need(oid, objs, line)
            v.same.append((w[1:], line))
        elif head == "pools":
            for oid in w[1:]:
                if _need(oid, objs, line)["type"] != "participant":
                    raise DslError(f"line {line}: {oid} is not a participant (pool)")
            v.pools = w[1:]
        elif head == "frame":
            if len(w) != 2 or kinds[1] != "string":
                raise DslError(f"line {line}: a frame is  frame \"Label\" {{ … }}")
            item = Item("frame", None, line, dict(st.attrs), label=w[1])
            _place(item, v, parent, seen)
            for c in st.block or []:
                _view_stmt(c, v, item, objs, mm, seen, bpmn)
            if not item.children:
                raise DslError(f"line {line}: frame \"{w[1]}\" is empty")
        elif head == "group":
            if len(w) < 3 or kinds[1] != "string":
                raise DslError(f"line {line}: a group is  group \"Title\" ID ID …")
            members = w[2:]
            types = {_need(m, objs, line)["type"] for m in members}
            if len(types) != 1:
                raise DslError(f"line {line}: a group's members share one type; these are {', '.join(sorted(types))}")
            item = Item("group", None, line, dict(st.attrs), label=w[1])
            item.members = members
            item.otype = types.pop()
            for m in members:
                if m in seen:
                    raise DslError(f"line {line}: {m} is already drawn in this view (line {seen[m]})")
                seen[m] = line
            _place(item, v, parent, seen)
        elif head == "pill":
            if len(w) != 2:
                raise DslError(f"line {line}: pill takes one id (use  ID on HOST  to put it on a box's edge)")
            _check_pill(_need(w[1], objs, line), mm, line)
            _place(Item("pill", w[1], line, dict(st.attrs)), v, parent, seen)
        elif head == "hide":
            e = _edge_ref(st, objs, line, 1)
            v.hidden.append(e[:3] + (line,))
        elif head == "matrix":
            v.matrices.append(_matrix(st, objs, mm, line))
        return

    if "arrow" in kinds:
        f, verb, t, label = _edge_ref(st, objs, line, 0)
        v.edges.append((f, verb, t, label, line))
        return
    if len(w) == 3 and w[1] == "on":
        o = _need(w[0], objs, line)
        _need(w[2], objs, line)
        _check_pill(o, mm, line)
        if w[0] in seen:
            raise DslError(f"line {line}: {w[0]} is already drawn in this view (line {seen[w[0]]})")
        seen[w[0]] = line
        v.attached.append((w[0], w[2], line, dict(st.attrs)))
        return
    if len(w) == 3 and w[1] == "above":
        _need(w[0], objs, line)
        _need(w[2], objs, line)
        v.above.append((w[0], w[2], line))
        return
    if len(w) != 1 or kinds[0] != "word":
        raise DslError(f"line {line}: don't know what '{' '.join(map(str, w))}' means in a view")
    o = _need(w[0], objs, line)
    shape = mm.types.get(o["type"], {}).get("shape")
    if st.block is not None:
        kind = "container"
    elif shape == "junction":
        kind = "junction"
    elif shape == "pill" and mm.notation != "archimate":
        kind = "pill"
    else:
        kind = "node"
    item = Item(kind, w[0], line, dict(st.attrs))
    _place(item, v, parent, seen)
    for c in st.block or []:
        _view_stmt(c, v, item, objs, mm, seen, bpmn)


def _one(w, line):
    if len(w) != 2:
        raise DslError(f"line {line}: {w[0]} takes one value")
    return w[1]


def _choice(val, options, line, what):
    if val not in options:
        raise DslError(f"line {line}: {what} is {' or '.join(options)}, not {val}")
    return val


def _check_pill(o, mm, line):
    t = o["type"]
    ok = t.endswith("Interface") or t.endswith("Service") if mm.notation == "archimate" \
        else mm.types.get(t, {}).get("shape") == "pill"
    if not ok:
        raise DslError(f"line {line}: {o['id']} is a {t}; pills are for service and interface types")


def _edge_ref(st, objs, line, start):
    toks = st.toks[start:]
    if len(toks) not in (3, 4) or toks[1].kind != "arrow":
        raise DslError(f"line {line}: an edge is  FROM -[verb]-> TO  or  FROM --> TO, optionally \"label\"")
    f, verb, t = toks[0].value, toks[1].value, toks[2].value
    _need(f, objs, line)
    _need(t, objs, line)
    label = None
    if len(toks) == 4:
        if toks[3].kind != "string":
            raise DslError(f"line {line}: put the edge label in quotes")
        label = toks[3].value
    return f, verb, t, label


def _matrix(st, objs, mm, line):
    """matrix "verb" rows A B … cols C D …   or   matrix writes=CU reads=R rows … cols …
    rows / cols may also be one "Type Name" in quotes: every object of it."""
    w, kinds = st.words(), [t.kind for t in st.toks]
    if "rows" not in w or "cols" not in w or w.index("rows") > w.index("cols"):
        raise DslError(f"line {line}: a matrix is  matrix \"verb\" rows ID … cols ID …")
    ri, ci = w.index("rows"), w.index("cols")
    verbs = [x for x, k in zip(w[1:ri], kinds[1:ri])]
    attrs = dict(st.attrs)
    letters = {k: v for k, v in attrs.items() if k in mm.relationships}
    for k in letters:
        attrs.pop(k)
    if verbs and letters:
        raise DslError(f"line {line}: give the matrix verb in quotes, or verb=LETTERS pairs, not both")
    if not verbs and not letters:
        raise DslError(f"line {line}: the matrix needs the relationship verb its cells come from")
    for vb in verbs:
        if vb not in mm.relationships:
            raise DslError(f"line {line}: {vb} is not a {mm.name} relationship")
    rows = _ids_or_type(w[ri + 1:ci], kinds[ri + 1:ci], objs, mm, line)
    cols = _ids_or_type(w[ci + 1:], kinds[ci + 1:], objs, mm, line)
    verb = letters if letters else (verbs[0] if len(verbs) == 1 else {vb: None for vb in verbs})
    out = {"verb": verb, "rows": rows, "cols": cols, "line": line}
    for k, v in attrs.items():
        if k in ("row_w", "col_w"):
            out[k] = _int(v, line, k)
        elif k in ("title", "mark"):
            out[k] = v
        else:
            raise DslError(f"line {line}: unknown matrix setting {k}=")
    return out


def _ids_or_type(words, kinds, objs, mm, line):
    if len(words) == 1 and kinds[0] == "string":
        t = words[0]
        if t not in mm.types:
            raise DslError(f"line {line}: {t} is not a {mm.name} type")
        ids = [o["id"] for o in objs.values() if o["type"] == t]
        if not ids:
            raise DslError(f"line {line}: the model has no {t}")
        return ids
    if not words:
        raise DslError(f"line {line}: the matrix needs row and column ids")
    for oid in words:
        _need(oid, objs, line)
    return list(words)


# ------------------------------------------------------------------ rendering

def render_document(doc, outdir, only=None, render=True):
    """Validate the model, lay out and draw each view (or those in `only`),
    and save them to outdir. Returns (paths, views drawn)."""
    from .metamodel import validate
    validate(doc.model)
    from .layout import draw
    paths, drawn = [], []
    for spec in doc.views:
        if only and spec.vid not in only:
            continue
        v, height = draw(doc.model, spec)
        paths += v.save(height, outdir, render=render)
        drawn.append(v)
    if only:
        missing = set(only) - {v.vid for v in drawn}
        if missing:
            raise DslError(f"{doc.path}: no view {', '.join(sorted(missing))}")
    return paths, drawn


def is_document(path):
    return str(path).endswith(".ead")


def model_of(path):
    """The model a .ead file declares or imports, for commands that take a
    model path."""
    return load_document(path).model

