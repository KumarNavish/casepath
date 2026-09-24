"""Small, auditable Boolean expression language for benchmark predicates."""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from typing import Any


class ExpressionError(ValueError):
    """Raised when a predicate is unsafe, malformed, or cannot be evaluated."""


_LITERAL_REPLACEMENTS = {
    "true": "True",
    "false": "False",
    "null": "None",
}


def _normalise(expression: str) -> str:
    value = expression.strip()
    if not value:
        raise ExpressionError("predicate must not be empty")
    for source, target in _LITERAL_REPLACEMENTS.items():
        value = re.sub(rf"\b{source}\b", target, value, flags=re.IGNORECASE)
    return value


def parse_expression(expression: str) -> ast.Expression:
    """Parse and validate the expression without executing user code."""

    try:
        tree = ast.parse(_normalise(expression), mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"invalid predicate syntax: {exc.msg}") from exc
    _validate_node(tree)
    return tree


def evaluate_expression(expression: str, assignment: Mapping[str, Any]) -> bool:
    """Evaluate a validated expression against an explicit variable assignment."""

    return bool(_evaluate(parse_expression(expression).body, assignment))


def referenced_names(expression: str) -> frozenset[str]:
    """Return the variables referenced by an expression."""

    tree = parse_expression(expression)
    return frozenset(
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id not in {"True", "False", "None"}
    )


def _validate_node(node: ast.AST) -> None:
    allowed = (
        ast.Expression,
        ast.BoolOp,
        ast.UnaryOp,
        ast.Compare,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.List,
        ast.Tuple,
        ast.And,
        ast.Or,
        ast.Not,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.In,
        ast.NotIn,
        ast.Is,
        ast.IsNot,
    )
    if not isinstance(node, allowed):
        raise ExpressionError(f"unsupported predicate operation: {type(node).__name__}")
    for child in ast.iter_child_nodes(node):
        _validate_node(child)


def _evaluate(node: ast.AST, assignment: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in assignment:
            raise ExpressionError(f"missing predicate variable: {node.id}")
        return assignment[node.id]
    if isinstance(node, ast.List):
        return [_evaluate(item, assignment) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_evaluate(item, assignment) for item in node.elts)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not bool(_evaluate(node.operand, assignment))
    if isinstance(node, ast.BoolOp):
        values = (_evaluate(value, assignment) for value in node.values)
        return (
            all(bool(value) for value in values)
            if isinstance(node.op, ast.And)
            else any(bool(value) for value in values)
        )
    if isinstance(node, ast.Compare):
        left = _evaluate(node.left, assignment)
        for operator, comparator in zip(node.ops, node.comparators, strict=True):
            right = _evaluate(comparator, assignment)
            if not _compare(operator, left, right):
                return False
            left = right
        return True
    raise ExpressionError(f"unsupported predicate operation: {type(node).__name__}")


def _compare(operator: ast.cmpop, left: Any, right: Any) -> bool:
    try:
        if isinstance(operator, ast.Eq):
            return bool(left == right)
        if isinstance(operator, ast.NotEq):
            return bool(left != right)
        if isinstance(operator, ast.Lt):
            return bool(left < right)
        if isinstance(operator, ast.LtE):
            return bool(left <= right)
        if isinstance(operator, ast.Gt):
            return bool(left > right)
        if isinstance(operator, ast.GtE):
            return bool(left >= right)
        if isinstance(operator, ast.In):
            return bool(left in right)
        if isinstance(operator, ast.NotIn):
            return bool(left not in right)
        if isinstance(operator, ast.Is):
            return left is right
        if isinstance(operator, ast.IsNot):
            return left is not right
    except (TypeError, ValueError) as exc:
        raise ExpressionError(f"invalid comparison: {exc}") from exc
    raise ExpressionError(f"unsupported comparator: {type(operator).__name__}")
