from twisted.web import resource

from hatena import ServerLog, Silent, request_args, client_ip
from DB import Database


class PyResource(resource.Resource):
    isLeaf = True

    def render_GET(self, request):
        ServerLog.write("%s got 403 when requesting post/flipnote.post with GET" % client_ip(request), Silent)
        request.setResponseCode(405)
        return b"405 - Method Not Allowed"

    def render_POST(self, request):
        data = request.content.read()
        channel = request_args(request).get("channel", [""])[0]
        add = Database.AddFlipnote(data, channel)
        if add:
            ServerLog.write('%s successfully uploaded "%s.ppm"' % (client_ip(request), add[1]), Silent)
            request.setResponseCode(200)
        else:
            ServerLog.write("%s tried to upload a flipnote, but failed..." % client_ip(request), Silent)
            request.setResponseCode(500)
        return b""
