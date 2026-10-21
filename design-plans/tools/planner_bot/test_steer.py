#!/usr/bin/env python3
"""Unit tests for planner bot v2. Stdlib only; mocks gh and the Anthropic client. No network.

Run: /tmp/claude-0/-home-user/e812972b-ebf3-51a0-bcb0-c18d7b98dee7/scratchpad/steer/venv/bin/python -m unittest -v
"""
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import steer  # noqa: E402

AFTER = "2099-01-01T00:00:00Z"   # after any CUTOFF
LATER = "2099-01-01T00:00:05Z"
BEFORE = "2000-01-01T00:00:00Z"  # before any CUTOFF

_TMP, _PATCHES = None, []


def setUpModule():
    """Keep tests off the live bot's log, ledger, pid file and concept images."""
    global _TMP
    _TMP = tempfile.TemporaryDirectory()
    t = Path(_TMP.name)
    (t / "northstar").mkdir()
    for name, val in (("LOG", t / "steer.log"), ("STATE", t / "state.json"),
                      ("PIDFILE", t / "steer.pid"), ("NORTHSTAR_DIR", t / "northstar")):
        p = mock.patch.object(steer, name, val)
        p.start()
        _PATCHES.append(p)


def tearDownModule():
    for p in _PATCHES:
        p.stop()
    _TMP.cleanup()


def cmt(cid, body, created_at=AFTER):
    return {"id": cid, "body": body, "created_at": created_at, "html_url": f"url/{cid}"}


def main_text(content):
    return next(b["text"] for b in content if b["type"] == "text" and "THE POST TO ANSWER" in b["text"])


# --------------------------------------------------------------------------- triggers
class TestTriggers(unittest.TestCase):
    def test_codex_ready(self):
        self.assertTrue(steer.is_trigger("CODEX W6 READY — f68bd78..."))

    def test_codex_blocked_question(self):
        self.assertTrue(steer.is_trigger("CODEX W8 BLOCKED — cannot reach seed"))
        self.assertTrue(steer.is_trigger("CODEX QUESTION — which form?"))

    def test_ready_for_mac_is_trigger_and_final(self):
        self.assertTrue(steer.is_trigger("READY FOR MAC"))
        self.assertTrue(steer.is_final("READY FOR MAC"))
        self.assertTrue(steer.is_trigger("CODEX READY FOR MAC — all green"))
        self.assertTrue(steer.is_final("CODEX READY FOR MAC — all green"))

    def test_ready_for_mac_anywhere_in_first_line(self):
        self.assertTrue(steer.is_final("W8 done — READY FOR MAC now"))

    def test_codex_ack_ignored(self):
        self.assertFalse(steer.is_trigger("CODEX ACK — W6 review 6314756996. Folding..."))

    def test_real_ack_posts_never_trigger(self):
        # 6314932362 and 6315222197 on PR #21: ACKs that mention READY later on the line.
        self.assertFalse(steer.is_trigger("CODEX ACK W6 CHANGES — 6314907292. Prioritizing all five items before W7 READY."))
        self.assertFalse(steer.is_trigger("CODEX ACK roadmap 6315202743. W7 is cancelled; READY FOR MAC later."))

    def test_ready_mentioning_ack_still_triggers(self):
        self.assertTrue(steer.is_trigger("CODEX NS2 READY — ACK of 6316377107 folded in"))

    def test_planner_ignored(self):
        self.assertFalse(steer.is_trigger("PLANNER: **APPROVED W5** (`352a553`)."))
        self.assertFalse(steer.is_trigger("PLANNER review of W3-A"))

    def test_plain_comment_ignored(self):
        self.assertFalse(steer.is_trigger("Just a note about the schedule."))

    def test_ready_not_at_start(self):
        # A line that merely contains READY mid-sentence without CODEX or READY FOR MAC is not a trigger.
        self.assertFalse(steer.is_trigger("We are getting READY to post soon."))

    def test_strip_marker_before_match(self):
        body = "CODEX W7 READY — abc\n" + steer.make_marker(1, "W7", "APPROVED", 0.1).strip()
        self.assertTrue(steer.is_trigger(body))


# --------------------------------------------------------------------------- item key
class TestItemKey(unittest.TestCase):
    def test_keys_from_first_line(self):
        self.assertEqual(steer.item_key("CODEX NS1a READY — shell and static 01"), "NS1a")
        self.assertEqual(steer.item_key("CODEX NS1b READY — 01 in motion, states 1–5"), "NS1b")
        self.assertEqual(steer.item_key("CODEX W6 READY — f68bd78"), "W6")
        self.assertEqual(steer.item_key("CODEX W3-A READY (rev) — 4fcf3e2"), "W3-A")
        self.assertEqual(steer.item_key("CODEX QUESTION — which form for NS2?"), "NS2")
        self.assertEqual(steer.item_key("CODEX BLOCKED — seed missing\nW8 later"), "other")

    def test_any_ready_for_mac_is_mac(self):
        self.assertEqual(steer.item_key("READY FOR MAC — " + "a" * 40), "MAC")
        self.assertEqual(steer.item_key("CODEX W8 READY FOR MAC — all green"), "MAC")


# ------------------------------------------------------------------ pending detection
class TestPending(unittest.TestCase):
    def test_pending_from_markers(self):
        answer = cmt(200, "PLANNER: **APPROVED W5**" + steer.make_marker(100, "W5", "APPROVED", 0.11))
        thread = [
            cmt(100, "CODEX W5 READY — 352a553"),           # answered by cmt 200
            answer,
            cmt(300, "CODEX W6 READY — f68bd78"),            # pending
            cmt(50, "CODEX W4 READY — old", created_at=BEFORE),  # before cutoff
            cmt(400, "CODEX ACK — noted"),                   # not a trigger
        ]
        pend = steer.pending(thread)
        self.assertEqual([c["id"] for c in pend], [300])

    def test_answered_set_and_rounds(self):
        thread = [
            cmt(1, "x" + steer.make_marker(10, "W6", "CHANGES", 0.2)),
            cmt(2, "y" + steer.make_marker(11, "W6", "CHANGES", 0.3)),
            cmt(3, "z" + steer.make_marker(12, "W6", "APPROVED", 0.4)),
        ]
        answered, costs, changes = steer.parse_markers(thread)
        self.assertEqual(answered, {10, 11, 12})
        self.assertEqual(changes["W6"], 2)
        self.assertAlmostEqual(sum(costs), 0.9, places=6)


# ------------------------------------------------------------------- spend & cap
class TestSpend(unittest.TestCase):
    def test_total_spend_markers_plus_ledger(self):
        thread = [
            cmt(1, "a" + steer.make_marker(10, "W5", "APPROVED", 0.1000)),
            cmt(2, "b" + steer.make_marker(11, "W6", "CHANGES", 0.2500)),
        ]
        self.assertAlmostEqual(steer.total_spend(thread, 0.199), 0.549, places=6)

    def test_cap_posts_stop_and_exits(self):
        thread = [cmt(300, "CODEX W6 READY — f68bd78")]
        posts = []
        with mock.patch.object(steer, "comments", return_value=thread), \
             mock.patch.object(steer, "load_ledger", return_value=99.0), \
             mock.patch.object(steer, "post", side_effect=lambda r, m: posts.append((r, m)) or "url") as p, \
             mock.patch.object(steer, "BUDGET_USD", 15.0):
            result = steer.process_once(object())
        self.assertEqual(result, "stopped")
        self.assertEqual(len(posts), 1)
        self.assertIn("spending cap", posts[0][0])
        self.assertIn("verdict:STOP", posts[0][1])


# ---------------------------------------------------------------------- marker format
class TestMarkers(unittest.TestCase):
    def test_make_and_parse_roundtrip(self):
        m = steer.make_marker(6314892503, "W6", "APPROVED", 0.09012)
        self.assertIn("re:6314892503", m)
        self.assertIn("item:W6", m)
        self.assertIn("verdict:APPROVED", m)
        self.assertIn("cost:0.0901", m)
        answered, costs, changes = steer.parse_markers([cmt(1, "body" + m)])
        self.assertEqual(answered, {6314892503})
        self.assertAlmostEqual(costs[0], 0.0901, places=4)

    def test_four_decimal_cost(self):
        self.assertIn("cost:0.1000", steer.make_marker(1, "W5", "CHANGES", 0.1))


# --------------------------------------------------------------------- reply prefixing
class TestReplyShape(unittest.TestCase):
    def test_ensure_prefix(self):
        self.assertTrue(steer.ensure_prefix("**APPROVED W5** done.").startswith("PLANNER: "))
        self.assertEqual(steer.ensure_prefix("PLANNER: **CHANGES W6** x"), "PLANNER: **CHANGES W6** x")

    def test_verdict_of(self):
        self.assertEqual(steer.verdict_of("PLANNER: **APPROVED W5** (`abc`)."), "APPROVED")
        self.assertEqual(steer.verdict_of("PLANNER: **CHANGES W6** (`abc`)."), "CHANGES")
        self.assertEqual(steer.verdict_of("PLANNER: **CHANGES READY FOR MAC** (`abc`)."), "CHANGES")
        self.assertEqual(steer.verdict_of("PLANNER: **HANDOFF TO MAC** (`abc`)."), "HANDOFF")
        self.assertEqual(steer.verdict_of("PLANNER: **ANSWER scope**. Continue."), "ANSWER")


# ---------------------------------------------------------------------- attachments
class TestAttachments(unittest.TestCase):
    def test_blob_link_images_and_docs(self):
        body = (
            "CODEX W6 READY — f68bd78db262007b3492abd78db1531b6be658ff\n"
            "Frames: https://github.com/KumarNavish/casepath/blob/f68bd78db262007b3492abd78db1531b6be658ff/design-plans/w6-20261021/defect.png "
            "and receipt https://github.com/KumarNavish/casepath/blob/f68bd78db262007b3492abd78db1531b6be658ff/design-plans/w6-20261021/verification.json"
        )
        files = {"design-plans/w6-20261021/defect.png": b"\x89PNG" + b"0" * 100,
                 "design-plans/w6-20261021/verification.json": b'{"files":1730}'}
        with mock.patch.object(steer, "fetch_file", side_effect=lambda sha, path: files[path]):
            images, docs = steer.attachments(body)
        self.assertEqual([p for p, _ in images], ["design-plans/w6-20261021/defect.png"])
        self.assertEqual([p for p, _ in docs], ["design-plans/w6-20261021/verification.json"])
        self.assertIn("1730", docs[0][1])

    def test_sha_plus_path_mention(self):
        sha = "f68bd78db262007b3492abd78db1531b6be658ff"
        body = f"CODEX W6 READY — {sha}. See `design-plans/w6-20261021/cases.png`."
        with mock.patch.object(steer, "fetch_file", side_effect=lambda s, p: b"\x89PNG" + b"x" * 10):
            images, docs = steer.attachments(body)
        self.assertEqual([p for p, _ in images], ["design-plans/w6-20261021/cases.png"])

    def test_large_image_skipped(self):
        sha = "f68bd78db262007b3492abd78db1531b6be658ff"
        body = f"CODEX W6 READY — {sha}. `design-plans/x/big.png`"
        with mock.patch.object(steer, "fetch_file", side_effect=lambda s, p: b"0" * (steer.IMG_MAX_BYTES + 1)):
            images, docs = steer.attachments(body)
        self.assertEqual(images, [])
        self.assertTrue(any("skipped" in d for _, d in docs))

    def test_diff_png_skipped(self):
        sha = "f68bd78db262007b3492abd78db1531b6be658ff"
        body = f"CODEX NS1b READY — {sha}. `design-plans/ns1/s3-diff.png` `design-plans/ns1/s3-side-by-side.png`"
        with mock.patch.object(steer, "fetch_file", return_value=b"\x89PNG") as ff:
            images, docs = steer.attachments(body)
        self.assertEqual([p for p, _ in images], ["design-plans/ns1/s3-side-by-side.png"])
        ff.assert_called_once_with(sha, "design-plans/ns1/s3-side-by-side.png")

    def test_raw_githubusercontent_links_fetched_at_their_sha(self):
        sealed, frames = "a" * 40, "b" * 40
        raw = f"https://raw.githubusercontent.com/KumarNavish/casepath/{frames}/design-plans/ns2"
        body = (f"CODEX NS2 READY — {sealed}\n![state 6]({raw}/state6.png)\n"
                f"![diff]({raw}/state6-diff.png)\n![side]({raw}/state6-side.png?raw=true)")
        with mock.patch.object(steer, "fetch_file", return_value=b"\x89PNG") as ff:
            images, docs = steer.attachments(body)
        self.assertEqual([p for p, _ in images], ["design-plans/ns2/state6.png", "design-plans/ns2/state6-side.png"])
        self.assertEqual(ff.call_args_list, [mock.call(frames, "design-plans/ns2/state6.png"),
                                             mock.call(frames, "design-plans/ns2/state6-side.png")])
        self.assertEqual(docs, [])


# ---------------------------------------------------------------- north star + context
class TestNorthstar(unittest.TestCase):
    def test_concepts_first_and_last_one_cached(self):
        with tempfile.TemporaryDirectory() as d:
            for name in steer.NORTHSTAR:
                Path(d, name).write_bytes(b"\x89PNG" + name.encode())
            c = cmt(500, f"CODEX NS2 READY — {'f' * 40}. `design-plans/ns2/frame.png`")
            with mock.patch.object(steer, "NORTHSTAR_DIR", Path(d)), \
                 mock.patch.object(steer, "fetch_file", return_value=b"\x89PNGframe"):
                content = steer.build_input(c, [c], rounds=0)
        self.assertEqual([b["type"] for b in content[:6]], ["text", "image"] * 3)
        for i, name in enumerate(steer.NORTHSTAR):
            self.assertIn(name, content[2 * i]["text"])
        self.assertEqual([i for i, b in enumerate(content) if "cache_control" in b], [5])
        self.assertEqual(content[5]["cache_control"], {"type": "ephemeral"})
        self.assertIn("THE POST TO ANSWER", content[6]["text"])
        self.assertEqual(content[-3]["text"], "Frame: design-plans/ns2/frame.png")
        self.assertEqual(content[-1]["text"], "Write the PLANNER reply now.")

    def test_bot_dir_ships_the_three_concepts(self):
        for name in steer.NORTHSTAR:
            self.assertTrue((steer.HERE / "northstar" / name).stat().st_size > 1000, name)


class TestContext(unittest.TestCase):
    def test_last_ten_comments_truncated_planner_replies_kept(self):
        thread = [cmt(i, "n%02d " % i + "x" * 3000) for i in range(1, 15)]
        thread.append(cmt(15, "PLANNER: **APPROVED NS1b** (`a6a9f39`)." + steer.FOOTER
                          + steer.make_marker(14, "NS1b", "APPROVED", 0.15)))
        c = cmt(16, "CODEX NS2 READY — nolinks")
        thread.append(c)
        ctx = main_text(steer.build_input(c, thread, rounds=0)).split("=== THE POST TO ANSWER")[0]
        self.assertEqual([int(x) for x in re.findall(r"--- comment (\d+) at", ctx)], list(range(7, 16)))
        self.assertIn("x" * 1796, ctx)        # 4-char prefix + 1796 = 1800
        self.assertNotIn("x" * 1797, ctx)
        self.assertIn("APPROVED NS1b", ctx)   # earlier planner replies are visible
        self.assertNotIn("planner-bot re:", ctx)


# --------------------------------------------------------------------------- gate
class TestGateSummary(unittest.TestCase):
    def test_clean_pass(self):
        s = {"test": {"exit": 0, "passed": 500, "failed": 0, "errors": 0, "skipped": 0, "duration_s": 12},
             "browser": {"cases_total": 9, "cases_passed": 9, "console_errors": 0, "page_errors": 0,
                         "write_requests": 0, "overlaps": 0, "failures": []},
             "verdict": "pass", "notes": ""}
        self.assertTrue(steer.gate_summary_clean(s))

    def test_test_failure(self):
        s = {"test": {"exit": 1, "failed": 2, "errors": 0},
             "browser": {"cases_total": 9, "cases_passed": 9, "console_errors": 0, "page_errors": 0,
                         "write_requests": 0, "overlaps": 0, "failures": []}}
        self.assertFalse(steer.gate_summary_clean(s))

    def test_browser_failure(self):
        s = {"test": {"exit": 0, "failed": 0, "errors": 0},
             "browser": {"cases_total": 9, "cases_passed": 8, "console_errors": 1, "page_errors": 0,
                         "write_requests": 0, "overlaps": 0, "failures": ["case 3"]}}
        self.assertFalse(steer.gate_summary_clean(s))

    def test_run_gate_missing_script(self):
        with mock.patch.object(steer, "GATE_CHECK", "/no/such/gate_check.sh"):
            ok, summary, tail, reason = steer.run_gate("a" * 40, "/tmp/does-not-matter")
        self.assertFalse(ok)
        self.assertIn("not found", reason)


# ------------------------------------------------------- final flow (gate -> verdict)
GOOD_SUMMARY = ('{"test":{"exit":0,"failed":0,"errors":0},'
                '"browser":{"cases_total":9,"cases_passed":9,"console_errors":0,'
                '"page_errors":0,"write_requests":0,"overlaps":0,"failures":[]}}')


class TestFinalFlow(unittest.TestCase):
    def _review(self, final_body, gate_tuple, model_reply):
        thread = [cmt(900, final_body)]
        with mock.patch.object(steer, "run_gate", return_value=gate_tuple), \
             mock.patch.object(steer, "call_model", return_value=(model_reply, 0.5, "end_turn", steer.MODEL)), \
             mock.patch.object(steer, "fetch_file", side_effect=lambda s, p: b"x"):
            return steer.review(object(), thread[0], thread, {})

    def test_gate_pass_handoff(self):
        body = "CODEX READY FOR MAC — " + "a" * 40
        reply, verdict, cost, is_handoff = self._review(
            body, (True, GOOD_SUMMARY, None, None), "PLANNER: **HANDOFF TO MAC** (`aaaaaaa`).")
        self.assertEqual(verdict, "HANDOFF")
        self.assertTrue(is_handoff)

    def test_gate_fail_forces_changes(self):
        body = "CODEX READY FOR MAC — " + "b" * 40
        reply, verdict, cost, is_handoff = self._review(
            body, (False, "{}", "FAILED: 2", "gate exited 1"),
            "PLANNER: **HANDOFF TO MAC** (`bbbbbbb`).")  # model wrongly says handoff
        self.assertEqual(verdict, "CHANGES")
        self.assertFalse(is_handoff)
        self.assertIn("CHANGES READY FOR MAC", reply)

    def test_gate_missing_never_handoff(self):
        body = "CODEX READY FOR MAC — " + "c" * 40
        reply, verdict, cost, is_handoff = self._review(
            body, (False, None, None, "gate script not found at /x"),
            "PLANNER: **HANDOFF TO MAC** (`ccccccc`).")
        self.assertEqual(verdict, "CHANGES")
        self.assertFalse(is_handoff)
        self.assertIn("independent gate could not run", reply)

    def test_process_once_handoff_returns(self):
        body = "CODEX READY FOR MAC — " + "d" * 40
        thread = [cmt(900, body)]
        posts = []
        with mock.patch.object(steer, "comments", return_value=thread), \
             mock.patch.object(steer, "load_ledger", return_value=1.0), \
             mock.patch.object(steer, "run_gate", return_value=(True, GOOD_SUMMARY, None, None)), \
             mock.patch.object(steer, "call_model",
                               return_value=("PLANNER: **HANDOFF TO MAC** (`ddddddd`).", 0.5, "end_turn", steer.MODEL)), \
             mock.patch.object(steer, "fetch_file", side_effect=lambda s, p: b"x"), \
             mock.patch.object(steer, "post", side_effect=lambda r, m: posts.append((r, m)) or "url"):
            result = steer.process_once(object())
        self.assertEqual(result, "handoff")
        self.assertIn("verdict:HANDOFF", posts[0][1])


# ------------------------------------------------------------------- rounds >= 2 text
class TestRounds(unittest.TestCase):
    def test_approve_unless_blocker_added_after_two_rounds(self):
        c = cmt(500, "CODEX W6 READY — nolinks")
        content = steer.build_input(c, [c], rounds=2)
        self.assertIn("two change rounds", main_text(content))

    def test_no_instruction_before_two_rounds(self):
        c = cmt(500, "CODEX W6 READY — nolinks")
        content = steer.build_input(c, [c], rounds=1)
        self.assertNotIn("two change rounds", main_text(content))


# ----------------------------------------------------------------- retry / backoff
class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class TestRetry(unittest.TestCase):
    def test_backoff_schedule_and_cap(self):
        clock = FakeClock()
        rb = steer.RetryBook(now=clock)
        cid = 42
        self.assertTrue(rb.ready(cid))             # first time, no record
        n1 = rb.record_failure(cid)                # attempt 1 -> wait 120s
        self.assertEqual(n1, 1)
        self.assertFalse(rb.ready(cid))            # inside backoff
        clock.t += 120
        self.assertTrue(rb.ready(cid))
        rb.record_failure(cid)                     # attempt 2 -> wait 300s
        clock.t += 300
        self.assertTrue(rb.ready(cid))
        rb.record_failure(cid)                     # attempt 3 -> exhausted
        self.assertTrue(rb.exhausted(cid))
        clock.t += 100000
        self.assertFalse(rb.ready(cid))            # never ready again this process

    def test_clear_resets(self):
        clock = FakeClock()
        rb = steer.RetryBook(now=clock)
        rb.record_failure(7)
        rb.clear(7)
        self.assertTrue(rb.ready(7))
        self.assertFalse(rb.exhausted(7))

    def test_failed_review_records_and_skips(self):
        thread = [cmt(300, "CODEX W6 READY — nolinks")]
        rb = steer.RetryBook()
        with mock.patch.object(steer, "comments", return_value=thread), \
             mock.patch.object(steer, "load_ledger", return_value=1.0), \
             mock.patch.object(steer, "review", side_effect=RuntimeError("api down")), \
             mock.patch.object(steer, "post") as p:
            steer.process_once(object(), rb)
        self.assertEqual(rb.attempts.get(300), 1)
        p.assert_not_called()

    def test_failed_review_ends_the_poll_then_next_trigger_proceeds(self):
        a, b = cmt(301, "CODEX NS2 READY — a"), cmt(302, "CODEX NS3 READY — b", created_at=LATER)
        calls = []

        def fake_review(client, c, thread, changes):
            calls.append(c["id"])
            if c["id"] == 301:
                raise RuntimeError("api down")
            return "PLANNER: **APPROVED NS3** (`abc1234`).", "APPROVED", 0.1, False

        rb = steer.RetryBook(now=FakeClock())
        with mock.patch.object(steer, "comments", return_value=[a, b]), \
             mock.patch.object(steer, "review", side_effect=fake_review), \
             mock.patch.object(steer, "post", return_value="url") as p:
            steer.process_once(object(), rb)
            self.assertEqual(calls, [301])
            p.assert_not_called()
            steer.process_once(object(), rb)  # 301 is backing off
            self.assertEqual(calls, [301, 302])
            p.assert_called_once()

    def test_post_failure_keeps_pending_counts_spend_and_backs_off(self):
        self.addCleanup(lambda: steer.STATE.unlink(missing_ok=True))
        steer.save_ledger(1.051)
        thread = [cmt(300, "CODEX NS2 READY — x")]
        clock = FakeClock()
        rb = steer.RetryBook(now=clock)
        ok = ("PLANNER: **APPROVED NS2** (`abc1234`).", "APPROVED", 0.25, False)
        with mock.patch.object(steer, "comments", return_value=thread), \
             mock.patch.object(steer, "review", return_value=ok) as rv, \
             mock.patch.object(steer, "post", side_effect=RuntimeError("HTTP 502")):
            self.assertIsNone(steer.process_once(object(), rb))
            self.assertEqual(rb.attempts[300], 1)
            self.assertNotIn(300, rb.posted)
            self.assertAlmostEqual(steer.load_ledger(), 1.301, places=6)
            steer.process_once(object(), rb)  # inside backoff: no second model call
            self.assertEqual(rv.call_count, 1)
        clock.t += steer.BACKOFFS_S[0]
        with mock.patch.object(steer, "comments", return_value=thread), \
             mock.patch.object(steer, "review", return_value=ok), \
             mock.patch.object(steer, "post", return_value="url") as p:
            steer.process_once(object(), rb)
            p.assert_called_once()
            self.assertIn("re:300", p.call_args[0][1])
        self.assertIn(300, rb.posted)


# ---------------------------------------------------------- one trigger per poll
class TestOnePerPoll(unittest.TestCase):
    def test_one_review_per_poll_on_a_refetched_thread(self):
        thread = [cmt(301, "CODEX NS2 READY — first"), cmt(302, "CODEX NS3 READY — second", created_at=LATER)]
        seen = []

        def fake_review(client, c, th, changes):
            seen.append((c["id"], [t["id"] for t in th]))
            return f"PLANNER: **APPROVED {steer.item_key(c['body'])}** (`abc1234`).", "APPROVED", 0.1, False

        def fake_post(reply, marker):
            thread.append(cmt(900 + len(thread), reply + steer.FOOTER + marker, created_at=LATER))
            return "url"

        rb = steer.RetryBook()
        with mock.patch.object(steer, "comments", side_effect=lambda: list(thread)) as cm, \
             mock.patch.object(steer, "review", side_effect=fake_review), \
             mock.patch.object(steer, "post", side_effect=fake_post):
            for _ in range(3):
                steer.process_once(object(), rb)
        self.assertEqual(cm.call_count, 3)
        self.assertEqual([cid for cid, _ in seen], [301, 302])  # one per poll, no repeats
        self.assertIn(902, seen[1][1])                          # second review saw the first reply
        self.assertEqual(len([t for t in thread if "planner-bot re:" in t["body"]]), 2)


# ------------------------------------------------------------- ledger + system prompt
class TestLedgerAndPrompt(unittest.TestCase):
    def test_ledger_seed_and_roundtrip(self):
        self.addCleanup(lambda: steer.STATE.unlink(missing_ok=True))
        steer.STATE.unlink(missing_ok=True)
        self.assertAlmostEqual(steer.load_ledger(), steer.V1_SPEND_SEED)
        steer.save_ledger(2.5)
        self.assertAlmostEqual(steer.load_ledger(), 2.5)

    def test_system_prompt_is_v1_plus_gate_section_once(self):
        text = (steer.HERE / "system.md").read_text()
        h = "## How to judge the independent gate summary (READY FOR MAC only)"
        self.assertEqual(text.count(h), 1)
        self.assertIn("## UPDATE 2, 21 Oct", text)
        self.assertLess(text.index("## Token discipline"), text.index(h))


# ------------------------------------------------------- call_model: cost, refusal, fallback
class FakeUsage:
    def __init__(self, it=0, out=0, cc=0, cr=0, iterations=None):
        self.input_tokens, self.output_tokens = it, out
        self.cache_creation_input_tokens, self.cache_read_input_tokens = cc, cr
        self.iterations = iterations


class FakeBlock:
    def __init__(self, text):
        self.type, self.text = "text", text


class FakeMsg:
    def __init__(self, text, usage, stop_reason="end_turn"):
        self.content = [FakeBlock(text)]
        self.usage = usage
        self.stop_reason = stop_reason


class FakeStream:
    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.msg


class FakeClient:
    def __init__(self, msg):
        self.msg = msg
        self.beta = self
        self.messages = self

    def stream(self, **kw):
        self.kw = kw
        return FakeStream(self.msg)


class FakeFallbackIter:
    def __init__(self, model):
        self.type, self.model = "fallback_message", model


class TestCallModel(unittest.TestCase):
    def test_cost_formula(self):
        u = FakeUsage(it=1_000_000, out=0, cc=0, cr=0)
        self.assertAlmostEqual(steer.usage_cost(u), 4.0, places=6)
        u = FakeUsage(it=0, out=1_000_000)
        self.assertAlmostEqual(steer.usage_cost(u), 20.0, places=6)
        u = FakeUsage(cc=1_000_000)  # cache write 1.25x input
        self.assertAlmostEqual(steer.usage_cost(u), 5.0, places=6)
        u = FakeUsage(cr=1_000_000)
        self.assertAlmostEqual(steer.usage_cost(u), 0.20, places=6)

    def test_refusal_raises(self):
        client = FakeClient(FakeMsg("", FakeUsage(it=10), stop_reason="refusal"))
        with mock.patch.object(steer, "HERE", steer.HERE):
            with self.assertRaises(RuntimeError):
                steer.call_model(client, [{"type": "text", "text": "x"}])

    def test_fallback_served_detected(self):
        it = [FakeFallbackIter("claude-opus-4-8")]
        client = FakeClient(FakeMsg("PLANNER: **ANSWER x**.", FakeUsage(it=10, out=5, iterations=it)))
        reply, cost, stop, served = steer.call_model(client, [{"type": "text", "text": "x"}])
        self.assertEqual(served, "claude-opus-4-8")
        self.assertEqual(stop, "end_turn")
        self.assertTrue(reply.startswith("PLANNER"))

    def test_request_parameters(self):
        client = FakeClient(FakeMsg("PLANNER: **ANSWER x**.", FakeUsage(it=10, out=5)))
        steer.call_model(client, [{"type": "text", "text": "x"}])
        kw = client.kw
        self.assertEqual(kw["model"], "claude-opus-5-5")
        self.assertEqual(kw["max_tokens"], 64000)
        self.assertEqual(kw["thinking"], {"type": "adaptive"})
        self.assertEqual(kw["output_config"], {"effort": "max"})
        self.assertEqual(kw["betas"], ["server-side-fallback-2026-07-01"])
        self.assertEqual(kw["extra_body"], {"fallbacks": "default"})
        self.assertEqual(kw["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(kw["messages"], [{"role": "user", "content": [{"type": "text", "text": "x"}]}])


if __name__ == "__main__":
    unittest.main()


class TestColdViewer(unittest.TestCase):
    SHA = "0123456789abcdef0123456789abcdef01234567"

    def test_video_links_from_blob_raw_and_bare_paths(self):
        blob = f"https://github.com/{steer.REPO}/blob/{self.SHA}/design-plans/w9/film.mp4"
        raw = f"https://raw.githubusercontent.com/{steer.REPO}/{self.SHA}/design-plans/w9/film.webm?raw=true"
        self.assertEqual(steer.video_links(f"CODEX W9 READY [f]({blob})"), [(self.SHA, "design-plans/w9/film.mp4")])
        self.assertEqual(steer.video_links(f"CODEX W9 READY ![f]({raw})"), [(self.SHA, "design-plans/w9/film.webm")])
        self.assertEqual(steer.video_links(f"CODEX W9 READY {self.SHA} `design-plans/w9/film.mp4`"),
                         [(self.SHA, "design-plans/w9/film.mp4")])
        self.assertEqual(steer.video_links("CODEX NS2 READY frame.png only"), [])

    @unittest.skipUnless(steer.shutil_which("ffmpeg") if hasattr(steer, "shutil_which") else __import__("shutil").which("ffmpeg"), "ffmpeg missing")
    def test_sample_frames_evenly_spaced(self):
        import subprocess, tempfile, os
        with tempfile.TemporaryDirectory() as d:
            clip = os.path.join(d, "c.mp4")
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=4:size=320x200:rate=30",
                            "-pix_fmt", "yuv420p", clip], check=True)
            frames = steer.sample_frames(open(clip, "rb").read(), n=4, width=160)
        self.assertEqual(len(frames), 4)
        self.assertAlmostEqual(frames[0][0], 0.5, places=1)
        self.assertTrue(all(data[:2] == b"\xff\xd8" for _, data in frames))

    def test_cold_report_runs_and_never_raises(self):
        body = f"CODEX W9 READY {self.SHA} `design-plans/w9/film.mp4`"
        with mock.patch.object(steer, "fetch_file", return_value=b"video"), \
             mock.patch.object(steer, "sample_frames", return_value=[(1.0, b"\xff\xd8x")]), \
             mock.patch.object(steer, "cold_viewer", return_value=("It handles claims.", 0.05)), \
             mock.patch.object(steer, "log"):
            report, cost = steer.cold_view_report(object(), body)
        self.assertIn("It handles claims.", report)
        self.assertEqual(cost, 0.05)
        with mock.patch.object(steer, "fetch_file", side_effect=RuntimeError("404")):
            report, cost = steer.cold_view_report(object(), body)
        self.assertIn("could not run", report)
        self.assertEqual(cost, 0.0)
        self.assertEqual(steer.cold_view_report(object(), "CODEX NS3 READY no film"), (None, 0.0))

    def test_build_input_includes_cold_report(self):
        c = {"id": 1, "created_at": "2026-10-21T20:00:00Z", "body": "CODEX W9 READY"}
        with mock.patch.object(steer, "attachments", return_value=([], [])), \
             mock.patch.object(steer, "northstar_blocks", return_value=[]):
            content = steer.build_input(c, [c], 0, None, cold="Viewer: it answers tenant claims.")
        text = "".join(b.get("text", "") for b in content if b["type"] == "text")
        self.assertIn("COLD-VIEWER TEST", text)
        self.assertIn("it answers tenant claims", text)
