"""Development probe: 16 hand-written tenancy claims whose defining event is denied, left open, or holds (controls).

    python3 build.py      # writes claims.json and references.json, then checks every reference

The texts below were written by hand (Claude, in the agent session of 2026-11-10) without any model call. Each reference
is computed as fresh/tenancy/generate.py computes it: the production engine with exact deferral
(harness/casepath_tenancy.py::plan_from_verified_exact) on the policy verdicts of the stated facts under the silence
policy (stated true -> true, stated false -> false, raised and left open -> unresolved, unmentioned branch fact ->
false, unmentioned defining event -> true). Development data only.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parent
sys.path.insert(0, str(TMIS / "harness"))
sys.path.insert(0, str(TMIS / "fresh" / "tenancy"))
import generate as G  # noqa: E402  (reference builder of the fresh data; importing it makes no model call)
from spec import ROUTING, SILENCE_CLAUSE  # noqa: E402
from casepath_api.assessment_grammar_v1 import FAMILY_FLAGS  # noqa: E402

LT, RI = "lease_termination_dispute", "rent_increase_dispute"

# kind: denied (defining event stated false), open (raised and left open), control (event holds).
# mode: how the event appears in the text: plain / passing / implied (denied); unknown (open); stated / implied (control).
# event: the fact state of the defining event recorded for the reference.
CLAIMS = [
    # ----------------------------------------------------------------- lease termination
    dict(slug="t1", family=LT, kind="denied", mode="plain", event="stated_false", flags=["family_home"],
         language="en", channel="email", canton="ZH", received_at="2026-11-02T09:14:00+01:00",
         subject="Landlord says he is ending our lease",
         body="""Dear Sir or Madam,

I am writing about our flat at Feldeggstrasse 12 in Uster, which we rent from Brändli Immobilien AG. Last Tuesday the property manager, Mr Vogt, called me and said the company is ending our lease at the end of March. I asked him to put this in writing. So far nothing has come: no letter, no e-mail, no form. I have checked our mailbox every day. To be clear, I have not received any written termination notice.

I live in the flat with my wife, Lena. We have been married for eleven years and this is our family home. Both of us are registered at this address.

I would like to know where I stand. Is a phone call like this valid? Should I do anything now, or wait for the letter? I do not want to miss a deadline because of a misunderstanding.

Kind regards,
Noah Kessler"""),
    dict(slug="t2", family=LT, kind="denied", mode="passing", event="stated_false", flags=["arrears", "extension_relevant"],
         language="de-CH", channel="portal", canton="SG", received_at="2026-11-03T18:40:00+01:00",
         subject="Kündigung wegen Mietrückstand",
         body="""Guten Tag

Ich miete seit 2017 eine 2.5-Zimmer-Wohnung an der Weiherstrasse 7 in Wil. Vermieterin ist die Toggenburg Wohnbau AG. Im Sommer konnte ich wegen Kurzarbeit zwei Monatsmieten nicht bezahlen. Die Verwaltung hat mir deshalb am Telefon gesagt, dass sie mir wegen dieser Mietrückstände kündigt (schriftlich ist bis heute nichts gekommen).

Mein grösstes Problem ist der Auszug. Meine Tochter geht hier in die vierte Klasse, und ich arbeite im Schichtbetrieb. In Wil ist es sehr schwierig, eine bezahlbare Wohnung zu finden. Ich habe mich schon auf sechs Wohnungen beworben, ohne Erfolg. Falls ich ausziehen muss, möchte ich auf jeden Fall eine Erstreckung des Mietverhältnisses verlangen, damit ich mehr Zeit für die Suche habe.

Können Sie mir sagen, wie ich jetzt vorgehen soll und welche Unterlagen Sie von mir brauchen?

Freundliche Grüsse
Selina Ammeter"""),
    dict(slug="t3", family=LT, kind="denied", mode="implied", event="stated_false", flags=["retaliation_screen"],
         language="en", channel="portal", canton="BE", received_at="2026-11-04T12:05:00+01:00",
         subject="Termination after my complaints",
         body="""Hello,

I rent a studio flat at Rosenbergweg 3 in Burgdorf from Emmental Liegenschaften GmbH. In September I wrote to them twice about water coming through the bathroom ceiling and asked for a rent reduction until it is repaired. They were not pleased. Two weeks ago the caretaker came by and told me at the door that the owner wants me out by the end of the year.

I am sure this is their answer to my complaints. I have lived here for nine years without any problem, and the only thing that changed is that I insisted on my rights as a tenant.

I am still waiting for the letter. The caretaker said it would "come from the office". Until then I do not really know which dates we are talking about.

What can I do against this? I want to contest it. Which papers will you need from me?

Best regards,
Marc Odermatt"""),
    dict(slug="t4", family=LT, kind="open", mode="unknown", event="open", flags=["family_home", "retaliation_screen"],
         language="de-CH", channel="email", canton="AG", received_at="2026-11-05T07:55:00+01:00",
         subject="Kündigung angeblich verschickt",
         body="""Sehr geehrte Damen und Herren

Meine Frau Ladina und ich wohnen seit 2015 in einer 4-Zimmer-Wohnung an der Mühlegasse 21 in Lenzburg. Es ist unsere Familienwohnung, wir sind beide hier angemeldet. Vermieterin ist die Seetal Immobilien AG.

Letzte Woche rief mich Frau Rüegg von der Verwaltung an und sagte, die Kündigung sei bereits verschickt. Bei uns ist nichts angekommen. Während eines Umbaus 2024 hatten wir der Verwaltung die Adresse meiner Mutter in Zofingen als Postadresse angegeben, und vielleicht ging der Brief dorthin. Meine Mutter ist verreist. Ob es überhaupt ein schriftliches Kündigungsschreiben gibt, weiss ich im Moment schlicht nicht.

Im Frühling haben wir bei der Schlichtungsbehörde eine Mietzinsherabsetzung verlangt und teilweise recht bekommen. Seither ist das Verhältnis zur Verwaltung sehr kühl. Wir sind überzeugt, dass die Kündigung eine Retourkutsche für dieses Verfahren ist.

Was sollen wir jetzt tun?

Mit freundlichen Grüssen
Gian Caduff"""),
    dict(slug="t5", family=LT, kind="open", mode="unknown", event="open", flags=["arrears"],
         language="en", channel="email", canton="TG", received_at="2026-11-05T16:20:00+01:00",
         subject="Termination because of rent arrears?",
         body="""Dear team,

I need advice about my flat at Bergstrasse 40 in Kreuzlingen. The landlord is Mr Walter Zürcher, a private owner. Earlier this year I fell behind with the rent for April and May after I lost my job; I have since paid part of it. Last week Mr Zürcher told me in the stairwell that he is terminating my lease because of the unpaid rent.

I do not know whether he has actually sent me a written termination. Our post goes into a shared mailbox for the whole building, and letters sometimes end up with other tenants or get lost. A notice for a registered letter could also have been taken by someone else. So there may be a letter, or there may not. I simply cannot say.

I would like to fight the termination if possible. What should I do first, and what will you need from me?

Kind regards,
Olivia Brunold"""),
    dict(slug="t6", family=LT, kind="control", mode="stated", event="stated_true", flags=["extension_relevant", "family_home"],
         language="de-CH", channel="portal", canton="ZH", received_at="2026-11-06T10:30:00+01:00",
         subject="Kündigung erhalten, Erstreckung",
         body="""Guten Tag

Am 3. November habe ich von der Limmattal Verwaltungen AG die schriftliche Kündigung unserer Wohnung an der Bachtelstrasse 9 in Wetzikon erhalten, auf dem amtlichen Formular und per Einschreiben. Das Mietverhältnis soll Ende März enden.

Ich wohne dort mit meinem Ehemann Raphael und unseren zwei Kindern. Die Wohnung ist unsere Familienwohnung.

Ein Auszug bis Ende März wäre für uns eine grosse Härte. Mein Mann ist seit einem Unfall auf den Rollstuhl angewiesen, und rollstuhlgängige Wohnungen sind in der Region kaum zu finden. Zudem gehen die Kinder hier zur Schule. Wir möchten deshalb eine Erstreckung des Mietverhältnisses beantragen.

Bitte teilen Sie mir mit, wie es weitergeht und welche Unterlagen Sie benötigen. Ich kann die Kündigung einscannen.

Freundliche Grüsse
Jasmin Rohrer"""),
    dict(slug="t7", family=LT, kind="control", mode="implied", event="unmentioned", flags=["arrears"],
         language="en", channel="email", canton="BL", received_at="2026-11-06T14:45:00+01:00",
         subject="Contesting the termination of my lease",
         body="""Dear Sir or Madam,

I want to contest the termination of my lease for the flat at Oberdorfstrasse 15 in Liestal. The landlord is Birseck Wohnen AG. The termination says the lease ends on 31 January, and the reason given is the unpaid rent for August and September.

I admit that I paid late. My employer paid my salary weeks late during a restructuring, and I could not cover the rent from my savings. But I paid both months in full by 10 October, with the late fees. I have rented this flat for six years and never had problems before.

I find the termination unfair and out of proportion. Can they really end my lease for this? What should I do now, and is there a deadline I have to keep? Please also tell me which documents you will need.

Kind regards,
Leonie Gasparini"""),
    dict(slug="t8", family=LT, kind="control", mode="implied", event="unmentioned", flags=["retaliation_screen", "extension_relevant"],
         language="de-CH", channel="email", canton="BE", received_at="2026-11-07T08:10:00+01:00",
         subject="Kündigung nach Beschwerden",
         body="""Sehr geehrte Damen und Herren

Die Kündigung meiner Wohnung an der Schützenmattstrasse 4 in Langenthal per Ende April kommt für mich völlig überraschend. Vermieterin ist die Oberaargau Immobilien GmbH. Eine Begründung wird nicht genannt.

Ich vermute aber stark, dass sie mit meinen Beschwerden zusammenhängt. Seit Mai habe ich mehrmals schriftlich verlangt, dass der defekte Lift repariert wird, und im September habe ich mich an die Schlichtungsbehörde gewandt. Kurz danach wurde mir gekündigt. Für mich ist das eine Rachekündigung.

Ich bin 78 Jahre alt und lebe seit 31 Jahren in dieser Wohnung. Eine neue Wohnung bis Ende April zu finden, ist für mich kaum möglich, zumal ich nach einer Hüftoperation noch schlecht gehe. Falls die Kündigung gültig bleibt, möchte ich deshalb eine Erstreckung beantragen.

Wie gehe ich vor?

Mit freundlichen Grüssen
Erika Lanz"""),
    # ----------------------------------------------------------------- rent increase
    dict(slug="r1", family=RI, kind="denied", mode="plain", event="stated_false", flags=["reference_rate"],
         language="de-CH", channel="email", canton="SG", received_at="2026-11-02T11:00:00+01:00",
         subject="Mündlich angekündigte Mietzinserhöhung",
         body="""Sehr geehrte Damen und Herren

Ich wohne in einer 3-Zimmer-Wohnung an der Rebgasse 11 in Rapperswil. Vermieterin ist die Zürichsee Wohnbau AG. Vor zehn Tagen hat mich der Hauswart im Treppenhaus angesprochen und gesagt, die Miete werde ab dem 1. April um rund 120 Franken steigen. Begründet hat er dies mit dem gestiegenen hypothekarischen Referenzzinssatz.

Eine schriftliche Mitteilung der Mietzinserhöhung habe ich nicht erhalten. Es gibt kein Formular, keinen Brief und keine E-Mail. Ich habe nur diese mündliche Aussage.

Ich bin unsicher, ob ich jetzt schon reagieren muss. Muss ich die Erhöhung bezahlen, wenn sie mir nur mündlich angekündigt wurde? Und läuft bereits eine Frist? Ich möchte nichts verpassen, aber auch nicht unnötig Streit anfangen.

Für eine kurze Einschätzung wäre ich dankbar.

Freundliche Grüsse
Fabienne Imhof"""),
    dict(slug="r2", family=RI, kind="denied", mode="passing", event="stated_false", flags=["renovation"],
         language="en", channel="portal", canton="LU", received_at="2026-11-03T20:15:00+01:00",
         subject="Rent increase after renovation",
         body="""Hello,

The owner of our building at Hofwiesenstrasse 6 in Sursee, Pilatus Residenz AG, replaced all windows and the facade insulation this summer. At the tenants' meeting in October the manager announced that our rents would go up by about 9 percent because of this renovation work, which he called a value-enhancing investment (he only said this at the meeting; nothing in writing has reached me). I pay CHF 1,640 a month at the moment.

I think the increase is far too high. The windows were old, yes, but in my opinion a large part of the work was simply overdue maintenance. I also wonder how they arrived at the percentage.

Could you tell me what my options are and how I should prepare? I would like to contest the increase if it is not justified.

Thank you,
Tobias Hürlimann"""),
    dict(slug="r3", family=RI, kind="denied", mode="implied", event="stated_false", flags=["reference_rate", "renovation"],
         language="de-CH", channel="portal", canton="TG", received_at="2026-11-04T19:30:00+01:00",
         subject="Angekündigte Mieterhöhung Siedlung Seerosenweg",
         body="""Guten Tag

Unsere Verwaltung, die Thurgau Liegenschaften AG, hat an der Mieterversammlung angekündigt, dass die Mietzinse in unserer Siedlung am Seerosenweg in Arbon steigen werden. Als Gründe nannte sie zwei Dinge: den höheren Referenzzinssatz und die Sanierung der Küchen und Bäder, die im Frühling abgeschlossen wurde.

Wir warten noch auf das Schreiben mit den genauen Zahlen. Herr Kunz von der Verwaltung meinte, es komme in den nächsten Wochen.

Ich zahle heute 1'480 Franken netto. Mehrere Nachbarn haben von einer Erhöhung um über 15 Prozent gehört. Das wäre für mich als Alleinerziehende kaum tragbar. Ich möchte mich vorbereiten und wissen, ob sich eine Anfechtung lohnen könnte und worauf ich achten muss.

Freundliche Grüsse
Nadia Gisler"""),
    dict(slug="r4", family=RI, kind="open", mode="unknown", event="open", flags=["renovation"],
         language="en", channel="email", canton="SZ", received_at="2026-11-05T09:40:00+01:00",
         subject="Rent increase - not sure I was notified",
         body="""Dear Sir or Madam,

I rent a flat at Seefeldstrasse 28 in Einsiedeln from Klosterhof Immobilien AG. In September the building got a new lift and new balconies. Last week a neighbour told me her rent is going up because of this renovation, and the property manager confirmed on the phone that the increase for all tenants is due to the renovation work.

I have not found anything in my letterbox. Until last year my post went to my former address in Schwyz, and I am not sure the manager ever updated it. A letter about my rent may be lying there, or perhaps none was sent to me at all. I honestly do not know whether a formal notification has been sent to me.

I would like to contest the increase if it is too high. What should I do now?

Kind regards,
Hannah Lüscher"""),
    dict(slug="r5", family=RI, kind="open", mode="unknown", event="open", flags=["reference_rate"],
         language="de-CH", channel="email", canton="AR", received_at="2026-11-06T13:25:00+01:00",
         subject="Mietzinserhöhung, Schreiben unauffindbar",
         body="""Sehr geehrte Damen und Herren

Seit vielen Jahren wohne ich an der Kronenstrasse 5 in Herisau, vermietet durch die Säntis Verwaltungs AG. Am Telefon sagte mir die Sachbearbeiterin kürzlich, mein Mietzins werde wegen des gestiegenen Referenzzinssatzes erhöht, und die Mitteilung sei unterwegs oder schon bei mir.

Ich finde aber kein solches Schreiben. Im Oktober war ich drei Wochen im Spital, und meine Nachbarin hat in dieser Zeit die Post geleert. Sie hat einige Briefe weggelegt, die wir noch nicht alle wiedergefunden haben; vielleicht war auch ein Abholschein für ein Einschreiben dabei. Ob mir eine formelle Mitteilung der Erhöhung zugestellt wurde, kann ich deshalb nicht sagen.

Ich möchte die Erhöhung prüfen lassen. Was muss ich jetzt unternehmen, und welche Fristen gelten?

Mit freundlichen Grüssen
Werner Tobler"""),
    dict(slug="r6", family=RI, kind="control", mode="stated", event="stated_true", flags=["reference_rate"],
         language="en", channel="email", canton="SO", received_at="2026-11-06T17:05:00+01:00",
         subject="Rent increase notice received",
         body="""Dear Sir or Madam,

On 28 October I received a letter from Aare Habitat AG, the manager of my flat at Ringstrasse 19 in Solothurn, notifying me of a rent increase on the official form. The rent is to rise from CHF 1,720 to CHF 1,805 per month from 1 February. The letter gives the rise in the mortgage reference interest rate as the reason.

I have checked the published rate myself, and I am not convinced the increase is calculated correctly. As far as I know, my rent was last adjusted many years ago, and it was never lowered when the rate fell.

I would like to contest the increase. Could you tell me what the deadline is and which documents you need from me? I can send a scan of the letter.

Best regards,
Daniel Fischbacher"""),
    dict(slug="r7", family=RI, kind="control", mode="implied", event="unmentioned", flags=["renovation"],
         language="de-CH", channel="portal", canton="AG", received_at="2026-11-07T10:50:00+01:00",
         subject="Anfechtung Mietzinserhöhung Grabenstrasse",
         body="""Guten Tag

Ich möchte die Mietzinserhöhung für meine Wohnung an der Grabenstrasse 14 in Brugg anfechten. Vermieterin ist die Habsburg Wohnen AG. Ab dem 1. März soll ich 210 Franken mehr bezahlen, also neu 1'890 Franken. Begründet wird die Erhöhung mit der Sanierung des Hauses: neue Fassade, neue Heizungsanlage und neue Fenster.

Ich bezweifle, dass dies alles wertvermehrend ist. Die alte Heizung war 35 Jahre alt und musste ohnehin ersetzt werden, das ist für mich normaler Unterhalt. Auch die Fenster waren am Ende ihrer Lebensdauer.

Wie hoch darf eine solche Erhöhung überhaupt sein? Und bis wann muss ich mich wehren? Ich möchte keine Frist verpassen.

Freundliche Grüsse
Jonas Pfister"""),
    dict(slug="r8", family=RI, kind="control", mode="implied", event="unmentioned", flags=["reference_rate", "renovation"],
         language="en", channel="portal", canton="TG", received_at="2026-11-07T15:35:00+01:00",
         subject="Contesting my rent increase",
         body="""Hello,

I am contesting the rent increase for my flat at Neugasse 8 in Weinfelden. The landlord is Mittelland Living AG. The increase takes effect on 1 April and brings my rent from CHF 2,050 to CHF 2,290 a month. Two reasons are given: the higher mortgage reference interest rate, and the renovation of the stairwell together with a new lift last year.

I accept that the reference rate went up. But the lift was mainly needed because the old one kept breaking down, so I am not sure it really adds value. I would also like to know whether some costs have been counted twice.

What are my chances, and what is the deadline to object? What should I prepare?

Regards,
Ana Morais"""),
]


def hid(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16]


def fact_states(c: dict) -> dict:
    routing = ROUTING[c["family"]]
    out = {routing: c["event"]}
    for f in FAMILY_FLAGS[c["family"]]:
        if f != routing:
            out[f] = "stated_true" if f in c["flags"] else "absent"
    return out


def verdicts(states: dict) -> dict:
    # stated_true and an unmentioned defining event -> true; stated_false and an absent branch fact -> false; open -> unresolved
    table = {"stated_true": "true", "unmentioned": "true", "stated_false": "false", "absent": "false", "open": "unresolved"}
    return {f: table[s] for f, s in states.items()}


def reference(c: dict, cid: str) -> dict:
    states = fact_states(c)
    pv = verdicts(states)
    verified = {"category": {"family": c["family"], "summary": "", "citations": []},
                "conditions": [{"flag": f, "verdict": v, "summary": "", "citations": []} for f, v in pv.items()],
                "documents": [], "steps": [], "item_rejections": []}
    plan = G.plan_from_verified_exact(cid, verified, [])
    docs = {d: G.state_name(r, None) for d, r in plan["document_states"].items()}
    routing = ROUTING[c["family"]]
    return {"claim_id": cid, "family": c["family"], "family_id": f"pfam_{c['family'][:2]}_{c['kind']}",
            "scenario": {f: f in c["flags"] for f in FAMILY_FLAGS[c["family"]] if f != routing},
            "implicit_flags": {routing: {"stated_false": False, "open": None}.get(c["event"], True)},
            "fact_states": states, "policy_verdicts": pv,
            "open_fact": {"flag": routing, "true_value": None} if c["event"] == "open" else None,
            "document_states": docs, "engine_routes": plan["document_states"], "questions": plan["questions"],
            "request_set": sorted(d for d, s in docs.items() if s in ("required_now", "supplied_insufficient")),
            "held_set": sorted(d for d, s in docs.items() if s == "held"),
            "answered": None, "attachments": [],
            "probe": {"kind": c["kind"], "mode": c["mode"], "slug": c["slug"], "language": c["language"],
                      "channel": c["channel"], "words": len(c["body"].split())},
            "silence_policy": SILENCE_CLAUSE,
            "engine": "casepath_api.causal_process_v1.evaluate via harness/casepath_tenancy.py::plan_from_verified_exact (supervaluation)"}


def packet(c: dict, cid: str) -> dict:
    return {"contract": {"name": "casepath_observable_claim", "version": "dev-probe-intake-only/1.0.0",
                         "rule": "Pass this object, and only this object, to downstream inference."},
            "submission": {"claim_id": cid, "channel": c["channel"], "language": c["language"],
                           "received_at": c["received_at"], "canton": c["canton"]},
            "customer_message": {"message_id": "pmsg_" + hid("dev-probe-message", c["slug"]), "subject": c["subject"],
                                 "body": c["body"], "sent_at": c["received_at"], "from_role": "customer",
                                 "to_role": "claims_inbox", "attachment_ids": []},
            "attachments": []}


def check(refs: dict) -> None:
    for cid, r in refs.items():
        k, words = r["probe"]["kind"], r["probe"]["words"]
        assert 100 <= words <= 200, (cid, words)
        if k == "denied":
            assert r["request_set"] == [] and r["held_set"] == [], cid
        elif k == "open":
            assert r["held_set"] and r["request_set"] == [], cid
        else:
            assert r["request_set"] and r["held_set"] == [], cid
    langs = [r["probe"]["language"] for r in refs.values()]
    assert langs.count("en") == langs.count("de-CH") == 8
    assert not any("ß" in c["body"] for c in CLAIMS)


def main() -> None:
    claims, refs = {}, {}
    for c in CLAIMS:
        cid = "pcl_" + hid("dev-probe-claim", c["slug"])
        claims[cid] = packet(c, cid)
        refs[cid] = reference(c, cid)
    check(refs)
    (HERE / "claims.json").write_text(json.dumps(claims, ensure_ascii=False, indent=1) + "\n")
    (HERE / "references.json").write_text(json.dumps(refs, ensure_ascii=False, indent=1) + "\n")
    for cid, r in refs.items():
        p = r["probe"]
        print(cid, p["slug"], r["family"][:5], p["kind"], p["mode"], p["language"], p["words"], "words",
              "req", len(r["request_set"]), "held", len(r["held_set"]))


if __name__ == "__main__":
    main()
