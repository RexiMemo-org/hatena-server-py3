from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import database as database_module


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CREATOR = "913304C0CC74CC1F"
SAMPLE_NAME = "74CC1F_0D3AA40F2B3A0_000"


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        temp_root = Path(self.tmp.name)
        shutil.copytree(ROOT / "database", temp_root / "database")
        os.chdir(temp_root)
        self.db = database_module.Database.__class__()

    def tearDown(self):
        # Prevent the per-test instance from having anything left to flush at interpreter exit.
        self.db.Creator.clear()
        self.db.new = False
        os.chdir(self.old_cwd)
        self.tmp.cleanup()

    def test_read_sample(self):
        self.assertTrue(self.db.CreatorExists(SAMPLE_CREATOR))
        row = self.db.GetFlipnote(SAMPLE_CREATOR, SAMPLE_NAME)
        self.assertTrue(row)
        self.assertEqual(row[0], SAMPLE_NAME)
        self.assertEqual(len(row), 9)
        self.assertTrue(self.db.GetFlipnotePPM(SAMPLE_CREATOR, SAMPLE_NAME).startswith(b"PARA"))
        self.assertEqual(len(self.db.GetFlipnoteTMB(SAMPLE_CREATOR, SAMPLE_NAME)), 0x6A0)

    def test_counters_and_write(self):
        self.assertTrue(self.db.AddView(SAMPLE_CREATOR, SAMPLE_NAME))
        self.assertTrue(self.db.AddStar(SAMPLE_CREATOR, SAMPLE_NAME, 5, "green"))
        self.assertTrue(self.db.AddDownload(SAMPLE_CREATOR, SAMPLE_NAME))
        self.assertEqual(self.db.Views, 1)
        self.assertEqual(self.db.Stars, 1)
        self.assertEqual(self.db.Downloads, 1)
        row = self.db.GetFlipnote(SAMPLE_CREATOR, SAMPLE_NAME, True)
        self.assertEqual(int(row[1]), 3)
        self.assertEqual(int(row[3]), 5)
        self.assertEqual(int(row[8]), 1)
        self.db.write()
        text = Path("database/Creators") / SAMPLE_CREATOR / "flipnotes.dat"
        self.assertIn("\t3\t", text.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
