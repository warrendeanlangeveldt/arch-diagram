"""Shared drawing primitives: text measuring, wrapping, the SVG canvas and
PNG rendering with headless Chrome. Standard library only."""
import json
import os
import shutil
import subprocess
import sys
from xml.sax.saxutils import escape

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.dirname(SCRIPTS)

STATUSES = ["Built", "Built in UAT", "Designed", "Proposed", "Not started", "Retired"]
NOT_BUILT = {"Proposed", "Designed", "Not started"}

FONT = "-apple-system, 'Helvetica Neue', Arial, sans-serif"

# House tokens shared by every notation (SKILL.md, design system).
HOUSE = {
    "font": FONT,
    "width": 740,
    "ink": "#0f172a",      # names
    "body": "#475569",     # edges, legend text
    "muted": "#64748b",    # sub-lines, verb labels
    "id": "#94a3b8",       # object ids
    "rule": "#e2e8f0",     # legend divider, matrix grid
    "frame": "#94a3b8",    # outer frames
    "paper": "#ffffff",
    "band": "#f8fafc",     # matrix header, pool label band
    "tag": ("#b4443c", "#fbeeed"),
}


def _hex(rgb):
    return "#" + "".join(f"{round(max(0, min(1, c)) * 255):02x}" for c in rgb)


def shade(stroke, fill, step, of=1):
    """Shade `step` of a layer's (stroke, fill), so the types of one layer
    stay in the layer's colour family but read apart. Step 0 is the layer
    colour itself; positive steps lighten the stroke and deepen the fill,
    negative steps darken the stroke and keep the fill pale, each with a
    small turn of the hue. `of` is the largest step in use, which narrows
    the turn when a layer has many types."""
    if not step:
        return stroke, fill
    import colorsys
    turn = min(8.0, 24.0 / of) / 360 * step
    h, l, s = colorsys.rgb_to_hls(*(int(stroke[i:i + 2], 16) / 255 for i in (1, 3, 5)))
    stroke = _hex(colorsys.hls_to_rgb((h + turn) % 1, min(0.52, max(0.18, l + 0.07 * step)), s))
    h, l, s = colorsys.rgb_to_hls(*(int(fill[i:i + 2], 16) / 255 for i in (1, 3, 5)))
    deeper = 0.035 * step if step > 0 else 0.012 * -step
    fill = _hex(colorsys.hls_to_rgb((h + turn) % 1, min(0.98, max(0.6, l - deeper)),
                                    min(1, s + (0.12 * step if step > 0 else 0))))
    return stroke, fill


def find_chrome():
    """Headless Chrome renders the PNGs. CHROME_PATH overrides the lookup."""
    if os.environ.get("CHROME_PATH"):
        return os.environ["CHROME_PATH"]
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.exists(mac):
        return mac
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


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


def box(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h, "r": x + w, "b": y + h,
            "cx": x + w / 2, "cy": y + h / 2}


def render_png(html_path, png_path, width, height, scale=2):
    chrome = find_chrome()
    if not chrome:
        raise RuntimeError("Chrome or Chromium not found: install it or set CHROME_PATH")
    subprocess.run([chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
                    f"--force-device-scale-factor={scale}", "--virtual-time-budget=3000",
                    f"--window-size={int(width)},{int(height)}",
                    f"--screenshot={png_path}", f"file://{os.path.abspath(html_path)}"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Canvas:
    """An SVG under construction: text and shape primitives, marker defs and
    output. Notation-specific views build on it."""

    def __init__(self, vid, theme, title=None):
        self.vid = vid
        self.title = title or vid
        self.t = theme
        self.W = theme["width"]
        self.parts = []
        self.defs = {}
        self.slug = "".join(c for c in vid.lower() if c.isalnum()) or "v"
        self.warnings = []          # printed by save() and kept in the manifest
        self.layout_warnings = []   # the automatic layout's share (ealib.layout)

    def add(self, s):
        self.parts.append(s)

    def define(self, key, svg):
        """Register a <defs> child once; returns its id."""
        did = f"{key}-{self.slug}"
        if did not in self.defs:
            self.defs[did] = svg.replace("{id}", did)
        return did

    def text(self, x, y, s, size=9, fill=None, anchor="start", weight=None,
             italic=False, spacing=None, halo=False, rotate=None):
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
        if rotate is not None:
            a.append(f'transform="rotate({rotate} {x:.1f} {y:.1f})"')
        self.add(f'<text {" ".join(a)}>{esc(s)}</text>')

    def svg(self, height):
        W = self.W
        defs = "<defs>" + "".join(self.defs.values()) + "</defs>" if self.defs else ""
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height:.0f}" '
                f'font-family="{esc(self.t["font"])}">\n'
                f'<title>{esc(self.title)}</title>\n'
                f'<rect x="0" y="0" width="{W}" height="{height:.0f}" fill="{self.t["paper"]}"/>\n'
                f'{defs}\n' + "\n".join(self.parts) + "\n</svg>\n")

    def manifest(self):
        """What save() writes to <vid>.objects.json. Views override."""
        return {}

    def save(self, height, outdir, render=True, scale=2):
        """Write <vid>.svg, <vid>.html, <vid>.objects.json (what was drawn,
        for traceability) and, with render, <vid>.png. Returns the paths."""
        for w in self.warnings:
            print("warning:", w, file=sys.stderr)
        height = int(round(height))
        self.height = height
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
            json.dump(self.manifest(), f, indent=1)
            f.write("\n")
        out = [base + ".svg", base + ".html", base + ".objects.json"]
        if render:
            render_png(base + ".html", base + ".png", self.W, height, scale)
            out.append(base + ".png")
        return out
