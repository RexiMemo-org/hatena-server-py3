# UGO.py by pbsds
# AGPL3 licensed
#
# Python 3 port. This class reads/writes Flipnote Hatena UGO files and
# imports/exports the project's UGOXML representation.

from __future__ import annotations

import os
import sys
from base64 import b64decode, b64encode
import xml.etree.ElementTree as ET

try:
    from . import PPM as _ppm_module
    HasPPM = True
except (ImportError, ValueError):
    try:
        import PPM as _ppm_module  # type: ignore
        HasPPM = True
    except ImportError:
        _ppm_module = None
        HasPPM = False


def AscDec(data, LittleEndian=False):
    """Convert a byte string to an integer (legacy Hatenatools helper)."""
    if isinstance(data, str):
        data = data.encode("latin-1")
    return int.from_bytes(bytes(data), "little" if LittleEndian else "big")


def DecAsc(dec, length=None, LittleEndian=False):
    """Convert an integer to bytes (legacy Hatenatools helper)."""
    if dec < 0:
        raise ValueError("DecAsc does not support negative values")
    if length is None:
        length = max(1, (dec.bit_length() + 7) // 8) if dec else 0
    if length == 0:
        return b""
    mask = (1 << (length * 8)) - 1
    dec &= mask
    return dec.to_bytes(length, "little" if LittleEndian else "big")


def zipalign(length, r=4):
    return length + (r - length % r) if length % r else length


def indentXML(elem, level=0):
    i = "\n" + level * "\t"
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "\t"
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for child in elem:
            indentXML(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    elif level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


class UGO:
    def __init__(self):
        self.Loaded = False
        self.Items = []
        self.Files = []

    def ReadFile(self, path):
        with open(path, "rb") as f:
            return self.Read(f.read())

    def Read(self, data):
        global HasPPM
        if isinstance(data, str):
            data = data.encode("latin-1")
        data = bytes(data)

        if data[:4] != b"UGAR":
            return False

        sections = AscDec(data[4:8], True)
        self.TableLength = AscDec(data[8:12], True) if sections >= 1 else 0
        self.ExtraLength = AscDec(data[12:16], True) if sections >= 2 else 0
        if sections > 2:
            print("Warning: This UGO file has more than the 2 known sections:", sections)
            print("Please send this UGO file to pbsds over at pbsds.net")
            print("This file could possibly be read incorrectly...")

        headerlength = 8 + sections * 4

        if sections >= 1:
            table_bytes = data[headerlength : headerlength + self.TableLength]
            table_text = table_bytes.decode("utf-8")
            TableOfContents = tuple(line.split("\t") for line in table_text.split("\n") if line != "")
        else:
            TableOfContents = []

        if sections >= 2:
            extra_start = zipalign(headerlength + self.TableLength)
            ExtraData = data[extra_start : extra_start + self.ExtraLength]
        else:
            ExtraData = b""

        self.Items = []
        self.Files = []
        pos = 0
        tmbcount = 1
        ntftcount = 1
        names = []

        for entry in TableOfContents:
            if not entry or not entry[0]:
                continue
            item_type = int(entry[0])
            if item_type == 0:
                self.Items.append(("layout", list(map(int, entry[1:]))))
                continue
            if item_type == 1:
                num = int(entry[1])
                labels = [b64decode(entry[n]).decode("UTF-16LE") for n in range(2, 7)]
                self.Items.append(("topscreen text", labels, num))
                continue
            if item_type == 2:
                link = entry[1]
                label = b64decode(entry[2]).decode("UTF-16LE")
                selected = int(entry[3]) != 0
                self.Items.append(("category", link, label, selected))
                continue
            if item_type == 3:
                link = entry[1]
                label = b64decode(entry[2]).decode("UTF-16LE")
                self.Items.append(("post", link, label))
                continue
            if item_type == 4:
                link = entry[1]
                trait = int(entry[2])
                label = b64decode(entry[3]).decode("UTF-16LE")
                other = list(entry[4:])

                embedded = None
                if trait < 100 and ExtraData:
                    if ExtraData == b"\x20":
                        pass
                    elif ExtraData[pos : pos + 4] == b"PARA":
                        filedata = ExtraData[pos : pos + 0x6A0]
                        pos += 0x6A0
                        if HasPPM and _ppm_module is not None:
                            tmb = _ppm_module.TMB().Read(filedata)
                            name = tmb.CurrentFilename[:-4] if tmb else "embedded tmb #%i" % tmbcount
                            if not tmb:
                                tmbcount += 1
                        else:
                            name = "embedded tmb #%i" % tmbcount
                            tmbcount += 1

                        if name + ".tmb" in names:
                            j = 2
                            while "%s_%i.tmb" % (name, j) in names:
                                j += 1
                            name = "%s_%i" % (name, j)
                        embedded = (name + ".tmb", filedata)
                        names.append(name + ".tmb")
                    else:
                        name = label.encode("ascii", "ignore").decode("ascii")
                        if not name:
                            name = "nameless ntft %i" % ntftcount
                            ntftcount += 1
                        if name + ".ntft" in names:
                            j = 2
                            while "%s_%i.ntft" % (name, j) in names:
                                j += 1
                            name = "%s_%i" % (name, j)
                        embedded = (name + ".ntft", ExtraData[pos : pos + 2048])
                        names.append(name + ".ntft")
                        pos += 2048

                self.Items.append(("button", trait, label, link, other, embedded))
                continue

            self.Items.append(("unknown", list(entry)))
            print("Unknown UGO item discovered:", entry)

        self.Loaded = True
        return self

    def WriteFile(self, path):
        if not self.Loaded:
            return False
        out = self.Pack()
        if out is False:
            return False
        with open(path, "wb") as f:
            f.write(out)
        return True

    def Pack(self):
        if not self.Loaded:
            return False

        table_rows = []
        extra_parts = []

        for item in self.Items:
            kind = item[0]
            if kind == "unknown":
                table_rows.append("\t".join(map(str, item[1])))
            elif kind == "layout":
                table_rows.append("\t".join(["0"] + [str(value) for value in item[1]]))
            elif kind == "topscreen text":
                labels, num = item[1:]
                encoded_labels = [b64encode(label.encode("UTF-16LE")).decode("ascii") for label in labels]
                # The format expects exactly five labels.
                encoded_labels = (encoded_labels + [""] * 5)[:5]
                table_rows.append("\t".join(["1", str(num)] + encoded_labels))
            elif kind == "category":
                link, label, selected = item[1:]
                encoded = b64encode(label.encode("UTF-16LE")).decode("ascii")
                table_rows.append("\t".join(("2", link, encoded, str(int(bool(selected))))))
            elif kind == "post":
                link, label = item[1:]
                encoded = b64encode(label.encode("UTF-16LE")).decode("ascii")
                table_rows.append("\t".join(("3", link, encoded)))
            elif kind == "button":
                trait, label, link, other, embedded = item[1:]
                encoded = b64encode(label.encode("UTF-16LE")).decode("ascii")
                table_rows.append("\t".join(["4", link, str(trait), encoded] + [str(v) for v in other]))
                if embedded:
                    extra_parts.append(bytes(embedded[1]))
            else:
                print("Unrecognized entry in self.Items:", item)

        table = "\n".join(table_rows).encode("utf-8")
        extra = b"".join(extra_parts)

        sections = 0
        lengths = []
        if table:
            sections += 1
            lengths.append(len(table))
        if extra:
            sections += 1
            lengths.append(len(extra))

        header = b"UGAR" + DecAsc(sections, 4, True) + b"".join(DecAsc(length, 4, True) for length in lengths)
        if table:
            table += b"\0" * ((-len(table)) % 4)
        if extra:
            extra += b"\0" * ((-len(extra)) % 4)
        return header + table + extra

    def WriteXML(self, xmlname="content.ugoxml", folder="content.ugoxml embedded"):
        if not self.Loaded:
            return False

        path, xml_basename = os.path.split(xmlname)
        ugo_xml = ET.Element("ugo_xml")
        files = []

        for item in self.Items:
            kind = item[0]
            if kind == "unknown":
                elem = ET.SubElement(ugo_xml, "raw", type=str(item[1][0]))
                for value in item[1][1:]:
                    ET.SubElement(elem, "value").text = str(value)
            elif kind == "layout":
                elem = ET.SubElement(ugo_xml, "layout")
                for value in item[1]:
                    ET.SubElement(elem, "value").text = str(value)
            elif kind == "topscreen text":
                elem = ET.SubElement(ugo_xml, "title")
                labels, num = item[1:]
                for label in labels:
                    ET.SubElement(elem, "label").text = label
                ET.SubElement(elem, "num").text = str(num)
            elif kind == "category":
                elem = ET.SubElement(ugo_xml, "category")
                link, label, selected = item[1:]
                ET.SubElement(elem, "label").text = label
                ET.SubElement(elem, "address").text = link
                ET.SubElement(elem, "selected").text = str(bool(selected)).lower()
            elif kind == "post":
                elem = ET.SubElement(ugo_xml, "post")
                link, label = item[1:]
                ET.SubElement(elem, "label").text = label
                ET.SubElement(elem, "address").text = link
            elif kind == "button":
                elem = ET.SubElement(ugo_xml, "button")
                trait, label, link, other, embedded = item[1:]
                ET.SubElement(elem, "label").text = label
                ET.SubElement(elem, "address").text = link
                ET.SubElement(elem, "trait").text = str(trait)
                for n, value in enumerate(other):
                    entry = ET.SubElement(elem, "value")
                    entry.text = str(value)
                    if n == 0 and trait == 3:
                        entry.attrib["tip"] = "stars"
                if embedded:
                    ET.SubElement(elem, "embedded_file").text = os.path.join(folder, embedded[0])
                    files.append((os.path.join(folder, embedded[0]), bytes(embedded[1])))

        indentXML(ugo_xml)
        files.append((xml_basename, ET.tostring(ugo_xml, encoding="UTF-8")))

        folder_path = os.path.join(path, folder)
        if folder and not os.path.isdir(folder_path):
            os.makedirs(folder_path, exist_ok=True)
        for name, data in files:
            full_path = os.path.join(path, name)
            parent = os.path.dirname(full_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(full_path, "wb") as f:
                f.write(data)
        return True

    def ReadXML(self, xmlfile, silent=True):
        ugo_xml = ET.parse(xmlfile).getroot()
        xmlpath = os.path.split(xmlfile)[0]

        items = []
        for elem in ugo_xml:
            if elem.tag == "raw":
                if "type" not in elem.attrib:
                    if not silent:
                        print('Invalid formatting. <raw> without "type" attribute')
                    return False
                values = [elem.attrib["type"]]
                for value in elem:
                    if value.tag != "value":
                        if not silent:
                            print("Invalid formatting. <%s> found within <unknown>" % value.tag)
                        return False
                    values.append(value.text or "")
                items.append(("unknown", values))

            elif elem.tag == "layout":
                values = []
                for value in elem:
                    if value.tag != "value":
                        if not silent:
                            print("Invalid formatting. <%s> found within <layout>" % value.tag)
                        return False
                    if not (value.text or "").isdigit():
                        if not silent:
                            print("Invalid entry. <value> in <layout> is not a number")
                        return False
                    values.append(int(value.text))
                items.append(("layout", values))

            elif elem.tag == "title":
                labels = ["", "", "", "", ""]
                num = 0
                pos = 0
                numset = False
                for value in elem:
                    if value.tag not in ("label", "num"):
                        if not silent:
                            print("Invalid formatting. <%s> found within <title>" % value.tag)
                        return False
                    if value.tag == "label":
                        if pos >= 5:
                            if not silent:
                                print("Invalid formatting. More than 5 <labels> in <title>")
                            return False
                        labels[pos] = value.text or ""
                        pos += 1
                    else:
                        if numset:
                            if not silent:
                                print("Invalid formatting. Multiple <num> in <title>")
                            return False
                        if not (value.text or "").isdigit():
                            if not silent:
                                print("Invalid entry. <num> in <title> is not a number!")
                            return False
                        num = int(value.text)
                        numset = True
                items.append(("topscreen text", labels, num))

            elif elem.tag == "category":
                link = label = selected = None
                for value in elem:
                    if value.tag not in ("label", "address", "selected"):
                        if not silent:
                            print("Invalid formatting. <%s> found within <category>" % value.tag)
                        return False
                    if value.tag == "address":
                        if link is not None:
                            return False
                        link = value.text or ""
                    elif value.tag == "label":
                        if label is not None:
                            return False
                        label = value.text or ""
                    else:
                        if selected is not None:
                            return False
                        selected = bool(value.text) and value.text[0].lower() in "t1"
                if link is None or label is None or selected is None:
                    return False
                items.append(("category", link, label, selected))

            elif elem.tag == "post":
                label = link = None
                for value in elem:
                    if value.tag == "label":
                        if label is not None:
                            return False
                        label = value.text or ""
                    elif value.tag == "address":
                        if link is not None:
                            return False
                        link = value.text or ""
                    else:
                        if not silent:
                            print("Invalid formatting. <%s> found within <post>" % value.tag)
                        return False
                if link is None or label is None:
                    return False
                items.append(("post", link, label))

            elif elem.tag == "button":
                trait = label = link = None
                other = []
                embedded = None
                for value in elem:
                    if value.tag not in ("label", "address", "trait", "value", "embedded_file"):
                        if not silent:
                            print("Invalid formatting. <%s> found within <button>" % value.tag)
                        return False
                    if value.tag == "label":
                        if label is not None:
                            return False
                        label = value.text or ""
                    elif value.tag == "address":
                        if link is not None:
                            return False
                        link = value.text or ""
                    elif value.tag == "trait":
                        if trait is not None or not (value.text or "").isdigit():
                            return False
                        trait = int(value.text)
                    elif value.tag == "value":
                        other.append(value.text or "")
                    else:
                        if embedded is not None:
                            return False
                        if not value.text:
                            return False
                        embedded_path = os.path.join(xmlpath, value.text)
                        if not os.path.isfile(embedded_path):
                            if not silent:
                                print('Invalid entry. Embedded file "%s" not found!' % value.text)
                            return False
                        with open(embedded_path, "rb") as f:
                            embedded = (os.path.split(value.text)[1], f.read())
                if trait is None or label is None or link is None:
                    return False
                items.append(("button", trait, label, link, other, embedded))

            else:
                if not silent:
                    print("Invalid formatting: <%s> found within <ugo_xml>" % elem.tag)
                return False

        self.Items = items
        self.Loaded = True
        return self


def _main():
    print("              ==      UGO.py      ==")
    print("             ==      by pbsds      ==")
    print("              ==       v0.93      ==")
    print()
    if len(sys.argv) < 2:
        print("Usage:")
        print("      UGO.py [<mode>] <input> [<output> [<foldername>]]")
        print("      -d: UGO -> UGOXML")
        print("      -e: UGOXML -> UGO")
        return 0

    mode = sys.argv[1]
    if mode not in ("-d", "-e"):
        if os.path.exists(mode):
            with open(mode, "rb") as f:
                magic = f.read(4)
            mode = "-d" if magic == b"UGAR" else "-e"
            print("No mode specified. %s chosen" % ("UGO -> UGOXML" if mode == "-d" else "UGOXML -> UGO"))
            sys.argv.insert(1, mode)
        else:
            print("Invalid <mode> given!")
            return 1

    input_path = sys.argv[2]
    if mode == "-d":
        output = sys.argv[3] if len(sys.argv) >= 4 else input_path + "xml"
        foldername = sys.argv[4] if len(sys.argv) >= 5 else os.path.split(output)[1] + " embedded"
        print("Reading %s..." % os.path.split(input_path)[1])
        ugo = UGO().ReadFile(input_path)
        if not ugo:
            print("Error!\n The given file is not a UGO file!")
            return 1
        print("Writing XML...")
        ugo.WriteXML(output, foldername)
        print("Done!")
        return 0

    output = sys.argv[3] if len(sys.argv) >= 4 else ".".join(input_path.split(".")[:-1]) + ".ugo"
    print("Reading %s..." % os.path.split(input_path)[1])
    try:
        ugo = UGO().ReadXML(input_path, False)
    except ET.ParseError:
        print("Error!\nThe given file is not in the XML format!")
        return 1
    if not ugo:
        return 1
    print("Writing UGO...")
    ugo.WriteFile(output)
    print("Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
