"""Supervising the prepared work: the decisions of a step as one set, a correction made in one action and said in
general afterwards, the call about an offer, the letter that went out read in place, and what a letter's review lists.

Model-free: the episode's synthetic case after its replies (tests/test_episode.py), the update tests' offer
(tests/test_offer_stance.py) and the Knowledge gate's prepared cases (tests/test_knowledge_gate.py)."""
from pathlib import Path
import unittest

from casepath.process import completion, live
from tests import test_offer_stance
from tests.test_episode import Episode
from tests.test_knowledge_gate import Gate

SCRIPT = (Path(__file__).parents[1] / "casepath" / "web" / "ui" / "assets" / "casepath.js").read_text(encoding="utf-8")
STYLE = (Path(__file__).parents[1] / "casepath" / "web" / "ui" / "assets" / "casepath.css").read_text(encoding="utf-8")


class DecisionSetTests(Episode):
    """The three decisions before an assessment is approved are one set: open, taken, and changed where they stand."""

    def state(self, case):
        st = self.view(case)["completion"]
        return st["decisions"], [(d["key"], d["value"]) for d in st["decided"]]

    def test_the_card_knows_every_decision_of_the_step_before_the_first_is_taken(self):
        case = self.cases["e1"]
        self.assertEqual(self.state(case), (["Deckung", "Empfehlung", "Erfolgsaussichten"], []))

    def test_each_decision_taken_stays_in_the_set_with_its_answer_and_its_undo(self):
        case = self.cases["e1"]
        self.decide(case, "deckung", "bestätigt", reason="6 Punkte laut Police, nicht einzeln bestätigt")
        self.assertEqual(self.state(case), (["Empfehlung", "Erfolgsaussichten"], [("deckung", "bestätigt")]))
        self.adopt(case)
        self.assertEqual(self.state(case), (["Erfolgsaussichten"], [("deckung", "bestätigt"), ("empfehlung", "übernommen")]))
        self.decide(case, "aussichten", "genügend")
        open_, taken = self.state(case)
        self.assertEqual((open_, taken), ([], [("deckung", "bestätigt"), ("empfehlung", "übernommen"), ("aussichten", "genügend")]))  # the order the card asks them
        rows = self.view(case)["completion"]["decided"]
        self.assertTrue(all(r["by"] and r["at"] for r in rows))
        cover = next(r for r in rows if r["key"] == "deckung")
        self.assertEqual(self.store.get_edit(cover["edit"])["reason"], "6 Punkte laut Police, nicht einzeln bestätigt")  # what the confirmation covered, kept with it
        # changed where it stands: the decision's own edit undone, and the card asks it again
        self.assertEqual(self.client.post(f"/api/edits/{cover['edit']}/undo").status_code, 200)
        open_, taken = self.state(case)
        self.assertEqual((open_, [k for k, _ in taken]), (["Deckung"], ["empfehlung", "aussichten"]))

    def test_an_adopted_recommendation_is_taken_back_and_asked_again(self):
        case = self.cases["e1"]
        self.decide(case, "deckung", "bestätigt")
        refused = self.client.delete(f"/api/cases/{case}/recommendation")
        self.assertEqual((refused.status_code, refused.json()["detail"]), (409, "Für diesen Schritt ist keine Empfehlung übernommen."))
        self.adopt(case)
        self.assertEqual(self.client.delete(f"/api/cases/{case}/recommendation").status_code, 200)
        view = self.view(case)
        self.assertEqual((view["completion"]["decisions"], view["screen"]["decision"]["key"]), (["Empfehlung", "Erfolgsaussichten"], "empfehlung"))
        log = [r["what"] for r in view["verlauf"] if r["kind"] == "gesture"]
        self.assertEqual(log[-1], "Empfehlung zurückgenommen")
        self.assertTrue(log[-2].startswith("Empfehlung übernommen: ") and "_" not in log[-2], log[-2])  # the ways in words, not their ids

    def test_what_a_step_settles_by_itself_is_no_row_and_a_study_copy_has_none(self):
        facts = {"deckung": "bestätigt"}
        self.assertEqual(completion.decided({"kind": "A5", "form": "A5", "needs": []}, facts, None, edits=[]), [])  # answered, but by no edit of a person
        undone = [{"id": "ed_1", "op": "set_fact", "args": {"fact": "deckung", "value": "bestätigt"}, "status": "undone"}]
        self.assertEqual(completion.decided({"kind": "A5", "form": "A5", "needs": []}, facts, None, edits=undone), [])

    def test_the_screen_shows_the_set_and_names_what_confirming_the_cover_includes(self):
        strip = SCRIPT[SCRIPT.index("function decisionsStrip(dec, primary)"):SCRIPT.index("function decisionLine(dec, primary)")]
        self.assertIn("st.decided", strip)
        self.assertIn("st.decisions", strip)
        self.assertIn("data-decided-undo", strip)
        self.assertIn("data-decided-withdraw", strip)
        self.assertIn("nur die Police klärt", SCRIPT)
        self.assertIn("laut Police, nicht einzeln bestätigt", SCRIPT)


class LetterElementsTests(Episode):
    def test_a_letter_that_is_no_assessment_rests_on_no_answer_or_recommendation(self):
        draft = {"kind": "A7", "form": "A7", "text": "Statusanfrage", "required": [], "also": []}
        brief = {"assessment": False, "chosen": ["frist_beseitigung", "schadenersatz"], "questions": [{"state": "beantwortet", "intent": "hinterlegen", "points": ["hinterlegung"]}],
                 "in_case": [{"key": "fall.besteht"}]}
        process = {"id": "mietmangel-handler"}
        self.assertEqual([k for k in completion.relied_elements(draft, brief, process) if "empfehlung" in k or "antwort" in k or "fall." in k], [])
        said = completion.relied_elements({**draft, "kind": "A5", "form": "A5"}, {**brief, "assessment": True}, process)
        self.assertIn("mietmangel-handler:empfehlung.schadenersatz", said)
        self.assertIn("mietmangel-handler:antwort.hinterlegung.hinterlegen", said)
        self.assertIn("mietmangel-handler:fall.besteht", said)

    def test_what_went_out_is_read_in_place_from_the_package_itself(self):
        case = self.cases["e1"]
        view = self.ready(case)
        approval = self.approve(case)["approval"]
        self.dispatch(case, approval["version"])
        letter = self.client.get(f"/api/cases/{case}/actions/{approval['version']}/letter")
        self.assertEqual(letter.status_code, 200, letter.text)
        body = letter.json()
        self.assertEqual((body["title"], body["approved_by"]), (approval["title"], approval["expert"]))
        self.assertEqual(body["text"].split(), view["draft"]["text"].split())  # the approved text, read back from the stored .docx
        self.assertEqual([a["kind"] for a in body["also"]], [a["kind"] for a in approval["also"]])
        self.assertEqual(self.client.get(f"/api/cases/{case}/actions/{'0' * 64}/letter").status_code, 404)
        self.assertIn('id="sent-open"', SCRIPT)
        self.assertIn("/letter`", SCRIPT)


class CorrectionTests(Gate):
    """One more document is one action; that it should hold for similar cases is said afterwards, and only proposed."""

    def add(self, case_id, title="Wohnungsabnahmeprotokoll"):
        made = self.client.post(f"/api/cases/{case_id}/edits", json={"op": "add_document", "args": {"title": title, "why": "von der Fallbearbeitung verlangt", "step": "klaeren"},
                                                                      "reason": "", "reason_code": "none", "recheck": False})
        self.assertEqual(made.status_code, 201, made.text)
        return made.json()

    def test_a_document_is_requested_without_a_reason_and_teaches_nothing_by_itself(self):
        case = self.prepared("Fall A (synthetisch)")
        made = self.add(case["id"])
        self.assertIsNone(made["knowledge"])
        view = self.client.get(f"/api/cases/{case['id']}").json()
        self.assertIn("– Wohnungsabnahmeprotokoll", view["draft"]["text"])
        # what the change moved is said as the line it added, and the log names the document, not the step it was added at
        letter = next(c for c in made["consequences"]["changes"] if c["what"] == "Brieftext")
        self.assertEqual((letter["before"], letter["after"]), ([], ["– Wohnungsabnahmeprotokoll"]))
        self.assertEqual([r["what"] for r in view["verlauf"] if r["kind"] == "gesture"][-1], "Unterlage verlangt: Wohnungsabnahmeprotokoll")
        self.assertEqual([k for k in self.store.list_knowledge() if (k.get("origin") or {}).get("kind") == "case_edit"], [])

    def test_said_in_general_afterwards_it_is_proposed_once_and_changes_no_other_case(self):
        a, b = self.prepared("Fall A (synthetisch)"), self.prepared("Fall B (synthetisch)")
        made = self.add(a["id"])
        said = self.client.post(f"/api/edits/{made['edit']['id']}/general")
        self.assertEqual(said.status_code, 201, said.text)
        item = said.json()["knowledge"]
        self.assertEqual((item["status"], item["content"]["title"], item["origin"]["edit_id"]), ("candidate", "Wohnungsabnahmeprotokoll", made["edit"]["id"]))
        self.assertEqual(item["replay"]["version"], item["version"])  # proposed with the replay of its version: a reviewer sees its effect
        again = self.client.post(f"/api/edits/{made['edit']['id']}/general").json()["knowledge"]
        self.assertEqual(again["id"], item["id"])  # asked twice, proposed once
        self.assertNotIn("Wohnungsabnahmeprotokoll", self.client.get(f"/api/cases/{b['id']}").json()["draft"]["text"])  # a proposal changes no case

    def test_an_undone_change_cannot_be_said_in_general(self):
        case = self.prepared("Fall A (synthetisch)")
        made = self.add(case["id"])
        self.assertEqual(self.client.post(f"/api/edits/{made['edit']['id']}/undo").status_code, 200)
        refused = self.client.post(f"/api/edits/{made['edit']['id']}/general")
        self.assertEqual((refused.status_code, refused.json()["detail"]), (409, "Diese Änderung gilt nicht mehr."))

    def test_the_screen_asks_no_reason_before_a_change_and_lists_changes_above_the_letter(self):
        self.assertNotIn("data-add-doc-reason", SCRIPT)
        self.assertNotIn('T("Why?", "Warum?")', SCRIPT)
        self.assertIn("data-add-general", SCRIPT)
        strip = SCRIPT[SCRIPT.index("function changesStrip()"):SCRIPT.index("function sideChangeLine()")]
        self.assertIn('(S.data.verlauf || []).filter((r) => r.kind === "gesture" && r.undo', strip)  # read from the case's own log
        self.assertIn("data-change-undo", strip)


class CallSheetTests(unittest.TestCase):
    """The call about an offer: the offer and what to ask stand in the card, and the note is filed with the customer."""
    _base = test_offer_stance.OfferStanceTests  # its synthetic offer, without running its tests a second time
    setUp, tearDown, post, view, asked = _base.setUp, _base.tearDown, _base.post, _base.view, _base.asked

    def test_the_step_that_asks_the_customer_carries_the_offer_and_the_questions(self):
        view, action = self.view()
        self.assertEqual(action["action"], "A2")
        sheet = view["draft"]["call"]
        self.assertEqual(sheet["questions"], live.stances()["angebot"]["call"])
        self.assertEqual(len(sheet["questions"]), 3)
        self.assertIn("05.11.2026", sheet["offer"])
        self.assertNotRegex(sheet["offer"], r"\d{4}-\d{2}-\d{2}")  # dates as a letter writes them
        self.asked()
        self.assertNotIn("call", self.view()[0]["draft"])  # once the customer was asked, the card asks the one question

    def test_no_call_sheet_for_anything_but_an_offer(self):
        self.assertIsNone(live.call_sheet({"kind": "kostennote", "value": "x"}))
        self.assertIsNone(live.call_sheet(None))

    def test_the_note_of_that_step_is_with_the_customer_and_written_in_the_card(self):
        self.assertIn('act && act.action === "A2" && draft.form !== "A2_bericht" ? "kunde"', SCRIPT)
        self.assertIn("S.noteInCard", SCRIPT)


class WalkTests(Gate):
    """Working through the cases: approval and copy are one gesture, a settled case offers the next one, and a letter
    changed after its approval is approved again before it is marked as sent."""

    def test_approval_copies_and_a_settled_case_leads_on(self):
        approve = SCRIPT[SCRIPT.index("async function approve()"):SCRIPT.index("function letterHtml(text)")]
        self.assertIn("copyLetter(active.main ? null : active.kind, true)", approve)
        self.assertIn("Freigeben und kopieren", SCRIPT)
        self.assertIn('id="next-case"', SCRIPT)
        self.assertIn('id="walk-start"', SCRIPT)
        self.assertIn('id="skip-case"', SCRIPT)
        walk = SCRIPT[SCRIPT.index("async function nextCase(fresh)"):SCRIPT.index("function bucketTables")]
        self.assertIn("passed.includes(c.id)", walk)  # a case passed is not offered twice in one walk

    def test_a_stale_approval_offers_no_bare_dispatch(self):
        stale = SCRIPT[SCRIPT.index('if (bar.kind === "stale") {'):SCRIPT.index('if (bar.kind === "dispatch") {')]
        self.assertIn('S.staleSent === id', stale)
        self.assertIn('id="stale-sent"', stale)
        self.assertIn("reconcileLine()", SCRIPT)

    def test_the_page_scrolls_as_one_document(self):
        self.assertNotRegex(STYLE, r"\.cp-letter\{[^}]*overflow:auto")
        self.assertNotRegex(STYLE, r"\.cp-decide-more\{[^}]*max-height")
        self.assertRegex(STYLE, r"\.cp-prepared>footer\.cp-bar\{position:sticky;bottom:0")
        self.assertIn("el.style.minHeight", SCRIPT)

    def test_the_counts_of_today_narrow_the_list(self):
        self.assertIn("data-today-filter", SCRIPT)
        self.assertIn("const LIST_FILTERS", SCRIPT)
        self.assertIn('class="cp-week"', SCRIPT)   # the working week ahead: what falls due on each of the next five working days
        self.assertIn("day:", SCRIPT)
        self.assertNotIn("data-today-bucket", SCRIPT)

    def test_the_jurists_state_is_not_said_in_the_handlers_word(self):
        area = SCRIPT[SCRIPT.index("function areaLine(d)"):SCRIPT.index("function markInReview()")]
        self.assertIn('"juristisch noch nicht geprüft"', area)
        self.assertIn("r.of && S.mayReview", area)  # the element count is the reviewers' entry, not every handler's line


class DayTests(Gate):
    """«Heute» says how far the reader's own day has come: the cases they sent a letter in or closed today, each once."""

    def test_the_day_counts_the_readers_own_cases_sent_or_closed_today(self):
        a, b = self.prepared("Fall A (synthetisch)"), self.prepared("Fall B (synthetisch)")
        self.assertEqual(self.client.get("/api/today").json()["done"]["cases"], 0)
        approval = self.approve(a["id"], "op-approve-day")
        sent = self.client.post(f"/api/cases/{a['id']}/actions/dispatch", json={"version": approval["version"], "date": completion.swiss_today().isoformat(),
                                                                               "channel": "email", "op_id": "op-dispatch-day"})
        self.assertEqual(sent.status_code, 200, sent.text)
        done = self.client.get("/api/today").json()["done"]
        self.assertEqual((done["cases"], done["sent"], done["closed"], done["day"]), (1, 1, 0, completion.swiss_today().isoformat()))
        self.assertIn("since.done", SCRIPT)
        self.assertIn("data-day", SCRIPT)


class CraftTests(unittest.TestCase):
    """How it looks and moves: one accent, sheets on a canvas, movement only where something changed, none on request."""

    def test_motion_is_short_marks_a_change_and_stops_for_readers_who_ask(self):
        self.assertIn("@media (prefers-reduced-motion: reduce)", STYLE)
        self.assertIn("function barChanged(kind)", SCRIPT)   # the bar moves when its state changes, never on a mere re-render
        self.assertIn("S.arrive = S.arriveNext", SCRIPT)     # a case arrives once; from the right when the reader went on
        self.assertIn("S.listFresh", SCRIPT)                 # the list arrives once per visit, not on every keystroke
        longest = max(float(x) for x in __import__("re").findall(r"animation: cp-(?:rise|pop|sheet-in|sheet-next|draw|underline)\b[^;]*? (\.\d+)s", STYLE))
        self.assertLessEqual(longest, 0.6)

    def test_the_ground_is_white_and_a_choice_slides_to_its_place(self):
        self.assertIn(":root { --ground: #fff;", STYLE)
        self.assertIn("html, body { background: var(--ground); }", STYLE)
        self.assertIn("function glide()", SCRIPT)                       # the fill of the tabs, the filter and the letters slides
        self.assertIn('[".cp-tabs", \'.cp-tab[aria-current="page"]\']', SCRIPT)
        self.assertIn("|| reducedMotion() ||", SCRIPT)                  # and stands still for a reader who asked

    def test_a_tab_arrives_once_and_what_casepath_did_is_told_when_it_is_done(self):
        self.assertIn("S.tabIn = true;", SCRIPT)                        # set where the tab changes, used by the one render after
        self.assertIn('${tabIn ? " cp-tab-in" : ""}', SCRIPT)
        self.assertIn("const pageIn = () => { const now = S.pageIn; S.pageIn = false;", SCRIPT)
        self.assertIn(".cp-tab-in .cp-steps > li { animation: cp-rise-in", STYLE)   # Prozess: the path is walked
        self.assertIn("function workTrail(fresh)", SCRIPT)              # files read, facts found, history, documents, letter, decisions
        self.assertIn("const open = fresh || S.trailOpen || S.storyOpen === S.route.id;", SCRIPT)     # shown when it finishes under the reader's eyes, else one press away
        self.assertIn('id="trail-open"', SCRIPT)
        self.assertIn("`#/case/${id}/document_finder`", SCRIPT)         # each step leads to where it can be checked

    def test_a_day_of_the_week_pressed_narrows_the_list_to_that_day(self):
        self.assertIn('const only = dayOnly ? (c) => Boolean(c.due && c.due.date === dayOnly', SCRIPT)
        self.assertIn("S.rowsIn = true; renderCases(true);", SCRIPT)    # the rows come in again, the head stays
        self.assertIn("if (!(kept && S.listData && S.listData.lang === LANG)) {", SCRIPT)  # from the cases already here: at once

    def test_what_is_opened_is_read_from_its_top_and_a_menu_stays_on_its_page(self):
        self.assertIn("if (moved) window.scrollTo(0, 0);", SCRIPT)
        self.assertIn("if (moved) { S.moreOpen = false; S.overviewSource = false; }", SCRIPT)
        self.assertIn('if (event.key !== "Escape" || S.route.view !== "case" || !S.data) return;', SCRIPT)  # Esc leaves a menu or a small form
        self.assertIn("const fold = (text) => String(text || \"\").toLowerCase().normalize(\"NFD\")", SCRIPT)  # «larchenweg» finds «Lärchenweg»

    def test_the_case_is_shown_as_a_picture_built_from_its_real_state(self):
        assets = Path(__file__).parents[1] / "casepath" / "web" / "ui" / "assets"
        engine, look = (assets / "story.js").read_text(encoding="utf-8"), (assets / "story.css").read_text(encoding="utf-8")
        page = (assets.parent / "index.html").read_text(encoding="utf-8")
        self.assertIn('<script src="/assets/story.js" defer></script>', page)
        self.assertIn('<link rel="stylesheet" href="/assets/story.css">', page)
        self.assertIn("CasePathStory", engine)
        self.assertIn("prefers-reduced-motion", engine + look)            # a reader who asked for stillness gets each state, no travel
        self.assertNotIn("innerHTML =", engine.replace('innerHTML = ""', ""))  # what a case says is put in as text, never as markup
        # the picture is the case's own state: its files, the run's events in order, needs, knowledge, letter, decisions
        self.assertIn("function storyModel(events, live)", SCRIPT)
        for kind in ('e.kind === "fact.located"', 'e.kind === "document.recorded"', 'e.kind === "process.state"', 'e.kind === "record.recorded"'):
            self.assertIn(kind, SCRIPT)
        self.assertIn('edge(`file:${e.cite.file}`, nid, "cites", page(e.cite))', SCRIPT)   # a finding is joined to the passage it rests on
        self.assertIn('edge(kid, `need:${i.key}`, "learned")', SCRIPT)                     # what practice taught reaches the need it asks for
        # live while CasePath works, in a layer a redraw leaves standing; a replay one press from the prepared step
        self.assertIn('id="story" data-story="live"', SCRIPT)
        self.assertIn('layer.id = "cp-story-layer"', SCRIPT)
        self.assertIn("S.story.ctrl.update(storyModel(events, true));", SCRIPT)
        self.assertIn('id="story-open"', SCRIPT)
        self.assertIn("onOpen: (n) => openFromStory(n)", SCRIPT)                           # a node opens the real thing: its page or its row
        # each tab shows its own state with the same engine: the path with what decided it and its branches, the history
        # as who wrote to whom with a request joined to its answer, the documents with why each is asked and where it is
        for kind, build in (("process", "processStory"), ("history", "historyStory"), ("documents", "documentsStory")):
            self.assertIn(f'tabPicture("{kind}", ', SCRIPT)
            self.assertIn(f"function {build}()", SCRIPT)
        self.assertIn('ids.map((x) => k.edge(at, x, "branch"))', SCRIPT)                   # the ways on from the current step
        self.assertIn('learned.map((i) => k.edge(kid, `need:${i.key}`, "learned"))', SCRIPT)  # closed cases → what this case needs
        self.assertIn('localStorage.setItem("casepath.picture", shown ? "on" : "off")', SCRIPT)  # put away once, it stays away until asked for
        self.assertIn('opened.style.viewTransitionName = "cp-case"', SCRIPT)               # a case opened from the list grows out of its row
        self.assertIn(".cp-morph #case-title { view-transition-name: cp-case; }", STYLE)
        # Wissen: where each rule came from and the cases it was applied in since, one moment per case
        self.assertIn('tabPicture("knowledge", 380)', SCRIPT)
        self.assertIn('group.map((g) => k.edge(itemNode(g.e), to, "learned"))', SCRIPT)
        # the list: a case whose status changed since it was last on screen says what it was before
        self.assertIn("if (seen[c.id] && seen[c.id].text !== now.text) moved[c.id] = seen[c.id];", SCRIPT)
        self.assertIn('class="cp-muted cp-row-was"', SCRIPT)
        self.assertIn("if (grew) S.story.ctrl.play();", SCRIPT)                            # a change under the reader's eyes arrives as its own movement

    def test_the_keyboard_walks_the_list_and_takes_the_cards_one_primary(self):
        self.assertIn('["ArrowDown", "ArrowUp", "j", "k", "Enter"]', SCRIPT)
        self.assertIn('document.querySelector(".cp-prepared .cp-button.primary:not(:disabled)")', SCRIPT)
        self.assertIn("cp-row-on", STYLE)

    def test_the_walk_shows_where_the_reader_stands(self):
        self.assertIn("function walkPlace(id)", SCRIPT)
        self.assertIn(".cp-walkbar", STYLE)

    def test_a_case_at_rest_is_a_compact_sheet(self):
        self.assertIn("cp-resting", SCRIPT)
        self.assertIn(".cp-prepared.cp-resting { min-height: 0 !important; }", STYLE)

    def test_what_is_secondary_waits_folded_and_the_step_says_what_casepath_did(self):
        self.assertIn("function foldSide()", SCRIPT)          # «Der Fall» in lines: long sections fold to a name, a count, a first line
        self.assertIn('class="cp-segs-fold"', SCRIPT)         # a file's documents wait folded under it
        self.assertIn("function preparedBy()", SCRIPT)        # what CasePath did and when it finished, above the step
        self.assertIn("S.justFinished = here", SCRIPT)        # said in green when it finished while the reader watched
        self.assertIn("S.finishing = true", SCRIPT)            # and said for a moment on the stage, every step ticked, before the step arrives
        self.assertIn('class="cp-runline cp-work"', SCRIPT)    # at work: what it does, what it reads now, what it found so far
        self.assertIn("function enter(key)", SCRIPT)           # a moment plays once, when it happens, never on a mere refresh
        self.assertIn('data-head-open="news"', SCRIPT)        # the head is one sentence; what changed opens from it
        self.assertNotIn("linear-gradient", STYLE[STYLE.index("Craft layer"):])  # no ornament: flat colour, one accent
