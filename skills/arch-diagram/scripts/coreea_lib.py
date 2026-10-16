"""CoreEA helper for arch-diagram, kept for scripts written against it.

CoreEA is now one of the metamodels in `ealib` (metamodels/coreea.json),
alongside ArchiMate, TOGAF, Essential and BPMN, so CoreEA models get the same
validation, views, CSV catalogue and OrbusInfinity import as the others. This
module keeps the original API working on top of it:

    from coreea_lib import load_model, validate, View
    model = load_model("model.json")     # "metamodel": "coreea" is assumed
    validate(model)                      # raises ModelError listing every problem
    v = View(model, "V1")
    a = v.node("APP-01", 16, 16, 180)
    ...
    v.legend(y); v.save(height, outdir)  # writes V1.svg / V1.html / V1.png

New scripts can use `ealib` directly with "metamodel": "coreea" in the model.
"""
import json

from ealib import ModelError, load_metamodel, make_theme as _make_theme  # noqa: F401
from ealib import catalogue_rows as _catalogue_rows, validate as _validate
from ealib.common import HOUSE, NOT_BUILT, STATUSES, esc, find_chrome, text_width, wrap  # noqa: F401
from ealib.views import View as _View

CHROME = find_chrome()
_MM = load_metamodel("coreea")

TYPE_PREFIX = {t: d["prefix"] for t, d in _MM.types.items()}
TYPE_LAYER = {t: d["layer"] for t, d in _MM.types.items()}
TYPE_ORDER = list(_MM.types)
VERBS, VERB_PAIRS = {}, {}
for _v, _r in _MM.relationships.items():
    _src = sorted({t for s, _ in _r["pairs"] for t in s})
    _tgt = sorted({t for _, t in _r["pairs"] for t in t})
    VERBS[_v] = (_src, _tgt)
    if len(_r["pairs"]) > 1:
        VERB_PAIRS[_v] = {(s[0], t[0]) for s, t in _r["pairs"]}

DEFAULT_THEME = dict(HOUSE, layers={k: tuple(v) for k, v in _MM.layers.items()})


def make_theme(**overrides):
    """Copy of DEFAULT_THEME with overrides; `layers` merges per layer."""
    return _make_theme(DEFAULT_THEME, **overrides)


def _coreea(model):
    model.setdefault("metamodel", "coreea")
    if model["metamodel"] != "coreea":
        raise ModelError(f"coreea_lib draws CoreEA models, not '{model['metamodel']}'; use ealib")
    return model


def load_model(path):
    with open(path) as f:
        return _coreea(json.load(f))


def validate(model, extra_verbs=None, strict_prefix=True):
    return _validate(_coreea(model), extra_verbs, strict_prefix)


def catalogue_rows(model):
    """Flat rows for an OrbusInfinity / spreadsheet import: one per object,
    then one per relationship, names resolved."""
    return _catalogue_rows(_coreea(model))


class View(_View):
    def __init__(self, model, vid, theme=None, title=None, viewpoint=None):
        super().__init__(_coreea(model), vid, title=title, viewpoint=viewpoint,
                         theme=theme or make_theme())

    def manifest(self):
        return self.drawn       # the ids drawn, for tracing back to the catalogue


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        sys.exit("usage: python3 coreea_lib.py model.json   # validate a model")
    try:
        print(validate(load_model(sys.argv[1])))
    except ModelError as e:
        sys.exit(str(e))
