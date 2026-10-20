import json
import os
import re
import tempfile
import unittest
import zipfile

import helpers  # noqa: F401
from ealib import icons

SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><title>t</title><defs>'
       '<linearGradient id="g1"><stop offset="0" stop-color="#f00"/></linearGradient></defs>'
       '<rect id="bg" width="64" height="64" fill="url(#g1)"/><use href="#bg"/></svg>')


def fake_zip(path, names):
    with zipfile.ZipFile(path, "w") as z:
        for n in names:
            z.writestr(n, SVG)
            z.writestr("__MACOSX/._" + n, "junk")


class Generic(unittest.TestCase):
    def test_glyphs(self):
        g = icons.generic()
        self.assertEqual(len(g), 64)
        for name, inner in g.items():
            self.assertIn("currentColor", inner, name)

    def test_aliases_name_real_glyphs(self):
        seen = set()
        for c in icons.aliases():
            self.assertIn(c["generic"], icons.generic(), c["concept"])
            self.assertNotIn(c["concept"], seen)
            seen.add(c["concept"])
            for p in icons.PACKS:
                if p in c:
                    self.assertIsInstance(c[p]["icons"], list)

    def test_terms_are_unambiguous(self):
        owner = {}
        for c in icons.aliases():
            for scope in ["neutral"] + [p for p in icons.PACKS if p in c]:
                terms = c.get("terms", []) if scope == "neutral" else c[scope]["terms"]
                for t in terms:
                    k = (scope, icons.norm(t))
                    self.assertNotIn(k, owner, f"'{t}' in {c['concept']} and {owner.get(k)}")
                    owner[k] = c["concept"]

    def test_inline_generic(self):
        s = icons.inline("generic:database", 10, 20, 24, "#123456")
        self.assertIn('translate(10.0 20.0) scale(1.0000)', s)
        self.assertIn("#123456", s)
        self.assertNotIn("currentColor", s)


class Packs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("ARCH_DIAGRAM_ICONS")
        os.environ["ARCH_DIAGRAM_ICONS"] = self.tmp.name
        icons._PACK_CACHE.clear()

    def tearDown(self):
        if self.old is None:
            os.environ.pop("ARCH_DIAGRAM_ICONS", None)
        else:
            os.environ["ARCH_DIAGRAM_ICONS"] = self.old
        icons._PACK_CACHE.clear()
        self.tmp.cleanup()

    def test_terms_required(self):
        with self.assertRaises(icons.IconError) as cm:
            icons.fetch("azure", accept_terms=False)
        self.assertIn("Microsoft permits", str(cm.exception))

    def test_index_and_resolve_offline(self):
        z = os.path.join(self.tmp.name, "aws.zip")
        fake_zip(z, ["Architecture-Service-Icons_07312026/Arch_Storage/48/Arch_Amazon-Simple-Storage-Service_48.svg",
                     "Architecture-Service-Icons_07312026/Arch_Storage/32/Arch_Amazon-Simple-Storage-Service_32.svg",
                     "Architecture-Service-Icons_07312026/Arch_Analytics/48/Arch_Amazon-Kinesis-Video-Streams_48.svg",
                     "Resource-Icons_07312026/Res_Storage/Res_Amazon-Simple-Storage-Service_Bucket_48.svg",
                     "Resource-Icons_07312026/Res_General-Icons/Res_48_Dark/Res_Users_48_Dark.svg",
                     "Resource-Icons_07312026/Res_General-Icons/Res_48_Light/Res_Users_48_Light.svg",
                     "Architecture-Group-Icons_07312026/Region_32.svg",
                     "Architecture-Group-Icons_07312026/Region_32_Dark.svg"])
        st = icons.fetch("aws", accept_terms=True, from_zip=z, log=lambda *_: None)
        self.assertEqual(st["icons"], 5)
        slugs = {e["slug"]: e["kind"] for e in icons.pack_index("aws")}
        self.assertEqual(slugs, {"amazon-simple-storage-service": "service",
                                 "amazon-kinesis-video-streams": "service",
                                 "amazon-simple-storage-service-bucket": "resource",
                                 "users": "resource", "group-region": "group"})
        self.assertEqual(icons.resolve("S3")["ref"], "aws:amazon-simple-storage-service")
        # an icon's exact name (vendor prefix and plural allowed) beats the aliases
        self.assertEqual(icons.resolve("Kinesis Video Streams")["via"], "name")
        self.assertEqual(icons.resolve("Amazon Kinesis Video Stream")["ref"], "aws:amazon-kinesis-video-streams")
        self.assertEqual(icons.resolve("Kinesis Video")["via"], "search")
        # a generic glyph's own name stays generic, and never goes to the fuzzy match
        self.assertEqual(icons.resolve("users")["ref"], "generic:users")
        self.assertEqual(icons.resolve("server", "aws")["ref"], "generic:server")
        self.assertEqual(icons.resolve("Blob Storage")["ref"], "generic:bucket")
        self.assertIn("azure pack not fetched", icons.resolve("Blob Storage")["via"])
        self.assertEqual(icons.resolve("MinIO")["ref"], "generic:bucket")
        s1 = icons.inline("S3", 0, 0, 20)
        s2 = icons.inline("aws:amazon-simple-storage-service", 30, 0, 20)
        ids1 = set(re.findall(r'id="([^"]+)"', s1))
        ids2 = set(re.findall(r'id="([^"]+)"', s2))
        self.assertTrue(ids1 and not ids1 & ids2, "inlined icons must not share ids")
        refs = set(re.findall(r'url\(#([^)]+)\)|href="#([^"]+)"', s1))
        self.assertEqual({a or b for a, b in refs}, ids1, "every reference points at a renamed id")
        self.assertIn('viewBox="0 0 64 64"', s1)
        with self.assertRaises(icons.IconError):
            icons.resolve("aws:no-such-icon")

    def test_azure_and_gcp_naming(self):
        za = os.path.join(self.tmp.name, "az.zip")
        fake_zip(za, ["Azure_Public_Service_Icons/Icons/databases/10121-icon-service-Azure-Cosmos-DB.svg",
                      "Azure_Public_Service_Icons/Icons/other/10121-icon-service-Azure-Cosmos-DB.svg"])
        icons.fetch("azure", True, za, log=lambda *_: None)
        self.assertEqual([e["slug"] for e in icons.pack_index("azure")], ["azure-cosmos-db"])
        self.assertEqual(icons.resolve("Cosmos DB")["ref"], "azure:azure-cosmos-db")
        zl, zc = os.path.join(self.tmp.name, "l.zip"), os.path.join(self.tmp.name, "c.zip")
        fake_zip(zl, ["cloud_storage/cloud_storage.svg", "pubsub/pubsub.svg", "vertexai/vertexai.svg"])
        fake_zip(zc, ["Unique Icons/Cloud Storage/SVG/Cloud_Storage-512-color.svg"])
        icons.fetch("gcp", True, [zl, zc], log=lambda *_: None)
        e = {x["slug"]: x for x in icons.pack_index("gcp")}
        self.assertEqual(e["cloud-storage"]["category"], "Core products")
        self.assertEqual(icons.resolve("GCS")["ref"], "gcp:cloud-storage")
        self.assertEqual(icons.resolve("pub/sub")["ref"], "generic:queue")
        self.assertEqual(icons.resolve("Cloud Pub/Sub")["ref"], "gcp:pubsub")


class FetchedPacks(unittest.TestCase):
    """When the real packs are in the cache, every alias concept must still
    find at least one of its listed icons (catches vendor renames)."""

    def test_alias_slugs_exist(self):
        fetched = [p for p in icons.PACKS if icons.pack_index(p)]
        if not fetched:
            self.skipTest("no vendor packs fetched")
        missing = []
        for c in icons.aliases():
            for p in fetched:
                if p in c and c[p]["icons"] and not any(icons._entry(p, s) for s in c[p]["icons"]):
                    missing.append(f"{c['concept']} / {p}: {c[p]['icons']}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
