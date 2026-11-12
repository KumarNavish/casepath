"""Closed JSON-schema subset shared by Azure structured output and local validation.

Azure strict mode and CasePath both require every object to list all of its
properties as required and to forbid extra properties. Results are validated
again locally, so a deployment that ignores strict mode cannot widen them.
"""
from decimal import Decimal
import json
import re

TYPES = {"object", "array", "string", "boolean", "integer", "number", "null"}
KEYWORDS = {"type", "properties", "required", "additionalProperties", "items", "minItems", "maxItems",
            "minLength", "maxLength", "pattern", "minimum", "maximum", "enum", "const", "description", "title"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _types(schema):
    types = schema.get("type")
    return types if isinstance(types, list) else [types]


def validate_schema(schema, depth=0):
    if not isinstance(schema, dict) or depth > 12 or set(schema) - KEYWORDS:
        raise ValueError("unsupported schema keyword or depth")
    types = _types(schema)
    if not types or len(set(types)) != len(types) or any(t not in TYPES for t in types):
        raise ValueError("invalid schema type")
    if len(types) > 1 and (len(types) > 2 or "null" not in types):
        raise ValueError("only nullable type unions are supported")
    if "object" in types:
        props, required = schema.get("properties"), schema.get("required")
        if (not isinstance(props, dict) or not isinstance(required, list) or set(required) != set(props)
                or len(required) != len(props) or schema.get("additionalProperties") is not False):
            raise ValueError("objects must require all of their closed properties")
        for child in props.values():
            validate_schema(child, depth + 1)
    elif {"properties", "required", "additionalProperties"} & set(schema):
        raise ValueError("object keywords require an object type")
    if "array" in types:
        validate_schema(schema.get("items"), depth + 1)
    elif {"items", "minItems", "maxItems"} & set(schema):
        raise ValueError("array keywords require an array type")
    if "pattern" in schema:
        re.compile(schema["pattern"])
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise ValueError("enum must be a non-empty list")
    canonical(schema)


def validate_result(value, schema, path="$"):
    types = _types(schema)
    matches = {"null": value is None, "object": isinstance(value, dict), "array": isinstance(value, list),
               "string": isinstance(value, str), "boolean": type(value) is bool, "integer": type(value) is int,
               "number": type(value) in (int, float)}
    if not any(matches[t] for t in types):
        raise ValueError(f"{path}: type differs from schema")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: value outside enum")
    if "const" in schema and value != schema["const"]:
        raise ValueError(f"{path}: value differs from constant")
    if value is None:
        return
    if isinstance(value, dict):
        if set(value) != set(schema["properties"]):
            raise ValueError(f"{path}: properties differ from closed schema")
        for key, child in value.items():
            validate_result(child, schema["properties"][key], f"{path}.{key}")
    elif isinstance(value, list):
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 10_000):
            raise ValueError(f"{path}: array length outside bounds")
        for index, child in enumerate(value):
            validate_result(child, schema["items"], f"{path}[{index}]")
    elif isinstance(value, str):
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", 1_000_000):
            raise ValueError(f"{path}: text length outside bounds")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            raise ValueError(f"{path}: text does not match pattern")
    elif type(value) in (int, float):
        if not Decimal(str(value)).is_finite():
            raise ValueError(f"{path}: number is not finite")
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            raise ValueError(f"{path}: number outside bounds")


def obj(**properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def arr(items, **bounds):
    return {"type": "array", "items": items, **bounds}


def text(max_length=2000, **extra):
    return {"type": "string", "maxLength": max_length, **extra}


def choice(values):
    return {"type": "string", "enum": list(values)}


def fit_to_schema(value, schema, path="$", changes=None):
    """A report as the schema allows it: extra keys dropped, missing keys empty, texts and lists cut to their limits.

    Used for an agent's final report only, where a rejected report costs a whole rewritten turn; enums, patterns and
    types are still checked by validate_result afterwards.
    """
    changes = [] if changes is None else changes  # every change made: (path, what, original, kept); nothing is cut silently
    types = _types(schema)
    if isinstance(value, dict) and "object" in types:
        props = schema.get("properties", {})
        changes += [(f"{path}.{k}", "dropped", 1, 0) for k in value if k not in props]
        changes += [(f"{path}.{k}", "filled", 0, 0) for k in props if k not in value]
        return {k: fit_to_schema(value.get(k, _empty(props[k])), props[k], f"{path}.{k}", changes) for k in props}
    if isinstance(value, list) and "array" in types:
        keep = schema.get("maxItems", len(value))
        if len(value) > keep:
            changes.append((path, "items cut", len(value), keep))
        return [fit_to_schema(v, schema["items"], f"{path}[{i}]", changes) for i, v in enumerate(value[:keep])]
    if isinstance(value, str) and "string" in types and len(value) > schema.get("maxLength", len(value)):
        changes.append((path, "text cut", len(value), schema["maxLength"]))
        return value[:schema["maxLength"]]
    return value


def _empty(schema):
    types = _types(schema)
    if "null" in types:
        return None
    return {"string": "", "array": [], "object": {}, "boolean": False, "integer": 0, "number": 0}.get(types[0])
