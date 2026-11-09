"""CasePath's own PDF reader: text layers, object streams, CID fonts, scanned page images and fax-coded scans."""
import io
import struct
import sys
import unittest
import zlib
from unittest import mock

from casepath_internal import ccitt, pdfread
from casepath_internal.extract import extract


def build_pdf(objects, root=1, trailer_extra=b""):
    """A PDF from {number: bytes body}; streams are given as (dict bytes, data bytes)."""
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        body = objects[number]
        if isinstance(body, tuple):
            head, data = body
            out += b"%d 0 obj\n%s\nstream\n" % (number, head.replace(b">>", b" /Length %d>>" % len(data), 1)) + data + b"\nendstream\nendobj\n"
        else:
            out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (max(objects) + 1)
    for number in range(1, max(objects) + 1):
        out += b"%010d 00000 n \n" % offsets.get(number, 0)
    out += b"trailer\n<< /Size %d /Root %d 0 R %s>>\nstartxref\n%d\n%%%%EOF\n" % (max(objects) + 1, root, trailer_extra, xref)
    return bytes(out)


def gray_png_pixels(blob):
    """(width, height, rows) of an 8-bit grey PNG written by pdfread, decoded with zlib."""
    assert blob[:8] == b"\x89PNG\r\n\x1a\n"
    width, height, depth, kind = struct.unpack(">IIBB", blob[16:26])
    pos, idat = 8, b""
    while pos < len(blob):
        length, = struct.unpack(">I", blob[pos:pos + 4])
        if blob[pos + 4:pos + 8] == b"IDAT":
            idat += blob[pos + 8:pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * (3 if kind == 2 else 1) if depth == 8 else (width * depth + 7) // 8
    return width, height, [raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)] for y in range(height)]


TEXT_PAGE = (b"BT /F1 12 Tf 72 720 Td (Mietvertrag f\\374r die Wohnung) Tj 0 -14 Td [(M\\344ngelr) 20 (\\374ge) -300 (vom 3. M\\344rz)] TJ "
             b"T* (zweite Zeile) Tj ET")


def text_and_scan_pdf():
    image = b"".join(bytes([0 if 4 <= x < 12 else 255 for x in range(16)]) for _ in range(8))
    return build_pdf({
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2 /Resources << /Font << /F1 4 0 R >> >> >>",
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 5 0 R >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        5: (b"<< /Filter /FlateDecode >>", zlib.compress(TEXT_PAGE)),
        6: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 7 0 R /Resources << /XObject << /Im0 8 0 R >> >> >>",
        7: (b"<< >>", b"q 595 0 0 842 0 0 cm /Im0 Do Q"),
        8: (b"<< /Type /XObject /Subtype /Image /Width 16 /Height 8 /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode >>",
            zlib.compress(image)),
    })


class ReaderTests(unittest.TestCase):
    def test_a_text_page_and_a_scanned_page(self):
        text, details = pdfread.extract_text(text_and_scan_pdf())
        self.assertEqual((details["pages"], details["pages_without_text"], details["reader"]), (2, [2], "builtin"))
        self.assertIn("Mietvertrag für die Wohnung\nMängelrüge vom 3. März\nzweite Zeile", text)  # kerning joins, a wide gap is a space
        images, reasons = pdfread.page_images(text_and_scan_pdf(), [1, 2])
        self.assertEqual(reasons, {1: "no image"})
        media, blob = images[2]
        width, height, rows = gray_png_pixels(blob)
        self.assertEqual((media, width, height), ("image/png", 16, 8))
        self.assertEqual(rows[0], bytes([0 if 4 <= x < 12 else 255 for x in range(16)]))

    def test_object_streams_and_a_cid_font_with_its_unicode_map(self):
        cmap = (b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap 1 begincodespacerange <0000> <FFFF> endcodespacerange "
                b"2 beginbfchar <0003> <0020> <0010> <00FC> endbfchar 1 beginbfrange <0020> <0039> <0041> endbfrange endcmap end end")
        # "A B C" as 2-byte codes 0x20 0x21 0x22, then "ü": the range maps 0x20.. to A..
        content = b"BT /F1 11 Tf 50 700 Td <002000030021000300220010> Tj ET"
        inner = b"<< /Type /Font /Subtype /Type0 /BaseFont /ABCDEF+Arial /Encoding /Identity-H /ToUnicode 6 0 R >>"
        header = b"4 0 "
        objstm = header + inner
        data = build_pdf({
            1: b"<< /Type /Catalog /Pages 2 0 R >>",
            2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: b"<< /Type /Page /Parent 2 0 R /Contents 5 0 R /Resources << /Font << /F1 4 0 R >> >> >>",
            5: (b"<< /Filter /FlateDecode >>", zlib.compress(content)),
            6: (b"<< /Filter /FlateDecode >>", zlib.compress(cmap)),
            7: (b"<< /Type /ObjStm /N 1 /First %d /Filter /FlateDecode >>" % len(header), zlib.compress(objstm)),
        })
        text, details = pdfread.extract_text(data)
        self.assertEqual(text, "[page 1]\nA B Cü")

    def test_an_encrypted_file_is_reported_not_guessed(self):
        data = build_pdf({1: b"<< /Type /Catalog /Pages 2 0 R >>", 2: b"<< /Type /Pages /Kids [] /Count 0 >>", 3: b"<< /Filter /Standard >>"},
                         trailer_extra=b"/Encrypt 3 0 R ")
        with self.assertRaises(pdfread.PdfError):
            pdfread.extract_text(data)
        result = extract("dossier.pdf", "application/pdf", data)
        self.assertFalse(result["readable"])
        self.assertIn("password-protected", result["note"])

    def test_without_pypdf_the_upload_is_read_by_casepath_itself(self):
        with mock.patch.dict(sys.modules, {"pypdf": None}):
            result = extract("dossier.pdf", "application/pdf", text_and_scan_pdf())
        self.assertTrue(result["readable"])
        self.assertEqual((result["pages"], result["pages_without_text"], result["reader"]), (2, [2], "builtin"))
        self.assertIn("1 of 2 pages have no text layer", result["note"])


class FaxTests(unittest.TestCase):
    def setUp(self):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("Pillow (libtiff) makes the reference fax data")
        page = Image.new("L", (1240, 700), 255)
        draw = ImageDraw.Draw(page)
        for y in range(20, 680, 28):
            draw.text((30 + y % 40, y), "Kündigung und Rückforderung des Darlehens vom 12. Mai 2025", fill=0)
        draw.rectangle([700, 100, 1100, 400], fill=0)
        draw.ellipse([60, 420, 400, 650], outline=0, width=4)
        self.page, self.Image = page.convert("1"), Image

    def test_a_group_4_scan_in_a_pdf_is_decoded_exactly(self):
        buffer = io.BytesIO()
        self.page.save(buffer, format="PDF", resolution=150)  # Pillow stores bilevel pages as CCITT Group 4
        images, reasons = pdfread.page_images(buffer.getvalue(), [1])
        self.assertEqual(reasons, {})
        width, height, rows = gray_png_pixels(images[1][1])
        self.assertEqual((width, height), self.page.size)
        self.assertEqual(b"".join(rows), self.page.convert("L").tobytes())

    def test_group_3_and_group_4_strips_match_libtiff(self):
        for compression, k in (("group3", 0), ("group4", -1)):
            buffer = io.BytesIO()
            self.page.save(buffer, format="TIFF", compression=compression)
            tiff = self.Image.open(io.BytesIO(buffer.getvalue()))
            rows_per_strip, rows = tiff.tag_v2.get(278, self.page.height), []
            for offset, count in zip(tiff.tag_v2[273], tiff.tag_v2[279]):
                strip = buffer.getvalue()[offset:offset + count]
                rows += ccitt.decode(strip, columns=self.page.width, rows=min(rows_per_strip, self.page.height - len(rows)), k=k)
            decoded = bytes(255 - v for v in b"".join(rows))  # TIFF's BlackIsZero turns the fax colours around
            self.assertEqual(decoded, self.page.convert("L").tobytes(), compression)

    def test_a_large_scan_is_halved_keeping_thin_strokes(self):
        rows = [bytes([255] * 8), bytes([255, 0, 255, 255, 255, 255, 255, 255]), bytes([255] * 8), bytes([255] * 8)]
        self.assertEqual(ccitt._halve(rows, 8), [bytes([0, 255, 255, 255]), bytes([255] * 4)])


if __name__ == "__main__":
    unittest.main()
