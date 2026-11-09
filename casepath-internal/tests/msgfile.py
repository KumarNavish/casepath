"""Build Outlook .msg files (Compound File Binary, version 3) for tests, in the standard library."""
import datetime
import struct

FREE, END, FATSECT = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD
SECTOR, MINI, CUTOFF = 512, 64, 4096


def build_cfb(tree):
    """``tree``: {name: bytes (a stream) | dict (a storage)} under the root."""
    entries = [{"name": "Root Entry", "kind": 5, "data": None, "children": []}]

    def add(parent, items):
        for name, value in items.items():
            entry = {"name": name, "kind": 1 if isinstance(value, dict) else 2, "data": None if isinstance(value, dict) else value,
                     "children": []}
            entries.append(entry)
            parent["children"].append(len(entries) - 1)
            if isinstance(value, dict):
                add(entry, value)
    add(entries[0], tree)

    mini, minifat, big = bytearray(), [], []
    for entry in entries:
        if entry["kind"] != 2:
            continue
        data = entry["data"]
        entry["size"] = len(data)
        if len(data) < CUTOFF:
            count = max(1, -(-len(data) // MINI))
            entry["start"] = len(minifat)
            minifat += [len(minifat) + i + 1 for i in range(count - 1)] + [END]
            mini += data + bytes(count * MINI - len(data))
        else:
            big.append(entry)
    dir_sectors = -(-len(entries) // 4)
    minifat_sectors = -(-len(minifat) // 128) if minifat else 0
    mini_sectors = -(-len(mini) // SECTOR)
    big_sectors = sum(-(-e["size"] // SECTOR) for e in big)
    fat_sectors = 1
    while fat_sectors * 128 < fat_sectors + dir_sectors + minifat_sectors + mini_sectors + big_sectors:
        fat_sectors += 1
    fat, next_sector = [FATSECT] * fat_sectors, fat_sectors

    def chain(count):
        nonlocal next_sector
        start = next_sector
        fat.extend([next_sector + i + 1 for i in range(count - 1)] + [END])
        next_sector += count
        return start
    first_dir = chain(dir_sectors)
    first_minifat = chain(minifat_sectors) if minifat_sectors else END
    first_mini = chain(mini_sectors) if mini_sectors else END
    for entry in big:
        entry["start"] = chain(-(-entry["size"] // SECTOR))
    fat += [FREE] * (fat_sectors * 128 - len(fat))
    entries[0]["start"], entries[0]["size"] = first_mini, len(mini)

    def key(index):
        name = entries[index]["name"]
        return (len(name), name.upper())
    for entry in entries:  # children linked as a right-leaning chain in directory order
        kids = sorted(entry["children"], key=key)
        entry["child"] = kids[0] if kids else FREE
        for a, b in zip(kids, kids[1:] + [None]):
            entries[a]["right"] = FREE if b is None else b
    directory = bytearray()
    for entry in entries:
        name = (entry["name"] + "\0").encode("utf-16-le")
        directory += name.ljust(64, b"\0") + struct.pack("<HBB", len(name), entry["kind"], 1)
        directory += struct.pack("<III", FREE, entry.get("right", FREE), entry.get("child", FREE)) + bytes(16) + bytes(4) + bytes(16)
        directory += struct.pack("<II", entry.get("start", END) if entry["kind"] != 1 else 0, entry.get("size", 0)) + bytes(4)
    directory += b"".join(struct.pack("<64sHBBIII16sI16sIII", b"", 0, 0, 0, FREE, FREE, FREE, bytes(16), 0, bytes(16), 0, 0, 0)
                          for _ in range(dir_sectors * 4 - len(entries)))
    header = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(16) + struct.pack("<HHHHH", 0x3E, 3, 0xFFFE, 9, 6) + bytes(6)
    header += struct.pack("<IIIIIIIII", 0, fat_sectors, first_dir, 0, CUTOFF, first_minifat, minifat_sectors, END, 0)
    header += struct.pack("<109I", *(list(range(fat_sectors)) + [FREE] * (109 - fat_sectors)))
    body = struct.pack(f"<{len(fat)}I", *fat) + bytes(directory)
    if minifat_sectors:
        body += struct.pack(f"<{minifat_sectors * 128}I", *(minifat + [FREE] * (minifat_sectors * 128 - len(minifat))))
    body += bytes(mini) + bytes(mini_sectors * SECTOR - len(mini))
    for entry in big:
        body += entry["data"] + bytes(-(-entry["size"] // SECTOR) * SECTOR - entry["size"])
    return header + body


def _string(value):
    return value.encode("utf-16-le")


def _filetime(moment):
    return int((moment - datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)).total_seconds() * 10_000_000)


def message(*, subject, body="", html=None, sender_name="", sender_address="", to="", sent=None, attachments=(), header_size=32):
    """The streams of one message; ``attachments``: [(name, bytes)] or [(name, message dict)] for an attached e-mail."""
    tree = {"__substg1.0_0037001F": _string(subject)}
    if body:
        tree["__substg1.0_1000001F"] = _string(body)
    if html is not None:
        tree["__substg1.0_10130102"] = html.encode("utf-8")
    if sender_name:
        tree["__substg1.0_0C1A001F"] = _string(sender_name)
    if sender_address:
        tree["__substg1.0_5D01001F"] = _string(sender_address)
    if to:
        tree["__substg1.0_0E04001F"] = _string(to)
    properties = bytes(header_size)
    if sent is not None:
        properties += struct.pack("<IIQ", 0x00390040, 6, _filetime(sent))
    properties += struct.pack("<IIQ", 0x3FDE0003, 6, 65001)  # internet code page: UTF-8
    tree["__properties_version1.0"] = properties
    for index, (name, payload) in enumerate(attachments):
        attach = {"__substg1.0_3707001F": _string(name), "__properties_version1.0": bytes(8)}
        if isinstance(payload, dict):
            attach["__substg1.0_3701000D"] = payload
        else:
            attach["__substg1.0_37010102"] = payload
        tree[f"__attach_version1.0_#{index:08X}"] = attach
    return tree


def build_msg(**fields):
    return build_cfb(message(**fields))
