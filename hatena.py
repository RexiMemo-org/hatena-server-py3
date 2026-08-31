from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from urllib.parse import urlencode

from twisted.web import resource, static

from Hatenatools import NTFT, PPM, TMB, UGO

ServerLog = None  # Set by server.py
Silent = False


def as_text(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def as_bytes(value):
    if isinstance(value, bytes):
        return value
    return str(value).encode("utf-8")


def request_path(request):
    return as_text(request.path)


def request_headers(request):
    return {as_text(k).lower(): as_text(v) for k, v in request.getAllHeaders().items()}


def request_args(request):
    out = {}
    for key, values in request.args.items():
        out[as_text(key)] = [as_text(v) for v in values]
    return out


def client_ip(request):
    # getClientIP exists on the Twisted versions this project historically used;
    # getClientAddress is the modern fallback.
    getter = getattr(request, "getClientIP", None)
    if getter is not None:
        value = getter()
        if value:
            return as_text(value)
    address = request.getClientAddress()
    return as_text(getattr(address, "host", address))


def Log(request, path=None, silent=Silent):
    if path is None:
        path = '"%s"' % request_path(request)
    if ServerLog is not None:
        ServerLog.write("%s requested %s" % (client_ip(request), path), silent)


class AccessDeniedResource(resource.Resource):
    isLeaf = True

    def render(self, request):
        if ServerLog is not None:
            ServerLog.write(
                '%s got 403 when requesting "%s"' % (client_ip(request), request_path(request)),
                Silent,
            )
        request.setResponseCode(403)
        request.setHeader(b"content-type", b"text/plain; charset=utf-8")
        return b"403 - Access denied\nThis proxy is only allowed to use for Flipnote Hatena for the DSi."


AccessDenied = AccessDeniedResource()


class NotFoundResource(resource.Resource):
    isLeaf = True

    def render(self, request):
        args = request_args(request)
        query = urlencode([(k, v) for k, values in args.items() for v in values])
        path = request_path(request)
        if query:
            path += "?" + query
        if ServerLog is not None:
            ServerLog.write('%s got 404 when requesting "%s"' % (client_ip(request), path), Silent)
        request.setResponseCode(404)
        request.setHeader(b"content-type", b"text/plain; charset=utf-8")
        return b"404 - Not Found\nThis proxy is only allowed to use for Flipnote Hatena for the DSi."


NotFound = NotFoundResource()


class ConnectionTestResource(resource.Resource):
    isLeaf = True

    def render(self, request):
        if ServerLog is not None:
            ServerLog.write("%s performed a connection test" % client_ip(request), True)
        request.setHeader(b"X-Organization", b"Nintendo")
        request.setHeader(b"content-type", b"text/html; charset=utf-8")
        return b'<html><head><title>HTML Page</title></head><body bgcolor="#FFFFFF">This is test.html page</body></html>'


ConnectionTest = ConnectionTestResource()


class Root(resource.Resource):
    isLeaf = False

    def __init__(self):
        super().__init__()
        self.dsResource = ds()
        self.cssResource = static.File("hatenadir/css/")
        self.imagesResource = static.File("hatenadir/images/")

    def getChild(self, name, request):
        name = as_text(name)
        headers = request_headers(request)
        if "x-dsi-sid" not in headers:
            if headers.get("host", "").split(":", 1)[0].lower() == "conntest.nintendowifi.net":
                return ConnectionTest
            return AccessDenied

        if name == "ds":
            return self.dsResource
        if name == "css":
            return self.cssResource
        if name == "images":
            return self.imagesResource
        if name == "":
            return self
        # The original server intentionally tolerated extra leading path pieces.
        return self

    def render(self, request):
        headers = request_headers(request)
        if headers.get("host", "").split(":", 1)[0].lower() == "conntest.nintendowifi.net":
            return ConnectionTest.render(request)
        Log(request, "root")
        request.setHeader(b"content-type", b"text/plain; charset=utf-8")
        return b"Welcome to hatena.pbsds.net!\nThis is still in early stages, so please don't expect too much."


class ds(resource.Resource):
    isLeaf = False

    def __init__(self):
        super().__init__()
        self.region = UgoRoot()
        self.regions = {"v2-xx", "v2-eu", "v2-us", "v2-jp"}

    def getChild(self, name, request):
        name = as_text(name)
        if name in self.regions:
            return self.region
        if name == "":
            return self
        return NotFound

    def render(self, request):
        Log(request)
        return b"ds desu"


class UgoRoot(resource.Resource):
    isLeaf = False

    def __init__(self):
        super().__init__()
        LoadHatenadirStructure(self)

    def getChild(self, name, request):
        if as_text(name) == "":
            return self
        return NotFound

    def render(self, request):
        Log(request, "ugoroot")
        return b"UgoRoot desu"


class FileResource(resource.Resource):
    isLeaf = True

    def __init__(self, filepath, Store=False):
        super().__init__()
        self.Store = Store
        self.file = open(filepath, "rb").read() if Store else filepath
        self.html = filepath.split(".")[-1][:3].lower() == "htm"

    def render(self, request):
        path = "/".join(request_path(request).split("/")[3:])
        Log(request, path)
        if self.html:
            request.setHeader(b"content-type", b"text/html; charset=utf-8")
        else:
            request.setHeader(b"content-type", b"text/plain")
        if self.Store:
            return self.file
        return static.File(self.file).render(request)


class UGOXMLResource(resource.Resource):
    isLeaf = True

    def __init__(self, filepath):
        super().__init__()
        ugo = UGO().ReadXML(filepath, False)
        if not ugo:
            raise ValueError("Could not parse UGOXML file: %s" % filepath)
        self.ugofile = ugo.Pack()

    def render(self, request):
        path = "/".join(request_path(request).split("/")[3:])
        Log(request, path)
        request.setHeader(b"content-type", b"text/plain")
        return self.ugofile


class FolderResource(resource.Resource):
    isLeaf = False

    def getChild(self, name, request):
        if as_text(name) == "":
            return self
        return NotFound

    def render(self, request):
        path = "/".join(request_path(request).split("/")[3:])
        Log(request, path)
        return b"I am a folder, but I'm too lazy to list my contents..."


def _load_python_resource(filepath):
    module_name = "hatena_dynamic_" + hashlib.sha1(os.path.abspath(filepath).encode("utf-8")).hexdigest()
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    if spec is None or spec.loader is None:
        raise ImportError("Could not create import spec for %s" % filepath)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def LoadHatenadirStructure(Resource, path=os.path.join("hatenadir", "ds", "v2-xx")):
    for root, dirs, files in os.walk(path):
        if root != path:
            continue

        for filename in files:
            filetype = filename.split(".")[-1].lower()
            filepath = os.path.join(path, filename)
            if filetype == "ugoxml":
                Resource.putChild(filename[:-3].encode("utf-8"), UGOXMLResource(filepath))
            elif filetype == "py":
                try:
                    pyfile = _load_python_resource(os.path.abspath(filepath))
                except Exception as err:
                    print("Error!")
                    print('Failed to import the python file "%s"' % filepath)
                    print(err)
                    raise
                Resource.putChild(filename[:-3].encode("utf-8"), pyfile.PyResource())
            elif filetype == "pyc":
                continue
            else:
                Resource.putChild(filename.encode("utf-8"), FileResource(filepath))

        for foldername in dirs:
            if not foldername.startswith("__"):
                folder = FolderResource()
                LoadHatenadirStructure(folder, os.path.join(path, foldername))
                Resource.putChild(foldername.encode("utf-8"), folder)
        break


def Setup():
    return Root()
