"""Outlook .msg e-mails, read in the standard library.

A .msg file is a Compound File Binary (the OLE container). This module reads its directory and streams, then the
message properties CasePath needs: sender, recipients, date, subject, the body (plain text, else the HTML body as
text) and the attachments with their file names and bytes. Embedded messages (a .msg attached to a .msg) are returned
as attachments of their own, read the same way.
"""
import email.utils
import html.parser
import re
import struct

SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
END_OF_CHAIN, FREE = 0xFFFFFFFE, 0xFFFFFFFF
MAX_SIZE = 200 * 1024 * 1024


class MsgError(ValueError):
    pass


class _Entry:
    __slots__ = ("name", "kind", "left", "right", "child", "start", "size", "children")

    def __init__(self, name, kind, left, right, child, start, size):
        self.name, self.kind, self.left, self.right, self.child, self.start, self.size = name, kind, left, right, child, start, size
        self.children = {}


class Compound:
    """The directory tree and stream contents of a Compound File Binary."""

    def __init__(self, data):
        if not data.startswith(SIGNATURE) or len(data) < 512:
            raise MsgError("not an Outlook message file")
        self.data = data
        sector_shift, mini_shift = struct.unpack_from("<HH", data, 30)
        self.sector = 1 << sector_shift
        self.mini = 1 << mini_shift
        fat_count, first_dir = struct.unpack_from("<II", data, 44)
        self.cutoff, first_minifat, minifat_count, first_difat, difat_count = struct.unpack_from("<IIIII", data, 56)
        difat = list(struct.unpack_from("<109I", data, 76))
        sector, guard = first_difat, 0
        while sector not in (END_OF_CHAIN, FREE) and guard < difat_count + 1:
            values = struct.unpack_from(f"<{self.sector // 4}I", data, self._offset(sector))
            difat += values[:-1]
            sector, guard = values[-1], guard + 1
        self.fat = []
        for fat_sector in [s for s in difat if s not in (END_OF_CHAIN, FREE)][:fat_count]:
            self.fat += struct.unpack_from(f"<{self.sector // 4}I", data, self._offset(fat_sector))
        directory = self._chain(first_dir)
        entries = []
        for pos in range(0, len(directory) - 127, 128):
            raw = directory[pos:pos + 128]
            length = struct.unpack_from("<H", raw, 64)[0]
            name = raw[:max(0, length - 2)].decode("utf-16-le", errors="replace")
            kind = raw[66]
            left, right, child = struct.unpack_from("<III", raw, 68)
            start, size = struct.unpack_from("<II", raw, 116)
            entries.append(_Entry(name, kind, left, right, child, start, size))
        if not entries or entries[0].kind != 5:
            raise MsgError("no root entry")
        self.entries = entries
        root = entries[0]
        self.ministream = self._chain(root.start, root.size) if root.size else b""
        self.minifat = []
        if minifat_count and first_minifat not in (END_OF_CHAIN, FREE):
            raw = self._chain(first_minifat)
            self.minifat = list(struct.unpack_from(f"<{len(raw) // 4}I", raw))
        self._tree(0, set())
        self.root = root

    def _offset(self, sector):
        offset = (sector + 1) * self.sector
        if offset + self.sector > len(self.data) + self.sector:
            raise MsgError("sector out of range")
        return offset

    def _chain(self, start, size=None):
        out, sector, seen = bytearray(), start, set()
        while sector not in (END_OF_CHAIN, FREE) and sector < len(self.fat) + 1:
            if sector in seen or len(out) > MAX_SIZE:
                raise MsgError("broken sector chain")
            seen.add(sector)
            offset = self._offset(sector)
            out += self.data[offset:offset + self.sector]
            sector = self.fat[sector] if sector < len(self.fat) else END_OF_CHAIN
        return bytes(out[:size]) if size is not None else bytes(out)

    def _mini_chain(self, start, size):
        out, sector, seen = bytearray(), start, set()
        while sector not in (END_OF_CHAIN, FREE) and len(out) < size:
            if sector in seen or sector >= len(self.minifat):
                break
            seen.add(sector)
            out += self.ministream[sector * self.mini:(sector + 1) * self.mini]
            sector = self.minifat[sector]
        return bytes(out[:size])

    def _tree(self, index, seen):
        """Attach every entry to its storage through the red-black sibling links."""
        entry = self.entries[index]
        stack = [entry.child]
        while stack:
            i = stack.pop()
            if i == FREE or i >= len(self.entries) or i in seen:
                continue
            seen.add(i)
            child = self.entries[i]
            entry.children[child.name] = child
            stack += [child.left, child.right]
            if child.kind in (1, 5):
                self._tree(i, seen)

    def read(self, entry):
        if entry.kind != 2:
            return b""
        size = entry.size
        if size < self.cutoff:
            return self._mini_chain(entry.start, size)
        return self._chain(entry.start, size)


class _Text(html.parser.HTMLParser):
    BREAKS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "head"):
            self.skip += 1
        elif tag in self.BREAKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script", "head"):
            self.skip = max(0, self.skip - 1)
        elif tag in self.BREAKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_text(markup):
    parser = _Text()
    parser.feed(markup)
    text = "".join(parser.parts).replace("\xa0", " ")
    return re.sub(r"\n\s*\n+", "\n\n", "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines())).strip()


def _properties(storage, compound, codepage="cp1252"):
    """{property id: value} of the variable-length properties (strings, binaries) in a storage."""
    values = {}
    for name, entry in storage.children.items():
        match = re.fullmatch(r"__substg1\.0_([0-9A-Fa-f]{4})([0-9A-Fa-f]{4})", name)
        if not match or entry.kind != 2:
            continue
        prop, kind = int(match.group(1), 16), match.group(2).upper()
        raw = compound.read(entry)
        if kind == "001F":
            values[prop] = raw.decode("utf-16-le", errors="replace").rstrip("\x00")
        elif kind == "001E":
            values[prop] = raw.decode(codepage, errors="replace").rstrip("\x00")
        elif kind == "0102":
            values[prop] = raw
    return values


def _fixed(storage, compound, header):
    """{property id: 8 raw bytes} from the fixed-length property stream (dates, numbers)."""
    entry = storage.children.get("__properties_version1.0")
    if entry is None:
        return {}
    raw = compound.read(entry)
    out = {}
    for pos in range(header, len(raw) - 15, 16):
        tag, _flags = struct.unpack_from("<II", raw, pos)
        out[tag >> 16] = (tag & 0xFFFF, raw[pos + 8:pos + 16])
    return out


def _filetime(raw):
    value = struct.unpack("<Q", raw)[0]
    if not value:
        return None
    import datetime
    return datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(microseconds=value // 10)


def _codepage(fixed):
    for prop in (0x3FDE, 0x3FFD):  # internet code page, message code page
        if prop in fixed:
            number = struct.unpack("<I", fixed[prop][1][:4])[0]
            try:
                "".encode(f"cp{number}")
                return f"cp{number}"
            except LookupError:
                if number == 65001:
                    return "utf-8"
    return "cp1252"


def _message(storage, compound, header_size, depth=0):
    fixed = _fixed(storage, compound, header_size)
    codepage = _codepage(fixed)
    props = _properties(storage, compound, codepage)
    headers = props.get(0x007D) or ""
    parsed = email.message_from_string(headers) if isinstance(headers, str) and headers else None

    def header(name):
        return (parsed.get(name) if parsed is not None else None) or ""
    sender_name, sender_address = props.get(0x0C1A) or props.get(0x0042) or "", props.get(0x5D01) or props.get(0x0C1F) or ""
    sender = header("From") or (f"{sender_name} <{sender_address}>" if sender_name and "@" in sender_address else sender_name or sender_address)
    date = header("Date")
    if not date:
        for prop in (0x0039, 0x0E06):  # sent, delivered
            if prop in fixed and fixed[prop][0] == 0x0040:
                moment = _filetime(fixed[prop][1])
                if moment:
                    date = email.utils.format_datetime(moment)
                    break
    body = props.get(0x1000)
    if not isinstance(body, str) or not body.strip():
        markup = props.get(0x1013)
        if isinstance(markup, bytes):
            markup = markup.decode(codepage if codepage != "cp1252" else "utf-8", errors="replace")
        body = html_text(markup) if isinstance(markup, str) and markup.strip() else ""
    message = {"from": sender, "to": header("To") or props.get(0x0E04) or "", "cc": header("Cc") or props.get(0x0E03) or "",
               "date": date, "subject": props.get(0x0037) or header("Subject") or "", "body": (body or "").replace("\r\n", "\n").strip(),
               "attachments": []}
    for name, entry in sorted(storage.children.items()):
        if not name.startswith("__attach_version1.0_") or entry.kind != 1:
            continue
        attach = _properties(entry, compound, codepage)
        filename = attach.get(0x3707) or attach.get(0x3704) or attach.get(0x3001) or "Anhang"
        embedded = entry.children.get("__substg1.0_3701000D")
        if embedded is not None and depth < 3:
            inner = _message(embedded, compound, 24, depth + 1)
            message["attachments"].append({"name": (inner["subject"] or filename) + ".eml", "data": to_eml(inner),
                                           "attachments": inner["attachments"]})
        elif isinstance(attach.get(0x3701), bytes):
            message["attachments"].append({"name": filename, "data": attach[0x3701]})
    return message


def read(data):
    """The message: from, to, cc, date, subject, body and attachments [{name, data}]."""
    compound = Compound(data)
    return _message(compound.root, compound, 32)


def to_eml(message):
    """The message as an RFC 822 e-mail without its attachments, so it reads like any other e-mail."""
    from email.message import EmailMessage
    out = EmailMessage()
    for key, value in (("From", message["from"]), ("To", message["to"]), ("Cc", message["cc"]), ("Date", message["date"]),
                       ("Subject", message["subject"])):
        if value:
            out[key] = re.sub(r"[\r\n]+", " ", value)
    out.set_content(message["body"] or "")
    return out.as_bytes()
