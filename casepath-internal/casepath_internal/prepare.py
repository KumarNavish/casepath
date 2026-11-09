"""Prepare case files where the PDF libraries are, so that a runtime without them can still work on the case.

A prepared case is a folder (``casepath.prepared-case/1``): ``case.json`` names the case and lists its files with
the extraction already made (text, pages, pages without a text layer), each original file as it was, and a PNG image
of every page that has no text layer, so the model can read those pages later. A large photo also gets a smaller copy.
No model is called here: preparing reads and renders only.

    python -m casepath_internal.prepare <file or folder> ... --out <dir> [--image-side 1400]

makes one prepared case per file (named after the file), ready to be placed in a volume's ``incoming/`` folder.
"""
import argparse
import io
import json
import mimetypes
from pathlib import Path
import re

FORMAT = "casepath.prepared-case/1"
SUFFIXES = {".pdf", ".eml", ".msg", ".docx", ".txt", ".png", ".jpg", ".jpeg"}


class PreparedError(ValueError):
    pass


def _safe(name):
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(name).stem).strip("-")[:60] or "file"
    return stem + Path(name).suffix.lower()


def prepare_case(title, files, out_dir, *, intake=None, image_side=1400):
    """``files``: [(name, bytes)]. Writes the prepared case to ``out_dir`` and returns its manifest."""
    from .extract import extract
    from .reading import Renderer

    from .extract import attachments

    out = Path(out_dir)
    (out / "files").mkdir(parents=True, exist_ok=True)
    expanded = []  # an e-mail's attachments follow it as files of their own
    for name, data in files:
        expanded.append((name, data, None))
        expanded += [(inner, payload, name) for inner, payload in attachments(name, mimetypes.guess_type(name)[0], data)]
    rows = []
    for index, (name, data, attached_to) in enumerate(expanded, 1):
        result = extract(name, mimetypes.guess_type(name)[0] or "application/octet-stream", data)
        if attached_to:
            result["attached_to"] = attached_to
        stored = f"files/{index:02d}-{_safe(name)}"
        (out / stored).write_bytes(data)
        row = {"name": name, "file": stored, "media_type": result["media_type"], "kind": result["kind"], "extraction": result, "page_images": {}}
        missing = result.get("pages_without_text") or []
        if result["kind"] == "pdf" and missing:
            (out / "pages").mkdir(exist_ok=True)
            for page, png in Renderer(data, max_side=image_side).pages(missing):
                rel = f"pages/{index:02d}-p{page:04d}.png"
                (out / rel).write_bytes(png)
                row["page_images"][str(page)] = rel
        if result["kind"] == "image":
            from PIL import Image
            image = Image.open(io.BytesIO(data))
            image.thumbnail((1600, 1600))
            small = io.BytesIO()
            image.convert("RGB").save(small, format="JPEG", quality=85)
            rel = f"files/{index:02d}-photo-small.jpg"
            (out / rel).write_bytes(small.getvalue())
            row["photo_image"] = rel
        rows.append(row)
    manifest = {"format": FORMAT, "title": title, "intake": intake or {}, "files": rows}
    (out / "case.json").write_text(json.dumps(manifest, ensure_ascii=False))
    return manifest


def load_prepared(store, read, user, *, title=None, intake=None):
    """Make a case from a prepared folder; ``read(relative path)`` returns a file's bytes. No PDF library is used."""
    manifest = json.loads(read("case.json"))
    if manifest.get("format") != FORMAT:
        raise PreparedError(f"a prepared case needs format {FORMAT}")
    case = store.create_case((title or manifest["title"]).strip()[:300], {**manifest.get("intake", {}), **(intake or {})}, user)
    for row in manifest["files"]:
        extraction = dict(row["extraction"])
        images = {page: store.put_blob(read(rel)) for page, rel in (row.get("page_images") or {}).items()}
        if images:
            extraction["page_images"] = images
        if row.get("photo_image"):
            extraction["photo_image"] = store.put_blob(read(row["photo_image"]))
        store.add_file(case["id"], row["name"], row["media_type"], row["kind"], read(row["file"]), extraction, user)
    return store.get_case(case["id"])


def main(argv=None):
    parser = argparse.ArgumentParser(prog="casepath_internal.prepare")
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--out", required=True)
    parser.add_argument("--image-side", type=int, default=1400)
    args = parser.parse_args(argv)
    paths = []
    for given in map(Path, args.inputs):
        paths += sorted(p for p in given.rglob("*") if p.suffix.lower() in SUFFIXES) if given.is_dir() else [given]
    for path in paths:
        target = Path(args.out) / Path(_safe(path.name)).stem
        manifest = prepare_case(path.stem, [(path.name, path.read_bytes())], target, intake={"source": "prepared"}, image_side=args.image_side)
        row = manifest["files"][0]
        print(json.dumps({"case": target.name, "pages": row["extraction"].get("pages"), "page_images": len(row["page_images"])}))


if __name__ == "__main__":
    main()
