import re
import unittest

from helpers import clone, example  # noqa: F401  (sets sys.path)
from ealib import View, make_theme
from ealib.common import shade


def model(name):
    return example(name)


class TypeColours(unittest.TestCase):
    def test_types_in_one_layer_get_distinct_shades(self):
        for name in ("archimate", "essential", "coreea", "togaf"):
            m = model(name)
            v = View(m, "T")
            by_layer = {}
            for t in {o["type"] for o in m["objects"]}:
                by_layer.setdefault(v.mm.layer(t), []).append(v.colours(t))
            for layer, colours in by_layer.items():
                self.assertEqual(len(set(colours)), len(colours), f"{name} {layer}: {colours}")

    def test_first_type_of_a_layer_keeps_the_layer_colour(self):
        m = model("essential")
        v = View(m, "T")
        self.assertEqual(v.colours("Business Domain"), v.layer_colours("Business Domain"))
        self.assertNotEqual(v.colours("Business Capability"), v.layer_colours("Business Capability"))

    def test_same_type_same_colour_in_every_view(self):
        m = model("archimate")
        self.assertEqual(View(m, "A").colours("Data Object"), View(m, "B").colours("Data Object"))

    def test_theme_overrides(self):
        m = model("essential")
        plain = View(m, "T", theme=make_theme(type_shades=False))
        self.assertEqual(plain.colours("Business Capability"), plain.layer_colours("Business Capability"))
        fixed = View(m, "T", theme=make_theme(types={"Business Capability": ("#111111", "#eeeeee")}))
        self.assertEqual(fixed.colours("Business Capability"), ("#111111", "#eeeeee"))

    def test_shade_is_valid_hex_and_step_zero_is_identity(self):
        self.assertEqual(shade("#3f7f8c", "#eef6f8", 0), ("#3f7f8c", "#eef6f8"))
        for step in (1, -1, 2, -2):
            for c in shade("#3f7f8c", "#eef6f8", step, 2):
                self.assertRegex(c, r"^#[0-9a-f]{6}$")


class Legend(unittest.TestCase):
    def test_layer_headings_and_pill_swatch(self):
        m = model("essential")
        v = View(m, "T")
        a = v.node("APR-01", 16, 16, 200)
        v.pill("ASV-01", 16, a["b"] + 20)
        v.legend(200)
        svg = "\n".join(v.parts)
        self.assertIn(">APPLICATION<", svg)
        self.assertNotIn(">BUSINESS<", svg)
        stroke = v.colours("Application Service")[0]
        self.assertTrue(re.search(rf'rx="6" fill="#ffffff" stroke="{stroke}"', svg))

    def test_matrix_only_types_are_left_out(self):
        m = model("essential")
        v = View(m, "T")
        apps = [o["id"] for o in m["objects"] if o["type"] == "Application Provider"]
        other = [o["id"] for o in m["objects"] if v.mm.layer(o["type"]) != "Application"][:2]
        y = v.matrix(16, 16, apps, other, {})
        v.legend(y + 20)
        svg = "\n".join(v.parts)
        for layer in v.mm.layers:
            self.assertNotIn(f">{layer.upper()}<", svg)


if __name__ == "__main__":
    unittest.main()
