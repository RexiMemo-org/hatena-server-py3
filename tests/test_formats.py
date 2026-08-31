from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from Hatenatools import NTFT, PPM, TMB, UGO
from Hatenatools.PPM import WriteImage, get_metadata


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PPM = ROOT / "database" / "Creators" / "913304C0CC74CC1F" / "74CC1F_0D3AA40F2B3A0_000.ppm"
NEWS_NTFT = ROOT / "hatenadir" / "ds" / "v2-xx" / "__ntfts" / "News.ntft"
KAERU_NTFT = ROOT / "hatenadir" / "images" / "ds" / "kaeru.ntft"
INDEX_UGOXML = ROOT / "hatenadir" / "ds" / "v2-xx" / "index.ugoxml"
INBOX_UGOXML = ROOT / "hatenadir" / "ds" / "v2-xx" / "inbox.ugoxml"


class PPMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = SAMPLE_PPM.read_bytes()

    def test_tmb_metadata_and_exact_pack(self):
        tmb = TMB().Read(self.data[:0x6A0], DecodeThumbnail=True)
        self.assertTrue(tmb)
        self.assertEqual(tmb.EditorAuthorID, "913304C0CC74CC1F")
        self.assertEqual(tmb.CurrentFilename, "74CC1F_0D3AA40F2B3A0_000.tmb")
        self.assertEqual(tmb.FrameCount, 3)
        self.assertEqual(tmb.GetThumbnail().shape, (64, 48))
        self.assertEqual(tmb.Pack(), self.data[:0x6A0])

    def test_ppm_full_parse_and_frame(self):
        ppm = PPM().Read(self.data, DecodeThumbnail=True, ReadFrames=True, ReadSound=True)
        self.assertTrue(ppm)
        self.assertEqual(ppm.EditorAuthorID, "913304C0CC74CC1F")
        self.assertEqual(ppm.CurrentFilename, "74CC1F_0D3AA40F2B3A0_000.ppm")
        self.assertEqual(ppm.FrameCount, 3)
        self.assertEqual(ppm.GetThumbnail().shape, (64, 48))
        frame = ppm.GetFrame(0)
        self.assertIsInstance(frame, np.ndarray)
        self.assertEqual(frame.shape, (256, 192))
        self.assertEqual(len(ppm.SoundData), 4)

    def test_metadata_helper_infers_filetype(self):
        ppm = PPM().Read(self.data, ReadFrames=False)
        metadata = get_metadata(ppm)
        self.assertEqual(metadata["Current filename"], "74CC1F_0D3AA40F2B3A0_000.ppm")
        self.assertEqual(metadata["Number of frames"], 3)
        self.assertIn("Frame speed", metadata)

    def test_image_export(self):
        ppm = PPM().Read(self.data, DecodeThumbnail=True, ReadFrames=False)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "thumb.png"
            self.assertTrue(WriteImage(ppm.GetThumbnail(), str(output)))
            self.assertGreater(output.stat().st_size, 0)


class NTFTTests(unittest.TestCase):
    def test_exact_roundtrip_news(self):
        raw = NEWS_NTFT.read_bytes()
        image = NTFT().Read(raw, (32, 32))
        self.assertTrue(image)
        self.assertEqual(image.Pack(), raw)

    def test_exact_roundtrip_kaeru(self):
        raw = KAERU_NTFT.read_bytes()
        image = NTFT().Read(raw, (36, 30))
        self.assertTrue(image)
        self.assertEqual(image.Pack(), raw)


class UGOTests(unittest.TestCase):
    def _roundtrip_xml(self, path: Path):
        ugo = UGO().ReadXML(str(path), False)
        self.assertTrue(ugo)
        packed = ugo.Pack()
        self.assertIsInstance(packed, bytes)
        self.assertEqual(packed[:4], b"UGAR")
        decoded = UGO().Read(packed)
        self.assertTrue(decoded)
        # Embedded-file names are XML-side metadata and are not stored in the
        # binary UGO format. The meaningful binary round-trip is idempotence.
        self.assertEqual(decoded.Pack(), packed)

    def test_index_xml(self):
        self._roundtrip_xml(INDEX_UGOXML)

    def test_inbox_xml(self):
        self._roundtrip_xml(INBOX_UGOXML)


if __name__ == "__main__":
    unittest.main()
