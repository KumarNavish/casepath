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
        self._images(self.resolve(page.get("Resources")) or {}, found, 0, set())
        if not found:
            return None, "no image"
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

    def text(self, data):
        if self.composite:
            out = []
            for i in range(0, len(data) - self.width + 1, self.width):
                code = int.from_bytes(data[i:i + self.width], "big")
                out.append(self.map.get(code, ""))
            return "".join(out)
        out = []
        for byte in data:
            if byte in self.map:
                out.append(self.map[byte])
            elif byte in self.differences:
                out.append(self.differences[byte])
            elif self.base == "MacRomanEncoding" and byte >= 128:
                out.append(_MACROMAN[byte - 128])
            else:
                out.append(bytes([byte]).decode("cp1252", errors="replace").replace("�", ""))
        return "".join(out)


class _TextRun:
    """Walk a content stream and write its text in drawing order, a new line wherever the text moves down."""

    def __init__(self, doc):
        self.doc, self.out, self.fonts = doc, [], {}
        self.font, self.y, self.x_moved = None, None, False

    def _font(self, resources, name):
        fonts = self.doc.resolve(resources.get("Font")) if isinstance(resources, dict) else None
        ref = fonts.get(name) if isinstance(fonts, dict) else None
        key = ref if isinstance(ref, Ref) else (id(resources), name)
        if key not in self.fonts:
            self.fonts[key] = Font(self.doc, ref)
        return self.fonts[key]

    def _newline(self):
        if self.out and not self.out[-1].endswith("\n"):
            self.out.append("\n")

    def _space(self):
        if self.out and not self.out[-1].endswith((" ", "\n")):
            self.out.append(" ")

    def _move(self, y, sideways=False):
        if self.y is not None and abs(y - self.y) > 0.5:
            self._newline()
        elif sideways:
            self._space()
        self.y = y

    def _show(self, data):
        if self.font is None:
            self.font = Font(self.doc, None)
        self.out.append(self.font.text(data))

    def run(self, content, resources, depth):
        lex, operands, line_y, leading = Lexer(content), [], 0.0, 0.0
        while True:
            token = lex.parse()
            if token is None:
                break
            if not isinstance(token, Op):
                operands.append(token)
                continue
            op = str(token)
            if op == "BI":  # inline image: skip to EI
                end = re.compile(rb"\sEI(?=[\s]|$)").search(content, lex.pos)
                lex.pos = end.end() if end else len(content)
            elif op == "BT":
                line_y = 0.0
            elif op == "Tf" and len(operands) >= 2:
                self.font = self._font(resources, operands[-2])
            elif op == "TL" and operands:
                leading = _num(operands[-1])
            elif op in ("Td", "TD") and len(operands) >= 2:
                tx, ty = _num(operands[-2]), _num(operands[-1])
                if op == "TD":
                    leading = -ty
                line_y += ty
                self._move(line_y, sideways=tx > 0)
            elif op == "Tm" and len(operands) >= 6:
                line_y = _num(operands[-1])
                self._move(line_y, sideways=True)
            elif op == "T*":
                line_y -= leading or 1
                self._move(line_y)
            elif op == "Tj" and operands and isinstance(operands[-1], bytes):
                self._show(operands[-1])
            elif op in ("'", '"') and operands and isinstance(operands[-1], bytes):
                line_y -= leading or 1
                self._move(line_y)
                self._show(operands[-1])
            elif op == "TJ" and operands and isinstance(operands[-1], list):
                for item in operands[-1]:
                    if isinstance(item, bytes):
                        self._show(item)
                    elif isinstance(item, (int, float)) and item < -180:
                        self._space()
            elif op == "Do" and operands and depth < MAX_DEPTH:
                xobjects = self.doc.resolve(resources.get("XObject")) if isinstance(resources, dict) else None
                form = self.doc.resolve(xobjects.get(operands[-1])) if isinstance(xobjects, dict) else None
                if isinstance(form, Stream) and form.get("Subtype") == "Form":
                    data, coding = self.doc.stream_bytes(form)
                    if coding is None:
                        saved = (self.font, self.y)
                        self.run(data, self.doc.resolve(form.get("Resources")) or resources, depth + 1)
                        self.font, self.y = saved
            elif op == "ET":
                pass
            operands = []
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
    if isinstance(space, list) and space:
        kind = doc.resolve(space[0])
        if kind == "ICCBased" and len(space) > 1:
            profile = doc.resolve(space[1])
            n = _int(doc.resolve(profile.get("N"))) if isinstance(profile, Stream) else 3
            if n in (1, 3):
                return (0, 1, None) if n == 1 else (2, 3, None)
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
    if color_type == 2 and bpc != 8:
        raise PdfError("RGB image depth not supported")
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
            thinned = []
            for row in rows:
                out = bytearray(((width + step - 1) // step) * 3)
                out[0::3], out[1::3], out[2::3] = row[0::3 * step], row[1::3 * step], row[2::3 * step]
                thinned.append(bytes(out))
            rows = thinned
        width, height = (width + step - 1) // step, len(rows)
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
