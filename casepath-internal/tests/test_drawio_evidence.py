import base64
import io
import unittest
import urllib.parse
import zipfile
import zlib

from casepath_internal import drawio
from casepath_internal.evidence import Evidence
from casepath_internal.extract import extract

MODEL = """<mxGraphModel><root>
<mxCell id="0"/><mxCell id="1" parent="0"/>
<mxCell id="lane" value="System" style="swimlane;" vertex="1" parent="1"><mxGeometry x="0" y="0" width="800" height="400" as="geometry"/></mxCell>
<mxCell id="start" value="Start" style="ellipse;" vertex="1" parent="lane"><mxGeometry x="10" y="10" as="geometry"/></mxCell>
<mxCell id="ask" value="Ask for &lt;b&gt;photos&lt;/b&gt;" style="rounded=1;html=1;" vertex="1" parent="lane"><mxGeometry x="10" y="60" as="geometry"/></mxCell>
<object id="dec" label="Photos uploaded?"><mxCell style="rhombus;" vertex="1" parent="lane"><mxGeometry x="10" y="120" as="geometry"/></mxCell></object>
<mxCell id="yes" value="Case reported" style="ellipse;" vertex="1" parent="lane"><mxGeometry x="10" y="200" as="geometry"/></mxCell>
<mxCell id="no" value="No damage" style="ellipse;" vertex="1" parent="lane"><mxGeometry x="200" y="200" as="geometry"/></mxCell>
<mxCell id="note" value="Synthetic note" style="text;html=1;" vertex="1" parent="1"><mxGeometry x="400" y="10" as="geometry"/></mxCell>
<mxCell id="e1" style="edgeStyle=orthogonal;" edge="1" parent="1" source="start" target="ask"/>
<mxCell id="e2" edge="1" parent="1" source="ask" target="dec"/>
<mxCell id="e3" value="ja" edge="1" parent="1" source="dec" target="yes"/>
<mxCell id="e4" edge="1" parent="1" source="dec" target="no"/>
<mxCell id="e4l" value="nein" style="edgeLabel;" vertex="1" parent="e4"><mxGeometry as="geometry"/></mxCell>
</root></mxGraphModel>"""


def compressed(xml):
    deflate = zlib.compressobj(9, zlib.DEFLATED, -15)
    packed = deflate.compress(urllib.parse.quote(xml).encode()) + deflate.flush()
    return f'<mxfile><diagram name="Page 1">{base64.b64encode(packed).decode()}</diagram></mxfile>'.encode()


class DrawioTests(unittest.TestCase):
    def convert(self, data):
        rows = drawio.convert(data, source_title="example.drawio", version="2026-01-01")
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_structure_is_traced_to_cells(self):
        workflow = self.convert(f'<mxfile><diagram name="Page 1">{MODEL}</diagram></mxfile>'.encode())
        steps = {s["id"]: s for s in workflow["steps"]}
        self.assertEqual(workflow["start"], "s-start")
        self.assertEqual(steps["s-ask-for-photos"]["role"], "System")
        decision = steps["s-photos-uploaded"]
        self.assertEqual([e["label"] for e in decision["next"]], ["ja", "nein"])
        fact, = workflow["facts"]
        self.assertEqual((fact["question"], fact["values"]), ("Photos uploaded?", ["ja", "nein"]))
        self.assertEqual(decision["source_refs"], ["diagram#Page-1:dec"])
        self.assertEqual({o["title"] for o in workflow["outcomes"]}, {"Case reported", "No damage"})
        self.assertEqual(workflow["documents"], [])
        self.assertIsNone(workflow["applies_when"])
        self.assertIn("Diagram note: Synthetic note", [q["text"] for q in workflow["open_questions"]])

    def test_compressed_pages_decode_identically(self):
        plain = self.convert(f'<mxfile><diagram name="Page 1">{MODEL}</diagram></mxfile>'.encode())
        self.assertEqual(self.convert(compressed(MODEL)), plain)


class EvidenceTests(unittest.TestCase):
    def evidence(self):
        return Evidence([{"id": "f1", "name": "letter.pdf", "kind": "pdf",
                          "text": "[page 1]\nDer Vermieter wurde am 3. März schrift-\nlich informiert.\n\n[page 2]\nKeine Antwort."}])

    def test_quote_survives_line_break_hyphenation(self):
        hit = self.evidence().locate("f1", "Der Vermieter wurde am 3. März schriftlich informiert.")
        self.assertEqual(hit["page"], 1)

    def test_invented_or_tiny_quotes_are_rejected(self):
        evidence = self.evidence()
        self.assertIsNone(evidence.locate("f1", "Der Vermieter wurde nie informiert."))
        self.assertIsNone(evidence.locate("f1", "Keine"))
        self.assertIsNone(evidence.locate("other", "Keine Antwort."))

    def test_search_and_paged_read(self):
        evidence = self.evidence()
        self.assertEqual(evidence.search("Vermieter informiert")[0]["page"], 1)
        part = evidence.read("f1", from_page=2, to_page=2)
        self.assertEqual(part["text"], "[page 2] Keine Antwort.")


class ExtractTests(unittest.TestCase):
    def test_email_word_and_image(self):
        mail = extract("m.eml", "message/rfc822", b"From: a@example.org\r\nSubject: Schimmel\r\n\r\nBitte pruefen.\r\n")
        self.assertEqual(mail["kind"], "email")
        self.assertIn("Subject: Schimmel", mail["text"])
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                             '<w:body><w:p><w:r><w:t>Mietvertrag</w:t></w:r></w:p></w:body></w:document>')
        word = extract("v.docx", None, buffer.getvalue())
        self.assertEqual((word["kind"], word["text"]), ("word", "Mietvertrag"))
        image = extract("p.jpg", "image/jpeg", b"\xff\xd8\xff\xe0rest")
        self.assertEqual((image["kind"], image["readable"]), ("image", False))

    def test_damaged_pdf_is_reported_not_guessed(self):
        result = extract("x.pdf", "application/pdf", b"%PDF-1.7 broken")
        self.assertFalse(result["readable"])
        self.assertIn("could not be read", result["note"])


if __name__ == "__main__":
    unittest.main()
