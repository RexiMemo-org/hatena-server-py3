from twisted.web import resource

from hatena import Log, ServerLog, Silent, NotFound, as_text, request_path, request_args, request_headers, client_ip
from DB import Database
from Hatenatools import TMB


class PyResource(resource.Resource):
    isLeaf = False

    def __init__(self):
        super().__init__()
        self.CreatorID = CreatorIDResource()

    def getChild(self, name, request):
        name = as_text(name)
        if Database.CreatorExists(name):
            return self.CreatorID
        if name == "":
            return self
        return NotFound

    def render(self, request):
        request.setResponseCode(403)
        return b"403 - Denied access"


class CreatorIDResource(resource.Resource):
    isLeaf = False

    def __init__(self):
        super().__init__()
        self.CreatorIDFile = CreatorIDFileResource()

    def getChild(self, name, request):
        creator_id = request_path(request).split("/")[-2]
        name = as_text(name)
        filename = ".".join(name.split(".")[:-1])
        if Database.FlipnoteExists(creator_id, filename):
            return self.CreatorIDFile
        if name == "":
            return self
        return NotFound

    def render(self, request):
        request.setResponseCode(403)
        return b"403 - Denied access"


class CreatorIDFileResource(resource.Resource):
    isLeaf = True

    def render(self, request):
        creator, file = request_path(request).split("/")[-2:]
        filetype = file.rsplit(".", 1)[-1].lower()
        path = "/".join(request_path(request).split("/")[3:])

        if filetype == "ppm":
            Log(request, path)
            Database.AddView(creator, file[:-4])
            request.setHeader(b"content-type", b"text/plain")
            return Database.GetFlipnotePPM(creator, file[:-4])

        if filetype == "info":
            Log(request, path, True)
            request.setHeader(b"content-type", b"text/plain")
            return b"0\n0\n"

        if filetype == "htm":
            request.setHeader(b"content-type", b"text/html; charset=utf-8")
            return self.GenerateDetailsPage(creator, ".".join(file.split(".")[:-1])).encode("UTF-8")

        if filetype == "star":
            args = request_args(request)
            color = args.get("starcolor", ["yellow"])[0].split(",", 1)[0].lower()
            headers = request_headers(request)
            if "x-hatena-star-count" not in headers:
                ServerLog.write(
                    "%s got 403 when requesting %s without a X-Hatena-Star-Count header" % (client_ip(request), path),
                    Silent,
                )
                request.setResponseCode(403)
                return b"403 - Denied access\nRequest lacks a X-Hatena-Star-Count http header"
            try:
                amount = int(headers["x-hatena-star-count"])
            except ValueError:
                amount = 0
            if amount < 1 or amount > 65535:
                ServerLog.write(
                    "%s got 403 when requesting %s with an invalid X-Hatena-Star-Count header" % (client_ip(request), path),
                    Silent,
                )
                request.setResponseCode(403)
                return b"403 - Denied access\nRequest has an invalid X-Hatena-Star-Count http header"
            if not Database.AddStar(creator, file[:-5], amount, color):
                ServerLog.write("%s got 500 when requesting %s" % (client_ip(request), path), Silent)
                request.setResponseCode(500)
                return b"500 - Internal server error\nAdding the stars seems to have failed."
            ServerLog.write(
                "%s added %i %s stars to %s/%s.ppm" % (client_ip(request), amount, color, creator, file[:-5]),
                Silent,
            )
            return b"Success"

        if filetype == "dl":
            Log(request, path, True)
            Database.AddDownload(creator, file[:-3])
            return b"Noted ;)"

        ServerLog.write("%s got 403 when requesting %s" % (client_ip(request), path), Silent)
        request.setResponseCode(403)
        return b"403 - Denied access"

    def GenerateDetailsPage(self, CreatorID, filename):
        flipnote = Database.GetFlipnote(CreatorID, filename)
        if not flipnote:
            return "This flipnote doesn't exist!"
        tmb = TMB().Read(Database.GetFlipnoteTMB(CreatorID, filename))
        if not tmb:
            return "This flipnote is corrupt!"

        spinoff = ""
        if tmb.OriginalAuthorID != tmb.EditorAuthorID or tmb.OriginalFilename != tmb.CurrentFilename:
            if Database.FlipnoteExists(tmb.OriginalAuthorID, tmb.OriginalFilename[:-4]):
                spinoff = SpinoffTemplate1.replace("%%CreatorID%%", tmb.OriginalAuthorID).replace("%%Filename%%", tmb.OriginalFilename[:-4])
            elif tmb.OriginalAuthorID != tmb.EditorAuthorID:
                spinoff = SpinoffTemplate2

        entries = []
        content = '<a href="http://flipnote.hatena.com/ds/v2-xx/%s/profile.htm?t=260&pm=80">%s</a>' % (CreatorID, tmb.Username)
        entries.append(PageEntryTemplate.replace("%%Name%%", "Creator").replace("%%Content%%", content))

        content = '<a href="http://flipnote.hatena.com/ds/v2-xx/movie/%s/%s.htm?mode=stardetail"><span class="star0c">★</span> <span class="star0">%s</span></a>' % (CreatorID, filename, flipnote[2])
        for css, value in zip(("1", "2", "3", "4"), flipnote[3:7]):
            content += '<br/><a href="http://flipnote.hatena.com/ds/v2-xx/movie/%s/%s.htm?mode=stardetail"><span class="star%sc">★</span> <span class="star%s">%s</span></a>' % (CreatorID, filename, css, css, value)
        entries.append(PageEntryTemplate.replace("%%Name%%", "Stars").replace("%%Content%%", content))
        entries.append(PageEntryTemplate.replace("%%Name%%", "Views").replace("%%Content%%", str(flipnote[1])))
        entries.append(PageEntryTemplate.replace("%%Name%%", "Downloads").replace("%%Content%%", str(flipnote[8])))

        if flipnote[7]:
            content = '<a href="http://flipnote.hatena.com/ds/v2-xx/ch/%s.uls">%s</a>' % (flipnote[7], flipnote[7])
            entries.append(PageEntryTemplate.replace("%%Name%%", "Channel").replace("%%Content%%", content))

        return (
            DetailsPageTemplate.replace("%%CreatorID%%", CreatorID)
            .replace("%%Filename%%", filename)
            .replace("%%Username%%", tmb.Username)
            .replace("%%CommentCount%%", "0")
            .replace("%%Spinoff%%", spinoff)
            .replace("%%PageEntries%%", PageEntrySeparator.join(entries))
        )

#templates:
DetailsPageTemplate = """<html>
	<head>
		<title>Flipnote by %%Username%%</title>
		<meta name="upperlink" content="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.ppm">
		<meta name="starbutton" content="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.star">
    		<meta name="starbutton1" content="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.star?starcolor=green,9001">
    		<meta name="starbutton2" content="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.star?starcolor=red,9001">
    		<meta name="starbutton3" content="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.star?starcolor=blue,9001">
    		<meta name="starbutton4" content="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.star?starcolor=purple,9001">
		<meta name="savebutton" content="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.ppm">
		<meta name="playcontrolbutton" content="">
		<link rel="stylesheet" href="http://flipnote.hatena.com/css/ds/basic.css">
	</head>
	<body>
		<table width="240" border="0" cellspacing="0" cellpadding="0" class="tab">
			<tr>
				<td class="border" width="5" align="center">
					<div class="border"></div>
				</td>
				<td class="border" width="70" align="center">
					<div class="border"></div>
				</td>
				<td class="border" width="95" align="center">
					<div class="border"></div>
				</td>
			</tr>
			<tr>
				<td class="space"> </td>
				<td class="tabon" align="center">
					<div class="on" align="center">Description</div>
				</td>
				<td class="taboff" align="center">
					<a class="taboff" href="http://flipnote.hatena.com/ds/v2-eu/movie/%%CreatorID%%/%%Filename%%.htm?mode=commentshalfsize">Comments(%%CommentCount%%)</a>
				</td>
			</tr>
		</table>
		<div class="pad5b"></div>%%Spinoff%%
		<table width="226" border="0" cellspacing="0" cellpadding="0" class="detail">%%PageEntries%%
		</table>
	</body>
</html>"""
SpinoffTemplate1 = """
		<div class="notice2" align="center">
			This Flipnote is a spin-off.<br>
			<a href="http://flipnote.hatena.com/ds/v2-eu/movie/%%CreatorID%%/%%Filename%%.htm">Original Flipnote</a>
		</div>"""
SpinoffTemplate2 = """
		<div class="notice2" align="center">
			This Flipnote is a spin-off.
		</div>"""
PageEntryTemplate = """
			<tr>
				<th width="90">
					<div class="item-term" align="left">%%Name%%</div>
				</th>
				<td width="136">
					<div class="item-value" align="right">
						%%Content%%
					</div>
				</td>
			</tr>"""
PageEntrySeparator="""
			<tr> </tr>
			<tr>
				<td colspan="2">
					<div class="hr"></div>
				</td>
			</tr>"""
