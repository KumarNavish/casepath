"""Explicit applicability semantics; ordinary three-valued Boolean DAG evaluation.

Action prerequisites and display parents NEVER gate evidence acquisition.
This module consumes a source-compiled representation; it does not generate one.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence
import re

CONTRACT = "casepath.obligation-control/1.0.0"
MAX_NODES = 256
MAX_EXPRESSION_NODES = 256
MAX_EXPRESSION_DEPTH = 24
MAX_EXPANDED_EXPRESSION_CHARS = 65536


class Invalid(ValueError):
    """Invalid or unsupported input, never an empty successful plan."""


class Truth(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unresolved"


def truth(value: Any) -> Truth:
    if value is True:
        return Truth.TRUE
    if value is False:
        return Truth.FALSE
    if value is None:
        return Truth.UNKNOWN
    raise Invalid("truth values must be JSON boolean or null; no coercion")


def all3(values: Sequence[Truth]) -> Truth:
    if Truth.FALSE in values:
        return Truth.FALSE
    return Truth.UNKNOWN if Truth.UNKNOWN in values else Truth.TRUE


def any3(values: Sequence[Truth]) -> Truth:
    if Truth.TRUE in values:
        return Truth.TRUE
    return Truth.UNKNOWN if Truth.UNKNOWN in values else Truth.FALSE


def fields(value: Any, required: set[str], optional: set[str] = frozenset()) -> dict:
    if not isinstance(value, dict) or set(value) - required - optional or required - set(value):
        raise Invalid(f"expected fields {sorted(required)}; optional {sorted(optional)}")
    return value


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]{0,127}", value):
        raise Invalid("invalid identifier")
    return value


def ids(value: Any, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 512 or (nonempty and not value):
        raise Invalid("expected an identifier list")
    result = tuple(identifier(x) for x in value)
    if len(set(result)) != len(result):
        raise Invalid("duplicate identifiers")
    return result


def support(value: Any, registry: set[str]) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x or len(x) > 1024 for x in value):
        raise Invalid("invalid source reference list")
    refs = tuple(value)
    if len(set(refs)) != len(refs) or not set(refs) <= registry:
        raise Invalid("unresolved source references")
    return refs


@dataclass(frozen=True)
class Expr:
    op: str
    value: str | bool | None = None
    args: tuple[Expr, ...] = ()

    @classmethod
    def parse(cls, obj: Any, variables: set[str], depth: int = 0, counter: list[int] | None = None) -> Expr:
        counter = [0] if counter is None else counter
        counter[0] += 1
        if depth > MAX_EXPRESSION_DEPTH or counter[0] > MAX_EXPRESSION_NODES:
            raise Invalid("expression resource bound")
        if not isinstance(obj, dict) or len(obj) != 1:
            raise Invalid("expression must have exactly one operator")
        op, value = next(iter(obj.items()))
        if op == "const" and type(value) is bool:
            return cls(op, value)
        if op == "var":
            if not isinstance(value, str) or value not in variables:
                raise Invalid("unknown expression variable")
            return cls(op, value)
        if op == "not":
            return cls(op, args=(cls.parse(value, variables, depth + 1, counter),))
        if op in {"all", "any"} and isinstance(value, list) and value:
            return cls(op, args=tuple(cls.parse(v, variables, depth + 1, counter) for v in value))
        raise Invalid("unsupported expression; empty conjunctions/disjunctions are explicit constants")

    def evaluate(self, values: Mapping[str, Truth]) -> Truth:
        if self.op == "const":
            return truth(self.value)
        if self.op == "var":
            return values.get(str(self.value), Truth.UNKNOWN)
        if self.op == "not":
            value = self.args[0].evaluate(values)
            return {Truth.TRUE: Truth.FALSE, Truth.FALSE: Truth.TRUE, Truth.UNKNOWN: Truth.UNKNOWN}[value]
        vals = tuple(x.evaluate(values) for x in self.args)
        return all3(vals) if self.op == "all" else any3(vals)

    def native(self) -> str:
        if self.op == "const":
            return "true" if self.value else "false"
        if self.op == "var":
            return str(self.value)
        if self.op == "not":
            out = f"not ({self.args[0].native()})"
        else:
            joiner = " and " if self.op == "all" else " or "
            out = "(" + joiner.join(x.native() for x in self.args) + ")"
        if len(out) > MAX_EXPANDED_EXPRESSION_CHARS:
            raise Invalid("native expression expansion exceeds bound")
        return out


TRUE = Expr("const", True)


def conjunction(*values: Expr) -> Expr:
    return values[0] if len(values) == 1 else Expr("all", args=tuple(values))


@dataclass(frozen=True)
class Scope:
    scope_id: str
    when: Expr
    parents: tuple[str, ...]
    join: str
    source_refs: tuple[str, ...]
    display_parent: str | None = None


@dataclass(frozen=True)
class Obligation:
    obligation_id: str
    scope_id: str
    when: Expr
    acquire_when: Expr
    capability_ids: tuple[str, ...]
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class Action:
    action_id: str
    scope_id: str
    prerequisites: Expr
    obligation_ids: tuple[str, ...]
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class Graph:
    variables: tuple[str, ...]
    scopes: tuple[Scope, ...]
    obligations: tuple[Obligation, ...]
    actions: tuple[Action, ...]

    @classmethod
    def parse(cls, obj: dict, registry: set[str]) -> Graph:
        fields(obj, {"contract", "variables", "scopes", "obligations", "actions"})
        if obj["contract"] != CONTRACT:
            raise Invalid("control contract mismatch")
        variables = ids(obj["variables"])
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", v) or v.lower() in {"true", "false", "null", "and", "or", "not"} for v in variables):
            raise Invalid("variables must be native Boolean identifiers")
        for name in ("scopes", "obligations", "actions"):
            if not isinstance(obj[name], list) or len(obj[name]) > MAX_NODES:
                raise Invalid("graph family is not a bounded list")
        varset = set(variables)
        scopes = []
        for row in obj["scopes"]:
            fields(row, {"scope_id", "when", "parents", "join", "source_refs"}, {"display_parent"})
            parents = ids(row["parents"])
            if row["join"] not in {"all", "any"} or (not parents and row["join"] != "all"):
                raise Invalid("root scopes require join=all; other joins are all/any")
            scopes.append(Scope(identifier(row["scope_id"]), Expr.parse(row["when"], varset), parents,
                                row["join"], support(row["source_refs"], registry), row.get("display_parent")))
        obligations = []
        for row in obj["obligations"]:
            fields(row, {"obligation_id", "scope_id", "when", "acquire_when", "capability_ids", "source_refs"})
            obligations.append(Obligation(identifier(row["obligation_id"]), identifier(row["scope_id"]),
                Expr.parse(row["when"], varset), Expr.parse(row["acquire_when"], varset),
                ids(row["capability_ids"], nonempty=True), support(row["source_refs"], registry)))
        actions = []
        for row in obj["actions"]:
            fields(row, {"action_id", "scope_id", "prerequisites", "obligation_ids", "source_refs"})
            actions.append(Action(identifier(row["action_id"]), identifier(row["scope_id"]),
                Expr.parse(row["prerequisites"], varset), ids(row["obligation_ids"]), support(row["source_refs"], registry)))
        all_ids = [s.scope_id for s in scopes] + [o.obligation_id for o in obligations] + [a.action_id for a in actions]
        if len(all_ids) != len(set(all_ids)) or len(all_ids) > MAX_NODES:
            raise Invalid("graph ids must be globally unique and bounded")
        scope_ids = {s.scope_id for s in scopes}
        obligation_ids = {o.obligation_id for o in obligations}
        if any(not set(s.parents) <= scope_ids or (s.display_parent is not None and s.display_parent not in scope_ids) for s in scopes):
            raise Invalid("unknown parent scope")
        if any(x.scope_id not in scope_ids for x in [*obligations, *actions]):
            raise Invalid("unknown obligation/action scope")
        if any(not set(a.obligation_ids) <= obligation_ids for a in actions):
            raise Invalid("unknown action obligation")
        # Deterministic topological sort; a cycle never becomes an arbitrary root.
        ordered, done = [], set()
        pending = {s.scope_id: s for s in scopes}
        while pending:
            ready = sorted(k for k, s in pending.items() if set(s.parents) <= done)
            if not ready:
                raise Invalid("cyclic applicability graph")
            for key in ready:
                ordered.append(pending.pop(key)); done.add(key)
        return cls(variables, tuple(ordered), tuple(sorted(obligations, key=lambda o: o.obligation_id)),
                   tuple(sorted(actions, key=lambda a: a.action_id)))

    def values(self, observations: dict) -> dict[str, Truth]:
        if not isinstance(observations, dict) or set(observations) - set(self.variables):
            raise Invalid("observation contains unknown variables")
        return {v: truth(observations.get(v)) for v in self.variables}

    def evaluate(self, observations: dict) -> dict:
        values = self.values(observations)
        states: dict[str, Truth] = {}
        trace = {}
        for s in self.scopes:
            inherited = (all3 if s.join == "all" else any3)(tuple(states[p] for p in s.parents))
            states[s.scope_id] = all3((inherited, s.when.evaluate(values)))
            trace[s.scope_id] = {"parents": list(s.parents), "join": s.join,
                                "source_refs": list(s.source_refs), "state": states[s.scope_id].value}
        obligations = {o.obligation_id: {
            "applicability": all3((states[o.scope_id], o.when.evaluate(values))).value,
            "acquisition": o.acquire_when.evaluate(values).value,
            "scope_id": o.scope_id, "capability_ids": list(o.capability_ids),
            "source_refs": list(o.source_refs),
        } for o in self.obligations}
        return {"contract": CONTRACT, "scopes": trace, "obligations": obligations}

    def evaluate_compiled(self, observations: dict) -> dict:
        """Established comparator: evaluate flattened formulas, not graph traversal."""
        values = self.values(observations)
        expressions = self.expressions()
        scopes = {s.scope_id: {"parents": list(s.parents), "join": s.join,
                  "source_refs": list(s.source_refs),
                  "state": expressions[s.scope_id].evaluate(values).value} for s in self.scopes}
        obligations = {o.obligation_id: {
            "applicability": expressions[o.obligation_id].evaluate(values).value,
            "acquisition": o.acquire_when.evaluate(values).value,
            "scope_id": o.scope_id, "capability_ids": list(o.capability_ids),
            "source_refs": list(o.source_refs),
        } for o in self.obligations}
        return {"contract": CONTRACT, "scopes": scopes, "obligations": obligations}

    def expressions(self) -> dict[str, Expr]:
        """Flatten actual dependency semantics, never the observed case verdicts."""
        out: dict[str, Expr] = {}
        for s in self.scopes:
            inherited = Expr(s.join, args=tuple(out[p] for p in s.parents)) if s.parents else TRUE
            out[s.scope_id] = conjunction(inherited, s.when)
            out[s.scope_id].native()  # Check bounded expansion now.
        for o in self.obligations:
            out[o.obligation_id] = conjunction(out[o.scope_id], o.when)
            out[o.obligation_id].native()
        return out
