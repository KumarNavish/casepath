"""CCITT fax decoding (ITU-T T.4 and T.6) for bilevel scans inside PDFs, in the standard library.

Office scanners store black-and-white pages this way. ``decode`` returns the page as rows of 8-bit grey bytes
(255 white, 0 black), optionally halved in each direction, so it can be written as an ordinary PNG.
"""

WHITE_TERMINATING = [
    "00110101", "000111", "0111", "1000", "1011", "1100", "1110", "1111", "10011", "10100", "00111", "01000", "001000",
    "000011", "110100", "110101", "101010", "101011", "0100111", "0001100", "0001000", "0010111", "0000011", "0000100",
    "0101000", "0101011", "0010011", "0100100", "0011000", "00000010", "00000011", "00011010", "00011011", "00010010",
    "00010011", "00010100", "00010101", "00010110", "00010111", "00101000", "00101001", "00101010", "00101011",
    "00101100", "00101101", "00000100", "00000101", "00001010", "00001011", "01010010", "01010011", "01010100",
    "01010101", "00100100", "00100101", "01011000", "01011001", "01011010", "01011011", "01001010", "01001011",
    "00110010", "00110011", "00110100"]
WHITE_MAKEUP = [
    "11011", "10010", "010111", "0110111", "00110110", "00110111", "01100100", "01100101", "01101000", "01100111",
    "011001100", "011001101", "011010010", "011010011", "011010100", "011010101", "011010110", "011010111", "011011000",
    "011011001", "011011010", "011011011", "010011000", "010011001", "010011010", "011000", "010011011"]
BLACK_TERMINATING = [
    "0000110111", "010", "11", "10", "011", "0011", "0010", "00011", "000101", "000100", "0000100", "0000101", "0000111",
    "00000100", "00000111", "000011000", "0000010111", "0000011000", "0000001000", "00001100111", "00001101000",
    "00001101100", "00000110111", "00000101000", "00000010111", "00000011000", "000011001010", "000011001011",
    "000011001100", "000011001101", "000001101000", "000001101001", "000001101010", "000001101011", "000011010010",
    "000011010011", "000011010100", "000011010101", "000011010110", "000011010111", "000001101100", "000001101101",
    "000011011010", "000011011011", "000001010100", "000001010101", "000001010110", "000001010111", "000001100100",
    "000001100101", "000001010010", "000001010011", "000000100100", "000000110111", "000000111000", "000000100111",
    "000000101000", "000001011000", "000001011001", "000000101011", "000000101100", "000001011010", "000001100110",
    "000001100111"]
BLACK_MAKEUP = [
    "0000001111", "000011001000", "000011001001", "000001011011", "000000110011", "000000110100", "000000110101",
    "0000001101100", "0000001101101", "0000001001010", "0000001001011", "0000001001100", "0000001001101",
    "0000001110010", "0000001110011", "0000001110100", "0000001110101", "0000001110110", "0000001110111",
    "0000001010010", "0000001010011", "0000001010100", "0000001010101", "0000001011010", "0000001011011",
    "0000001100100", "0000001100101"]
EXTENDED_MAKEUP = [
    "00000001000", "00000001100", "00000001101", "000000010010", "000000010011", "000000010100", "000000010101",
    "000000010110", "000000010111", "000000011100", "000000011101", "000000011110", "000000011111"]

PEEK = 13  # the longest run code


class FaxError(ValueError):
    pass


def _table(terminating, makeup):
    codes = {code: run for run, code in enumerate(terminating)}
    codes.update({code: 64 * (i + 1) for i, code in enumerate(makeup)})
    codes.update({code: 1792 + 64 * i for i, code in enumerate(EXTENDED_MAKEUP)})
    table = [None] * (1 << PEEK)
    for code, run in codes.items():
        length, value = len(code), int(code, 2)
        for tail in range(1 << (PEEK - length)):
            table[(value << (PEEK - length)) | tail] = (run, length)
    return table


_RUNS = None

# Two-dimensional mode codes (T.4 section 4.2.1.3): name, vertical offset, length.
_MODES = {"0001": ("pass", 0), "001": ("horizontal", 0), "1": ("vertical", 0), "011": ("vertical", 1),
          "000011": ("vertical", 2), "0000011": ("vertical", 3), "010": ("vertical", -1), "000010": ("vertical", -2),
          "0000010": ("vertical", -3)}
_MODE_TABLE = [None] * 128
for _code, (_mode, _offset) in _MODES.items():
    for _tail in range(1 << (7 - len(_code))):
        _MODE_TABLE[(int(_code, 2) << (7 - len(_code))) | _tail] = (_mode, _offset, len(_code))


class _Bits:
    def __init__(self, data):
        self.data, self.pos, self.end = data, 0, len(data) * 8

    def peek(self, n):
        byte, shift = self.pos >> 3, self.pos & 7
        chunk = int.from_bytes(self.data[byte:byte + 4].ljust(4, b"\0"), "big")
        return (chunk >> (32 - shift - n)) & ((1 << n) - 1)

    def skip(self, n):
        self.pos += n

    def align(self):
        self.pos = (self.pos + 7) & ~7

    def done(self):
        return self.pos >= self.end

    def eol(self):
        """Skip an end-of-line code (eleven zeros and a one, after optional fill zeros)."""
        if self.peek(12) == 1:
            self.skip(12)
            return True
        if self.peek(11) == 0:
            start = self.pos
            while not self.done() and self.peek(1) == 0:
                self.skip(1)
            if not self.done() and self.pos - start >= 11:
                self.skip(1)
                return True
            self.pos = start
        return False


def _run(bits, color):
    table = _RUNS[color]
    total = 0
    while True:
        if bits.done():
            raise FaxError("data ends inside a run")
        entry = table[bits.peek(PEEK)]
        if entry is None:
            raise FaxError("invalid run code")
        run, length = entry
        bits.skip(length)
        total += run
        if run < 64:
            return total


def _line_2d(bits, ref, columns):
    """One coded line against the reference line's changing elements; returns this line's changing elements."""
    line, a0, color = [], -1, 0
    while a0 < columns:
        # b1: the first changing element on the reference line right of a0 that turns to the opposite colour
        i = 0
        while i < len(ref) and (ref[i] <= a0 or (i & 1) != color):
            i += 1
        b1 = ref[i] if i < len(ref) else columns
        b2 = ref[i + 1] if i + 1 < len(ref) else columns
        if bits.done():
            raise FaxError("data ends inside a line")
        entry = _MODE_TABLE[bits.peek(7)]
        if entry is None:
            raise FaxError("end of block")  # an EOL/EOFB or extension code
        mode, offset, length = entry
        bits.skip(length)
        if mode == "pass":
            a0 = b2
        elif mode == "horizontal":
            start = max(a0, 0)
            a1 = min(start + _run(bits, color), columns)
            a2 = min(a1 + _run(bits, 1 - color), columns)
            line += [a1, a2]
            a0 = a2
        else:
            a1 = max(0, min(b1 + offset, columns))
            line.append(a1)
            a0 = a1
            color = 1 - color
    return line


def _line_1d(bits, columns):
    line, x, color = [], 0, 0
    while x < columns:
        x = min(x + _run(bits, color), columns)
        line.append(x)
        color = 1 - color
    return [x for x in line if x < columns]


def _pixels(changes, columns):
    row = bytearray(b"\xff" * columns)
    for start, end in zip(changes[0::2], changes[1::2] + [columns] * (len(changes) % 2)):
        if end > start:
            row[start:end] = bytes(end - start)
    return row


def _halve(rows, columns):
    """2x2 minimum: a black pixel anywhere in a block keeps the block black, so thin strokes survive."""
    out = []
    for top, bottom in zip(rows[0::2], rows[1::2] + ([rows[-1]] if len(rows) % 2 else [])):
        both = (int.from_bytes(top, "big") & int.from_bytes(bottom, "big")).to_bytes(columns, "big")
        even, odd = both[0::2], both[1::2]
        if len(odd) < len(even):
            odd += b"\xff"
        out.append((int.from_bytes(even, "big") & int.from_bytes(odd, "big")).to_bytes(len(even), "big"))
    return out


def decode(data, *, columns=1728, rows=0, k=0, black_is_1=False, byte_align=False, halve=False):
    """Rows of grey bytes (255 white, 0 black). ``k`` < 0 is Group 4, 0 is Group 3 one-dimensional, > 0 mixed."""
    global _RUNS
    if _RUNS is None:
        _RUNS = (_table(WHITE_TERMINATING, WHITE_MAKEUP), _table(BLACK_TERMINATING, BLACK_MAKEUP))
    bits, out, ref = _Bits(data), [], []
    while (rows <= 0 or len(out) < rows) and not bits.done():
        if byte_align and k >= 0:
            bits.align()
        try:
            if k >= 0:
                while bits.eol():
                    pass
                two_d = False
                if k > 0:
                    two_d = bits.peek(1) == 0
                    bits.skip(1)
                line = _line_2d(bits, ref, columns) if two_d else _line_1d(bits, columns)
            else:
                if byte_align:
                    bits.align()
                line = _line_2d(bits, ref, columns)
        except FaxError:
            if not out:
                raise
            break  # the end of the block, or damage: keep the rows read so far
        out.append(_pixels(line, columns))
        ref = line
    if rows > 0 and len(out) < rows:
        out += [bytearray(b"\xff" * columns)] * (rows - len(out))
    if black_is_1:
        table = bytes(255 - v for v in range(256))
        out = [row.translate(table) for row in out]
    rows_out = [bytes(row) for row in out]
    return _halve(rows_out, columns) if halve else rows_out
