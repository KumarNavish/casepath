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
