"""Mutation kills required by the source-grounding contract."""
import hashlib
def valid(raw, expected): return hashlib.sha256(raw).hexdigest() == expected
def mutation_kills(raw, expected):
    assert valid(raw, expected)
    assert not valid(raw + b' stale', expected)
    assert not valid(b'fabricated', expected)
    assert not valid(raw[::-1], expected)
    return True
