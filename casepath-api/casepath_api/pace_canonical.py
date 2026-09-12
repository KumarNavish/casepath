from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any


PACE_MAX_SAFE_INTEGER = 9_007_199_254_740_991


class PACECanonicalError(ValueError):
    pass


def _require_nfc(value: str) -> None:
    if unicodedata.normalize("NFC", value) != value:
        raise PACECanonicalError("PACE strings and object keys must be NFC")


def validate_pace_value_v1(value: Any, *, path: str = "$") -> None:
    if value is None or isinstance(value, bool):
        return
    if type(value) is int:
        if not -PACE_MAX_SAFE_INTEGER <= value <= PACE_MAX_SAFE_INTEGER:
            raise PACECanonicalError(f"integer at {path} exceeds the PACE bound")
        return
    if isinstance(value, str):
        _require_nfc(value)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise PACECanonicalError(f"object key at {path} is not a string")
            _require_nfc(key)
            validate_pace_value_v1(item, path=f"{path}/{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            validate_pace_value_v1(item, path=f"{path}/{index}")
        return
    raise PACECanonicalError(
        f"unsupported PACE canonical value at {path}: {type(value).__name__}"
    )


def canonical_pace_json_bytes_v1(value: Any) -> bytes:
    validate_pace_value_v1(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def pace_digest_v1(value: Any) -> str:
    return hashlib.sha256(canonical_pace_json_bytes_v1(value)).hexdigest()


def parse_canonical_pace_json_v1(raw: bytes) -> Any:
    def closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PACECanonicalError("duplicate JSON object key")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=closed_object,
            parse_float=lambda _value: (_ for _ in ()).throw(
                PACECanonicalError("PACE JSON forbids floating-point values")
            ),
            parse_constant=lambda _value: (_ for _ in ()).throw(
                PACECanonicalError("PACE JSON forbids non-finite values")
            ),
        )
    except UnicodeDecodeError as exc:
        raise PACECanonicalError("PACE JSON must be UTF-8") from exc
    validate_pace_value_v1(value)
    if canonical_pace_json_bytes_v1(value) != raw:
        raise PACECanonicalError("PACE JSON bytes are not canonical")
    return value
