import io
import unittest

from casepath.read import cut, pdfread


def ten_pages():
    try:
        from reportlab.pdfgen import canvas
    except ImportError:
        return None
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    for n in range(1, 11):
        c.drawString(72, 720, f"Seite {n} des Dossiers")
        c.showPage()
    c.save()
    return buffer.getvalue()


def xref_stream_pdf(pages=3):
    """A PDF whose cross-reference is a stream (no classic trailer), as most scanners write."""
    objects = {1: b"<< /Type /Catalog /Pages 2 0 R >>",
               2: b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % (3 + i) for i in range(pages)) + b"] /Count %d /MediaBox [0 0 200 200] >>" % pages}
    for i in range(pages):
        objects[3 + i] = b"<< /Type /Page /Parent 2 0 R /Resources << >> >>"
    out, offsets = bytearray(b"%PDF-1.5\n"), {}
    for n, body in objects.items():
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
    xref_no = max(objects) + 1
    offsets[xref_no] = len(out)
    rows = b"\x00\x00\x00\x00\x00\xff\xff" + b"".join(b"\x01" + offsets[n].to_bytes(4, "big") + b"\x00\x00" for n in range(1, xref_no + 1))
    out += (b"%d 0 obj\n<< /Type /XRef /Size %d /W [1 4 2] /Root 1 0 R /Length %d >>\nstream\n" % (xref_no, xref_no + 1, len(rows))
            + rows + b"\nendstream\nendobj\nstartxref\n%d\n%%%%EOF\n" % offsets[xref_no])
    return bytes(out)


class CutTests(unittest.TestCase):
    def test_a_pdf_with_a_cross_reference_stream_is_cut_too(self):
        data = xref_stream_pdf()
        try:
            import pypdfium2
            self.assertEqual(len(pypdfium2.PdfDocument(data)), 3)
            self.assertEqual(len(pypdfium2.PdfDocument(cut.cut_pdf(data, [2, 3]))), 2)
        except ImportError:
            pass
        self.assertEqual(len(pdfread.Document(cut.cut_pdf(data, [2, 3])).pages), 2)

    def test_page_ranges(self):
        self.assertEqual(cut.parse_pages("5-7, 9", 10), [5, 6, 7, 9])
        for bad in ("", "0-3", "4-11", "x"):
            with self.assertRaises(ValueError):
                cut.parse_pages(bad, 10)

    def test_a_cut_pdf_shows_only_the_kept_pages_in_every_reader(self):
        data = ten_pages()
        if data is None:
            self.skipTest("reportlab makes the test PDF")
        out = cut.cut_pdf(data, [5, 6, 7, 8, 9, 10])
        doc = pdfread.Document(out)
        self.assertEqual(len(doc.pages), 6)
        self.assertIn("Seite 5 des", doc.page_text(doc.pages[0]))
        try:
            import pypdf
            self.assertEqual(len(pypdf.PdfReader(io.BytesIO(out)).pages), 6)
        except ImportError:
            pass
        try:
            import pypdfium2
            self.assertEqual(len(pypdfium2.PdfDocument(out)), 6)
        except ImportError:
            pass

    def test_the_read_text_and_documents_of_the_kept_pages_carry_over(self):
        extraction = {"text": "\n\n".join(f"[page {n}]\ntext {n}" for n in range(1, 11)), "pages": 10,
                      "pages_transcribed": [2, 6], "pages_without_text": [3, 9], "unread_reasons": {"3": "x", "9": "y"},
                      "page_images": {"6": "blob6", "2": "blob2"},
                      "segments": [{"first_page": 1, "last_page": 4}, {"first_page": 5, "last_page": 6}, {"first_page": 7, "last_page": 10}]}
        out = cut.cut_extraction(extraction, [5, 6, 7, 8, 9, 10])
        self.assertTrue(out["text"].startswith("[page 5]\ntext 5") and "text 4" not in out["text"])
        self.assertEqual((out["pages_transcribed"], out["pages_without_text"], out["unread_reasons"], out["page_images"]),
                         ([6], [9], {"9": "y"}, {"6": "blob6"}))
        self.assertEqual(out["segments"], [{"first_page": 5, "last_page": 6}, {"first_page": 7, "last_page": 10}])
        self.assertEqual(out["kept_pages"], [5, 6, 7, 8, 9, 10])


if __name__ == "__main__":
    unittest.main()


def pages_with_a_heavy_first_page(pages=3):
    """Each page shows 'Seite n'; page 1 also carries a 200 kB image, as a scanned page does."""
    heavy = b"0" * 200_000
    objects = {1: b"<< /Type /Catalog /Pages 2 0 R >>",
               2: b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % (10 + i) for i in range(pages)) + b"] /Count %d /MediaBox [0 0 595 842] >>" % pages,
               3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               4: b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /BitsPerComponent 8 /ColorSpace /DeviceGray /Length %d >>\nstream\n" % len(heavy) + heavy + b"\nendstream"}
    for i in range(pages):
        text = b"BT /F1 12 Tf 72 720 Td (Seite %d) Tj ET" % (i + 1)
        objects[20 + i] = b"<< /Length %d >>\nstream\n" % len(text) + text + b"\nendstream"
        xobject = b" /XObject << /Im1 4 0 R >>" if i == 0 else b""
        objects[10 + i] = b"<< /Type /Page /Parent 2 0 R /Contents %d 0 R /Resources << /Font << /F1 3 0 R >>%s >> >>" % (20 + i, xobject)
    out, offsets = bytearray(b"%PDF-1.4\n"), {}
    for n, body in sorted(objects.items()):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
    xref, size = len(out), max(objects) + 1
    out += b"xref\n0 %d\n0000000000 65535 f \n" % size + b"".join(
        (b"%010d 00000 n \n" % offsets[n]) if n in offsets else b"0000000000 65535 f \n" for n in range(1, size))
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (size, xref)
    return bytes(out)


class ExtractTests(unittest.TestCase):
    def test_an_extract_holds_only_the_chosen_pages_and_what_they_use(self):
        data = pages_with_a_heavy_first_page()
        out = cut.extract_pdf(data, [2, 3])
        self.assertLess(len(out), 5_000)  # page 1's image stays behind
        doc = pdfread.Document(out)
        self.assertEqual(len(doc.pages), 2)
        self.assertIn("Seite 2", doc.page_text(doc.pages[0]))
        try:
            import pypdfium2
            self.assertEqual(len(pypdfium2.PdfDocument(out)), 2)
            self.assertIn("Seite 3", pypdfium2.PdfDocument(out)[1].get_textpage().get_text_range())
        except ImportError:
            pass
        self.assertGreater(len(cut.extract_pdf(data, [1])), 200_000)
