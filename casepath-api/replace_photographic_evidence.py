#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageOps, ImageStat


SOURCE_DATE_EPOCH = int(os.environ.get("SOURCE_DATE_EPOCH", "1786406400"))
SOURCES = (
    {
        "source": "casepath-api/source-assets/flagship-bedroom-corner.png",
        "source_sha256": "70645bf156c85d3d6f8117aaa94fe359f3e685c5576173bc0037dd3452dfd65e",
        "output": "casepath-api/artifacts/bedroom-corner-2026-07-27.jpg",
        "role": "flagship bedroom corner",
    },
    {
        "source": "casepath-api/source-assets/later-window-condensation.png",
        "source_sha256": "ab2e71da9706f8dcf54a65fae5d6dbab65f4790c708b0f05996b75e80a0fbff8",
        "output": "casepath-api/artifacts/window-corner-2026-08-08.jpg",
        "role": "later window condensation",
    },
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def set_epoch(path: Path) -> None:
    os.utime(path, (SOURCE_DATE_EPOCH, SOURCE_DATE_EPOCH))


def prepare_jpeg(source: Path, destination: Path) -> tuple[list[int], str]:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        if image.width < 800 or image.height < 500:
            raise RuntimeError(f"Source image is too small: {source} ({image.size})")
        if sum(ImageStat.Stat(image).stddev) < 25:
            raise RuntimeError(f"Source image has insufficient visual variation: {source}")

        clean = Image.new("RGB", image.size)
        clean.paste(image)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".tmp.jpg")
        clean.save(
            temporary,
            format="JPEG",
            quality=92,
            subsampling=0,
            optimize=False,
            progressive=False,
            dpi=(72, 72),
        )
        os.replace(temporary, destination)

    with Image.open(destination) as result:
        if result.format != "JPEG":
            raise RuntimeError(f"Runtime image is not JPEG: {destination}")
        if result.getexif():
            raise RuntimeError(f"EXIF metadata was not stripped: {destination}")
        forbidden = {"comment", "exif", "icc_profile", "photoshop"}.intersection(result.info)
        if forbidden:
            raise RuntimeError(f"Metadata was not stripped from {destination}: {sorted(forbidden)}")
        dimensions = [result.width, result.height]

    set_epoch(destination)
    return dimensions, sha256_file(destination)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: replace_photographic_evidence.py <repository-or-runtime-root>")

    repository = Path(sys.argv[1]).resolve()
    records: list[dict[str, object]] = []
    runtime_hashes: set[str] = set()
    for specification in SOURCES:
        source = repository / specification["source"]
        destination = repository / specification["output"]
        if not source.is_file():
            raise RuntimeError(f"Missing project source image: {source}")
        source_sha = sha256_file(source)
        if source_sha != specification["source_sha256"]:
            raise RuntimeError(
                f"Source image hash mismatch for {source}: "
                f"expected {specification['source_sha256']}, got {source_sha}"
            )
        dimensions, runtime_sha = prepare_jpeg(source, destination)
        if runtime_sha in runtime_hashes:
            raise RuntimeError("Runtime evidence images are byte-identical")
        runtime_hashes.add(runtime_sha)
        records.append(
            {
                "dimensions": dimensions,
                "output": specification["output"],
                "output_sha256": runtime_sha,
                "role": specification["role"],
                "source": specification["source"],
                "source_sha256": source_sha,
                "transformation": "RGB JPEG quality 92, 4:4:4 subsampling, metadata removed",
            }
        )

    provenance_path = repository / "casepath-api" / "artifacts" / "IMAGE_PROVENANCE.json"
    provenance_path.write_text(
        json.dumps(
            {
                "contract": "casepath.image-provenance/1.0.0",
                "model_visible": False,
                "records": records,
                "source_date_epoch": SOURCE_DATE_EPOCH,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    set_epoch(provenance_path)
    set_epoch(provenance_path.parent)
    print(json.dumps({"images": records, "status": "prepared"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
