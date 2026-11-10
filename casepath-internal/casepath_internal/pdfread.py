"""A small PDF reader in the standard library, for runtimes without the PDF libraries.

It reads what a case file needs and nothing more:
- the text layer of each page, decoded through the fonts' ToUnicode maps or their simple encodings;
- for a page without text, the scanned image the page carries: a JPEG is passed on as it is, an uncompressed or
  Flate-compressed bitmap is written as a PNG. Other image codings (JPEG 2000, CCITT fax, JBIG2) are reported, not guessed.

It never runs code from the file and never follows external references. Where the libraries are installed, CasePath
uses them instead (``extract.py``, ``reading.Renderer``); this module is the fallback.
"""
import base64
import re
import struct
import zlib

MAX_DEPTH = 6  # nested Form XObjects and page-tree levels are followed this far


class PdfError(ValueError):
    pass


class Name(str):
    """A PDF name such as /Font; plain strings are bytes."""


class Op(str):
    """A content-stream operator or another bare keyword."""


class Ref(tuple):
    """An indirect reference (object number, generation)."""


# -- syntax ---------------------------------------------------------------------

WHITE = b" \t\r\n\f\x00"
DELIMS = b"()<>[]{}/%"
_ESCAPES = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12, ord("("): 40, ord(")"): 41, ord("\\"): 92}


class Lexer:
    def __init__(self, data, pos=0):
        self.data, self.pos = data, pos

    def skip(self):
        data, n = self.data, len(self.data)
        while self.pos < n:
            c = data[self.pos]
            if c in WHITE:
                self.pos += 1
            elif c == 37:  # % comment
                end = data.find(b"\n", self.pos)
                self.pos = n if end < 0 else end + 1
            else:
                break

    def _token(self):
        start = self.pos
        data, n = self.data, len(self.data)
        while self.pos < n and data[self.pos] not in WHITE and data[self.pos] not in DELIMS:
            self.pos += 1
        return data[start:self.pos]

    def parse(self):
        """The next object, or an Op for a bare keyword; None at the end."""
        self.skip()
        data = self.data
        if self.pos >= len(data):
            return None
        c = data[self.pos]
        if c == 47:  # /Name
            self.pos += 1
            raw = self._token()
            return Name(re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), raw).decode("latin-1"))
        if c == 40:  # (literal string)
            return self._literal()
        if c == 60:
            if data[self.pos:self.pos + 2] == b"<<":
                self.pos += 2
                result = {}
                while True:
                    self.skip()
                    if data[self.pos:self.pos + 2] == b">>" or self.pos >= len(data):
                        self.pos += 2
                        return result
                    key = self.parse()
                    value = self.parse()
                    if isinstance(key, Name):
                        result[key] = value
            end = data.find(b">", self.pos)
            hexdigits = re.sub(rb"[^0-9A-Fa-f]", b"", data[self.pos + 1:end])
            self.pos = end + 1
            if len(hexdigits) % 2:
                hexdigits += b"0"
            return bytes.fromhex(hexdigits.decode())
        if c == 91:  # [array]
            self.pos += 1
            items = []
            while True:
                self.skip()
                if self.pos >= len(data) or data[self.pos] == 93:
                    self.pos += 1
                    return items
                items.append(self.parse())
        if c in (93, 62, 41, 123, 125):  # stray closing delimiters: skip
            self.pos += 1
            return Op(chr(c))
        token = self._token()
        if not token:
            self.pos += 1
            return Op("")
        if re.fullmatch(rb"[+-]?\d+", token):
            number = int(token)
            # "12 0 R" is a reference
            save = self.pos
            self.skip()
            generation = re.match(rb"\d+", data[self.pos:self.pos + 12])
            if generation:
                after = self.pos + generation.end()
                lex = Lexer(data, after)
                lex.skip()
                if data[lex.pos:lex.pos + 1] == b"R" and (lex.pos + 1 >= len(data) or data[lex.pos + 1] in WHITE + DELIMS):
                    self.pos = lex.pos + 1
                    return Ref((number, int(generation.group())))
            self.pos = save
            return number
        if re.fullmatch(rb"[+-]?(\d+\.\d*|\.\d+|\d+\.)", token):
            return float(token)
        word = token.decode("latin-1")
        return {"true": True, "false": False, "null": None}.get(word, Op(word)) if word in ("true", "false", "null") else Op(word)

    def _literal(self):
        data, out, depth = self.data, bytearray(), 1
        self.pos += 1
        while self.pos < len(data):
            c = data[self.pos]
            self.pos += 1
            if c == 92:  # backslash
                if self.pos >= len(data):
                    break
                e = data[self.pos]
                self.pos += 1
                if e in _ESCAPES:
                    out.append(_ESCAPES[e])
                elif 48 <= e <= 55:  # octal
                    digits = bytes([e])
                    while len(digits) < 3 and self.pos < len(data) and 48 <= data[self.pos] <= 55:
                        digits += data[self.pos:self.pos + 1]
                        self.pos += 1
                    out.append(int(digits, 8) & 0xFF)
                elif e in (10, 13):  # line continuation
                    if e == 13 and data[self.pos:self.pos + 1] == b"\n":
                        self.pos += 1
                else:
                    out.append(e)
            elif c == 40:
                depth += 1
                out.append(c)
            elif c == 41:
                depth -= 1
                if depth == 0:
                    break
                out.append(c)
            else:
                out.append(c)
        return bytes(out)


# -- filters --------------------------------------------------------------------

IMAGE_CODINGS = {"DCTDecode": "jpeg", "DCT": "jpeg", "JPXDecode": "jpeg2000", "CCITTFaxDecode": "ccitt", "CCF": "ccitt",
                 "JBIG2Decode": "jbig2"}


def _inflate(raw):
    try:
        return zlib.decompress(raw)
    except zlib.error:
        out = zlib.decompressobj()  # a stream cut short still yields what it holds
        try:
            return out.decompress(raw)
        except zlib.error:
            return zlib.decompressobj(-15).decompress(raw[2:])


def _unpredict(data, parms):
    predictor = int(parms.get("Predictor", 1) or 1)
    if predictor < 10:
        return data
    colors, bpc, columns = int(parms.get("Colors", 1)), int(parms.get("BitsPerComponent", 8)), int(parms.get("Columns", 1))
    bpp = max(1, colors * bpc // 8)
    stride = (colors * bpc * columns + 7) // 8
    out, prior = bytearray(), bytearray(stride)
    for start in range(0, len(data), stride + 1):
        kind, row = data[start], bytearray(data[start + 1:start + 1 + stride])
        if len(row) < stride:
            row.extend(bytes(stride - len(row)))
        if kind == 1:
            for i in range(bpp, stride):
                row[i] = (row[i] + row[i - bpp]) & 0xFF
        elif kind == 2:
            for i in range(stride):
                row[i] = (row[i] + prior[i]) & 0xFF
        elif kind == 3:
            for i in range(stride):
                row[i] = (row[i] + ((row[i - bpp] if i >= bpp else 0) + prior[i]) // 2) & 0xFF
        elif kind == 4:
            for i in range(stride):
                a, b, c = (row[i - bpp] if i >= bpp else 0), prior[i], (prior[i - bpp] if i >= bpp else 0)
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
        out += row
        prior = row
    return bytes(out)


def _lzw(data):
    table = [bytes([i]) for i in range(256)] + [b"", b""]
    out, previous, code_bits, buffer, bits = bytearray(), None, 9, 0, 0
    for byte in data:
        buffer, bits = (buffer << 8) | byte, bits + 8
        while bits >= code_bits:
            bits -= code_bits
            code = (buffer >> bits) & ((1 << code_bits) - 1)
            if code == 256:
                table, previous, code_bits = table[:258], None, 9
                continue
            if code == 257:
                return bytes(out)
            if previous is None:
                entry = table[code]
            elif code < len(table):
                entry = table[code]
                table.append(previous + entry[:1])
            else:
                entry = previous + previous[:1]
                table.append(entry)
            out += entry
            previous = entry
            if len(table) + 1 >= (1 << code_bits) and code_bits < 12:
                code_bits += 1
    return bytes(out)


def _run_length(data):
    out, i = bytearray(), 0
    while i < len(data):
        n = data[i]
        if n == 128:
            break
        if n < 128:
            out += data[i + 1:i + 2 + n]
            i += n + 2
        else:
            out += data[i + 1:i + 2] * (257 - n)
            i += 2
    return bytes(out)


def _list(value):
    return value if isinstance(value, list) else [] if value is None else [value]


def decode(stream_dict, raw, resolve):
    """Apply the stream's filters. Returns (bytes, image coding or None); an image coding stops the chain."""
    filters = [resolve(f) for f in _list(resolve(stream_dict.get("Filter")))]
    parms = [resolve(p) or {} for p in _list(resolve(stream_dict.get("DecodeParms") or stream_dict.get("DP")))]
    data = raw
    for index, name in enumerate(filters):
        p = parms[index] if index < len(parms) and isinstance(parms[index], dict) else {}
        if name in ("FlateDecode", "Fl"):
            data = _unpredict(_inflate(data), p)
        elif name in ("LZWDecode", "LZW"):
            data = _unpredict(_lzw(data), p)
        elif name in ("ASCIIHexDecode", "AHx"):
            digits = re.sub(rb"[^0-9A-Fa-f]", b"", data.split(b">")[0])
            data = bytes.fromhex((digits + (b"0" if len(digits) % 2 else b"")).decode())
        elif name in ("ASCII85Decode", "A85"):
            body = data.strip()
            body = body[2:] if body.startswith(b"<~") else body
            body = body.split(b"~>")[0]
            data = base64.a85decode(re.sub(rb"\s", b"", body))
        elif name in ("RunLengthDecode", "RL"):
            data = _run_length(data)
        elif name in IMAGE_CODINGS:
            return data, IMAGE_CODINGS[name]
        else:
            raise PdfError(f"unsupported filter {name}")
    return data, None


# -- document -------------------------------------------------------------------

class Stream:
    __slots__ = ("dict", "raw")

    def __init__(self, d, raw):
        self.dict, self.raw = d, raw

    def get(self, key, default=None):
        return self.dict.get(key, default)


_OBJ = re.compile(rb"(?<![0-9])(\d{1,10})\s+(\d{1,5})\s+obj\b")


class Document:
    def __init__(self, data):
        if not data.lstrip()[:5] == b"%PDF-" and b"%PDF-" not in data[:1024]:
            raise PdfError("not a PDF")
        self.data, self.objects, self._decoded = data, {}, {}
        self._scan()
        self._expand_object_streams()
        trailer = self._trailer()
        if trailer.get("Encrypt") is not None:
            raise PdfError("encrypted")
        root = self.resolve(trailer.get("Root"))
        if not isinstance(root, dict):
            root = next((o for o in self.objects.values() if isinstance(o, dict) and o.get("Type") == "Catalog"), None)
        if not isinstance(root, dict):
            raise PdfError("no document catalogue")
        self.pages = []
        self._collect(self.resolve(root.get("Pages")), {}, 0, set())
        if not self.pages:
            raise PdfError("no pages")

    def _scan(self):
        """Every 'n g obj' in file order; a later definition (an incremental update) replaces an earlier one."""
        data, pos = self.data, 0
        self.trailers = []
        while True:
            match = _OBJ.search(data, pos)
            if not match:
                break
            number = int(match.group(1))
            lex = Lexer(data, match.end())
            try:
                value = lex.parse()
            except (ValueError, IndexError, RecursionError):
                pos = match.end()
                continue
            lex.skip()
            if isinstance(value, dict) and data.startswith(b"stream", lex.pos):
                start = lex.pos + 6
                if data[start:start + 2] == b"\r\n":
                    start += 2
                elif data[start:start + 1] in (b"\n", b"\r"):
                    start += 1
                length = value.get("Length")
                end = start + length if isinstance(length, int) and data[start + length:start + length + 30].lstrip().startswith(b"endstream") else -1
                if end < 0:
                    found = data.find(b"endstream", start)
                    end = found if found >= 0 else len(data)
                    while end > start and data[end - 1:end] in (b"\n", b"\r"):
                        end -= 1
                self.objects[number] = Stream(value, data[start:end])
                pos = end + 9
            else:
                self.objects[number] = value
                pos = lex.pos
        for match in re.finditer(rb"trailer\s*<<", data):
            try:
                self.trailers.append(Lexer(data, match.end() - 2).parse())
            except (ValueError, IndexError, RecursionError):
                continue

    def _expand_object_streams(self):
        for number, obj in list(self.objects.items()):
            if not (isinstance(obj, Stream) and obj.get("Type") == "ObjStm"):
                continue
            try:
                body, _ = decode(obj.dict, obj.raw, self.resolve)
                count, first = int(self.resolve(obj.get("N"))), int(self.resolve(obj.get("First")))
                header = Lexer(body[:first])
                pairs = [(header.parse(), header.parse()) for _ in range(count)]
                for inner, offset in pairs:
                    if isinstance(inner, int) and isinstance(offset, int) and inner not in self.objects:
                        self.objects[inner] = Lexer(body, first + offset).parse()
            except (PdfError, ValueError, TypeError, IndexError, zlib.error, RecursionError):
                continue

    def _trailer(self):
        for trailer in reversed(self.trailers):
            if isinstance(trailer, dict) and trailer.get("Root") is not None:
                return trailer
        for obj in reversed(list(self.objects.values())):  # a cross-reference stream carries the trailer keys
            if isinstance(obj, Stream) and obj.get("Type") == "XRef" and obj.get("Root") is not None:
                return obj.dict
        return {}

    def resolve(self, value, depth=0):
        while isinstance(value, Ref) and depth < 32:
            value, depth = self.objects.get(value[0]), depth + 1
        return value

    def stream_bytes(self, stream):
        """The decoded bytes of a stream (cached), or (bytes, coding) for an image coding."""
        key = id(stream)
        if key not in self._decoded:
            self._decoded[key] = decode(stream.dict, stream.raw, self.resolve)
        return self._decoded[key]

    def _collect(self, node, inherited, depth, seen):
        if not isinstance(node, dict) or depth > 64 or id(node) in seen:
            return
        seen.add(id(node))
        inherited = {**inherited, **{k: node[k] for k in ("Resources", "MediaBox", "Rotate") if k in node}}
        kids = self.resolve(node.get("Kids"))
        if node.get("Type") == "Pages" or isinstance(kids, list) and node.get("Type") != "Page":
            for kid in kids or []:
                self._collect(self.resolve(kid), inherited, depth + 1, seen)
        else:
            self.pages.append({**node, **{k: v for k, v in inherited.items() if k not in node}})

    # -- text --

    def page_text(self, page):
        resources = self.resolve(page.get("Resources")) or {}
        parts = []
        for content in _list(self.resolve(page.get("Contents"))):
            content = self.resolve(content)
            if isinstance(content, Stream):
                data, coding = self.stream_bytes(content)
                if coding is None:
                    parts.append(data)
        return _TextRun(self).run(b"\n".join(parts), resources, 0)

    # -- images --

    def page_image(self, page, max_side=1700):
        """The page's largest image as (media type, bytes), or (None, reason)."""
        found = []
        resources = self.resolve(page.get("Resources")) or {}
        self._images(resources, found, 0, set())
        found += self._inline_images(page, resources)
        if not found:  # a page drawn only with vector paths (text as outlines, for example) is drawn here
            from .raster import TooComplex, render
            try:
                png = render(self, page, max_side)
            except TooComplex:
                return None, "vector page too complex to draw"
            except (PdfError, ValueError, TypeError, IndexError, ZeroDivisionError, OverflowError) as error:
                return None, f"vector page: {str(error)[:60]}"
            return ("image/png", png) if png else (None, "no image or drawing")
        stream = max(found, key=lambda s: _int(self.resolve(s.get("Width"))) * _int(self.resolve(s.get("Height"))))
        try:
            return _encode_image(self, stream, max_side)
        except (PdfError, ValueError, zlib.error, TypeError) as error:
            return None, str(error)[:80]

    def _images(self, resources, found, depth, seen):
        xobjects = self.resolve(resources.get("XObject")) if isinstance(resources, dict) else None
        if not isinstance(xobjects, dict) or depth > MAX_DEPTH:
            return
        for value in xobjects.values():
            obj = self.resolve(value)
            if not isinstance(obj, Stream) or id(obj) in seen:
                continue
            seen.add(id(obj))
            if obj.get("Subtype") == "Image":
                found.append(obj)
            elif obj.get("Subtype") == "Form":
                self._images(self.resolve(obj.get("Resources")) or {}, found, depth + 1, seen)


    def page_content(self, page):
        parts = []
        for content in _list(self.resolve(page.get("Contents"))):
            content = self.resolve(content)
            if isinstance(content, Stream):
                try:
                    data, coding = self.stream_bytes(content)
                except (PdfError, zlib.error, ValueError):
                    continue
                if coding is None:
                    parts.append(data)
        return b"\n".join(parts)

    def _inline_images(self, page, resources):
        """Images drawn inline in the page's content (BI … ID … EI), as streams; some scanners store pages this way."""
        found, content = [], self.page_content(page)
        for match in re.finditer(rb"(?:^|\s)BI\s", content):
            lex = Lexer(content, match.end())
            fields = {}
            while True:
                lex.skip()
                if content[lex.pos:lex.pos + 2] == b"ID" or lex.pos >= len(content):
                    break
                key, value = lex.parse(), lex.parse()
                if isinstance(key, Name):
                    fields[INLINE_KEYS.get(str(key), str(key))] = INLINE_VALUES.get(value, value) if isinstance(value, str) else \
                        [INLINE_VALUES.get(v, v) if isinstance(v, str) else v for v in value] if isinstance(value, list) else value
            start = lex.pos + 3  # "ID" and one white-space byte
            length = fields.get("Length") or fields.get("L")
            end = start + length if isinstance(length, int) else None
            if end is None:
                stop = re.compile(rb"\sEI(?=\s|$)").search(content, start)
                end = stop.start() if stop else len(content)
            space = fields.get("ColorSpace")
            if isinstance(space, Name) and space not in ("DeviceGray", "DeviceRGB", "DeviceCMYK"):
                named = self.resolve(resources.get("ColorSpace")) if isinstance(resources, dict) else None
                fields["ColorSpace"] = (named or {}).get(space, space) if isinstance(named, dict) else space
            found.append(Stream({**fields, "Subtype": Name("Image")}, content[start:end]))
        return found


INLINE_KEYS = {"W": "Width", "H": "Height", "BPC": "BitsPerComponent", "CS": "ColorSpace", "F": "Filter", "DP": "DecodeParms",
               "IM": "ImageMask", "D": "Decode", "I": "Interpolate"}
INLINE_VALUES = {"G": Name("DeviceGray"), "RGB": Name("DeviceRGB"), "CMYK": Name("DeviceCMYK"), "I": Name("Indexed"),
                 "AHx": Name("ASCIIHexDecode"), "A85": Name("ASCII85Decode"), "LZW": Name("LZWDecode"), "Fl": Name("FlateDecode"),
                 "RL": Name("RunLengthDecode"), "CCF": Name("CCITTFaxDecode"), "DCT": Name("DCTDecode")}


def _int(value):
    return int(value) if isinstance(value, (int, float)) else 0


# -- fonts and text -------------------------------------------------------------

GLYPHS = {
    "space": " ", "exclam": "!", "quotedbl": '"', "numbersign": "#", "dollar": "$", "percent": "%", "ampersand": "&",
    "quotesingle": "'", "quoteright": "’", "quoteleft": "‘", "parenleft": "(", "parenright": ")", "asterisk": "*",
    "plus": "+", "comma": ",", "hyphen": "-", "minus": "−", "period": ".", "slash": "/", "colon": ":", "semicolon": ";",
    "less": "<", "equal": "=", "greater": ">", "question": "?", "at": "@", "bracketleft": "[", "backslash": "\\",
    "bracketright": "]", "asciicircum": "^", "underscore": "_", "grave": "`", "braceleft": "{", "bar": "|",
    "braceright": "}", "asciitilde": "~", "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "adieresis": "ä", "odieresis": "ö", "udieresis": "ü",
    "Adieresis": "Ä", "Odieresis": "Ö", "Udieresis": "Ü", "germandbls": "ß", "eacute": "é", "egrave": "è",
    "ecircumflex": "ê", "edieresis": "ë", "agrave": "à", "acircumflex": "â", "aacute": "á", "ccedilla": "ç",
    "Ccedilla": "Ç", "Eacute": "É", "Egrave": "È", "Agrave": "À", "icircumflex": "î", "idieresis": "ï", "iacute": "í",
    "igrave": "ì", "ocircumflex": "ô", "oacute": "ó", "ograve": "ò", "ucircumflex": "û", "uacute": "ú", "ugrave": "ù",
    "ntilde": "ñ", "endash": "–", "emdash": "—", "bullet": "•", "Euro": "€", "quotedblleft": "“", "quotedblright": "”",
    "quotedblbase": "„", "quotesinglbase": "‚", "guillemotleft": "«", "guillemotright": "»", "guilsinglleft": "‹",
    "guilsinglright": "›", "ellipsis": "…", "degree": "°", "section": "§", "paragraph": "¶", "copyright": "©",
    "registered": "®", "trademark": "™", "periodcentered": "·", "multiply": "×", "divide": "÷", "fi": "fi", "fl": "fl",
    "ff": "ff", "ffi": "ffi", "ffl": "ffl", "nbspace": " ", "uni00A0": " ", "sterling": "£", "yen": "¥", "cent": "¢",
    "onehalf": "½", "onequarter": "¼", "threequarters": "¾", "plusminus": "±", "mu": "µ", "dagger": "†",
}


def _glyph(name):
    if name in GLYPHS:
        return GLYPHS[name]
    if len(name) == 1 and name.isalpha():
        return name
    match = re.fullmatch(r"uni([0-9A-Fa-f]{4,6})", name) or re.fullmatch(r"u([0-9A-Fa-f]{4,6})", name)
    if match:
        return chr(int(match.group(1), 16))
    return ""


def _utf16(data):
    try:
        return data.decode("utf-16-be")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _cmap(text):
    """bfchar and bfrange entries of a ToUnicode CMap; the code width from its codespace."""
    mapping, widths = {}, set()
    for block in re.findall(rb"begincodespacerange(.*?)endcodespacerange", text, re.S):
        for low in re.findall(rb"<([0-9A-Fa-f]+)>\s*<[0-9A-Fa-f]+>", block):
            widths.add(len(low) // 2)
    for block in re.findall(rb"beginbfchar(.*?)endbfchar", text, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", block):
            mapping[int(src, 16)] = _utf16(bytes.fromhex(dst.decode()))
            widths.add(len(src) // 2)
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", text, re.S):
        for low, high, rest in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]*>)", block):
            lo, hi = int(low, 16), int(high, 16)
            widths.add(len(low) // 2)
            if rest.startswith(b"["):
                for offset, dst in enumerate(re.findall(rb"<([0-9A-Fa-f]*)>", rest)):
                    mapping[lo + offset] = _utf16(bytes.fromhex(dst.decode()))
            else:
                base = bytes.fromhex(rest[1:-1].decode())
                for offset in range(min(hi - lo + 1, 65536)):
                    value = bytearray(base)
                    if value:
                        carry, i = offset, len(value) - 1
                        while carry and i >= 0:
                            total = value[i] + carry
                            value[i], carry = total & 0xFF, total >> 8
                            i -= 1
                    mapping[lo + offset] = _utf16(bytes(value))
    return mapping, (min(widths) if widths else 1)


_MACROMAN = bytes(range(128, 256)).decode("mac-roman")

# Glyph widths of the standard PDF fonts, which files often use without a width table: codes 32 to 255 in WinAnsi
# order, one byte each in units of 4/1000 em (from the core font metrics Adobe publishes for these fonts).
STANDARD_WIDTHS = {
    "Helvetica": "RkZZi4vepzBTU2GSRlNGRouLi4uLi4uLi4tGRpKSkov+p6e0tKeZwrRGfaeL0LTCp8K0p5m0p+ynp5lGRkZ1i1OLi32Li0aLizg4fTjQi4uLi1N9Rot9tH19fVRBVJJYi1g4i1P6i4tT+qdT+liZWFg4OFNTWIv6U/p9U+xYfadGU4uLi4tBi1O4XIuSU7hTZJJTU1OLhkZTU1uL0NDQmaenp6enp/q0p6enp0ZGRka0tMLCwsLCksK0tLS0p6eZi4uLi4uL3n2Li4uLRkZGRouLi4uLi4uSmYuLi4t9i30=",
    "Helvetica-Bold": "RlN2i4vetDxTU2GSRlNGRouLi4uLi4uLi4tTU5KSkpn0tLS0tKeZwrRGi7SZ0LTCp8K0p5m0p+ynp5lTRlOSi1OLmYuZi1OZmUZGi0bemZmZmWGLU5mLwouLfWFGYZJYi1hGi336i4tT+qdT+liZWFhGRn19WIv6U/qLU+xYfadGU4uLi4tGi1O4XIuSU7hTZJJTU1OZi0ZTU1uL0NDQmbS0tLS0tPq0p6enp0ZGRka0tMLCwsLCksK0tLS0p6eZi4uLi4uL3ouLi4uLRkZGRpmZmZmZmZmSmZmZmZmLmYs=",
    "Times-Roman": "PlNmfX3Qwi1TU32NPlM+Rn19fX19fX19fX1GRo2NjW/mtKentJmLtLRTYbSZ3rS0i7Sni5m0tOy0tJlTRlN1fVNvfW99b1N9fUZGfUbCfX19fVNhRn19tH19b3gyeIdYfVhTfW/6fX1T+otT3liZWFhTU29vWH36U/VhU7RYb7Q+U319fX0yfVO+RX2NU75TZI1LS1N9cT5TS059vLy8b7S0tLS0tN6nmZmZmVNTU1O0tLS0tLS0jbS0tLS0tIt9b29vb29vp29vb29vRkZGRn19fX19fX2NfX19fX19fX0=",
    "Times-Bold": "PlOLfX360EZTU32OPlM+Rn19fX19fX19fX1TU46Ojn3otKe0tKeZwsJhfcKn7LTCmcK0i6e0tPq0tKdTRlORfVN9i2+Lb1N9i0ZTi0bQi32Li29hU4t9tH19b2I3YoJYfVhTfX36fX1T+otT+linWFhTU319WH36U/phU7RYb7Q+U319fX03fVO7S32OU7tTZI5LS1OLhz5TS1J9vLy8fbS0tLS0tPq0p6enp2FhYWG0tMLCwsLCjsK0tLS0tJmLfX19fX19tG9vb29vRkZGRn2LfX19fX2OfYuLi4t9i30=",
}


def _standard_widths(base_font):
    name = re.sub(r"^[A-Z]{6}\+", "", str(base_font or "")).replace(",", "-")
    if "Courier" in name:
        return {code: 600.0 for code in range(32, 256)}
    family = "Times" if "Times" in name else "Helvetica"
    bold = any(word in name for word in ("Bold", "Black", "Heavy"))
    key = f"{family}-Bold" if bold else ("Times-Roman" if family == "Times" else "Helvetica")
    return {32 + i: width * 4.0 for i, width in enumerate(base64.b64decode(STANDARD_WIDTHS[key]))}


class Font:
    def __init__(self, doc, font):
        font = doc.resolve(font) if font is not None else {}
        font = font if isinstance(font, dict) else {}
        self.composite = font.get("Subtype") == "Type0"
        self.map, self.width = {}, 2 if self.composite else 1
        to_unicode = doc.resolve(font.get("ToUnicode"))
        if isinstance(to_unicode, Stream):
            try:
                data, _ = doc.stream_bytes(to_unicode)
                self.map, width = _cmap(data)
                self.width = width if self.composite else 1
            except (PdfError, zlib.error, ValueError):
                pass
        self.base, self.differences = "WinAnsiEncoding", {}
        encoding = doc.resolve(font.get("Encoding"))
        if isinstance(encoding, str):
            self.base = str(encoding)
        elif isinstance(encoding, dict):
            self.base = str(doc.resolve(encoding.get("BaseEncoding")) or "WinAnsiEncoding")
            code = 0
            for item in doc.resolve(encoding.get("Differences")) or []:
                if isinstance(item, int):
                    code = item
                elif isinstance(item, Name):
                    self.differences[code] = _glyph(str(item))
                    code += 1
        # Glyph widths in thousandths of the font size, to know where each string ends on the page.
        self.widths, self.default_width = {}, 500.0
        if self.composite:
            descendants = doc.resolve(font.get("DescendantFonts")) or []
            cid = doc.resolve(descendants[0]) if descendants else {}
            cid = cid if isinstance(cid, dict) else {}
            self.default_width = _num(doc.resolve(cid.get("DW"))) or 1000.0
            entries, i = doc.resolve(cid.get("W")) or [], 0
            while i + 1 < len(entries):
                first, second = doc.resolve(entries[i]), doc.resolve(entries[i + 1])
                if isinstance(second, list):
                    for offset, width in enumerate(second):
                        self.widths[int(_num(first)) + offset] = _num(doc.resolve(width))
                    i += 2
                elif i + 2 < len(entries):
                    for code in range(int(_num(first)), min(int(_num(second)), int(_num(first)) + 65536) + 1):
                        self.widths[code] = _num(doc.resolve(entries[i + 2]))
                    i += 3
                else:
                    break
        else:
            first, widths = int(_num(doc.resolve(font.get("FirstChar")))), doc.resolve(font.get("Widths"))
            for offset, width in enumerate(widths if isinstance(widths, list) else []):
                self.widths[first + offset] = _num(doc.resolve(width))
            descriptor = doc.resolve(font.get("FontDescriptor"))
            missing = _num(doc.resolve(descriptor.get("MissingWidth"))) if isinstance(descriptor, dict) else 0
            if missing:
                self.default_width = missing
            if not self.widths and font.get("Subtype") in ("Type1", "TrueType", "MMType1"):
                self.widths = _standard_widths(doc.resolve(font.get("BaseFont")))  # a standard font without a width table

    def codes(self, data):
        if self.composite:
            return [int.from_bytes(data[i:i + self.width], "big") for i in range(0, len(data) - self.width + 1, self.width)]
        return list(data)

    def char(self, code):
        if code in self.map:
            return self.map[code]
        if self.composite:
            return ""
        if code in self.differences:
            return self.differences[code]
        if self.base == "MacRomanEncoding" and code >= 128:
            return _MACROMAN[code - 128]
        return bytes([code]).decode("cp1252", errors="replace").replace("\ufffd", "")

    def text(self, data):
        return "".join(self.char(code) for code in self.codes(data))

    def advance(self, code):
        return self.widths.get(code, self.default_width) / 1000.0


def _mult(m, n):
    """The product of two PDF matrices [a b c d e f]."""
    a, b, c, d, e, f = m
    p, q, r, s, t, u = n
    return (a * p + b * r, a * q + b * s, c * p + d * r, c * q + d * s, e * p + f * r + t, e * q + f * s + u)


IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


class _TextRun:
    """Walk a content stream and write its text in drawing order. Where each string starts and ends on the page comes
    from the text and graphics matrices and the glyph widths: a new line where the text moves to another line, a
    space where it jumps right by more than a fraction of the font size, nothing where letters are placed one by one."""

    def __init__(self, doc):
        self.doc, self.out, self.fonts = doc, [], {}
        self.last = None  # (x end, y, size) of the last string, in page space

    def _font(self, resources, name):
        fonts = self.doc.resolve(resources.get("Font")) if isinstance(resources, dict) else None
        ref = fonts.get(name) if isinstance(fonts, dict) else None
        key = ref if isinstance(ref, Ref) else (id(resources), name)
        if key not in self.fonts:
            self.fonts[key] = Font(self.doc, ref)
        return self.fonts[key]

    def _show(self, t, data):
        font = t["font"] or Font(self.doc, None)
        t["font"] = font
        trm = _mult(t["tm"], t["ctm"])
        size = abs(t["size"]) * ((trm[2] ** 2 + trm[3] ** 2) ** 0.5 or 1.0)
        x, y = trm[4], trm[5]
        text = font.text(data)
        if self.last and text.strip():
            last_x, last_y, last_size = self.last
            line = max(size, last_size, 1.0)
            if abs(y - last_y) > 0.5 * line:
                if self.out and not self.out[-1].endswith("\n"):
                    self.out.append("\n")
            elif x - last_x > 0.2 * line or x < last_x - 2 * line:
                if self.out and not self.out[-1].endswith((" ", "\n")) and not text.startswith(" "):
                    self.out.append(" ")
        self.out.append(text)
        width = 0.0
        for code in font.codes(data):
            width += (font.advance(code) * t["size"] + t["tc"] + (t["tw"] if not font.composite and code == 32 else 0)) * t["th"]
        t["tm"] = _mult((1.0, 0.0, 0.0, 1.0, width, 0.0), t["tm"])
        if text.strip():
            end = _mult(t["tm"], t["ctm"])
            self.last = (end[4], end[5], size)

    def run(self, content, resources, depth, ctm=IDENTITY):
        lex, operands, stack = Lexer(content), [], []
        t = {"ctm": ctm, "tm": IDENTITY, "tlm": IDENTITY, "font": None, "size": 1.0, "tc": 0.0, "tw": 0.0, "th": 1.0, "tl": 0.0}

        def line_move(tx, ty):
            t["tlm"] = _mult((1.0, 0.0, 0.0, 1.0, tx, ty), t["tlm"])
            t["tm"] = t["tlm"]
        while True:
            token = lex.parse()
            if token is None:
                break
            if not isinstance(token, Op):
                operands.append(token)
                continue
            op, n = str(token), operands
            if op == "BI":  # inline image: skip its data
                end = re.compile(rb"\sEI(?=[\s]|$)").search(content, lex.pos)
                lex.pos = end.end() if end else len(content)
            elif op == "q":
                stack.append(t["ctm"])
            elif op == "Q":
                t["ctm"] = stack.pop() if stack else ctm
            elif op == "cm" and len(n) >= 6:
                t["ctm"] = _mult(tuple(_num(v) for v in n[-6:]), t["ctm"])
            elif op == "BT":
                t["tm"] = t["tlm"] = IDENTITY
            elif op == "Tf" and len(n) >= 2:
                t["font"], t["size"] = self._font(resources, n[-2]), _num(n[-1])
            elif op == "Tc" and n:
                t["tc"] = _num(n[-1])
            elif op == "Tw" and n:
                t["tw"] = _num(n[-1])
            elif op == "Tz" and n:
                t["th"] = _num(n[-1]) / 100.0
            elif op == "TL" and n:
                t["tl"] = _num(n[-1])
            elif op in ("Td", "TD") and len(n) >= 2:
                if op == "TD":
                    t["tl"] = -_num(n[-1])
                line_move(_num(n[-2]), _num(n[-1]))
            elif op == "Tm" and len(n) >= 6:
                t["tm"] = t["tlm"] = tuple(_num(v) for v in n[-6:])
            elif op == "T*":
                line_move(0.0, -t["tl"])
            elif op == "Tj" and n and isinstance(n[-1], bytes):
                self._show(t, n[-1])
            elif op in ("'", '"') and n and isinstance(n[-1], bytes):
                if op == '"' and len(n) >= 3:
                    t["tw"], t["tc"] = _num(n[-3]), _num(n[-2])
                line_move(0.0, -t["tl"])
                self._show(t, n[-1])
            elif op == "TJ" and n and isinstance(n[-1], list):
                for item in n[-1]:
                    if isinstance(item, bytes):
                        self._show(t, item)
                    elif isinstance(item, (int, float)):
                        t["tm"] = _mult((1.0, 0.0, 0.0, 1.0, -item / 1000.0 * t["size"] * t["th"], 0.0), t["tm"])
            elif op == "Do" and n and depth < MAX_DEPTH:
                xobjects = self.doc.resolve(resources.get("XObject")) if isinstance(resources, dict) else None
                form = self.doc.resolve(xobjects.get(n[-1])) if isinstance(xobjects, dict) else None
                if isinstance(form, Stream) and form.get("Subtype") == "Form":
                    data, coding = self.doc.stream_bytes(form)
                    if coding is None:
                        matrix = self.doc.resolve(form.get("Matrix"))
                        inner = _mult(tuple(_num(v) for v in matrix), t["ctm"]) if isinstance(matrix, list) and len(matrix) == 6 else t["ctm"]
                        self.run(data, self.doc.resolve(form.get("Resources")) or resources, depth + 1, inner)
            operands = []
        if depth:
            return ""
        text = "".join(self.out)
        return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()).strip()


def _num(value):
    return float(value) if isinstance(value, (int, float)) else 0.0


# -- images ---------------------------------------------------------------------

def _png(width, height, color_type, bit_depth, rows, palette=None):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + row for row in rows)
    parts = [b"\x89PNG\r\n\x1a\n", chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0))]
    if palette:
        parts.append(chunk(b"PLTE", palette))
    parts += [chunk(b"IDAT", zlib.compress(raw, 6)), chunk(b"IEND", b"")]
    return b"".join(parts)


def _colors(doc, space):
    """(PNG colour type, components, palette or None) for a colour space, or raise for one CasePath cannot write."""
    space = doc.resolve(space)
    if space in ("DeviceGray", "G", "CalGray") or space is None:
        return 0, 1, None
    if space in ("DeviceRGB", "RGB", "CalRGB"):
        return 2, 3, None
    if space in ("DeviceCMYK", "CMYK"):
        return 2, 4, None  # converted to RGB
    if isinstance(space, list) and space:
        kind = doc.resolve(space[0])
        if kind == "ICCBased" and len(space) > 1:
            profile = doc.resolve(space[1])
            n = _int(doc.resolve(profile.get("N"))) if isinstance(profile, Stream) else 3
            if n in (1, 3, 4):
                return (0, 1, None) if n == 1 else (2, n, None)
        if kind in ("CalGray",):
            return 0, 1, None
        if kind in ("CalRGB",):
            return 2, 3, None
        if kind in ("Indexed", "I") and len(space) >= 4:
            base_type, base_n, _ = _colors(doc, space[1])
            lookup = doc.resolve(space[3])
            table = doc.stream_bytes(lookup)[0] if isinstance(lookup, Stream) else lookup if isinstance(lookup, bytes) else b""
            count = _int(doc.resolve(space[2])) + 1
            if base_n == 1:
                table = b"".join(bytes([v, v, v]) for v in table[:count])
            return 3, 1, table[:count * 3]
    raise PdfError("colour space not supported")


def _cmyk_rgb(row):
    c, m, y, k = row[0::4], row[1::4], row[2::4], row[3::4]
    out = bytearray(len(c) * 3)
    out[0::3] = bytes(max(0, 255 - a - d) for a, d in zip(c, k))
    out[1::3] = bytes(max(0, 255 - a - d) for a, d in zip(m, k))
    out[2::3] = bytes(max(0, 255 - a - d) for a, d in zip(y, k))
    return bytes(out)


def _encode_image(doc, stream, max_side):
    width, height = _int(doc.resolve(stream.get("Width"))), _int(doc.resolve(stream.get("Height")))
    if width <= 0 or height <= 0:
        raise PdfError("image without a size")
    data, coding = doc.stream_bytes(stream)
    if coding == "jpeg":
        if max(width, height) > 7900:
            raise PdfError("image too large")
        return "image/jpeg", data
    if coding == "ccitt":
        return "image/png", _fax_png(doc, stream, data, width, height, max_side)
    if coding:
        raise PdfError(f"{coding} image")
    mask = bool(doc.resolve(stream.get("ImageMask")))
    bpc = 1 if mask else _int(doc.resolve(stream.get("BitsPerComponent"))) or 8
    color_type, components, palette = (0, 1, None) if mask else _colors(doc, stream.get("ColorSpace"))
    if bpc == 16:  # keep the high byte of each sample
        stride16 = width * components * 2
        data = b"".join(data[y * stride16:(y + 1) * stride16][0::2] for y in range(height))
        bpc = 8
    if color_type == 2 and bpc != 8:
        raise PdfError("colour image depth not supported")
    if bpc not in (1, 2, 4, 8):
        raise PdfError("image depth not supported")
    stride = (width * components * bpc + 7) // 8
    if len(data) < stride * height:
        data += bytes(stride * height - len(data))
    rows = [data[y * stride:(y + 1) * stride] for y in range(height)]
    decode_array = doc.resolve(stream.get("Decode"))
    inverted = isinstance(decode_array, list) and len(decode_array) >= 2 and _num(decode_array[0]) > _num(decode_array[1])
    if inverted and color_type == 0:
        table = bytes(255 - v for v in range(256)) if bpc == 8 else bytes((~v) & 0xFF for v in range(256))
        rows = [row.translate(table) for row in rows]
    # Large greyscale or colour scans are thinned to about max_side; one-bit pages stay sharp and small as they are.
    step = 1
    while bpc == 8 and max(width, height) / step > max_side * 1.3:
        step += 1
    if step > 1:
        rows = rows[::step]
        if components == 1:
            rows = [row[::step] for row in rows]
        else:
            thinned, count = [], (width + step - 1) // step
            for row in rows:
                out = bytearray(count * components)
                for channel in range(components):
                    out[channel::components] = row[channel::components * step][:count]
                thinned.append(bytes(out))
            rows = thinned
        width, height = (width + step - 1) // step, len(rows)
    if components == 4:  # CMYK to RGB, after thinning so it stays quick
        rows = [_cmyk_rgb(row) for row in rows]
    if max(width, height) > 7900:
        raise PdfError("image too large")
    return "image/png", _png(width, height, color_type, bpc, rows, palette)


def _fax_png(doc, stream, data, width, height, max_side):
    from .ccitt import FaxError, decode as fax_decode

    filters = [doc.resolve(f) for f in _list(doc.resolve(stream.get("Filter")))]
    parms = [doc.resolve(p) for p in _list(doc.resolve(stream.get("DecodeParms") or stream.get("DP")))]
    index = next((i for i, f in enumerate(filters) if f in ("CCITTFaxDecode", "CCF")), 0)
    p = parms[index] if index < len(parms) and isinstance(parms[index], dict) else {}
    value = lambda key, default: doc.resolve(p.get(key, default))
    halve = max(width, height) > max_side * 1.3
    try:
        rows = fax_decode(data, columns=_int(value("Columns", 1728)) or width, rows=_int(value("Rows", 0)) or height,
                          k=_int(value("K", 0)), black_is_1=bool(value("BlackIs1", False)),
                          byte_align=bool(value("EncodedByteAlign", False)), halve=halve)
    except FaxError as error:
        raise PdfError(f"fax image: {error}") from None
    decode_array = doc.resolve(stream.get("Decode"))
    if isinstance(decode_array, list) and len(decode_array) >= 2 and _num(decode_array[0]) > _num(decode_array[1]):
        table = bytes(255 - v for v in range(256))
        rows = [row.translate(table) for row in rows]
    return _png(len(rows[0]) if rows else 1, len(rows), 0, 8, rows)


# -- entry points ---------------------------------------------------------------

def extract_text(data):
    """(text with [page n] markers, {"pages", "pages_without_text", "reader"}) — the same shape as extract._pdf."""
    doc = Document(data)
    parts, empty = [], []
    for number, page in enumerate(doc.pages, 1):
        try:
            text = doc.page_text(page)
        except (PdfError, ValueError, TypeError, zlib.error, RecursionError):
            text = ""
        if len(re.sub(r"\W", "", text)) >= 3:
            parts.append(f"[page {number}]\n{text}")
        else:
            empty.append(number)
    return "\n\n".join(parts), {"pages": len(doc.pages), "pages_without_text": empty, "reader": "builtin"}


def page_images(data, numbers, max_side=1700):
    """{page: (media type, bytes)} for the given pages that carry an image CasePath can pass on, and {page: reason} for the rest."""
    doc = Document(data)
    images, reasons = {}, {}
    for number in numbers:
        if not 1 <= number <= len(doc.pages):
            reasons[number] = "no such page"
            continue
        media, payload = doc.page_image(doc.pages[number - 1], max_side)
        if media:
            images[number] = (media, payload)
        else:
            reasons[number] = payload
    return images, reasons


def compare(paths):
    """Content-free comparison with pypdf where installed: one line of counts per file, numbered, no names, no text.

    For text: pages with text, word recall against pypdf, and letter recall (5-letter sequences with all spacing
    removed, so a spacing difference in either reader does not count); for the weakest pages, word counts, the share of
    one-letter words in each reader's output and the font types. For scanned pages: how each is coded and whether its
    image was taken, why not, and what a page without any image holds."""
    import collections
    import io
    import json
    import os
    import time

    def grams(text):
        letters = re.sub(r"\W", "", text.lower())
        return {letters[i:i + 5] for i in range(max(0, len(letters) - 4))}

    def one_letter_share(words):
        return round(sum(1 for w in words if len(w) == 1) / len(words), 2) if words else None

    for index, path in enumerate(sorted(paths, key=os.path.basename), 1):  # numbered, not named: file names can be claim numbers
        data = open(path, "rb").read()
        row = {"file": f"D{index}", "mb": round(len(data) / 1e6, 1)}
        started = time.monotonic()
        text, doc = "", None
        try:
            doc = Document(data)
            text, details = extract_text(data)
            row.update(pages=details["pages"], builtin_text_pages=details["pages"] - len(details["pages_without_text"]))
            codings, reasons, empty = collections.Counter(), collections.Counter(), collections.Counter()
            for number in details["pages_without_text"]:
                page = doc.pages[number - 1]
                found = []
                resources = doc.resolve(page.get("Resources")) or {}
                doc._images(resources, found, 0, set())
                inline = doc._inline_images(page, resources)
                if not found and not inline:
                    media, payload = doc.page_image(page)
                    empty["vector page drawn" if media else payload] += 1
                    continue
                largest = max(found + inline, key=lambda st: _int(doc.resolve(st.get("Width"))) * _int(doc.resolve(st.get("Height"))))
                filters = [str(doc.resolve(f)) for f in _list(doc.resolve(largest.get("Filter")))] or ["none"]
                media, payload = doc.page_image(page)
                codings[f"{'inline ' if largest in inline else ''}{'+'.join(filters)}:{'ok' if media else 'not read'}"] += 1
                if not media:
                    reasons[payload] += 1
            row["scanned_pages"] = dict(codings)
            if reasons:
                row["not_read_because"] = dict(reasons)
            if empty:
                row["pages_without_any_image"] = dict(empty)
        except PdfError as error:
            row["builtin_error"] = str(error)[:60]
        row["builtin_seconds"] = round(time.monotonic() - started, 1)
        try:
            from pypdf import PdfReader
        except ImportError:
            print(json.dumps(row, ensure_ascii=False))
            continue
        reference = [(page.extract_text() or "").strip() for page in PdfReader(io.BytesIO(data)).pages]
        mine = {int(m.group(1)): m.group(2) for m in re.finditer(r"\[page (\d+)\]\n(.*?)(?=\n\n\[page \d+\]\n|\Z)", text, re.S)}
        pages = []
        for number, page_text in enumerate(reference, 1):
            theirs, ours = re.findall(r"\w+", page_text.lower()), re.findall(r"\w+", mine.get(number, "").lower())
            if not theirs:
                continue
            their_grams = grams(page_text)
            letters = len(their_grams & grams(mine.get(number, ""))) / len(their_grams) if their_grams else 1.0
            pages.append({"page": number, "word_recall": round(len(set(theirs) & set(ours)) / len(set(theirs)), 2),
                          "letter_recall": round(letters, 2), "pypdf_words": len(theirs), "builtin_words": len(ours),
                          "pypdf_one_letter_share": one_letter_share(theirs), "builtin_one_letter_share": one_letter_share(ours)})
        row["pypdf_text_pages"] = sum(1 for t in reference if t)
        if pages:
            row["word_recall_mean"] = round(sum(p["word_recall"] for p in pages) / len(pages), 3)
            row["letter_recall_mean"] = round(sum(p["letter_recall"] for p in pages) / len(pages), 3)
            row["letter_recall_min"] = min(p["letter_recall"] for p in pages)
            weakest = sorted(pages, key=lambda p: (p["letter_recall"], p["word_recall"]))[:3]
            for weak in weakest:
                if doc is not None:
                    fonts = doc.resolve((doc.resolve(doc.pages[weak["page"] - 1].get("Resources")) or {}).get("Font")) or {}
                    kinds = set()
                    for value in (fonts.values() if isinstance(fonts, dict) else []):
                        font = doc.resolve(value)
                        if isinstance(font, dict):
                            encoding = doc.resolve(font.get("Encoding"))
                            kinds.add("/".join([str(font.get("Subtype")), str(encoding) if isinstance(encoding, str) else "custom" if encoding else "none",
                                                "tounicode" if font.get("ToUnicode") is not None else "no-tounicode",
                                                "widths" if font.get("Widths") is not None or font.get("DescendantFonts") is not None else "no-widths"]))
                    weak["fonts"] = sorted(kinds)
            row["weakest_pages"] = weakest
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3 or sys.argv[1] != "compare":
        sys.exit("usage: python -m casepath_internal.pdfread compare <file.pdf> ...")
    compare(sys.argv[2:])
