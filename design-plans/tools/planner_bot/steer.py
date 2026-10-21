#!/usr/bin/env python3
"""Planner bot v2: reviews Codex milestone posts on KumarNavish/casepath PR #21 via the Claude API.

Restart-proof and stateless by design: the PR thread itself is the source of truth.
Every comment this bot posts ends with a hidden marker

    <!-- planner-bot re:<comment_id> item:<item> verdict:<APPROVED|CHANGES|ANSWER|HANDOFF|STOP> cost:<usd 4dp> -->

so a trigger comment is "pending" iff it was created after CUTOFF, matches the trigger
regex, and no comment in the thread already carries a marker that answers it. A trigger
counts as handled only once its reply (with marker) is posted. At most one trigger is
reviewed per poll and the thread is refetched before the next, so every review sees the
replies before it. A local state file only caches a spend ledger (v1's spend, dry runs,
replies that failed to post); correctness never depends on it (the container and /tmp can
vanish). Spend is reconstructed from the markers plus that ledger.

Every review sends the three north star concept PNGs (northstar/) first, the last one
carrying cache_control, so system prompt + concepts form the cached prefix.

On a final "READY FOR MAC" post the bot runs an independent gate (gate_check.sh) at the
sealed commit and passes the gate's summary.json to the model; it may only hand off when
BOTH Codex's report is complete AND the independent gate passed. The gate missing or
crashing forces CHANGES, never a handoff.

The key is read from the environment or a key file, never logged, printed, put in argv,
or posted. Model/API errors back off (2, 5, 15 min, 3 attempts max per comment per
process); GitHub errors are logged and retried next poll.
"""
import base64
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = os.environ.get("STEER_REPO", "KumarNavish/casepath")
PR = int(os.environ.get("STEER_PR", "21"))
MODEL = "claude-opus-5-5"
# claude-opus-5-5 list price, USD per MTok. Cache writes cost ~1.25x input.
PRICE_IN, PRICE_OUT, PRICE_CACHE_READ, CACHE_WRITE_MULT = 4.0, 20.0, 0.20, 1.25
BUDGET_USD = float(os.environ.get("STEER_BUDGET_USD", "15"))
POLL_S = 30
MAX_TOKENS = 64000
EFFORT = "max"
# created_at of the newest trigger v1 handled (6316042892, CODEX NS1b READY); later triggers are v2's.
CUTOFF = "2026-10-21T12:35:45Z"
# v1's total spend (last total=$ in its log, dry runs included; its replies carry no markers).
# Seeds the ledger so the cap covers all spending across the handover.
V1_SPEND_SEED = 1.051
CTX_COMMENTS, CTX_CHARS = 10, 1800
NORTHSTAR_DIR = HERE / "northstar"
NORTHSTAR = ("01-decision-building.png", "02-completed-process.png", "03-reviewed-memory-payoff.png")

STATE = HERE / "state.json"
LOG = HERE / "steer.log"
LOG_MAX = 5 * 1024 * 1024
PIDFILE = HERE / "steer.pid"

GATE_CHECK = os.environ.get(
    "GATE_CHECK",
    "/tmp/claude-0/-home-user/e812972b-ebf3-51a0-bcb0-c18d7b98dee7/scratchpad/gate/gate_check.sh",
)
GATE_TIMEOUT_S = 120 * 60

# Trigger: a CODEX ... READY/BLOCKED/QUESTION line, or a READY FOR MAC line.
TRIGGER = re.compile(r"^(CODEX\b[^\n]*\b(?:READY|BLOCKED|QUESTION)\b|READY FOR MAC)")
# Hidden marker the bot stamps on every comment it posts.
MARKER_RE = re.compile(
    r"<!--\s*planner-bot\s+re:(\d+)\s+item:(\S+)\s+verdict:(\w+)\s+cost:([0-9.]+)\s*-->"
)
FOOTER = "\n\n---\n_Planner review, automated through the Claude API on the user's instruction._"

IMG_MAX_BYTES = 4_800_000
IMG_MAX_COUNT = 10
DOC_MAX_COUNT = 3
DOC_MAX_BYTES = 30_000
BACKOFFS_S = [120, 300, 900]
MAX_ATTEMPTS = 3


# --------------------------------------------------------------------------- logging
def log(msg):
    try:
        if LOG.exists() and LOG.stat().st_size > LOG_MAX:
            LOG.replace(LOG.with_suffix(".log.1"))
    except OSError:
        pass
    line = time.strftime("%Y-%m-%dT%H:%M:%SZ ", time.gmtime()) + msg + "\n"
    with LOG.open("a") as f:
        f.write(line)


# ------------------------------------------------------------------------------- gh
def gh(*args, data=None, raw=False):
    out = subprocess.run(["gh", "api", *args], input=data, capture_output=True, timeout=120)
    if out.returncode:
        raise RuntimeError(out.stderr.decode()[:500])
    return out.stdout if raw else json.loads(out.stdout or b"null")


def comments():
    out, page = [], 1
    while True:
        batch = gh(f"repos/{REPO}/issues/{PR}/comments?per_page=100&page={page}")
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def fetch_file(sha, path):
    meta = gh(f"repos/{REPO}/contents/{path}?ref={sha}")
    b64 = meta.get("content") or gh(f"repos/{REPO}/git/blobs/{meta['sha']}")["content"]
    return base64.b64decode(b64)


# ---------------------------------------------------------------------------- state
def load_ledger():
    """Local dry-run spend cache only. Never authoritative."""
    if STATE.exists():
        try:
            return float(json.loads(STATE.read_text()).get("ledger", V1_SPEND_SEED))
        except (ValueError, OSError):
            pass
    return V1_SPEND_SEED


def save_ledger(value):
    try:
        STATE.write_text(json.dumps({"ledger": round(value, 6)}, indent=1))
    except OSError as e:
        log(f"could not write ledger: {e}")


# ------------------------------------------------------------------- body & triggers
def strip_body(body):
    """The body without the bot's own marker/footer and with surrounding whitespace gone."""
    b = MARKER_RE.sub("", body or "")
    return b.strip()


def first_line(body):
    s = strip_body(body)
    return s.splitlines()[0] if s else ""


def is_trigger(body):
    """A CODEX READY/BLOCKED/QUESTION or READY FOR MAC post. CODEX ACK and PLANNER are not triggers."""
    line = first_line(body)
    if not line:
        return False
    if line.startswith("PLANNER"):
        return False
    if re.match(r"^CODEX\s+ACK\b", line):
        return False
    if is_final(body):
        return True
    return bool(TRIGGER.match(line))


def is_final(body):
    """READY FOR MAC anywhere in the first line is the closing post (incl. 'CODEX READY FOR MAC')."""
    return "READY FOR MAC" in first_line(body)


def extract_sha(body):
    m = re.search(r"\b([0-9a-f]{40})\b", body or "")
    return m.group(1) if m else None


def item_key(body):
    """From the first line: CODEX NS1a READY -> NS1a, CODEX W6 READY -> W6, READY FOR MAC -> MAC."""
    first = first_line(body)
    if "READY FOR MAC" in first:
        return "MAC"
    m = re.match(r"CODEX\s+(?!ACK\b)([A-Z]+\d+[a-z]?(?:\.\d+)?(?:-[A-Z])?)", first)
    if m:
        return m.group(1)
    m = re.search(r"\b(?:NS|W)\d+[a-z]?(?:\.\d+)?(?:-[A-Z])?", first)
    return m.group(0) if m else "other"


# --------------------------------------------------------------------------- markers
def make_marker(re_id, item, verdict, cost):
    return f"\n<!-- planner-bot re:{re_id} item:{item} verdict:{verdict} cost:{float(cost):.4f} -->"


def parse_markers(thread):
    """Reduce the whole thread to: ids already answered, each marker's cost, CHANGES rounds per item."""
    answered, costs, changes = set(), [], {}
    for c in thread:
        for m in MARKER_RE.finditer(c.get("body", "")):
            re_id, item, verdict, cost = m.group(1), m.group(2), m.group(3), m.group(4)
            answered.add(int(re_id))
            try:
                costs.append(float(cost))
            except ValueError:
                pass
            if verdict == "CHANGES":
                changes[item] = changes.get(item, 0) + 1
    return answered, costs, changes


def pending(thread):
    answered, _, _ = parse_markers(thread)
    out = []
    for c in thread:
        if c.get("created_at", "") <= CUTOFF:
            continue
        if c["id"] in answered:
            continue
        if not is_trigger(c.get("body", "")):
            continue
        out.append(c)
    out.sort(key=lambda c: (c.get("created_at", ""), c["id"]))
    return out


def total_spend(thread, ledger):
    _, costs, _ = parse_markers(thread)
    return sum(costs) + ledger


def verdict_of(reply):
    head = reply.lstrip()
    m = re.match(r"PLANNER:?\s*\*\*\s*(APPROVED|CHANGES READY FOR MAC|CHANGES|ANSWER|HANDOFF)", head)
    if not m:
        return "ANSWER"
    token = m.group(1)
    if token.startswith("CHANGES"):
        return "CHANGES"
    if token == "HANDOFF":
        return "HANDOFF"
    if token == "APPROVED":
        return "APPROVED"
    return "ANSWER"


def ensure_prefix(reply):
    reply = reply.strip()
    return reply if reply.startswith("PLANNER") else "PLANNER: " + reply


# ----------------------------------------------------------------------- attachments
def attachments(body):
    """Frames (png) and short receipts (md/json) linked from the post.

    Explicit links (github.com blob/raw URLs, raw.githubusercontent.com URLs) carry their own
    sha; a bare `design-plans/...` or `docs/...` path is paired with the post's first 40-char
    sha unless the same path is already linked explicitly. *-diff.png is skipped (the
    side-by-side and overlay carry the comparison).
    """
    images, docs, seen = [], [], set()
    shas = re.findall(r"\b([0-9a-f]{40})\b", body)
    repo = re.escape(REPO)
    links = [
        (sha, re.split(r"[?#]", path)[0])
        for sha, path in re.findall(
            r"(?:github\.com/%s/(?:blob|raw)|raw\.githubusercontent\.com/%s)/([0-9a-f]{7,40})/([^\s)\]<>\"']+)"
            % (repo, repo),
            body,
        )
    ]
    linked = {p for _, p in links}
    if shas:
        for p in re.findall(r"`?((?:design-plans|docs)/[^\s`)\]<>\"']+\.(?:png|md|json))`?", body):
            if p not in linked:
                links.append((shas[0], p))
    for sha, path in links:
        if (sha, path) in seen:
            continue
        seen.add((sha, path))
        if path.lower().endswith("-diff.png"):
            continue
        try:
            if path.lower().endswith(".png"):
                if len(images) >= IMG_MAX_COUNT:
                    docs.append((path, "[frame skipped: more than 10 frames linked]"))
                    continue
                data = fetch_file(sha, path)
                if len(data) <= IMG_MAX_BYTES:
                    images.append((path, base64.b64encode(data).decode()))
                else:
                    docs.append((path, f"[frame skipped: {len(data)} bytes exceeds 4.8 MB]"))
                    log(f"skip large image {path} ({len(data)} bytes)")
            elif path.lower().endswith((".md", ".json")) and len(docs) < DOC_MAX_COUNT:
                docs.append((path, fetch_file(sha, path).decode("utf-8", "replace")[:DOC_MAX_BYTES]))
        except Exception as e:  # a missing file is reported to the model, never fatal
            docs.append((path, f"[could not fetch: {e}]"))
    return images, docs


# ---------------------------------------------------------------------------- gate
def run_gate(sha, outdir):
    """Run the independent gate at the sealed sha.

    Returns (ok, summary_text, log_tail, reason). ok is True only when the script exists,
    exits 0, and writes a summary.json whose test+browser sections are clean.
    """
    script = Path(GATE_CHECK)
    if not script.exists():
        return False, None, None, f"gate script not found at {GATE_CHECK}"
    Path(outdir).mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            ["bash", str(script), sha, str(outdir)],
            capture_output=True,
            timeout=GATE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False, None, None, f"gate timed out after {GATE_TIMEOUT_S // 60} minutes"
    except Exception as e:
        return False, None, None, f"gate crashed: {e}"

    summary_path = Path(outdir) / "summary.json"
    summary_text, summary = None, None
    if summary_path.exists():
        summary_text = summary_path.read_text()[:DOC_MAX_BYTES]
        try:
            summary = json.loads(summary_text)
        except ValueError:
            summary = None
    tail = None
    if proc.returncode != 0 or summary is None or not gate_summary_clean(summary):
        logpath = Path(outdir) / "test.log"
        if logpath.exists():
            tail = "\n".join(logpath.read_text(errors="replace").splitlines()[-80:])

    if proc.returncode != 0:
        return False, summary_text, tail, f"gate exited {proc.returncode}"
    if summary is None:
        return False, summary_text, tail, "gate wrote no readable summary.json"
    if not gate_summary_clean(summary):
        return False, summary_text, tail, "gate summary reports failures"
    return True, summary_text, tail, None


def gate_summary_clean(summary):
    try:
        t = summary.get("test", {})
        b = summary.get("browser", {})
    except AttributeError:
        return False
    def n(value):  # the gate lists console errors, page errors and writes; counts are ints
        if isinstance(value, (list, tuple)):
            return len(value)
        return value if isinstance(value, int) and not isinstance(value, bool) else 1

    # effective_* exclude only environment-only failures the gate matched by exact signature
    test_ok = (
        t.get("effective_exit", t.get("exit")) == 0
        and t.get("effective_failed", t.get("failed", 1)) == 0
        and t.get("errors", 1) == 0
    )
    browser_ok = (
        b.get("cases_total") is not None
        and b.get("cases_passed") == b.get("cases_total")
        and n(b.get("console_errors", 1)) == 0
        and n(b.get("page_errors", 1)) == 0
        and n(b.get("write_requests", 1)) == 0
        and n(b.get("overlaps", 1)) == 0
        and not b.get("failures")
    )
    return bool(test_ok and browser_ok)


# -------------------------------------------------------------------------- the model
def make_client():
    import anthropic

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        key_file = os.environ.get(
            "STEER_KEY_FILE", str(HERE / ".key")
        )
        key = Path(key_file).read_text().strip()
    return anthropic.Anthropic(api_key=key, max_retries=2)


def northstar_blocks():
    """The three approved north star concepts, first in every review so they sit in the cached prefix."""
    blocks = []
    for name in NORTHSTAR:
        p = NORTHSTAR_DIR / name
        if p.exists():
            blocks.append({"type": "text", "text": f"North star concept {name} (the exact target: layout, palette, type, icons; the user confirmed it)."})
            blocks.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(p.read_bytes()).decode()}})
        else:
            log(f"north star concept missing: {p}")
    if blocks:
        blocks[-1]["cache_control"] = {"type": "ephemeral"}
    return blocks


def build_input(c, thread, rounds, final_payload=None):
    body = c["body"]
    key = item_key(body)
    ctx = "\n\n".join(
        f"--- comment {t['id']} at {t['created_at']}\n{strip_body(t['body'])[:CTX_CHARS]}"
        for t in thread[-CTX_COMMENTS:]
        if t["id"] != c["id"]
    )
    images, docs = attachments(body)
    text = (
        f"RECENT PR #{PR} THREAD (oldest first):\n{ctx}\n\n"
        f"=== THE POST TO ANSWER (comment {c['id']}, item {key}, prior change rounds on this item: {rounds}) ===\n{body}\n"
    )
    for path, content in docs:
        text += f"\n=== Linked file {path} ===\n{content}\n"
    if final_payload is not None:
        text += "\n=== INDEPENDENT GATE (run by the planner at the sealed commit) ===\n"
        if final_payload.get("ran"):
            text += "The planner's own gate ran. Its summary.json:\n"
            text += (final_payload.get("summary") or "[summary.json was empty]") + "\n"
            if final_payload.get("tail"):
                text += "\nTail of test.log (gate reported failures):\n" + final_payload["tail"] + "\n"
            if final_payload.get("passed"):
                text += "\nThe independent gate PASSED.\n"
            else:
                text += f"\nThe independent gate did NOT pass: {final_payload.get('reason')}\n"
        else:
            text += (
                f"The independent gate could not run: {final_payload.get('reason')}.\n"
                "You must not hand off. Reply CHANGES READY FOR MAC and make the first body line "
                f"'independent gate could not run: {final_payload.get('reason')}'.\n"
            )
    if rounds >= 2:
        text += (
            "\nThis item has had two change rounds. Approve now unless a blocker breaks honesty, "
            "real function, overlaps or the writing rules; put remaining polish as fold-ins for the next item.\n"
        )
    content = northstar_blocks() + [{"type": "text", "text": text}]
    for path, b64 in images:
        content.append({"type": "text", "text": f"Frame: {path}"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}})
    content.append({"type": "text", "text": "Write the PLANNER reply now."})
    return content


def usage_cost(u):
    def g(name):
        return getattr(u, name, None) or 0

    return (
        (g("input_tokens") + g("cache_creation_input_tokens") * CACHE_WRITE_MULT) * PRICE_IN
        + g("cache_read_input_tokens") * PRICE_CACHE_READ
        + g("output_tokens") * PRICE_OUT
    ) / 1e6


def call_model(client, content):
    """Returns (reply_text, cost, stop_reason). Raises on refusal or transport error."""
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": (HERE / "system.md").read_text(), "cache_control": {"type": "ephemeral"}}],
        thinking={"type": "adaptive"},
        output_config={"effort": EFFORT},
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"fallbacks": "default"},
        messages=[{"role": "user", "content": content}],
    ) as stream:
        msg = stream.get_final_message()
    cost = usage_cost(msg.usage)
    served = MODEL
    its = getattr(msg.usage, "iterations", None) or []
    for it in its:
        if getattr(it, "type", None) == "fallback_message":
            served = getattr(it, "model", served)
    if msg.stop_reason == "refusal":
        raise RuntimeError("model refused")
    reply = "".join(b.text for b in msg.content if b.type == "text").strip()
    return reply, cost, msg.stop_reason, served


# ----------------------------------------------------------------------------- post
def post(reply, marker):
    payload = json.dumps({"body": reply + FOOTER + marker}).encode()
    r = gh(f"repos/{REPO}/issues/{PR}/comments", "--method", "POST", "--input", "-", data=payload)
    return r["html_url"]


# ------------------------------------------------------------------- review one post
def review(client, c, thread, changes, dry=False):
    """Review one comment. Returns (reply, verdict, cost, is_final_handoff)."""
    body = c["body"]
    key = item_key(body)
    rounds = changes.get(key, 0)

    final_payload = None
    if is_final(body):
        sha = extract_sha(body)
        if not sha:
            final_payload = {"ran": False, "reason": "no 40-char commit sha in the post"}
        else:
            outdir = HERE / "gate-out" / sha
            ok, summary_text, tail, reason = run_gate(sha, outdir)
            if reason and ("not found" in reason or "timed out" in reason or "crashed" in reason):
                final_payload = {"ran": False, "reason": reason}
            else:
                final_payload = {
                    "ran": True,
                    "passed": ok,
                    "summary": summary_text,
                    "tail": tail,
                    "reason": reason,
                }
            log(f"gate for {sha[:12]} (comment {c['id']}): ran={final_payload['ran']} passed={final_payload.get('passed')} reason={reason}")

    content = build_input(c, thread, rounds, final_payload)
    reply, cost, stop, served = call_model(client, content)
    reply = ensure_prefix(reply)
    verdict = verdict_of(reply)

    # Never hand off unverified: if this is a final post and the gate did not pass, force CHANGES.
    if is_final(body):
        gate_passed = bool(final_payload and final_payload.get("ran") and final_payload.get("passed"))
        if verdict == "HANDOFF" and not gate_passed:
            reason = (final_payload or {}).get("reason") or "independent gate did not pass"
            if not (final_payload or {}).get("ran"):
                lead = f"PLANNER: **CHANGES READY FOR MAC** (`{(extract_sha(body) or '')[:7]}`). independent gate could not run: {reason}."
            else:
                lead = f"PLANNER: **CHANGES READY FOR MAC** (`{(extract_sha(body) or '')[:7]}`). independent gate did not pass: {reason}."
            reply = lead + "\n\nThe handoff waits until the independent gate passes at the sealed commit. Revise, reseal and post READY FOR MAC again."
            verdict = "CHANGES"

    log(f"model for {c['id']} ({key}): cost=${cost:.4f} stop={stop} served={served} verdict={verdict}")
    is_handoff = is_final(body) and verdict == "HANDOFF"
    return reply, verdict, cost, is_handoff


# --------------------------------------------------------------------- retry bookkeeping
class RetryBook:
    """Per-process backoff for comments whose model call failed. At most MAX_ATTEMPTS tries each."""

    def __init__(self, now=time.time):
        self._now = now
        self.attempts = {}   # id -> count
        self.next_at = {}    # id -> earliest epoch to retry
        self.posted = set()  # ids answered by this process (guards against a lagging comment list)

    def ready(self, cid):
        if self.attempts.get(cid, 0) >= MAX_ATTEMPTS:
            return False
        return self._now() >= self.next_at.get(cid, 0)

    def exhausted(self, cid):
        return self.attempts.get(cid, 0) >= MAX_ATTEMPTS

    def record_failure(self, cid):
        n = self.attempts.get(cid, 0) + 1
        self.attempts[cid] = n
        if n < MAX_ATTEMPTS:
            delay = BACKOFFS_S[min(n - 1, len(BACKOFFS_S) - 1)]
            self.next_at[cid] = self._now() + delay
        return n

    def clear(self, cid):
        self.attempts.pop(cid, None)
        self.next_at.pop(cid, None)


# ----------------------------------------------------------------------------- driver
def process_once(client, retry=None):
    """Review at most one pending trigger (the oldest ready one) on a freshly fetched thread.

    The trigger is handled only once its reply and marker are posted; a failed review or post
    leaves it pending and backs off. Returns "handoff", "stopped" or None.
    """
    retry = retry if retry is not None else RetryBook()
    thread = comments()
    _, _, changes = parse_markers(thread)
    ledger = load_ledger()
    for c in pending(thread):
        if c["id"] in retry.posted or not retry.ready(c["id"]):
            continue
        key = item_key(c["body"])
        spent = total_spend(thread, ledger)
        if spent >= BUDGET_USD:
            log(f"budget reached (${spent:.4f} >= ${BUDGET_USD:.2f}); posting STOP and exiting")
            stop_reply = (
                "PLANNER: **STOP**. The automated planner reached its spending cap and has stopped. "
                "Codex: finish the current item to the roadmap and post READY; the user will steer next."
            )
            post(stop_reply, make_marker(c["id"], key, "STOP", 0.0))
            return "stopped"
        try:
            reply, verdict, cost, is_handoff = review(client, c, thread, changes)
        except Exception as e:
            n = retry.record_failure(c["id"])
            log(f"review failed for {c['id']} (attempt {n}/{MAX_ATTEMPTS}): {e}")
            return None
        try:
            url = post(reply, make_marker(c["id"], key, verdict, cost))
        except Exception as e:
            # No marker reached the thread: the trigger stays pending and the spend goes to the ledger.
            save_ledger(load_ledger() + cost)
            n = retry.record_failure(c["id"])
            log(f"post failed for {c['id']} (attempt {n}/{MAX_ATTEMPTS}, ${cost:.4f} to ledger): {e}")
            return None
        retry.clear(c["id"])
        retry.posted.add(c["id"])
        log(f"posted {url} (verdict {verdict}, cost ${cost:.4f})")
        return "handoff" if is_handoff else None
    return None


def main():
    args = sys.argv[1:]

    if args[:1] == ["--dry"]:
        client = make_client()
        thread = comments()
        c = next(t for t in thread if str(t["id"]) == args[1])
        _, _, changes = parse_markers(thread)
        reply, verdict, cost, _ = review(client, c, thread, changes, dry=True)
        print(reply)
        print(f"\n[dry] verdict={verdict} cost=${cost:.4f}")
        save_ledger(load_ledger() + cost)
        return 0

    if args[:1] == ["--once"]:
        client = make_client()
        process_once(client, RetryBook())
        return 0

    # Daemon mode.
    try:
        PIDFILE.write_text(str(os.getpid()))
    except OSError:
        pass
    log(f"start; budget ${BUDGET_USD:.2f}, ledger ${load_ledger():.3f}, cutoff {CUTOFF}, gate {GATE_CHECK}")
    client = make_client()
    retry = RetryBook()
    while True:
        try:
            result = process_once(client, retry)
            if result in ("handoff", "stopped"):
                break
        except Exception as e:  # GitHub / transport error: log and retry next poll
            log(f"poll error: {e}")
        time.sleep(POLL_S)
    log("finished")
    try:
        PIDFILE.unlink()
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
