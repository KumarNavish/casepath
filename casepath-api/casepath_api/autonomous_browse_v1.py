"""Read-only excerpts of explicit customer requests; never engine facts."""
import re

_REQUEST = re.compile(
    r"(?:specifically asking for|specific request is|meine Bitte|bitte konkret um|request is|"
    r"Mein Anliegen ist|Als Nächstes brauche ich|Jetzt benötige ich|Ich ersuche um)\s*:\s*([^;\n.]+)",
    re.IGNORECASE,
)
_QUOTED_REQUEST = re.compile(r'(?:for the request|für)\s*[“«"]([^”»"]+)[”»"]', re.IGNORECASE)


def customer_request(message):
    """Return a literal span, or None when the message has no explicit request."""
    if not isinstance(message, str):
        return None
    match = _REQUEST.search(message) or _QUOTED_REQUEST.search(message)
    return match.group(1).strip() or None if match else None
