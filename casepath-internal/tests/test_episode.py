"""The reply episode integrated: «a reply arrives → the assessment is prepared → the decision is carried through», on S-D11A
(tests/episode.py, synthetic), with S-D11B (E2) as the contrasting variant, through the case service's routes as a handler
takes the steps. The three outcomes of the newer steering:

(a) a substantive response package: the A5 answers each question with its rule and the conditions with their evidence,
    names the recommendation, the alternative and what would change it, asks only the electricity receipts with what
    they block; after the four decisions and «Freigeben» the letter, the Versandpaket, every download, the file note and
    the Wiedervorlage are one version and agree;
(b) the case advances when evidence arrives: the receipts prepare the judgment they were asked for instead of the A5 + 90
    wait; an unrelated attachment and a same-amount receipt for another expense change nothing; a partial reply leaves
    only the remainder awaited; a contradiction reopens the judgment; silence brings the status inquiry at A5 + 90;
(c) one correction repairs the whole package, keeps the handler's unrelated edits, and undo restores it; a jurist's mark on
    what an unsent approval rests on makes it stale with the same bytes; a sent version is kept and reconciled.

Then (d) every labelled perturbation ends without duplicates or lost edits, (e) the episode activates no Knowledge, and (f)
the item list's hash changes exactly where declared, while every frozen study copy keeps its hash (the seeded copy, and the
release check with the candidate's startup).

Deterministic and scripted: no model, no network. The dispatched copies are placed relative to today (episode.EpisodeClock
stamps their steps on the episode's own days), so the tests pass on any day and at any hour."""
from datetime import date, timedelta
import html
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
import threading
import unittest
import zipfile

from fastapi.testclient import TestClient

from casepath.config import load_settings
from casepath.process import completion
from casepath.process.workflows import Catalogue
from casepath.quality import frozen
from casepath.web import actions, bundle as versandpaket
from casepath.web.app import create_app
from tests import episode

USER = "N. Kumar"
EP = episode.EPISODE  # S-D11A, the replies of 05.09.2026
E2 = episode.analog(names=episode.VARIANT_B)  # S-D11B: one question (the deposit), no claim, receipts only promised
RECEIPTS = "Belege zu: Stromkosten für den Bautrockner"
Q3 = "Werden mir die Stromkosten für den Bautrockner ersetzt?"


def without_reaction(ns):
    """What the reader records of the replies, without the management's reaction: the A5 then asks it as well (a fact ask
    with what it decides), beside the receipts, so a reply can meet one ask and leave the other (the partial reply)."""
    facts = [f for f in ns.facts_b if (f[1] or {}).get("fact") != "reaktion_vermieter"]
    return episode.update_turns(ns.entries_b, facts, ns.summary_b, ns.questions_b, ns.timeline_b, claims=ns.claims_b)


def settings(root, **env):
    return load_settings({"CASEPATH_DATA_DIR": str(Path(root) / "data"), "CASEPATH_WORKFLOW_CATALOGUE": str(Path(root) / "catalogue"),
                          "CASEPATH_DEV_USER": USER, **env})


def docx_text(data):
    """Every paragraph's text of a .docx, one line each."""
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8")
    return "\n".join(html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))) for p in re.findall(r"<w:p[ >].*?</w:p>", xml))


def asked_lines(text):
    """The lines under «Bitte reichen Sie uns noch nach:» of a letter, without the dash."""
    if "Bitte reichen Sie uns noch nach:\n" not in text:
        return []
    return [line[2:] for line in text.split("Bitte reichen Sie uns noch nach:\n", 1)[1].split("\n\n", 1)[0].split("\n") if line.startswith("– ")]


def day(d):
    return f"{d:%d.%m.%Y}"


# -- one template store: E1 and E2 after their replies, the frozen study copy, and S-D11A dispatched N days ago -------------

TEMPLATE = {}
DISPATCHED = {"d21": (21, "4321.6011.0011", None), "partial": (21, "4321.6011.0012", without_reaction),
              "d89": (89, "4321.6011.0013", None), "d90": (90, "4321.6011.0014", None)}


def template():
    """Built once: E1 as it stood on d+34 («e1a»), E1 (S-D11A) and E2 (S-D11B) after the scripted update of their two
    replies, the frozen study copy of the preview (episode.seed_frozen_copy), and copies of S-D11A whose A5 was decided,
    approved and dispatched 21, 89 and 90 days ago through the routes (episode.seed_dispatched; «partial»: the A5 also
    asked the management's reaction)."""
    if "dir" not in TEMPLATE:
        root = Path(tempfile.mkdtemp(prefix="cp-episode-template-"))
        (root / "catalogue").mkdir()
        app = create_app(settings(root), model_factory=lambda: None)
        store, runs = app.state.store, app.state.runs
        cases, names = {"e1a": episode.seed_phase_a(store, runs, EP, title=f"D11-Analogon A, vor den Antworten (synthetisch) {EP.reference}")["id"]}, {}
        for key, ns in (("e1", EP), ("e2", E2)):
            case = episode.seed_phase_a(store, runs, ns)
            episode.add_replies(store, case["id"], ns)
            runs.model_factory = lambda token=None, c=case["id"], n=ns: episode.update_model(store, c, n.turns_b(), n.reply_names)
            run = episode.wait(store, runs.update(case["id"], USER)["id"])
            assert run["status"] == "completed", run.get("error")
            cases[key] = case["id"]
        source, study = episode.seed_frozen_copy(store, runs)
        cases.update(frozen=source["id"], study=study["id"])
        for key, (days, reference, variant) in DISPATCHED.items():
            case, ns = episode.seed_dispatched(app, days=days, reference=reference, turns_b=variant)
            cases[key], names[key] = case["id"], ns
        runs.shutdown()
        store.close()
        TEMPLATE.update(dir=root, cases=cases, ns=names)
    return TEMPLATE


class Episode(unittest.TestCase):
    """A copy of the template store for each test, opened by the case service."""
    env = {}

    def setUp(self):
        t = template()
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        shutil.copytree(t["dir"], self.root, dirs_exist_ok=True)
        self.cases, self.ns = t["cases"], t["ns"]
        self.client = self.app()

    def app(self, model_factory=None, **env):
        return TestClient(create_app(settings(self.root, **{**self.env, **env}), model_factory=model_factory or (lambda: None)))

    def tearDown(self):
        self.client.app.state.runs.shutdown()
        self.client.app.state.store.close()
        self.directory.cleanup()

    @property
    def store(self):
        return self.client.app.state.store

    # what the handler sees
    def view(self, case):
        return self.client.get(f"/api/cases/{case}").json()

    def row(self, case):
        return next(c for c in self.client.get("/api/cases").json()["cases"] if c["id"] == case)

    def events(self, case, kind=None):
        return [e for e in self.store.list_case_events(case) if kind is None or e["kind"] == kind]

    def action(self, view):
        return next(i for i in view["items"] if i["kind"] == "next_action")

    def entries(self, case):
        """The numbers of the account's entries the latest completed run recorded, in number order."""
        run = self.store.latest_run(case, "completed")
        return sorted(e["n"] for e in ((run.get("result") or {}).get("record") or {}).get("entries") or ())

    # what the handler does
    def post(self, path, body, expect=(200, 201)):
        r = self.client.post(path, json=body)
        self.assertIn(r.status_code, expect if isinstance(expect, tuple) else (expect,), r.text)
        return r.json()

    def decide(self, case, fact, value, reason="", code="none"):
        return self.post(f"/api/cases/{case}/edits", {"op": "set_fact", "args": {"fact": fact, "value": value}, "reason": reason,
                                                      "reason_code": code, "recheck": False}, 201)

    def adopt(self, case):
        brief = self.view(case)["assessment"]
        return self.post(f"/api/cases/{case}/recommendation", {"chosen": brief["proposal"], "proposal": brief["proposal"]}, 201)

    def approve(self, case, op="op-approve-1", expect=200):
        draft = self.view(case)["draft"]
        return self.post(f"/api/cases/{case}/actions/approve", {"form": draft["form"], "version": draft["version"], "op_id": op}, expect)

    def dispatch(self, case, version, op="op-dispatch-1"):
        return self.post(f"/api/cases/{case}/actions/dispatch", {"version": version, "date": completion.swiss_today().isoformat(),
                                                                  "channel": "email", "op_id": op}, 200)

    def edit_part(self, case, starts, text, op="op-edit-1"):
        """The handler rewrites one part of the letter (saved per part, as the letter box does)."""
        draft = self.view(case)["draft"]
        part = next(p for p in draft["parts"] if p["text"].startswith(starts))
        r = self.client.put(f"/api/cases/{case}/drafts/{draft['form']}", json={"parts": [{"part": part["part"], "base_sha256": part["base_sha256"], "text": text}],
                                                                              "parent_id": draft.get("draft_id"), "op_id": op})
        self.assertEqual(r.status_code, 200, r.text)
        return part["part"]

    def upload(self, case, files, expect=201):
        r = self.client.post(f"/api/cases/{case}/files", files=[("files", (name, data, "message/rfc822" if name.endswith(".eml") else "text/plain"))
                                                                for name, data in files])
        self.assertEqual(r.status_code, expect, r.text)
        return r.json()

    def update(self, case, turns, names, model=None, expect="completed"):
        """«Aktualisieren»: one update of the case's unread files by the scripted reader (``turns``, file ids by ``names``).
        The model is called exactly as often as the script has turns: none left over, none asked for beyond them."""
        runs, used = self.client.app.state.runs, []
        runs.model_factory = lambda token=None: model or used.append(episode.update_model(self.store, case, turns, names)) or used[-1]
        run = episode.wait(self.store, runs.update(case, USER)["id"])
        self.assertEqual(run["status"], expect, run.get("error"))
        if expect == "completed" and model is None:
            self.assertEqual((len(used), used[0].turns), (1, []))  # one model, its script used up
        return run

    def dispatched_n(self, case):
        return next(e for e in self.store.list_edits(case) if e["op"] == "add_dispatch")["args"]["n"]

    def first_free(self, case):
        """The next number of an account entry (after the dispatch's)."""
        return max(self.entries(case) + [self.dispatched_n(case)]) + 1

    def reply(self, ns, name, body, attachments=(), plus=20, at="11:20"):
        """A reply of the customer to the A5, ``plus`` days after it went out (an e-mail as saved from the mailbox)."""
        k = ns.names["kunde"]
        return name, episode.eml(f"{k} <{ns.names['mail']}>", f"Protekta Rechtsschutz <{episode.INSURER_MAIL}>", ns.a5_day + timedelta(days=plus), at,
                                 f"AW: Rechtliche Einschätzung {ns.reference}", f"Guten Tag\n\n{body}\n\nFreundliche Grüsse\n{k}", attachments=list(attachments))

    def ready(self, case):
        """The three decisions of the A5 before «Freigeben»: Deckung, the recommendation, the prospects."""
        self.decide(case, "deckung", "bestätigt")
        self.adopt(case)
        self.decide(case, "aussichten", "genügend")
        return self.view(case)


# -- §2 rows 1 and 2: the replies dropped on the case --------------------------------------------------------------------------

class DropTests(Episode):
    env = {"CASEPATH_AUTO_UPDATE": "1"}  # as the preview: the upload starts the bounded update

    def test_the_drop_starts_one_update_of_the_replies_and_the_head_says_what_changed_and_what_it_means(self):
        case = self.cases["e1a"]
        before = self.row(case)["stand"]
        used = []
        self.client.app.state.runs.model_factory = lambda token=None: used.append(episode.update_model(self.store, case, EP.turns_b(), EP.reply_names)) or used[-1]
        body = self.upload(case, EP.replies)
        self.assertEqual((body["auto"], [f["name"] for f in body["files"]], body["skipped"]), ("gestartet", [n for n, _ in EP.replies], []))
        run = episode.wait(self.store, body["run"]["id"])
        self.assertEqual((run["status"], run["kind"]), ("completed", "update"), run.get("error"))
        self.assertEqual((len(used), used[0].turns), (1, []))  # the update's script, every turn used, no call more
        replies = sorted(f["id"] for f in body["files"])
        self.assertEqual(sorted(run["result"]["update"]["files"]), replies)  # it read the two replies, nothing else
        again = self.client.post(f"/api/cases/{case}/files", files=[("files", (EP.replies[0][0], EP.replies[0][1], "message/rfc822"))])
        self.assertEqual(again.status_code, 409)
        self.assertTrue(again.json()["detail"].startswith(f"Bereits in der Akte: «{EP.replies[0][0]}» vom "), again.json())
        view = self.view(case)
        head = view["screen"]["head"]
        self.assertEqual(head["changed"], view["changes"]["ledger"][0])
        self.assertEqual(view["changes"]["ledger"][-1], "2 Nachrichten der Kundschaft vom 05.09.2026")
        self.assertEqual(head["meaning"], "Einschätzung vorbereitet (1 Frage beantwortet, 2 bedingt); kann nach dem Deckungsentscheid freigegeben werden.")
        self.assertEqual((self.action(view)["action"], self.row(case)["stand"]["bucket"]), ("A5", "urteil"))
        self.assertNotEqual(self.row(case)["stand"], before)


# -- (a) the response package ------------------------------------------------------------------------------------------------

class PackageTests(Episode):
    def test_after_the_replies_the_a5_answers_each_question_names_the_way_and_asks_only_the_receipts(self):
        view = self.view(self.cases["e1"])
        brief, text = view["assessment"], view["draft"]["text"]
        self.assertEqual((self.action(view)["action"], view["draft"]["form"]), ("A5", "A5"))
        # each customer question: its state, the rule it rests on and the passage it was asked in
        questions = brief["questions"]
        self.assertEqual([(q["text"], q["state"]) for q in questions],
                         [("Muss ich weiterhin die volle Miete bezahlen?", "beantwortet"), ("Darf ich die Miete hinterlegen?", "bedingt"), (Q3, "bedingt")])
        files = {f["id"] for f in view["files"]}
        for q in questions:
            self.assertIsInstance(q["row"], int)
            self.assertRegex(q["answer"], r"\(Art\. \d+[a-z]? (Abs\. \d )?OR")  # the rule, cited
            self.assertTrue(q["evidence"] and all(e["file"] in files and e["quote"] == q["text"] for e in q["evidence"]))
            self.assertIn(f"«{q['text']}»: {q['answer']}", text)  # the letter answers it in these words
        self.assertEqual([(q["reason"], (q["next"] or {}).get("kind")) for q in questions[1:]], [("vorher mit uns besprechen", "discuss"), (RECEIPTS, "residual")])
        # the conditions of the proposed ways, each with the passage that meets it
        proposed = [o for o in brief["options"] if o["id"] in brief["proposal"]]
        self.assertEqual(brief["proposal"], ["frist_beseitigung", "schadenersatz"])
        met_conditions = [c for o in proposed for c in o["conditions"] if c["state"] == "erfüllt" and c.get("fact")]
        self.assertEqual([c["fact"] for c in met_conditions], ["mangel_gemeldet", "reaktion_vermieter"])
        for c in met_conditions:
            rule = next(r for r in brief["rules"] for x in r["conditions"] if x["fact"] == c["fact"])
            met = next(x for x in rule["conditions"] if x["fact"] == c["fact"])
            self.assertTrue(met["evidence"] and all(e["file"] in files and e["quote"] for e in met["evidence"]), c)
        # the recommendation, the alternative and what would change it
        self.assertIn("Wir empfehlen Ihnen, der Vermieterschaft schriftlich eine angemessene Frist zur Beseitigung des Mangels zu setzen (Art. 259g Abs. 1 OR)", text)
        self.assertIn("Zudem empfehlen wir Ihnen, Ihre Kosten mit Belegen zu beziffern", text)
        self.assertEqual([(a["id"], a["selectable"]) for a in brief["alternatives"]], [("frist_androhung", True), ("hinterlegung", False)])
        self.assertIn("eine Hinterlegung droht sie nicht an. Wir empfehlen Ihnen, eine Hinterlegung vorher mit uns zu besprechen.", text)
        self.assertEqual([c["fact"] for c in brief["changes_if"]], ["mangel_besteht", "reaktion_vermieter", "will_schadenersatz"])
        self.assertIn("Unsere Empfehlung beruht darauf, dass der Mangel weiterhin besteht und die Vermieterschaft den Mangel nicht behoben hat; "
                      "ändert sich daran etwas, teilen Sie uns das bitte mit.", text)
        # only the remainder is asked: the electricity receipts, with the question, the way and the condition they settle
        self.assertEqual(brief["asks"], [{"key": "residual:claim.0", "what": RECEIPTS, "kind": "claim", "ref": 0,
                                          "blocks": {"question": "customer_question:2", "option": "schadenersatz", "condition": "Kosten mit Belegen nachgewiesen"}}])
        self.assertEqual(asked_lines(text), [RECEIPTS])
        self.assertNotIn("Kaufbelege", text)  # the first request's generic documents are not asked again
        self.assertEqual([b["key"] for b in brief["blocking"]], ["deckung", "empfehlung", "aussichten"])
        self.assertEqual(view["completion"]["bar"]["gaps"], 0)

    def test_the_contrasting_variant_asks_nothing_and_answers_its_one_question(self):
        view = self.view(self.cases["e2"])
        brief, text = view["assessment"], view["draft"]["text"]
        self.assertEqual([(q["text"], q["state"]) for q in brief["questions"]], [("Darf ich die Miete hinterlegen?", "bedingt")])
        self.assertEqual((brief["proposal"], brief["asks"], brief["residual"]), (["frist_beseitigung"], [], []))
        self.assertEqual([c["fact"] for c in brief["changes_if"]], ["mangel_besteht", "reaktion_vermieter"])
        self.assertEqual(asked_lines(text), [])  # she claims nothing: no receipts asked, no claim line
        self.assertNotIn("Stromkosten", text)
        self.assertIn("Nach Ihren Angaben hat die Vermieterschaft auf Ihre Meldung nicht reagiert.", text)
        self.assertEqual([b["key"] for b in brief["blocking"]], ["deckung", "empfehlung", "aussichten"])

    def check_package(self, case, expected_asks):
        """After the decisions and «Freigeben»: the approved letter, the Versandpaket, every download, the note and the
        Wiedervorlage are the version approved and agree with it. Returns (approval, letter bytes)."""
        before = self.view(case)
        self.assertEqual(before["assessment"]["blocking"], [])
        self.assertEqual((before["completion"]["bar"]["label"], before["completion"]["decisions"]), ("Freigeben", []))
        out = self.approve(case)
        approval, saved = out["approval"], out["bundle"]
        view = self.view(case)
        draft = view["draft"]
        self.assertEqual((approval["version"], saved["version"], view["completion"]["state"], view["completion"]["valid"]),
                         (draft["version"], draft["version"], "freigegeben", True))
        today = completion.swiss_today()
        # the Versandpaket: the exact letter and enclosures, its manifest names the version and every part's bytes
        blob = self.client.get(f"/api/cases/{case}/actions/{draft['version']}/bundle").content
        self.assertEqual(blob, self.store.blob(saved["sha256"]))
        archive = zipfile.ZipFile(io.BytesIO(blob))
        letter = archive.read("Kundschaft/Brief.docx")
        self.assertEqual(versandpaket.text_of(letter), "\n".join(line if line.strip() else "" for line in draft["text"].split("\n")))
        manifest = json.loads(archive.read("manifest.json"))
        self.assertEqual((manifest["version"], manifest["approval"], manifest["form"]), (draft["version"], approval["event_id"], "A5"))
        for part in manifest["parts"]:
            self.assertEqual(part["sha256"], versandpaket._sha(archive.read(part["name"])), part["name"])
        self.assertEqual([(r["to"], r["recipient"]) for r in manifest["recipients"]], [(r["to"], r["recipient"]) for r in draft["recipients"]])
        enclosures = [a for a in draft["also"] if a.get("text")]
        self.assertEqual(sorted(p["kind"] for p in manifest["parts"] if p["kind"]), sorted(["A5"] + [a["kind"] for a in enclosures]))
        # every download is that letter: the case's approved letter, the version's .docx, the draft download, the report
        found = actions.approved_letter(self.store, case)
        self.assertEqual((found["version"], found["docx"], found["bundle"]), (draft["version"], letter, saved["sha256"]))
        self.assertEqual(self.client.get(f"/api/cases/{case}/actions/{draft['version']}/docx/A5").content, letter)
        run = self.store.latest_run(case, "completed")
        self.assertEqual(self.client.get(f"/api/runs/{run['id']}/draft.docx").content, letter)
        report = docx_text(self.client.get(f"/api/cases/{case}/report.docx").content)
        for line in found["text"].split("\n"):
            if line.strip():
                self.assertIn(line, report)
        # the note and the Wiedervorlage say what the letter asks and the same date
        wiedervorlage = archive.read("Wiedervorlage.txt").decode().split("\n")
        when = f"Wiedervorlage 90 Tage nach dem Versand: {day(today + timedelta(days=90))} bei Versand am {day(today)}"
        self.assertEqual(wiedervorlage[:2], [when, "Erwartet: " + (", ".join(expected_asks) or "Rückmeldung")])
        self.assertEqual(asked_lines(draft["text"]), expected_asks)
        note = archive.read("Aktennotiz.txt").decode().strip()
        expected = f"Erwartet: {', '.join(expected_asks) or 'Rückmeldung'}; {when}."
        self.assertTrue(note.endswith(expected), note)
        self.assertIn(f"Zum Versand freigegeben am {day(today)} ({USER}): {draft['title']}.", note)
        self.assertIn("Empfehlung übernommen:", note)
        self.assertTrue(view["file_note"].endswith(expected), view["file_note"])  # «Aktennotiz kopieren» says the same
        self.assertEqual(manifest["follow_up"], {"days": 90, "due": (today + timedelta(days=90)).isoformat(), "if_sent": today.isoformat()})
        return approval, letter

    def test_four_decisions_and_the_approved_letter_is_the_one_version_everywhere(self):
        case = self.cases["e1"]
        # the queue and the head name the decision the card asks next, in the card's order
        for fact, value, then in (("deckung", "bestätigt", "Empfehlung"), (None, None, "Erfolgsaussichten"), ("aussichten", "genügend", None)):
            self.assertEqual(self.view(case)["completion"]["decisions"][0], {"deckung": "Deckung", None: "Empfehlung", "aussichten": "Erfolgsaussichten"}[fact])
            self.decide(case, fact, value) if fact else self.adopt(case)
            view = self.view(case)
            self.assertEqual(self.row(case)["stand"]["text"], f"Entscheid: {then}" if then else "vorbereitet")
            self.assertTrue(view["screen"]["head"]["meaning"].endswith({"Empfehlung": "kann nach dem Entscheid zur Empfehlung freigegeben werden.",
                                                                      "Erfolgsaussichten": "kann nach dem Entscheid zu den Erfolgsaussichten freigegeben werden.",
                                                                      None: "kann freigegeben werden."}[then]), view["screen"]["head"]["meaning"])
        approval, letter = self.check_package(case, [RECEIPTS])
        decisions = [e for e in self.events(case) if e["kind"] in ("item.corrected", "action.approved") and e.get("item_id") in ("fact:deckung", "point:empfehlung", "fact:aussichten", None)]
        self.assertEqual([e.get("item_id") or e["kind"] for e in decisions], ["fact:deckung", "point:empfehlung", "fact:aussichten", "action.approved"])
        effort = self.view(case)["completion"]["effort"]
        self.assertEqual([(x["step"], x["state"]) for x in effort["external"]], [("senden", "offen"), ("ablegen", "offen"), ("eintragen", "offen")])
        # «Versandt am»: the account records what the letter asked, each ask with the judgment it waits for, in words
        self.dispatch(case, approval["version"])
        sent = next(e for e in self.store.list_edits(case) if e["op"] == "add_dispatch")["args"]
        self.assertEqual([(a["what"], a["blocks"]["question"], a["blocks"]["question_id"], a["blocks"]["option_title"]) for a in sent["asks"]],
                         [(RECEIPTS, Q3, "customer_question:2", "Kosten belegen und Ersatz verlangen")])
        self.assertEqual([a["what"] for a in sent["answers"]], ["Muss ich weiterhin die volle Miete bezahlen?"])
        view = self.view(case)
        today = completion.swiss_today()
        self.assertEqual(view["follow_up"]["due"], (today + timedelta(days=90)).isoformat())  # the date the package named
        self.assertIn(f"Versandt: Rechtliche Einschätzung an die Kundschaft am {day(today)} (E-Mail, {USER}).", view["file_note"])
        self.assertTrue(view["file_note"].endswith(f"Erwartet: {RECEIPTS}; Wiedervorlage {day(today + timedelta(days=90))}."), view["file_note"])
        self.assertEqual(self.client.get(f"/api/cases/{case}/actions/{approval['version']}/docx/A5").content, letter)  # sent: still that letter

    def test_the_contrasting_variant_carries_its_own_package(self):
        case = self.cases["e2"]
        self.ready(case)
        self.check_package(case, [])

    def test_the_date_beside_freigeben_is_the_one_the_package_files_and_the_wait_keeps(self):
        """Before «Freigeben» the bar names the date the Versandpaket will file (A5 + 90 from a dispatch today), not the
        date the case fell due; a date the handler sets there is the package's, the note's and the wait's after the
        dispatch."""
        case, today = self.cases["e1"], completion.swiss_today()
        counted = {"due": (today + timedelta(days=90)).isoformat(), "days": 90, "if_sent": today.isoformat()}
        self.assertEqual(self.view(case)["follow_after_dispatch"], counted)  # before the decisions too: the A5 goes out at its stage
        self.ready(case)
        self.assertEqual(self.view(case)["follow_after_dispatch"], counted)
        own = today + timedelta(days=30)
        self.post(f"/api/cases/{case}/events", {"kind": "followup.set", "item_id": "followup:0", "fields": {"date": own.isoformat(), "step": "A5"}}, 201)
        self.assertEqual(self.view(case)["follow_after_dispatch"], {"due": own.isoformat(), "set": True})
        approval = self.approve(case)["approval"]
        archive = zipfile.ZipFile(io.BytesIO(self.client.get(f"/api/cases/{case}/actions/{approval['version']}/bundle").content))
        self.assertEqual(archive.read("Wiedervorlage.txt").decode().split("\n")[:2], [f"Wiedervorlage {day(own)}", f"Erwartet: {RECEIPTS}"])
        self.assertEqual(json.loads(archive.read("manifest.json"))["follow_up"], {"due": own.isoformat(), "set": True})
        self.assertTrue(archive.read("Aktennotiz.txt").decode().strip().endswith(f"Erwartet: {RECEIPTS}; Wiedervorlage {day(own)}."))
        self.dispatch(case, approval["version"])
        view = self.view(case)
        self.assertEqual((view["follow_up"]["due"], self.row(case)["stand"]["text"]), (own.isoformat(), f"wartet auf Kundschaft bis {day(own)}"))
        self.assertTrue(view["file_note"].endswith(f"Erwartet: {RECEIPTS}; Wiedervorlage {day(own)}."), view["file_note"])


# -- (b) the case advances when evidence arrives ----------------------------------------------------------------------------

class ArrivalTests(Episode):
    def receipts(self, case, ns):
        rec = ns.branches["B-receipts"]
        self.upload(case, rec.files())
        return self.update(case, rec.turns(self.first_free(case), self.dispatched_n(case)), {"fs": "Belege Stromkosten.eml", "ft": episode.BILL})

    def test_b_receipts_fulfils_the_ask_merges_the_quoted_a5_and_prepares_the_judgment(self):
        """B-receipts. DESIGN §2 row 9b kept the A7 dated A5 + 90; the newer steering (§2) asks the consequence prepared:
        the receipts resolve the judgment they were asked for, so the assessment is what comes next, not the wait."""
        case, ns = self.cases["d21"], self.ns["d21"]
        before = self.view(case)
        self.assertEqual((self.action(before)["action"], self.row(case)["stand"]["bucket"]), ("A7", "wartet"))
        self.receipts(case, ns)
        view = self.view(case)
        brief, act = view["assessment"], self.action(view)
        q3 = next(q for q in brief["questions"] if q["text"] == Q3)
        self.assertEqual((q3["state"], q3["reason"], q3["row"]), ("beantwortet", "Belege liegen vor", 10))  # the blocked question is answered
        self.assertEqual(brief["residual"], [])
        bill = next(f["id"] for f in view["files"] if f["name"] == episode.BILL)
        resolved = next(r for r in brief["resolved"] if r["key"] == "residual:claim.0")
        self.assertEqual((resolved["now"], [b["file"] for b in resolved["by"]]), ({"question": "beantwortet", "option": "holds", "condition": "erfüllt"}, [bill]))
        # the consequence is prepared now: the assessment again, with the evidence named; not the follow-up at A5 + 90
        self.assertEqual((act["action"], act["reason"]), ("A5", f"eingegangen: {RECEIPTS}; jetzt zu beurteilen: «{Q3}»"))
        self.assertEqual(act["consequence"]["judgments"][0]["file"], bill)
        self.assertEqual((self.row(case)["stand"]["bucket"], self.row(case)["stand"]["text"]), ("urteil", "erfüllt: Einschätzung vorbereitet"))
        self.assertEqual(view["screen"]["head"]["meaning"], f"Eingegangen: {RECEIPTS}; jetzt zu beurteilen: «{Q3}»; Einschätzung vorbereitet.")
        self.assertIsNone(view["completion"]["waiting_until"])
        self.assertNotIn("Bitte reichen Sie uns noch nach", view["draft"]["text"])  # nothing left to ask
        # the A5 quoted below the reply joins the dispatch («zitiert in Nr. …»): no second A5 in the account
        ours = [i for i in view["items"] if i["kind"] == "entry" and i.get("value") == "Rechtliche Einschätzung"]
        self.assertEqual(len(ours), 1)
        notes = [n["text"] for n in ours[0]["notes"]]
        self.assertTrue(any(n.startswith("zitiert in Nr. ") for n in notes), notes)
        self.assertTrue(any(n.startswith(f"verlangt von der Kundschaft: {RECEIPTS} · beantwortet") for n in notes), notes)

    def test_an_unrelated_attachment_leaves_the_wait_quiet_and_prepares_no_letter(self):
        case, ns = self.cases["d21"], self.ns["d21"]
        photo = "Foto Schlafzimmer.txt"
        name, data = self.reply(ns, "Foto.eml", "Anbei ein Foto vom Schlafzimmer.", [(photo, "Foto: Wand im Schlafzimmer, Schimmel sichtbar.".encode())])
        self.upload(case, [(name, data)])
        first = self.first_free(case)
        self.update(case, episode.update_turns([
            episode.entry(first, "fs", None, ns.a5_day + timedelta(days=20), "kunde", "versicherer", "unterlagen", "Foto zugestellt", "Anbei ein Foto vom Schlafzimmer."),
            episode.entry(first + 1, "ft", None, None, "kunde", "versicherer", "andere", "Foto Schlafzimmer", "Foto: Wand im Schlafzimmer, Schimmel sichtbar.")],
            [], "Die Kundschaft reicht ein Foto ein."), {"fs": name, "ft": photo})
        self.assert_quiet(case, ns)

    def assert_quiet(self, case, ns):
        view = self.view(case)
        until = ns.a5_day + timedelta(days=90)
        act = self.action(view)
        self.assertEqual((act["action"], act.get("consequence")), ("A7", None))  # the status inquiry at A5 + 90, not a letter now
        self.assertEqual((view["completion"]["last"]["consequence"]["kind"], view["completion"]["bucket"], view["completion"]["waiting_until"]),
                         ("unrelated", None, until.isoformat()))
        self.assertEqual(self.row(case)["stand"], {**self.row(case)["stand"], "bucket": "wartet", "text": f"wartet auf Kundschaft bis {day(until)}"})
        self.assertEqual([r["key"] for r in view["assessment"]["residual"]], ["residual:claim.0"])  # the receipts are still owed
        return view

    def carpet(self, case, ns, linked):
        """A reply with a receipt of the same amount for another expense (a carpet cleaning, CHF 85.40), as the reader records
        it; ``linked``: the reader also takes the reply as the answer to the A5's request."""
        other = "Quittung Teppichreinigung.txt"
        name, data = self.reply(ns, "Quittung.eml", "Anbei eine Quittung.", [(other, "Teppich Beispiel GmbH\nReinigung Teppich Wohnzimmer\nBetrag: CHF 85.40\nBar bezahlt.".encode())])
        self.upload(case, [(name, data)])
        first = self.first_free(case)
        self.update(case, episode.update_turns([
            episode.entry(first, "fs", None, ns.a5_day + timedelta(days=20), "kunde", "versicherer", "unterlagen", "Quittung zugestellt", "Anbei eine Quittung.",
                          **({"answers": [episode.answer("Quittung", self.dispatched_n(case), "Anbei eine Quittung.")]} if linked else {})),
            episode.entry(first + 1, "ft", None, None, "andere", "kunde", "andere", "Quittung Teppichreinigung CHF 85.40", "Betrag: CHF 85.40",
                          receipt=episode.receipt("Betrag: CHF 85.40", "Teppichreinigung Wohnzimmer", "Reinigung", amount="CHF 85.40", role="paid",
                                                  party="Teppich Beispiel GmbH"))],
            [], "Die Kundschaft reicht eine Quittung der Teppichreinigung ein."), {"fs": name, "ft": other})
        return next(f["id"] for f in self.store.list_files(case) if f["name"] == other)

    def test_a_same_amount_receipt_for_another_expense_is_never_counted(self):
        case, ns = self.cases["d21"], self.ns["d21"]
        carpet = self.carpet(case, ns, linked=False)
        view = self.assert_quiet(case, ns)
        line = view["assessment"]["residual"][0]
        self.assertIn((carpet, ["andere Ausgabe: Teppichreinigung Wohnzimmer"]), [(x["file"], x["why"]) for x in line["set_aside"]])
        q3 = next(q for q in view["assessment"]["questions"] if q["text"] == Q3)
        self.assertEqual(q3["state"], "bedingt")

    def test_a_same_amount_receipt_given_as_the_answer_is_not_counted_and_asks_the_handler_to_check(self):
        case, ns = self.cases["d21"], self.ns["d21"]
        self.carpet(case, ns, linked=True)
        view = self.view(case)
        self.assertEqual((view["completion"]["last"]["consequence"]["kind"], self.row(case)["stand"]["text"]), ("unbelegt", "Antwort ohne Beleg – prüfen"))
        self.assertEqual(([r["key"] for r in view["assessment"]["residual"]], self.action(view).get("consequence")), (["residual:claim.0"], None))

    def test_a_partial_reply_leaves_only_the_remainder_awaited(self):
        case, ns = self.cases["partial"], self.ns["partial"]
        sent = next(e for e in self.store.list_edits(case) if e["op"] == "add_dispatch")["args"]
        self.assertEqual([a["what"] for a in sent["asks"]], [RECEIPTS, "Wie hat die Vermieterschaft auf Ihre Meldung reagiert?"])
        said = "Die Verwaltung hat auf meine Meldung nicht mehr reagiert."
        name, data = self.reply(ns, "Antwort Verwaltung.eml", said)
        self.upload(case, [(name, data)])
        first = self.first_free(case)
        self.update(case, episode.update_turns([
            episode.entry(first, "fs", None, ns.a5_day + timedelta(days=20), "kunde", "versicherer", "antwort", "Reaktion der Verwaltung: keine",
                          f"Subject: AW: Rechtliche Einschätzung {ns.reference}",  # the answer names the request it answers by its id (C8)
                          answers=[{**episode.answer("Reaktion der Verwaltung", self.dispatched_n(case), said), "request": f"r{self.dispatched_n(case)}.1"}])],
            [episode.fact("fs", "reaktion_vermieter", "Keine Reaktion", said)], "Die Kundschaft beantwortet die Frage nach der Reaktion der Verwaltung."),
            {"fs": name})
        view = self.view(case)
        meaning = view["completion"]["last"]["consequence"]
        self.assertEqual((meaning["kind"], [a["what"] for a in meaning["remainder"]]), ("partial", [RECEIPTS]))
        self.assertEqual(view["completion"]["status"], f"teilweise erfüllt: offen {RECEIPTS}")
        self.assertEqual(self.row(case)["stand"]["bucket"], "urteil")  # what came settles a judgment (the deadline to set)
        self.assertTrue(view["file_note"].endswith(f"Erwartet: {RECEIPTS}; Wiedervorlage {day(ns.a5_day + timedelta(days=90))}."), view["file_note"])
        self.assertIn(f"Offen bei der Kundschaft: {RECEIPTS} · seit {day(ns.a5_day)} · 1× verlangt.", view["file_note"])  # the account agrees
        self.assertEqual([a["what"] for a in view["assessment"]["asks"]], [RECEIPTS])  # only the remainder is asked

    def test_a_contradiction_reopens_the_judgment(self):
        case, ns = self.cases["d21"], self.ns["d21"]
        said = "Der Schimmel ist inzwischen weg; die Verwaltung hat die Wand saniert."
        name, data = self.reply(ns, "Mangel behoben.eml", said, at="09:40")
        self.upload(case, [(name, data)])
        self.update(case, episode.update_turns([
            episode.entry(self.first_free(case), "fs", None, ns.a5_day + timedelta(days=20), "kunde", "versicherer", "antwort", "Mangel behoben",
                          f"Subject: AW: Rechtliche Einschätzung {ns.reference}")],
            [episode.fact("fs", "mangel_besteht", "nein", said)], "Die Kundschaft meldet, der Mangel sei behoben."), {"fs": name})
        view = self.view(case)
        st = view["completion"]
        self.assertEqual((st["last"]["consequence"]["kind"], st["bucket"]), ("contradiction", "urteil"))
        self.assertEqual(self.row(case)["stand"]["text"], "versandt mit früherem Stand – prüfen: Besteht der Mangel aktuell noch?")
        self.assertEqual([q["state"] for q in view["assessment"]["questions"]], ["offen", "offen", "bedingt"])  # the deposit answers rested on it
        self.assertEqual(view["assessment"]["proposal"], ["schadenersatz"])
        self.assertEqual(st["bar"]["reconcile"], st["last"]["version"])  # what went out is reconciled, never unsent

    def test_b_silence_prepares_the_a7_from_the_dispatch_date(self):
        waiting, due = self.cases["d89"], self.cases["d90"]
        a5 = self.ns["d89"].a5_day
        view = self.view(waiting)
        self.assertEqual((self.action(view)["action"], view["completion"]["bucket"], view["completion"]["last"]["consequence"]["kind"]), ("A7", None, "waiting"))
        self.assertEqual(self.row(waiting)["stand"]["text"], f"wartet auf Kundschaft bis {day(a5 + timedelta(days=90))}")
        view = self.view(due)
        act = self.action(view)
        self.assertEqual((act["action"], view["draft"]["form"], view["draft"]["title"]), ("A7", "A7", "Statusanfrage mit Abschlussankündigung"))
        a5 = self.ns["d90"].a5_day  # 90 days before the day the template was built: due that day
        self.assertEqual((act["since"], view["follow_up"]["due"]), (a5.isoformat(), (a5 + timedelta(days=90)).isoformat()))
        self.assertEqual(self.row(due)["stand"]["bucket"], "urteil")
        self.assertTrue(self.row(due)["stand"]["text"].endswith("Statusanfrage mit Abschlussankündigung vorbereitet"), self.row(due)["stand"])
        self.assertEqual((view["completion"]["bar"]["label"], view["completion"]["bar"]["gaps"], view["completion"]["decisions"]), ("Freigeben", 0, []))
        self.assertIn(f"seit unserem letzten Kontakt vom {day(self.ns['d90'].a5_day)}", view["draft"]["text"])


# -- (c) one correction repairs the whole package -----------------------------------------------------------------------------

class CorrectionTests(Episode):
    CONTRA = EP.perturbations["P-contra"].edit  # «Mangel behoben» (Telefon mit der Kundin), set after the approval

    def test_mangel_behoben_after_approval_repairs_every_part_keeps_the_handlers_edit_and_undo_restores_it(self):
        case = self.cases["e1"]
        mine = "Vielen Dank für Ihre Unterlagen und Ihre Geduld."
        self.edit_part(case, "Vielen Dank", mine)  # the handler's own sentence, unrelated to the correction
        self.ready(case)
        approved = self.approve(case)["approval"]
        before = self.view(case)
        report_before = self.client.get(f"/api/cases/{case}/report.docx").content
        row_before = self.row(case)["stand"]
        out = self.post(f"/api/cases/{case}/edits", self.CONTRA, 201)
        after = self.view(case)
        a, b = before["assessment"], after["assessment"]
        # the recommendation, the answers and the letter follow; the basis and every change are shown before/after
        self.assertEqual((a["proposal"], b["proposal"]), (["frist_beseitigung", "schadenersatz"], ["schadenersatz"]))
        self.assertEqual([q["state"] for q in b["questions"]], ["offen", "offen", "bedingt"])
        self.assertEqual([q["reason"] for q in b["questions"][:2]], ["Regel trifft nach der Akte nicht zu"] * 2)
        self.assertEqual([r["line"] for r in b["residual"]], [RECEIPTS])  # the claim does not rest on the defect: still owed
        self.assertEqual([x["kind"] for x in after["draft"]["also"]], [])  # the deadline's template is no longer enclosed
        self.assertNotEqual(after["draft"]["version"], approved["version"])
        self.assertIn(mine, after["draft"]["text"])  # the handler's edit survives
        self.assertEqual(out["consequences"]["basis"], "Besteht der Mangel aktuell noch?: ja → nein (Mangel behoben (Telefon mit der Kundin); N. Kumar)")
        changed = {c["what"] for c in out["consequences"]["changes"]}
        self.assertTrue({"Status", "Freigabe", "Brieftext", "Aktennotiz"} <= changed, changed)
        # the approval is stale, the queue says so, the note no longer claims it, the exports serve the corrected letter
        st = after["completion"]
        self.assertEqual((st["valid"], st["status"], st["bucket"]), (False, "Freigabe veraltet: Entscheid geändert", "urteil"))
        self.assertEqual((row_before["bucket"], self.row(case)["stand"]["bucket"]), ("versandbereit", "urteil"))
        self.assertNotIn("Zum Versand freigegeben", after["file_note"])
        self.assertNotIn("Empfehlung übernommen", after["file_note"])  # the adoption lapsed with the proposal
        self.assertIn("Besteht der Mangel aktuell noch?: nein (durch die Fallbearbeitung)", after["file_note"])
        self.assertEqual([x["key"] for x in b["blocking"]], ["empfehlung"])  # to confirm again
        report = self.client.get(f"/api/cases/{case}/report.docx").content
        self.assertNotEqual(report, report_before)
        self.assertNotIn("Zudem empfehlen wir Ihnen", docx_text(report))  # the approved letter's sentence is not in the report any more
        self.assertIn("[bitte ergänzen: Antwort auf diese Frage]", docx_text(report))  # the corrected letter, with its gaps
        self.assertEqual(self.client.get(f"/api/runs/{self.store.latest_run(case, 'completed')['id']}/draft.docx").status_code, 404)  # no stale letter
        self.assertEqual(self.client.get(f"/api/cases/{case}/actions/{approved['version']}/bundle").status_code, 200)  # the approved version stays
        # undo: everything follows back, the handler's edit included, and the approval holds again (same version, premise)
        undone = self.post(f"/api/edits/{out['edit']['id']}/undo", {}, 200)
        self.assertEqual(undone["limits"], [])
        back = self.view(case)
        self.assertEqual((back["draft"]["version"], back["assessment"]["proposal"], back["completion"]["valid"]), (approved["version"], a["proposal"], True))
        self.assertIn(mine, back["draft"]["text"])
        self.assertEqual(self.row(case)["stand"]["bucket"], "versandbereit")

    def test_the_contrasting_variant_is_repaired_the_same_way(self):
        case = self.cases["e2"]
        self.ready(case)
        approved = self.approve(case)["approval"]
        out = self.post(f"/api/cases/{case}/edits", self.CONTRA, 201)
        view = self.view(case)
        self.assertEqual(view["assessment"]["proposal"], [])  # no deadline to set for a defect that is gone; she claims nothing
        self.assertEqual((view["completion"]["valid"], self.row(case)["stand"]["bucket"]), (False, "urteil"))
        self.assertNotEqual(view["draft"]["version"], approved["version"])
        self.assertNotIn("Zum Versand freigegeben", view["file_note"])
        self.post(f"/api/edits/{out['edit']['id']}/undo", {}, 200)
        back = self.view(case)
        self.assertEqual((back["draft"]["version"], back["completion"]["valid"]), (approved["version"], True))

    def test_a_jurist_mark_on_what_the_unsent_letter_rests_on_makes_the_approval_stale_with_the_same_bytes(self):
        case = self.cases["e1"]
        self.ready(case)
        out = self.approve(case)
        self.assertIn("mietmangel-handler:rahmen.conditions", out["approval"]["relies"])  # the assessment's frame («@conditions»)
        self.post("/api/review/mietmangel-handler/rahmen.conditions", {"mark": "frage", "comment": "Belegpflicht so allgemein richtig?"}, 201)
        view = self.view(case)
        self.assertEqual(view["draft"]["version"], out["approval"]["version"])  # the same bytes
        self.assertEqual((view["completion"]["valid"], view["completion"]["status"]), (False, "Freigabe veraltet: Grundlage in Prüfung"))
        self.assertEqual(self.row(case)["stand"]["bucket"], "urteil")
        self.assertNotIn("Zum Versand freigegeben", view["file_note"])

    def test_a_sent_version_is_kept_and_reconciled_never_unsent(self):
        case = self.cases["e1"]
        self.ready(case)
        approved = self.approve(case)
        self.dispatch(case, approved["approval"]["version"])
        blob = self.client.get(f"/api/cases/{case}/actions/{approved['approval']['version']}/bundle").content
        out = self.post(f"/api/cases/{case}/edits", self.CONTRA, 201)
        st = self.view(case)["completion"]
        self.assertTrue(st["status"].startswith("versandt mit früherem Stand – prüfen: "), st["status"])
        self.assertEqual(st["bar"]["reconcile"], approved["approval"]["version"])
        undone = self.post(f"/api/edits/{out['edit']['id']}/undo", {}, 200)  # undo cannot unsend
        self.assertEqual(len(self.events(case, "action.dispatched")), 1)
        self.assertEqual(self.client.get(f"/api/cases/{case}/actions/{approved['approval']['version']}/bundle").content, blob)  # kept as it went out
        self.assertEqual(undone["limits"], [])  # the dispatch came before the correction: nothing after it to name
        self.post(f"/api/cases/{case}/edits", self.CONTRA, 201)
        self.post(f"/api/cases/{case}/actions/reconcile", {"version": approved["approval"]["version"], "op_id": "op-reconcile-1"}, 200)
        st = self.view(case)["completion"]
        self.assertFalse(str(st["status"] or "").startswith("versandt mit früherem Stand"), st["status"])
        self.assertEqual(len(self.events(case, "action.dispatched")), 1)


# -- (d) every labelled perturbation ends without duplicates or lost edits ----------------------------------------------------

class PerturbationTests(Episode):
    MINE = "Vielen Dank für Ihre Unterlagen und Ihre Geduld."

    def kept(self, case, entries):
        """No entry twice, none lost, every file once, the handler's edit and decisions still there."""
        numbers = self.entries(case)
        self.assertEqual(len(numbers), len(set(numbers)))
        self.assertTrue(set(entries) <= set(numbers), (entries, numbers))
        shas = [f["sha256"] for f in self.store.list_files(case)]
        self.assertEqual(len(shas), len(set(shas)))
        self.assertIn(self.MINE, self.view(case)["draft"]["text"])
        self.assertIn(("deckung", "bestätigt"), {(e["args"]["fact"], e["args"]["value"]) for e in self.store.list_edits(case) if e["op"] == "set_fact"})

    def started(self):
        case = self.cases["e1"]
        self.edit_part(case, "Vielen Dank", self.MINE)
        self.decide(case, "deckung", "bestätigt")
        return case, self.entries(case)

    def test_p_dup_the_same_reply_again_is_refused_and_starts_nothing(self):
        case, entries = self.started()
        runs = len(self.store._all("select id from runs where case_id=?", case))
        r = self.client.post(f"/api/cases/{case}/files", files=[("files", (EP.perturbations["P-dup"].name, EP.perturbations["P-dup"].data, "message/rfc822"))])
        self.assertEqual(r.status_code, 409, r.text)
        self.assertEqual(len(self.store._all("select id from runs where case_id=?", case)), runs)
        self.kept(case, entries)
        self.assertEqual(self.entries(case), entries)

    def test_p_contra_after_approval_and_its_undo_lose_nothing(self):
        case, entries = self.started()
        self.adopt(case)
        self.decide(case, "aussichten", "genügend")
        self.approve(case)
        out = self.post(f"/api/cases/{case}/edits", EP.perturbations["P-contra"].edit, 201)
        self.kept(case, entries)
        self.post(f"/api/edits/{out['edit']['id']}/undo", {}, 200)
        self.kept(case, entries)
        self.assertEqual(self.entries(case), entries)

    def test_p_retract_the_promise_then_the_withdrawal_ends_the_claim_and_keeps_the_rest(self):
        case, entries = self.started()
        p = EP.perturbations["P-retract"]
        promise, withdrawal = p.turns(max(entries) + 1)
        for (name, data), turns, placeholder in zip(p.files, (promise, withdrawal), p.ids):
            self.upload(case, [(name, data)])
            self.update(case, turns, {placeholder: name})
        view = self.view(case)
        self.assertEqual(view["assessment"]["residual"], [])  # the claim is withdrawn: no receipts asked any more
        self.assertNotIn("schadenersatz", view["assessment"]["proposal"])
        self.assertEqual(asked_lines(view["draft"]["text"]), [])
        self.kept(case, entries + [max(entries) + 1, max(entries) + 2])

    def test_p_refuse_the_reply_without_receipts_ends_the_wait_once(self):
        case, ns = self.cases["d21"], self.ns["d21"]
        p = ns.perturbations["P-refuse"]
        n = self.dispatched_n(case)
        self.upload(case, p.files)
        self.update(case, p.turns(self.first_free(case), n), {"fr": p.files[0][0]})
        view = self.view(case)
        self.assertEqual((view["completion"]["last"]["consequence"]["kind"], self.row(case)["stand"]["text"]), ("refused", f"abgelehnt: {RECEIPTS}"))
        self.assertEqual(len([e for e in self.store.list_edits(case) if e["op"] == "add_dispatch"]), 1)
        numbers = self.entries(case)
        self.assertEqual(len(numbers), len(set(numbers)))

    def test_p_fail_a_failed_update_keeps_everything_and_the_retry_reads_once(self):
        case, entries = self.started()
        p = EP.perturbations["P-retract"]
        promise, _ = p.turns(max(entries) + 1)
        self.upload(case, p.files[:1])
        self.update(case, None, None, model=EP.perturbations["P-fail"].model(), expect="failed")
        self.assertEqual((self.row(case)["stand"]["bucket"], self.row(case)["stand"]["text"]), ("fehlgeschlagen", "Aktualisierung fehlgeschlagen"))
        self.kept(case, entries)
        self.update(case, promise, {p.ids[0]: p.files[0][0]})
        self.kept(case, entries + [max(entries) + 1])

    def test_p_restart_an_update_left_running_is_resumed_once_and_reads_nothing_twice(self):
        case, entries = self.started()
        p = EP.perturbations["P-retract"]
        promise, _ = p.turns(max(entries) + 1)
        self.upload(case, p.files[:1])
        left = EP.perturbations["P-restart"].leave(self.store, case)
        self.client.app.state.runs.shutdown()
        self.client.app.state.store.close()
        models, ready = [], threading.Event()

        def factory(token=None):  # the resumed update waits until the restarted service is in place
            ready.wait(10)
            models.append(episode.update_model(self.store, case, promise, {p.ids[0]: p.files[0][0]}))
            return models[-1]
        self.client = self.app(model_factory=factory, CASEPATH_AUTO_UPDATE="1")  # the service started again on its store
        ready.set()
        runs = self.client.app.state.runs
        self.assertEqual(self.store.get_run(left["id"])["status"], "interrupted")
        resumed, = runs.resumed
        done = episode.wait(self.store, resumed)
        self.assertEqual((done["status"], len(models)), ("completed", 1), done.get("error"))
        self.kept(case, entries + [max(entries) + 1])


# -- (e) no Knowledge, (f) item hashes and the frozen study copies ---------------------------------------------------------

class GuardTests(Episode):
    """The episode's whole path on E1, step by step: the replies read, a refused duplicate, a text edit, the three decisions,
    «Freigeben», the downloads, a jurist's mark and «Erneut freigeben», «Versandt am», «Mangel behoben» and its undo."""

    def knowledge(self):
        return sorted((k["id"], k["status"], k.get("version")) for k in self.store.list_knowledge())

    def walk(self):
        case = self.cases["e1"]
        hashes = [("nach den Antworten", self.view(case)["items_sha256"])]
        step = lambda name: hashes.append((name, self.view(case)["items_sha256"]))
        self.client.post(f"/api/cases/{case}/files", files=[("files", (EP.perturbations["P-dup"].name, EP.perturbations["P-dup"].data, "message/rfc822"))])
        step("P-dup abgewiesen")
        self.edit_part(case, "Vielen Dank", "Vielen Dank für Ihre Unterlagen und Ihre Geduld.")
        step("Brieftext bearbeitet")
        self.decide(case, "deckung", "bestätigt")
        step("Deckung")
        self.adopt(case)
        step("Empfehlung")
        self.decide(case, "aussichten", "genügend")
        step("Erfolgsaussichten")
        approved = self.approve(case)["approval"]
        step("Freigeben")
        for path in (f"/api/cases/{case}/actions/{approved['version']}/bundle", f"/api/cases/{case}/report.docx", f"/api/cases/{case}/actions/{approved['version']}/docx/A5"):
            self.assertEqual(self.client.get(path).status_code, 200, path)
        step("Downloads")
        self.post("/api/review/mietmangel-handler/rahmen.conditions", {"mark": "frage", "comment": "Belegpflicht so allgemein richtig?"}, 201)
        step("Juristische Markierung")
        self.approve(case, op="op-approve-2")
        step("Erneut freigeben")
        self.dispatch(case, self.view(case)["draft"]["version"])
        step("Versandt am")
        out = self.post(f"/api/cases/{case}/edits", EP.perturbations["P-contra"].edit, 201)
        step("Mangel behoben")
        self.post(f"/api/edits/{out['edit']['id']}/undo", {}, 200)
        step("rückgängig")
        return hashes

    def test_item_hash_changes_are_the_declared_ones(self):
        hashes = self.walk()
        # declared: the item list changes with what the handler decides about the case, with the dispatch (the account's
        # entry and the next step) and with the correction and its undo; never with a refused upload, a text edit, the
        # adoption (an event, not an item), an approval, a download or a jurist's mark (the approval's validity only)
        changed = [name for (name, h), (_, before) in zip(hashes[1:], hashes) if h != before]
        self.assertEqual(changed, ["Deckung", "Erfolgsaussichten", "Versandt am", "Mangel behoben", "rückgängig"])
        self.assertEqual(hashes[-1][1], hashes[-3][1])  # the undo restores the list as it was

    def test_the_episode_activates_no_knowledge(self):
        knowledge = self.knowledge()
        self.walk()
        self.assertEqual(self.knowledge(), knowledge)  # nothing proposed, nothing activated, nothing retired
        self.assertFalse([k for k in self.store.list_knowledge() if k["status"] == "active" and (k["id"], "active", k.get("version")) not in knowledge])

    def test_every_frozen_study_copy_keeps_its_hash_in_the_service_and_after_the_candidates_startup(self):
        self.walk()
        self.assertEqual(frozen.check(self.store, self.client.app.state.runs.catalogue), {self.cases["study"]: "equal", self.cases["frozen"]: "equal"})
        self.assertTrue(self.client.get(f"/api/cases/{self.cases['study']}/study-check").json()["ok"])
        self.client.app.state.runs.shutdown()
        self.client.app.state.store.close()
        with tempfile.TemporaryDirectory() as tmp:  # the release check on a copy of the store, as the notebook copies the volume's
            shutil.copyfile(self.root / "data" / "casepath.db", Path(tmp) / "casepath.db")
            out = frozen.preflight(Path(tmp), Catalogue.load(None), "0123456789ab")
        self.assertEqual((out["cases"], out["startup"]), ({self.cases["study"]: "equal", self.cases["frozen"]: "equal"}, {"ran": "create_app", "knowledge_added": 0}))
        self.assertEqual(frozen.lines(out)[-1], "deploy: the frozen study is unchanged")
        self.client = self.app()


if __name__ == "__main__":
    unittest.main()
