from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def install_twisted_stub():
    """Install only the Twisted surface needed to smoke-test this project."""
    if importlib.util.find_spec("twisted") is not None:
        return

    twisted = types.ModuleType("twisted")
    web = types.ModuleType("twisted.web")
    resource_mod = types.ModuleType("twisted.web.resource")
    static_mod = types.ModuleType("twisted.web.static")
    internet_mod = types.ModuleType("twisted.internet")

    class Resource:
        isLeaf = False

        def __init__(self):
            self.children = {}

        def putChild(self, name, child):
            if not isinstance(name, bytes):
                raise TypeError("Twisted child names must be bytes")
            self.children[name] = child

        def getChild(self, name, request):
            return self

        def getChildWithDefault(self, name, request):
            return self.children.get(name, self.getChild(name, request))

    class File(Resource):
        def __init__(self, path):
            super().__init__()
            self.path = path

        def render(self, request):
            p = Path(self.path)
            return p.read_bytes() if p.is_file() else b""

    class Reactor:
        def __init__(self):
            self.calls = []

        def callLater(self, delay, func, *args, **kwargs):
            self.calls.append((delay, func, args, kwargs))
            return object()

        def callInThread(self, func, *args, **kwargs):
            return func(*args, **kwargs)

    resource_mod.Resource = Resource
    static_mod.File = File
    web.resource = resource_mod
    web.static = static_mod
    internet_mod.reactor = Reactor()
    twisted.web = web
    twisted.internet = internet_mod

    sys.modules.update(
        {
            "twisted": twisted,
            "twisted.web": web,
            "twisted.web.resource": resource_mod,
            "twisted.web.static": static_mod,
            "twisted.internet": internet_mod,
        }
    )


class ResourceTreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_twisted_stub()
        cls.old_cwd = Path.cwd()
        import os
        os.chdir(ROOT)
        import hatena
        cls.hatena = hatena
        cls.root = hatena.Setup()

    @classmethod
    def tearDownClass(cls):
        import os
        os.chdir(cls.old_cwd)

    def test_core_resource_tree_loads(self):
        region = self.root.dsResource.region
        expected = {
            b"index.ugo",
            b"inbox.ugo",
            b"movie",
            b"post",
            b"frontpage",
            b"help",
            b"eula_list.tsv",
        }
        self.assertTrue(expected.issubset(region.children))
        self.assertIn(b"flipnote.post", region.children[b"post"].children)
        self.assertIn(b"hotmovies.ugo", region.children[b"frontpage"].children)
        self.assertIn(b"likedmovies.ugo", region.children[b"frontpage"].children)
        self.assertIn(b"newmovies.ugo", region.children[b"frontpage"].children)

    def test_prepacked_ugo_resources_are_binary(self):
        region = self.root.dsResource.region
        self.assertTrue(region.children[b"index.ugo"].ugofile.startswith(b"UGAR"))
        self.assertTrue(region.children[b"inbox.ugo"].ugofile.startswith(b"UGAR"))

    def test_hot_page_builds_from_database(self):
        hot = self.root.dsResource.region.children[b"frontpage"].children[b"hotmovies.ugo"]
        self.assertGreaterEqual(len(hot.pages), 1)
        self.assertTrue(hot.pages[0].startswith(b"UGAR"))


if __name__ == "__main__":
    unittest.main()
