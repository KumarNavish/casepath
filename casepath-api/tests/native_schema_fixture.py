"""Pinned, unmodified public contracts for standalone offline tests."""
import hashlib
import os
from pathlib import Path

EXPECTED = {
    'schema.py': '7dd9b8b805e46c134bc3e4f8decf1679f447f46ed34ca8c737b7c9fad5920591',
    'expressions.py': '1f374afc5d916e03e712279a0bdfaf4b75c7c6414a1a31f88f024a82089b5e76',
}


def native_schema_directory():
    bundled = Path(__file__).parent / 'fixtures/native150-schema/contracts'
    directory = Path(os.environ.get('CASEPATH_NATIVE_SCHEMA_DIR', bundled))
    for name, expected in EXPECTED.items():
        path = directory / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise AssertionError('native contract differs from frozen public release: ' + name)
    return directory
