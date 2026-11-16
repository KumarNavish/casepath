"""The way out of an approved letter, without assuming any program it goes out with: who it goes to and under which
subject, shown beside the letter and recorded with its approval.

Nothing is sent from here and nothing is guessed. An address is proposed only where the case's own files hold a mail
header whose sender is the recipient by name (the latest such mail), and it is shown with that line; the handler may
overwrite it («handover.address», attributed). The letter itself leaves as the approved text (formatted on the
clipboard, or the Versandpaket's own documents).
"""
import re

ADDRESS = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
SENDER = re.compile(r"^(?:From|Von|Absender|De|Da|Expéditeur|Mittente)\s*:\s*(.+)$", re.I)
SUBJECT = re.compile(r"^(?:Subject|Betreff|Objet|Oggetto)\s*:\s*(.+)$", re.I)
DATED = re.compile(r"^(?:Date|Datum|Gesendet|Sent|Envoyé|Inviato)\s*:\s*(.+)$", re.I)
TITLES = {"herr", "frau", "herrn", "dr", "prof", "lic", "iur", "med", "ra", "mme", "m", "sig", "sig.ra", "ag", "gmbh", "sa", "co", "und", "the"}
REPLY = re.compile(r"^\s*(?:(?:AW|RE|WG|FW|FWD|TR|R|I)\s*:\s*)+", re.I)


def mail_headers(files):
    """Each mail header block in the case's files, in the files' order: [{file, name, line, display, address, subject,
    date, order}]. A block is a sender line («From:», «Von:») holding an address, with the subject and date lines that
    follow within the next lines; a forwarded thread in one file gives one block per sender line."""
    out = []
    for order, f in enumerate(files or ()):
        lines = str((f.get("extraction") or {}).get("text") or "").split("\n")
        for i, raw in enumerate(lines):
            m = SENDER.match(raw.strip())
            found = ADDRESS.search(m.group(1)) if m else None
            if not found:
                continue
            block = {"file": f.get("id"), "name": f.get("name"), "line": raw.strip()[:200], "address": found.group(0),
                     "display": re.sub(r"[<>\"'()\[\]]", " ", m.group(1).replace(found.group(0), " ")).strip(), "subject": None, "date": None,
                     "order": (order, i)}
            for later in lines[i + 1:i + 8]:
                later = later.strip()
                if SENDER.match(later):
                    break
                s, d = SUBJECT.match(later), DATED.match(later)
                if s and not block["subject"]:
                    block["subject"] = s.group(1).strip()[:200]
                if d and not block["date"]:
                    block["date"] = d.group(1).strip()[:80]
            out.append(block)
    return out


def _words(name):
    return [w for w in re.findall(r"[a-zà-öø-ÿ]{2,}", str(name or "").lower()) if w not in TITLES]


def _is(name, block):
    """Whether a mail's sender is the party named ``name``: its surname (the name's last word) stands in the display
    name or in the address before the @, as a word. An organisation: every word of its name."""
    words = _words(name)
    if not words:
        return False
    hay = set(_words(block["display"])) | set(_words(block["address"].split("@", 1)[0].replace(".", " ").replace("_", " ").replace("-", " ")))
    return words[-1] in hay if len(words) <= 3 else all(w in hay for w in words)


def proposed(name, blocks):
    """The address the case's files hold for the party named ``name`` (``blocks``: mail_headers of its files): {address,
    file, name (the file's), line, subject} from the latest mail it sent, or None. Never an address of another sender,
    never one from running text."""
    own = [b for b in blocks or () if _is(name, b)]
    if not own:
        return None
    b = own[-1]
    return {"address": b["address"], "file": b["file"], "name": b["name"], "line": b["line"], "subject": b["subject"]}


def overrides(events):
    """The addresses the handler set, by recipient: the latest «handover.address» of each ({address, by, at}); an empty
    one takes the proposal away."""
    out = {}
    for e in events or ():
        if e.get("kind") == "handover.address" and e.get("to"):
            out[e["to"]] = {"address": str(e.get("address") or "").strip(), "by": e.get("expert"), "at": e.get("at")}
    return out


def valid_address(value):
    value = str(value or "").strip()
    return bool(ADDRESS.fullmatch(value)) and len(value) <= 254


def subject(reference, letter_title, replied=None, pattern=None):
    """The mail's subject: the claim number first where the case has one, then «AW: <the subject of the party's latest
    mail>», else the letter's title. ``pattern``: the deployment's own («{referenz}», «{betreff}»)."""
    core = f"AW: {REPLY.sub('', replied).strip()}" if replied and REPLY.sub("", replied).strip() else str(letter_title or "Schreiben")
    if reference and reference in core:
        return core[:240]
    text = (pattern or "{referenz} {betreff}").replace("{referenz}", reference or "").replace("{betreff}", core)
    return re.sub(r"\s+", " ", text).strip(" :–-")[:240]


def rows(approval, blocks, events, reference=None, pattern=None, party_name=None):
    """What the handler carries out, per recipient of an approved version (or of the letter prepared, before it):
    [{to, title, recipient, forms, address {value, source {file, name, line} | None, set_by}, subject}]. ``blocks``:
    mail_headers of the case's files; ``party_name``: role → the name the file states."""
    set_by_hand = overrides(events)
    out = []
    for r in approval.get("recipients") or ():
        name = party_name(r.get("to")) if party_name else None
        found = proposed(name, blocks) if name else None
        own = set_by_hand.get(r.get("to"))
        frozen = r.get("address")  # the address the version was approved with
        value = own["address"] if own else frozen if frozen is not None else (found or {}).get("address") or ""
        source = {k: found[k] for k in ("file", "name", "line")} if found and value == found["address"] else None
        first = (r.get("forms") or [approval.get("form")])[0]
        title = approval.get("title") if first == approval.get("form") else (r.get("titles") or {}).get(first) or first
        out.append({"to": r.get("to"), "title": r.get("title"), "recipient": r.get("recipient"), "forms": r.get("forms") or [],
                    "address": {"value": value, "source": source, "set_by": (own or {}).get("by") if own else None},
                    "subject": subject(reference, title, (found or {}).get("subject"), pattern)})
    return out
