"""Icon packs: the house generic glyphs plus the official AWS, Azure and
Google Cloud architecture icon sets.

The vendor packs are not shipped with the plugin: their terms allow use in
architecture diagrams and documentation but not redistribution in a tool.
`fetch()` downloads the current official pack from the vendor's own icon
page into a local cache (ARCH_DIAGRAM_ICONS, default
~/.cache/arch-diagram/icons) once the person has accepted those terms, and
indexes it. Everything else reads the cache.

Resolution (`resolve()`), for a component name such as "S3", "Cosmos DB",
"Pub/Sub", "Kafka" or "aws:amazon-simple-queue-service":
1. an explicit "pack:slug" reference;
2. the alias table (scripts/icon_aliases.json): a term names a concept and,
   when it belongs to a platform, that platform's icon. The platform icon is
   used when its pack is fetched; otherwise the concept's generic glyph;
3. a fuzzy match on the names in the fetched packs (restricted to a
   platform when one is given);
4. the generic glyph whose name matches.
Anything that is not a platform service (users, browsers, SaaS, on-premises
kit) resolves to a generic glyph.
"""
import html
import json
import os
import re
import shutil
import tempfile
import urllib.request
import zipfile

from .common import SKILL, SCRIPTS, esc, render_png

GENERIC_SVG = os.path.join(SKILL, "icons.svg")
ALIASES = os.path.join(SCRIPTS, "icon_aliases.json")
UA = "Mozilla/5.0 (arch-diagram icon fetch)"

PACKS = {
    "aws": {
        "name": "AWS Architecture Icons",
        "page": "https://aws.amazon.com/architecture/icons/",
        "terms": "https://aws.amazon.com/architecture/icons/ (usage guidelines on the page)",
        "zip": r"https://d1\.awsstatic\.com/[^\"' ]*Icon-package[^\"' ]*\.zip",
    },
    "azure": {
        "name": "Azure Public Service Icons",
        "page": "https://learn.microsoft.com/en-us/azure/architecture/icons/",
        "terms": "Microsoft permits the use of these icons in architectural diagrams, training "
                 "materials, or documentation. You can copy, distribute, and display the icons "
                 "only for the permitted use unless granted explicit permission by Microsoft.",
        "zip": r"https://arch-center\.azureedge\.net/icons/Azure_Public_Service_Icons[^\"' ]*\.zip",
    },
    "gcp": {
        "name": "Google Cloud Icons",
        "page": "https://cloud.google.com/icons",
        "terms": "https://cloud.google.com/icons (usage guidelines on the page)",
        "zip": r"https://services\.google\.com/fh/files/misc/[a-z-]*icons\.zip",
    },
}


class IconError(LookupError):
    pass


def cache_dir():
    return os.environ.get("ARCH_DIAGRAM_ICONS") or os.path.join(
        os.path.expanduser("~"), ".cache", "arch-diagram", "icons")


def slugify(s):
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip().lower())
    return s.strip("-")


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


# ------------------------------------------------------------------ fetch

def _get(url, dest=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        if dest is None:
            return r.read().decode("utf-8", "replace")
        with open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        return dest


def zip_urls(pack):
    """The current download links, read from the vendor's icon page."""
    p = PACKS[pack]
    page = html.unescape(_get(p["page"]))
    urls = sorted(set(re.findall(p["zip"], page)))
    if pack == "aws":
        urls = [u for u in urls if "PPT" not in u.upper()]
    if pack == "gcp":
        urls = [u for u in urls if any(k in u for k in ("core-products", "category", "legacy"))]
    if not urls:
        raise IconError(f"no icon package link found on {p['page']}; download it by hand "
                        f"and run: icons.py fetch {pack} --from-zip FILE --accept-terms")
    return urls


def _aws_entry(path):
    parts = path.split("/")
    fn = parts[-1][:-4]
    if parts[0].startswith("Architecture-Service-Icons"):
        if len(parts) < 4 or parts[-2] != "48":
            return None
        name = re.sub(r"^Arch_|_48$", "", fn).replace("-", " ")
        return {"kind": "service", "name": name, "slug": slugify(name),
                "category": parts[1].replace("Arch_", "").replace("-", " ")}
    if parts[0].startswith("Resource-Icons"):
        if "_Dark" in fn or not fn.endswith(("_48", "_48_Light")):
            return None
        name = re.sub(r"^Res_|_48(_Light)?$", "", fn).replace("_", " ").replace("-", " ")
        return {"kind": "resource", "name": name, "slug": slugify(name),
                "category": parts[1].replace("Res_", "").replace("-", " ")}
    if parts[0].startswith("Architecture-Group-Icons"):
        if "_Dark" in fn:
            return None
        name = re.sub(r"_32$", "", fn).replace("-", " ")
        return {"kind": "group", "name": name, "slug": "group-" + slugify(name), "category": "Group"}
    if parts[0].startswith("Category-Icons"):
        if "_48" not in fn and "48" not in parts[-2]:
            return None
        name = re.sub(r"^Arch-Category_|_48$", "", fn).replace("-", " ")
        return {"kind": "category", "name": name, "slug": "category-" + slugify(name),
                "category": "Category"}
    return None


def _azure_entry(path):
    parts = path.split("/")
    if len(parts) < 3 or "Icons" not in parts:
        return None
    fn = parts[-1][:-4]
    name = re.sub(r"^\d+-icon-service-", "", fn).replace("-", " ").strip()
    return {"kind": "service", "name": name, "slug": slugify(name), "category": parts[-2].title()}


def _gcp_entry(path):
    parts = path.split("/")
    if parts[0] == "Unique Icons" and len(parts) >= 4:
        return {"kind": "service", "name": parts[1], "slug": slugify(parts[1]),
                "category": "Core products", "rank": 2}
    if parts[0] == "Category Icons" and len(parts) >= 4:
        return {"kind": "category", "name": parts[1].replace(" _ ", " & "),
                "slug": "category-" + slugify(parts[1]), "category": "Category", "rank": 2}
    if len(parts) == 2 and parts[1][:-4] == parts[0]:
        name = parts[0].replace("_", " ")
        name = " ".join(w.upper() if w in ("api", "ai", "iam", "sql", "vpc", "dns", "cdn", "vpn", "gke", "iot")
                        else w.capitalize() for w in name.split())
        return {"kind": "service", "name": name, "slug": slugify(name), "category": "Products", "rank": 1}
    return None


ENTRY = {"aws": _aws_entry, "azure": _azure_entry, "gcp": _gcp_entry}


def index_zip(pack, zpath, out=None):
    """Extract the usable SVGs from one vendor zip into the cache and merge
    them into the pack index. Returns the number of icons indexed."""
    out = out or os.path.join(cache_dir(), pack)
    svgdir = os.path.join(out, "svg")
    os.makedirs(svgdir, exist_ok=True)
    idx_path = os.path.join(out, "index.json")
    index = {}
    if os.path.exists(idx_path):
        with open(idx_path) as f:
            index = {e["slug"]: e for e in json.load(f)["icons"]}
    n = 0
    with zipfile.ZipFile(zpath) as z:
        for path in z.namelist():
            if "__MACOSX" in path or not path.lower().endswith(".svg"):
                continue
            e = ENTRY[pack](path)
            if not e or not e["slug"]:
                continue
            old = index.get(e["slug"])
            if old and old.get("rank", 0) > e.get("rank", 0):
                continue
            if old and old.get("rank", 0) == e.get("rank", 0) and old.get("source") != path:
                if e["kind"] == "resource" and old["kind"] == "service":
                    e["slug"] = "res-" + e["slug"]
                elif old["kind"] == e["kind"]:
                    continue
            data = z.read(path)
            if b"<svg" not in data[:4000]:
                continue
            fn = e["slug"] + ".svg"
            with open(os.path.join(svgdir, fn), "wb") as f:
                f.write(data)
            e.update({"file": fn, "source": path})
            index[e["slug"]] = e
            n += 1
    icons = sorted(index.values(), key=lambda e: (e["kind"], e["slug"]))
    with open(idx_path, "w") as f:
        json.dump({"pack": pack, "name": PACKS[pack]["name"], "icons": icons}, f, indent=0)
    _PACK_CACHE.pop(pack, None)
    return n


def fetch(pack, accept_terms=False, from_zip=None, log=print):
    """Download (or take from_zip) and index a vendor pack."""
    if pack not in PACKS:
        raise IconError(f"unknown pack '{pack}' (known: {', '.join(PACKS)})")
    p = PACKS[pack]
    if not accept_terms:
        raise IconError(f"{p['name']} terms: {p['terms']}\nRe-run with --accept-terms once the "
                        "person has agreed to use the icons on those terms.")
    out = os.path.join(cache_dir(), pack)
    if os.path.isdir(out) and not from_zip:
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)
    sources = []
    if from_zip:
        zips = from_zip if isinstance(from_zip, (list, tuple)) else [from_zip]
        for z in zips:
            n = index_zip(pack, z, out)
            log(f"{pack}: {n} icons from {z}")
            sources.append(os.path.abspath(z))
    else:
        with tempfile.TemporaryDirectory() as tmp:
            for i, url in enumerate(zip_urls(pack)):
                dest = _get(url, os.path.join(tmp, f"{pack}-{i}.zip"))
                n = index_zip(pack, dest, out)
                log(f"{pack}: {n} icons from {url}")
                sources.append(url)
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump({"pack": pack, "name": p["name"], "page": p["page"], "terms": p["terms"],
                   "sources": sources, "accepted_terms": True}, f, indent=1)
    return status()[pack]


# ------------------------------------------------------------------ packs

_PACK_CACHE = {}
_GENERIC = None
_ALIASES = None


def generic():
    """{name: inner svg} from icons.svg (24x24, stroke currentColor)."""
    global _GENERIC
    if _GENERIC is None:
        with open(GENERIC_SVG) as f:
            s = f.read()
        _GENERIC = {m.group(1): m.group(2).strip() for m in
                    re.finditer(r'<symbol id="([^"]+)" viewBox="0 0 24 24">(.*?)</symbol>', s, re.S)}
    return _GENERIC


def pack_index(pack):
    if pack == "generic":
        return [{"slug": k, "name": k.replace("-", " "), "kind": "glyph", "category": "Generic"}
                for k in generic()]
    if pack not in _PACK_CACHE:
        p = os.path.join(cache_dir(), pack, "index.json")
        if not os.path.exists(p):
            _PACK_CACHE[pack] = None
        else:
            with open(p) as f:
                _PACK_CACHE[pack] = json.load(f)["icons"]
    return _PACK_CACHE[pack]


def available():
    return ["generic"] + [p for p in PACKS if pack_index(p)]


def status():
    out = {"generic": {"icons": len(generic()), "fetched": True}}
    for p in PACKS:
        idx = pack_index(p)
        out[p] = {"icons": len(idx) if idx else 0, "fetched": bool(idx),
                  "path": os.path.join(cache_dir(), p)}
    return out


def aliases():
    global _ALIASES
    if _ALIASES is None:
        with open(ALIASES) as f:
            _ALIASES = json.load(f)["concepts"]
    return _ALIASES


def _entry(pack, slug):
    for e in pack_index(pack) or []:
        if e["slug"] == slug:
            return e
    return None


def search(query, pack=None, limit=12, kinds=None):
    """Best matches for `query` across the available packs: list of
    {ref, pack, slug, name, kind, category, score}."""
    q = norm(query)
    qt = set(q.split())
    if not qt:
        return []
    res = []
    for p in ([pack] if pack else available()):
        for e in pack_index(p) or []:
            if kinds and e["kind"] not in kinds:
                continue
            n = norm(e["name"])
            nt = set(n.split()) - {"amazon", "aws", "azure", "google", "cloud", "service", "services"}
            if n == q or e["slug"] == slugify(query):
                score = 100
            else:
                words = nt | set(n.split())
                hit = {t for t in qt if t in words
                       or (len(t) >= 3 and any(w.startswith(t) for w in words))}
                if not hit:
                    continue
                score = 60 * len(hit) / len(qt) + 30 * len(hit) / max(1, len(nt))
                if q in n:
                    score += 15
                if e["kind"] == "service":
                    score += 2
            res.append({"ref": f"{p}:{e['slug']}", "pack": p, "slug": e["slug"], "name": e["name"],
                        "kind": e["kind"], "category": e.get("category", ""), "score": round(score, 1)})
    res.sort(key=lambda r: (-r["score"], len(r["name"])))
    return res[:limit]


def resolve(name, platform=None):
    """The icon for a component name; see the module docstring for the order.
    Returns {ref, pack, slug, name, via}. Raises IconError with suggestions
    when nothing fits."""
    if ":" in name and name.split(":", 1)[0] in ("generic",) + tuple(PACKS):
        pack, slug = name.split(":", 1)
        if pack == "generic":
            if slug not in generic():
                raise IconError(f"no generic glyph '{slug}'")
            return {"ref": name, "pack": "generic", "slug": slug, "name": slug, "via": "explicit"}
        if not pack_index(pack):
            raise IconError(f"{PACKS[pack]['name']} not fetched: run icons.py fetch {pack} --accept-terms")
        e = _entry(pack, slug)
        if not e:
            hint = ", ".join(r["ref"] for r in search(slug.replace("-", " "), pack, 5))
            raise IconError(f"no icon '{slug}' in {pack}" + (f"; closest: {hint}" if hint else ""))
        return {"ref": name, "pack": pack, "slug": slug, "name": e["name"], "via": "explicit"}
    q = norm(name)
    hit = None
    for c in aliases():                       # a platform's own term wins
        for p in PACKS:
            if p in c and q in (norm(t) for t in c[p].get("terms", [])):
                hit = (c, p)
                break
        if hit:
            break
    if hit is None:
        for c in aliases():                   # then platform-neutral terms
            if q in (norm(t) for t in c.get("terms", [])):
                hit = (c, platform if platform in c else None)
                break
    if hit:
        c, owner = hit
        if owner and pack_index(owner):
            for slug in c[owner]["icons"]:
                e = _entry(owner, slug)
                if e:
                    return {"ref": f"{owner}:{slug}", "pack": owner, "slug": slug,
                            "name": e["name"], "via": f"alias {c['concept']}"}
        return {"ref": f"generic:{c['generic']}", "pack": "generic", "slug": c["generic"],
                "name": c["concept"], "via": f"alias {c['concept']}"
                + ("" if not owner else f" ({owner} pack not fetched)")}
    packs = [platform] if platform else [p for p in PACKS]
    for p in packs:
        if not pack_index(p):
            continue
        hits = search(name, p, 1, kinds=("service", "resource"))
        if hits and hits[0]["score"] >= 75:
            h = hits[0]
            return {"ref": h["ref"], "pack": p, "slug": h["slug"], "name": h["name"], "via": "search"}
    g = slugify(name)
    if g in generic():
        return {"ref": f"generic:{g}", "pack": "generic", "slug": g, "name": g, "via": "generic"}
    sugg = ", ".join(r["ref"] for r in search(name, None, 5))
    raise IconError(f"no icon for '{name}'" + (f"; closest: {sugg}" if sugg else "")
                    + ". Map it in icon_aliases.json or use a plain box.")


# ------------------------------------------------------------------ inline

def _prefix_ids(svg, pfx):
    ids = set(re.findall(r'\bid="([^"]+)"', svg))
    for i in sorted(ids, key=len, reverse=True):
        q = re.escape(i)
        svg = re.sub(rf'\bid="{q}"', f'id="{pfx}{i}"', svg)
        svg = re.sub(rf'url\(#{q}\)', f'url(#{pfx}{i})', svg)
        svg = re.sub(rf'href="#{q}"', f'href="#{pfx}{i}"', svg)
    return svg


_SEQ = [0]


def vendor_svg(pack, slug):
    e = _entry(pack, slug)
    if not e:
        raise IconError(f"no icon '{slug}' in {pack}")
    with open(os.path.join(cache_dir(), pack, "svg", e["file"]), encoding="utf-8") as f:
        return f.read()


def inline(ref, x, y, size=20, colour="#475569", platform=None):
    """An SVG fragment drawing the icon with its top-left at (x, y), `size`
    px square. Generic glyphs take `colour`; vendor icons keep theirs."""
    r = resolve(ref, platform)
    if r["pack"] == "generic":
        inner = generic()[r["slug"]].replace("currentColor", colour)
        return (f'<g transform="translate({x:.1f} {y:.1f}) scale({size / 24:.4f})" '
                f'color="{colour}">{inner}</g>')
    s = vendor_svg(r["pack"], r["slug"])
    m = re.search(r"<svg\b([^>]*)>(.*)</svg>", s, re.S)
    if not m:
        raise IconError(f"{r['ref']}: not an SVG")
    attrs, body = m.group(1), m.group(2)
    vb = re.search(r'viewBox="([^"]+)"', attrs)
    if vb:
        viewbox = vb.group(1)
    else:
        w = re.search(r'\bwidth="([\d.]+)', attrs)
        h = re.search(r'\bheight="([\d.]+)', attrs)
        viewbox = f"0 0 {w.group(1) if w else 64} {h.group(1) if h else 64}"
    body = re.sub(r"<title>.*?</title>|<!--.*?-->|<\?xml.*?\?>|<metadata>.*?</metadata>", "", body, flags=re.S)
    _SEQ[0] += 1
    body = _prefix_ids(body, f"i{_SEQ[0]}-{r['pack']}-")
    xlink = ' xmlns:xlink="http://www.w3.org/1999/xlink"' if "xlink:" in body else ""
    return (f'<svg x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" viewBox="{viewbox}"'
            f'{xlink} overflow="visible"><title>{esc(r["name"])}</title>{body.strip()}</svg>')


def sheet(refs, out, cols=6, render=True):
    """Contact sheet of icons (refs or names) to check a choice by eye.
    Writes <out>.html (+ .png). Returns the paths."""
    cell, W = 120, 120 * cols
    parts, rows = [], 0
    for i, ref in enumerate(refs):
        r = resolve(ref)
        cx, cy = (i % cols) * cell, (i // cols) * 100
        rows = i // cols + 1
        parts.append(inline(r["ref"], cx + 44, cy + 14, 32))
        label = r["ref"] if len(r["ref"]) < 26 else r["ref"][:24] + "…"
        parts.append(f'<text x="{cx + 60}" y="{cy + 66}" font-size="8" text-anchor="middle" '
                     f'fill="#0f172a">{esc(label)}</text>')
        parts.append(f'<text x="{cx + 60}" y="{cy + 78}" font-size="7" text-anchor="middle" '
                     f'fill="#94a3b8">{esc(ref if ref != r["ref"] else r["via"])}</text>')
    H = rows * 100 + 10
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
           f'font-family="-apple-system, Helvetica, Arial, sans-serif"><rect width="{W}" height="{H}" '
           f'fill="#fff"/>' + "".join(parts) + "</svg>")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out + ".html", "w") as f:
        f.write(f'<!doctype html><html><head><meta charset="utf-8"><style>body{{margin:0}}'
                f'svg{{display:block;width:{W}px}}</style></head><body>{svg}</body></html>')
    paths = [out + ".html"]
    if render:
        render_png(out + ".html", out + ".png", W, H)
        paths.append(out + ".png")
    return paths
