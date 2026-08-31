# NTFT.py by pbsds
# AGPL3 licensed
# Python 3 port

from __future__ import annotations

import os
import sys
import numpy as np

try:
    from PIL import Image
    hasPIL = True
except ImportError:
    Image = None
    hasPIL = False


def AscDec(data, LittleEndian=False):
    if isinstance(data, str):
        data = data.encode("latin-1")
    return int.from_bytes(bytes(data), "little" if LittleEndian else "big")


def DecAsc(dec, length=None, LittleEndian=False):
    if dec < 0:
        raise ValueError("DecAsc does not support negative values")
    if length is None:
        length = max(1, (dec.bit_length() + 7) // 8) if dec else 0
    if length == 0:
        return b""
    dec &= (1 << (length * 8)) - 1
    return dec.to_bytes(length, "little" if LittleEndian else "big")


def clamp(value, minimum, maximum):
    if value > maximum:
        return maximum
    if value < minimum:
        return minimum
    return value


class NTFT:
    """Reader/writer for Nintendo's raw ARGB1555 NTFT image data."""

    def __init__(self):
        self.Loaded = False
        self.Image = None

    def ReadFile(self, path, size):
        with open(path, "rb") as f:
            return self.Read(f.read(), size)

    def Read(self, data, size):
        w, h = size
        data = bytes(data)

        psize = []
        for dimension in (w, h):
            p = 1
            while 1 << p < dimension:
                p += 1
            psize.append(1 << p)
        pw, ph = psize

        if pw * ph * 2 != len(data):
            print("Invalid sizes")
            return False

        self.Image = np.zeros((w, h), dtype=">u4")
        for y in range(h):
            for x in range(w):
                pos = (x + y * pw) * 2
                value = AscDec(data[pos : pos + 2], True)

                a = ((value >> 15) & 0x1) * 0xFF
                b = (((value >> 10) & 0x1F) * 0xFF + 15) // 0x1F
                g = (((value >> 5) & 0x1F) * 0xFF + 15) // 0x1F
                r = ((value & 0x1F) * 0xFF + 15) // 0x1F
                self.Image[x, y] = (r << 24) | (g << 16) | (b << 8) | a

        self.Loaded = True
        return self

    def WriteFile(self, path):
        if not self.Loaded:
            return False
        with open(path, "wb") as f:
            f.write(self.Pack())
        return True

    def Pack(self):
        if not self.Loaded or self.Image is None:
            return False

        w, h = self.Image.shape
        psize = []
        for dimension in (w, h):
            p = 1
            while 1 << p < dimension:
                p += 1
            psize.append(1 << p)

        out = bytearray()
        for y in range(psize[1]):
            for x in range(psize[0]):
                c = int(self.Image[clamp(x, 0, w - 1), clamp(y, 0, h - 1)])
                r = c >> 24
                g = (c >> 16) & 0xFF
                b = (c >> 8) & 0xFF
                a = c & 0xFF

                a = 1 if a >= 0x80 else 0
                r = (r * 0x1F + 127) // 0xFF
                g = (g * 0x1F + 127) // 0xFF
                b = (b * 0x1F + 127) // 0xFF
                value = (a << 15) | (b << 10) | (g << 5) | r
                out.extend(DecAsc(value, 2, True))
        return bytes(out)

    def SetImage(self, image):
        self.Image = image
        self.Loaded = True
        return self


def WriteImage(image, outputPath):
    if not hasPIL:
        print("Error: PIL not found!")
        return False

    out = image.tobytes(order="F")
    pil_image = Image.frombytes("RGBA", (len(image), len(image[0])), out)
    filetype = outputPath[outputPath.rfind(".") + 1 :]
    pil_image.save(outputPath, filetype)
    return True


def ReadImage(path):
    if not hasPIL:
        return False

    image = Image.open(path).convert("RGBA")
    pixeldata = np.asarray(image, dtype=np.uint8)
    w, h = image.size
    ret = np.zeros((w, h), dtype=">u4")
    for x in range(w):
        for y in range(h):
            r, g, b, a = (int(value) for value in pixeldata[y, x])
            ret[x, y] = (r << 24) | (g << 16) | (b << 8) | a
    return ret


def _main():
    print("              ==      NTFT.py     ==")
    print("             ==      by pbsds      ==")
    print("              ==       v0.95      ==")
    print()
    if not hasPIL:
        print("PIL not found! Exiting...")
        return 1

    if len(sys.argv) < 2:
        print("Usage:")
        print("      NTFT.py <input> [<output> [<width> <height>]]")
        print()
        print("Can convert an NTFT to PNG or the other way around.")
        print("32x32 is the normal resolution for button icons in UGO files.")
        return 0

    input_path = sys.argv[1]
    encode = not (input_path[-4:].lower() == "ntft" or len(sys.argv) >= 5)
    print("Mode: image -> NTFT" if encode else "Mode: NTFT -> image")

    width = height = None
    if len(sys.argv) >= 3:
        output = sys.argv[2]
        if len(sys.argv) >= 5:
            if not sys.argv[3].isdigit() or not sys.argv[4].isdigit():
                print("Invalid size input!")
                return 1
            width, height = int(sys.argv[3]), int(sys.argv[4])
        if not (width and height) and not encode:
            print("Image size not provided!")
            return 1
    else:
        output = ".".join(input_path.split(".")[:-1]) + (".ntft" if encode else ".png")

    print("Converting...")
    try:
        if encode:
            image = ReadImage(input_path)
            if image is False:
                return 1
            NTFT().SetImage(image).WriteFile(output)
        else:
            ntft = NTFT().ReadFile(input_path, (width, height))
            if not ntft:
                return 1
            WriteImage(ntft.Image, output)
    except OSError as err:
        print(err)
        return 1

    print("Done!")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
