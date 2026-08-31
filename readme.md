# Hatena server — Python 3 port

This is a replacement server for the discontinued Flipnote Hatena service used by Flipnote Studio on Nintendo DSi.

This repository has been ported from its original Python 2.7 implementation to **Python 3**. The server protocol, URL layout, plaintext database, bundled Hatena resources, PPM/TMB handling, UGO handling, and NTFT handling are retained.

## Requirements

- Python 3.9 or newer (the port is tested with Python 3.13)
- Twisted
- NumPy
- Pillow
- `ffmpeg` only if you want to use the optional PPM-to-MKV export command

Install Python dependencies with:

```bash
python3 -m pip install -r requirements.txt
```

## Run the server

From the repository root:

```bash
python3 server.py
```

The server listens on TCP port **8080** by default, matching the original project. Point the DSi proxy settings at the machine running this server, port 8080, then open Flipnote Studio.

The server accepts the absolute-form HTTP request targets normally sent by a proxy client and restricts normal Hatena routes to requests carrying the DSi session header, as the original implementation did.

## Hatenatools utilities

The bundled format utilities are Python 3 compatible:

```bash
python3 Hatenatools/PPM.py
python3 Hatenatools/UGO.py
python3 Hatenatools/NTFT.py
```

PPM/TMB parsing, thumbnails, frame decoding, sound decoding, UGO packing/parsing, and NTFT packing/parsing use `bytes` explicitly under Python 3. The PPM sound decoder no longer depends on the removed `audioop` standard-library module, so it works on Python 3.13+.

## Tests

Run the included smoke/regression suite with:

```bash
python3 -m unittest discover -s tests -v
```

The tests use the original repository's bundled sample Flipnote and NTFT/UGO assets. The server resource-tree smoke test can run even when Twisted is not installed by using a minimal test-only stub; running the actual server still requires Twisted.

## Notes

The database remains the original single-process plaintext backend. Its files live under `database/`, and uploaded Flipnotes are written under `database/Creators/<creator-id>/`.

The original project and Hatenatools licensing files are retained. See `license.md` and `Hatenatools/License.txt`.
