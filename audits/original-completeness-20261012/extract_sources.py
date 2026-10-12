#!/usr/bin/env python3
"""Deterministic source receipts only; never infers facts or legal verdicts.

Run from the repository root. Reads only the original synthetic-150 manifest,
its referenced claim/registry/artifact bytes, and the authorized taxonomy's
literal three-field browsing rows. Registry content is not legal evidence.
"""
import ast
import base64
import hashlib
import json
from collections import Counter
from email import policy
from email.parser import BytesParser
from pathlib import Path

import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
CORPUS = ROOT / "casepath-api/casepath_api/corpora/synthetic-150"
TAXONOMY = ROOT / "casepath-api/casepath_api/autonomous_taxonomy_v1.py"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def checked(ref):
    data = (CORPUS / ref["path"]).read_bytes()
    assert len(data) == ref["size_bytes"], ref["path"]
    assert sha(data) == ref["sha256"], ref["path"]
    return data


def taxonomy_rows():
    for node in ast.parse(TAXONOMY.read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_ROWS" for t in node.targets
        ):
            return {r[0]: {"domain": r[1], "family_id": r[2]} for r in ast.literal_eval(node.value)}
    raise AssertionError("No authorized taxonomy rows")


def main():
    manifest_bytes = (CORPUS / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    rows = taxonomy_rows()
    records = []
    unique_files = {}
    for ref in [manifest["license"], *manifest["static_template"]["files"]]:
        checked(ref)
        unique_files[ref["path"]] = {k: ref[k] for k in ("path", "sha256", "size_bytes")}
    for number, binding in enumerate(manifest["claims"], 1):
        cid = binding["claim_id"]
        claim_bytes = checked(binding["claim"])
        checked(binding["source_registry"])
        claim = json.loads(claim_bytes)
        raw = claim["customer_message"]["raw_file"]
        artifacts = []
        for ref in binding["source_documents"] + [binding["claim"], binding["source_registry"]]:
            checked(ref)
            unique_files[ref["path"]] = {k: ref[k] for k in ("path", "sha256", "size_bytes")}
        for ref in binding["observable_artifacts"]:
            data = checked(ref)
            original = raw if ref["role"] == "customer_message" else next(
                a for a in claim["attachments"] if a["artifact_id"] == ref["artifact_id"]
            )
            assert base64.b64decode(original["content_base64"], validate=True) == data
            a = dict(ref)
            a["received"] = True
            if ref["role"] == "customer_message":
                if ref["media_type"] == "message/rfc822":
                    message = BytesParser(policy=policy.default).parsebytes(data)
                    body_part = message.get_body(preferencelist=("plain",)) if message.is_multipart() else message
                    assert body_part is not None and body_part.get_content_type() == "text/plain"
                    a["decoded_text"] = body_part.get_content().replace("\r\n", "\n").rstrip()
                    a["decoded_representation"] = "RFC822 transfer-decoded text/plain body; LF-normalized"
                else:
                    a["decoded_text"] = data.decode("utf-8").replace("\r\n", "\n").rstrip()
                    a["decoded_representation"] = "UTF8 original phone/web note including headers; LF-normalized"
                a["decoded_text_sha256"] = sha(a["decoded_text"].encode())
            elif ref["media_type"] == "application/pdf":
                with fitz.open(stream=data, filetype="pdf") as pdf:
                    a["physical_page_count"] = len(pdf)
                    a["pages"] = [
                        {"physical_page": i + 1, "text": p.get_text(sort=True),
                         "text_sha256": sha(p.get_text(sort=True).encode())}
                        for i, p in enumerate(pdf)
                    ]
                a["extraction_method"] = "PyMuPDF visible text, sort=True; physical pages retained"
            elif ref["media_type"] == "image/jpeg":
                with Image.open(CORPUS / ref["path"]) as im:
                    a["pixel_size"] = list(im.size)
                    a["format"] = im.format
                a["extraction_method"] = "No machine text extraction; received JPEG requires native visual inspection"
            if ref["role"] == "customer_message" and len(a["decoded_text"]) > 20000:
                a["decoded_text_preview"] = a.pop("decoded_text")[:1500]
                a["preview_limit"] = "1500 characters; full original bytes remain hash-bound at source path"
            artifacts.append(a)
        body = claim["customer_message"]["body"]
        projection = next((ref for ref in binding["source_documents"] if ref["path"].endswith("message-body-projection.txt")), None)
        if projection:
            assert checked(projection).decode().rstrip() == body.rstrip()
        records.append({"number": number, "claim_id": cid, **rows[cid],
                        "subject": binding["subject"], "received_at": binding["received_at"],
                        "canton": claim["submission"]["canton"], "language": binding["language"],
                        "claim_receipt": binding["claim"], "registry_receipt": binding["source_registry"],
                        "binding_sha256": binding["binding_sha256"],
                        "message_body": body, "message_body_pointer": "/customer_message/body",
                        "message_body_sha256": sha(body.encode()), "body_projection_receipt": projection,
                        "artifacts": artifacts})
    assert len(records) == 150 and len({r["claim_id"] for r in records}) == 150
    assert set(rows) == {r["claim_id"] for r in records}
    assert len(unique_files) == manifest["aggregate"]["file_count"]
    assert sum(r["size_bytes"] for r in unique_files.values()) == manifest["aggregate"]["size_bytes"]
    save("source_receipts.json", records)
    save("inventory_receipt.json", {
        "base_commit": "ae0ec12de331898280bd9000fb6548c848ce48b1",
        "manifest_file_sha256": sha(manifest_bytes), "manifest_aggregate": manifest["aggregate"],
        "manifest_identity": {k: manifest[k] for k in ("manifest_sha256", "source_manifest_file_sha256")},
        "taxonomy_file_sha256": sha(TAXONOMY.read_bytes()),
        "claim_count": len(records), "verified_unique_manifest_files": len(unique_files),
        "domain_counts": dict(Counter(r["domain"] for r in records)),
        "artifact_media_counts": dict(Counter(a["media_type"] for r in records for a in r["artifacts"])),
        "verified_files": [unique_files[k] for k in sorted(unique_files)]})
    blocks = []
    for r in records:
        blocks.append(f"\n[{r['number']:03}] {r['claim_id']} | {r['domain']} | {r['family_id']}\n{r['subject']}\nReceived {r['received_at']}; canton {r['canton']}\n")
        for a in r["artifacts"]:
            blocks.append(f"SOURCE {a['artifact_id']} | SHA256 {a['sha256']} | {a['path']}\n")
            if a["role"] == "customer_message":
                blocks.append("NARRATIVE: original intake claim JSON /customer_message/body; hash-bound matching body projection where received\n" + r["message_body"] + "\n")
            for p in a.get("pages", []):
                blocks.append(f"PHYSICAL PAGE {p['physical_page']} OF {a['physical_page_count']}\n" + p["text"] + "\n")
            if a["media_type"] == "image/jpeg":
                blocks.append(f"RECEIVED JPEG {a['pixel_size']}: native view required\n")
    (OUT / "reading_transcript.txt").write_text("\n".join(blocks))
    print(json.dumps({"claims": len(records), "verified_files": len(unique_files),
                      "domains": dict(Counter(r['domain'] for r in records)),
                      "source_receipts_sha256": sha((OUT / 'source_receipts.json').read_bytes())}, indent=2))


if __name__ == "__main__":
    main()
