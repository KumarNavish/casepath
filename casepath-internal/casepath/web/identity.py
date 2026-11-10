"""Who is calling, from the header the platform gateway sets after it has authenticated the employee.

``plain``: the header holds the user's id. ``jwt``: it holds a token the gateway has already verified (optionally after
``Bearer``); the user id and roles are read from configurable claims, dotted for nested claims such as
``realm_access.roles``. The service must be reachable only through that gateway, since it does not verify the
signature itself. A required role (for example the line of business's access role) is refused with 403 when absent.
"""
import base64
from dataclasses import dataclass
import json


class IdentityError(ValueError):
    pass


@dataclass(frozen=True)
class Identity:
    user: str
    roles: tuple = ()


def _claim(claims, path):
    value = claims
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def from_header(value, *, fmt="plain", user_claim="sub", roles_claim="roles"):
    value = (value or "").strip()
    if not value:
        raise IdentityError("no identity")
    if fmt == "plain":
        return Identity(user=value[:200])
    if fmt != "jwt":
        raise IdentityError(f"unknown identity format {fmt!r}")
    token = value.split()[-1]
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError) as error:
        raise IdentityError("the identity token cannot be read") from error
    user = _claim(claims, user_claim)
    if not isinstance(user, str) or not user:
        raise IdentityError(f"the identity token has no {user_claim!r} claim")
    roles = _claim(claims, roles_claim) or ()
    roles = (roles,) if isinstance(roles, str) else tuple(r for r in roles if isinstance(r, str))
    return Identity(user=user[:200], roles=roles)
