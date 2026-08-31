from twisted.web import resource
from twisted.internet import reactor
import time

from hatena import Log, NotFound, request_args, request_path
from DB import Database
from Hatenatools import UGO


class PyResource(resource.Resource):
    isLeaf = True

    def __init__(self):
        super().__init__()
        self.pages = []
        self.newestflip = None
        self.neweststar = None
        reactor.callLater(2, self.Update)

    def render(self, request):
        try:
            page = int(request_args(request).get("page", ["1"])[0])
        except ValueError:
            page = 1
        if 1 <= page <= len(self.pages):
            path = "/".join(request_path(request).split("/")[3:])
            Log(request, "%s page %i" % (path, page))
            request.setHeader(b"content-type", b"text/plain")
            return self.pages[page - 1]
        return NotFound.render(request)

    def Update(self):
        reactor.callLater(600, self.Update)
        current = Database.Newest[0] if Database.Newest else None
        if current != self.newestflip or self.neweststar != Database.Stars:
            self.newestflip = current
            self.neweststar = Database.Stars
            reactor.callInThread(self.UpdateThreaded, list(Database.Newest))

    def UpdateThreaded(self, flipnotes):
        def score(item):
            i, (creator_id, flip) = item
            views, stars = Database.GetFlipnote(creator_id, flip)[1:3]
            return int(stars) * 110 + int(views) // 10 - i
        flipnotes = [x[1] for x in sorted(enumerate(flipnotes), key=score, reverse=True)[:500]]
        pages = []
        pagecount = (len(flipnotes) + 49) // 50
        pagecount = min(pagecount, 10)
        flipcount = min(len(flipnotes), 500)
        for i in range(pagecount):
            pages.append(self.MakePage(flipnotes[i * 50 : i * 50 + 50], i + 1, i < pagecount - 1, flipcount))
        if self.pages:
            print(time.strftime("[%H:%M:%S] Updated likedmovies.ugo"))
        self.pages = pages

    def MakePage(self, flipnotes, page, has_next, count):
        ugo = UGO()
        ugo.Loaded = True
        ugo.Items = []
        ugo.Items.append(("layout", (2, 1)))
        ugo.Items.append(("topscreen text", ["Liked Flipnotes", "Flipnotes", str(count), "", "The most liked new Flipnotes."], 0))
        ugo.Items.append(("category", "http://flipnote.hatena.com/ds/v2-xx/frontpage/hotmovies.uls", "Most Popular", False))
        ugo.Items.append(("category", "http://flipnote.hatena.com/ds/v2-xx/frontpage/likedmovies.uls", "Most Liked", True))
        ugo.Items.append(("category", "http://flipnote.hatena.com/ds/v2-xx/frontpage/newmovies.uls", "New Flipnotes", False))
        ugo.Items.append(("unknown", ("3", "http://flipnote.hatena.com/ds/v2-xx/help/post_howto.htm", "UABvAHMAdAAgAEYAbABpAHAAbgBvAHQAZQA=")))
        if page > 1:
            ugo.Items.append(("button", 115, "Previous", "http://flipnote.hatena.com/ds/v2-xx/frontpage/likedmovies.uls?page=%i" % (page - 1), ("", ""), None))
        for creatorid, filename in flipnotes:
            stars = str(Database.GetFlipnote(creatorid, filename)[2])
            ugo.Items.append(("button", 3, "", "http://flipnote.hatena.com/ds/v2-xx/movie/%s/%s.ppm" % (creatorid, filename), (stars, "765", "573", "0"), (filename + ".ppm", Database.GetFlipnoteTMB(creatorid, filename))))
        if has_next:
            ugo.Items.append(("button", 115, "Next", "http://flipnote.hatena.com/ds/v2-xx/frontpage/likedmovies.uls?page=%i" % (page + 1), ("", ""), None))
        return ugo.Pack()
