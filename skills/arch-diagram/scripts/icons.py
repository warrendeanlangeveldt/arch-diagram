#!/usr/bin/env python3
"""Icon packs for arch-diagram.

  icons.py status                           which packs are fetched
  icons.py fetch aws|azure|gcp|all --accept-terms [--from-zip FILE ...]
                                            download the official pack from the
                                            vendor's icon page and index it
  icons.py search QUERY [--pack P]          best matches across packs
  icons.py resolve NAME [--platform P]      the icon a component name gets
  icons.py svg REF [--size 20 --x 0 --y 0 --colour HEX]
                                            inline SVG fragment for a diagram
  icons.py sheet NAME... --out FILE         contact sheet (HTML + PNG) to check by eye

Packs are cached in $ARCH_DIAGRAM_ICONS (default ~/.cache/arch-diagram/icons).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ealib import icons  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("status")
    f = sp.add_parser("fetch"); f.add_argument("pack", choices=list(icons.PACKS) + ["all"])
    f.add_argument("--accept-terms", action="store_true"); f.add_argument("--from-zip", nargs="+")
    s = sp.add_parser("search"); s.add_argument("query"); s.add_argument("--pack"); s.add_argument("--limit", type=int, default=12)
    r = sp.add_parser("resolve"); r.add_argument("name"); r.add_argument("--platform", choices=list(icons.PACKS))
    v = sp.add_parser("svg"); v.add_argument("ref"); v.add_argument("--size", type=float, default=20)
    v.add_argument("--x", type=float, default=0); v.add_argument("--y", type=float, default=0)
    v.add_argument("--colour", default="#475569"); v.add_argument("--platform", choices=list(icons.PACKS))
    h = sp.add_parser("sheet"); h.add_argument("names", nargs="+"); h.add_argument("--out", required=True)
    a = p.parse_args()
    try:
        if a.cmd == "status":
            print(json.dumps(icons.status(), indent=1))
        elif a.cmd == "fetch":
            packs = list(icons.PACKS) if a.pack == "all" else [a.pack]
            if a.from_zip and len(packs) > 1:
                sys.exit("--from-zip takes one pack")
            for pk in packs:
                print(json.dumps({pk: icons.fetch(pk, a.accept_terms, a.from_zip)}))
        elif a.cmd == "search":
            for r in icons.search(a.query, a.pack, a.limit):
                print(f"{r['score']:6.1f}  {r['ref']:<60} {r['kind']:<9} {r['category']}")
        elif a.cmd == "resolve":
            print(json.dumps(icons.resolve(a.name, a.platform)))
        elif a.cmd == "svg":
            print(icons.inline(a.ref, a.x, a.y, a.size, a.colour, a.platform))
        elif a.cmd == "sheet":
            for path in icons.sheet(a.names, a.out):
                print(path)
    except icons.IconError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
