from __future__ import annotations

import atexit
import os

try:
    from twisted.internet import reactor
except ImportError:  # Allows the database module to be used/tested without Twisted installed.
    reactor = None

from Hatenatools import TMB


class Database:
    """Plain-text Flipnote database used by the original server.

    This backend is intentionally single-process, matching the original design.
    """

    def __init__(self):
        newest_path = "database/new_flipnotes.dat"
        if os.path.exists(newest_path):
            with open(newest_path, "r", encoding="utf-8", newline="") as f:
                raw = f.read()
        else:
            raw = ""

        self.Newest = [tuple(line.split("\t")) for line in raw.splitlines() if line] if raw else []
        self.Creator = {}

        self.new = False
        self.Views = 0
        self.Stars = 0
        self.Downloads = 0

        if reactor is not None:
            reactor.callLater(60 * 3, self.flusher)
        atexit.register(self.write)

    def flusher(self):
        if reactor is not None:
            reactor.callLater(60 * 3, self.flusher)
        self.write()

    def write(self):
        if self.new:
            if len(self.Newest) > 5000:
                self.Newest = self.Newest[:5000]
            with open("database/new_flipnotes.dat", "w", encoding="utf-8", newline="") as f:
                f.write("\n".join("\t".join(map(str, row)) for row in self.Newest))
            self.new = False

        for creator_id in list(self.Creator.keys()):
            creator_dir = os.path.join("database", "Creators", creator_id)
            os.makedirs(creator_dir, exist_ok=True)
            with open(os.path.join(creator_dir, "flipnotes.dat"), "w", encoding="utf-8", newline="") as f:
                f.write("\n".join("\t".join(map(str, row)) for row in self.Creator[creator_id]))
            del self.Creator[creator_id]

    def CreatorExists(self, CreatorID):
        return os.path.exists(os.path.join("database", "Creators", CreatorID)) or CreatorID in self.Creator

    def FlipnoteExists(self, CreatorID, filename):
        return os.path.exists(self.FlipnotePath(CreatorID, filename))

    def GetCreator(self, CreatorID, Store=False):
        if CreatorID in self.Creator:
            return self.Creator[CreatorID]

        creator_dir = os.path.join("database", "Creators", CreatorID)
        if not os.path.exists(creator_dir):
            return None

        with open(os.path.join(creator_dir, "flipnotes.dat"), "r", encoding="utf-8", newline="") as f:
            raw = f.read()
        ret = [line.split("\t") for line in raw.splitlines() if line]

        # Current format:
        # filename, views, stars, green, red, blue, purple, channel, downloads
        for row in ret:
            filename = row[0]
            defaults = (filename, 0, 0, 0, 0, 0, 0, "", 0)
            while len(row) < len(defaults):
                row.append(defaults[len(row)])

        if Store:
            self.Creator[CreatorID] = ret
        return ret

    def GetFlipnote(self, CreatorID, filename, Store=False):
        for row in self.GetCreator(CreatorID, Store) or []:
            if row[0] == filename:
                return row
        return False

    def GetFlipnotePPM(self, CreatorID, filename):
        with open(self.FlipnotePath(CreatorID, filename), "rb") as f:
            return f.read()

    def GetFlipnoteTMB(self, CreatorID, filename):
        with open(self.FlipnotePath(CreatorID, filename), "rb") as f:
            return f.read(0x6A0)

    def AddFlipnote(self, content, Channel=""):
        content = bytes(content)
        tmb = TMB().Read(content)
        if not tmb:
            return False

        CreatorID = tmb.EditorAuthorID
        filename = tmb.CurrentFilename[:-4]
        if self.FlipnoteExists(CreatorID, filename):
            return False

        self.new = True
        self.Newest.insert(0, (CreatorID, filename))

        if not self.GetCreator(CreatorID, True):
            self.Creator[CreatorID] = [[filename, 0, 0, 0, 0, 0, 0, Channel, 0]]
        else:
            self.Creator[CreatorID].append([filename, 0, 0, 0, 0, 0, 0, Channel, 0])

        creator_dir = os.path.join("database", "Creators", CreatorID)
        os.makedirs(creator_dir, exist_ok=True)
        with open(self.FlipnotePath(CreatorID, filename), "wb") as f:
            f.write(content)
        return CreatorID, filename

    def AddView(self, CreatorID, filename):
        for i, flipnote in enumerate(self.GetCreator(CreatorID, True) or []):
            if flipnote[0] == filename:
                self.Creator[CreatorID][i][1] = int(flipnote[1]) + 1
                self.Views += 1
                return True
        return False

    def AddStar(self, CreatorID, filename, amount=1, color="yellow"):
        starindices = {"yellow": 2, "green": 3, "red": 4, "blue": 5, "purple": 6}
        if color not in starindices:
            return False
        for i, flipnote in enumerate(self.GetCreator(CreatorID, True) or []):
            if flipnote[0] == filename:
                idx = starindices[color]
                self.Creator[CreatorID][i][idx] = int(flipnote[idx]) + amount
                self.Stars += 1
                return True
        return False

    def AddDownload(self, CreatorID, filename):
        for i, flipnote in enumerate(self.GetCreator(CreatorID, True) or []):
            if flipnote[0] == filename:
                self.Creator[CreatorID][i][8] = int(flipnote[8]) + 1
                self.Downloads += 1
                return True
        return False

    def FlipnotePath(self, CreatorID, filename):
        return os.path.join("database", "Creators", CreatorID, filename + ".ppm")


Database = Database()
