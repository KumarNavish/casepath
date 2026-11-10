"""Eight new theft stories (ids 8-15) for the fresh2 confirmatory data.

Each story is a case text in a different form (broker's letter, intake note, claim form completed by a relative,
loss adjuster's report, lawyer's letter, social worker's e-mail, call log, handover note) with its own setting,
stolen objects, people and policy details. The nine condition sentences of the frozen source contract are
embedded verbatim at the marked places «KEY»; their position and the surrounding text differ between stories.
The sentences themselves are fixed by the contract (STATE_TEXT in the released construction script) and are
substituted by build_theft.py: the 'off' text has every condition false, an 'on' text replaces one false sentence
by its true sentence, an 'unresolved' text replaces it by the open-condition sentence of harness/theft_data.py.

Surrounding detail is written to be compatible with both values of every condition and with the open-condition
sentences: no phone or SIM-bearing device is named, no bicycle is excluded or named, the list of stolen items is
never closed, no contractor or third party is mentioned, no repair, valuation dispute, insurer demand, decision or
recovery is described.

CONTEXT is the one-sentence setting passed to the released construction script (as the four new contexts of
fresh/ were) to check that the reference depends on the condition only.
"""
from __future__ import annotations

KEYS = {
    "scheduled": "PR_scheduled_valuable_1000",
    "bicycle": "PR_bicycle_claimed",
    "sim": "PR_sim_card_stolen",
    "third": "PR_third_party_causer",
    "expert": "PR_expert_procedure_requested",
    "repair": "PR_repair_over_500",
    "nachfrist": "PR_nachfrist_set",
    "recovered": "PR_goods_recovered",
    "declined": "PR_declined",
}

STORIES = {
    8: {
        "form": "broker's cover letter",
        "context": "Burglars entered a Zurich couple's holiday apartment in Chur between two visits in January 2026; ski equipment and a coffee machine are among the missing items, discovered by the cleaner.",
        "text": """Brunner & Caflisch Versicherungsbroker GmbH
Postplatz 3, 7000 Chur

To: Household claims department
Re: Policy HR-7741-0092, Mr and Mrs Lorenz and Simone Haefeli, holiday apartment Via Sumvitg 14, Chur

Dear colleagues,

We are writing on behalf of our clients, Mr and Mrs Haefeli, who live in Zurich and keep a furnished two-room holiday apartment in Chur, covered as a second residence under the above policy (household contents, sum insured CHF 60,000, deductible CHF 300).

On 23 January 2026 their cleaner, Mrs Arpagaus, found the balcony door forced and the apartment ransacked. The couple had last been there on 11 January. Among the missing items are two pairs of touring skis with bindings, ski boots, a bean-to-cup coffee machine and a set of copper pans. «bicycle» The cantonal police in Chur recorded the break-in the same afternoon (file 26-0193-CH); no suspect has been named.

For your file, our clients have asked us to confirm the following points. «scheduled» «sim» «third»

Mr Haefeli is compiling a list of the missing items with purchase years and approximate prices and will send it to us next week. «repair» «expert»

As to the status of the matter: «nachfrist» «declined» «recovered»

Please address any questions to the undersigned.

Kind regards,
Corina Caflisch
Broker""",
    },
    9: {
        "form": "insurer's intake note (structured fields and narrative)",
        "context": "A nurse's ground-floor flat in Sion was broken into during her night shift on 9 March 2026; a drone and two designer handbags are among the stolen items.",
        "text": """CLAIM INTAKE – HOUSEHOLD THEFT
Claim no.: 26-HT-04418
Policyholder: Ms Valérie Rey, Rue du Scex 31, 1950 Sion (ground-floor flat, 2.5 rooms)
Cover: household contents incl. theft at home; sum insured CHF 45,000; deductible CHF 200
Date of loss: night of 9 to 10 March 2026, between 20:30 and 07:15
Reported to police: yes, Police cantonale valaisanne, 10 March 2026, 08:05

Circumstances as reported by the policyholder:
Ms Rey works night shifts at the hospital. When she came home on the morning of 10 March, the bedroom window facing the courtyard had been levered open and the flat searched. «third» She states that a camera drone, two designer handbags, a perfume collection and some cash in a drawer are among the things taken; she is still going through cupboards.

Points clarified on the phone:
– «scheduled»
– «sim»
– «bicycle»
– «repair»

File status:
«expert» «nachfrist» «declined»

Follow-up: «recovered» Ms Rey will upload the police report and her list of stolen items through the portal.

Note taken by: J. Bonvin, claims intake, 10 March 2026""",
    },
    10: {
        "form": "online claim form completed by the policyholder's daughter",
        "context": "During a family wedding celebration in April 2026, a retired couple's house in Fribourg was burgled; kitchen appliances and a silver cutlery set are among the items taken.",
        "text": """ONLINE CLAIM FORM – HOUSEHOLD
Completed by: Nadia Overney (daughter of the policyholder, with his consent)
Policyholder: Mr Gilbert Overney, Route de la Gruyère 52, 1700 Fribourg
Policy: Ménage Confort 3318-554, sum insured CHF 90,000

What happened?
My parents spent Saturday 18 April 2026 at my brother's wedding in Bulle and stayed overnight at the hotel. When they returned on Sunday at noon, the back door of their house had been forced and several rooms had been searched. Their neighbour had noticed nothing. The police in Fribourg came the same day and took fingerprints; my father has the report number.

What is missing?
Among other things, a stand mixer and an espresso machine from the kitchen, a silver cutlery set for twelve that my mother inherited, and the envelope with the wedding present they had not yet handed over. «bicycle» My parents are still checking the cellar and the attic.

Other information requested by the form:
«third»
«sim»
«repair»
«scheduled»

Contact with the insurer so far:
My father phoned your hotline on 20 April. «declined» «nachfrist» «expert»

Anything else we should know?
«recovered» My father is 81 and finds forms difficult, so please contact me for questions (079 318 44 27).""",
    },
    11: {
        "form": "loss adjuster's site visit report",
        "context": "Basement storage compartments in an apartment block in Thun were broken open in May 2026; one tenant's camping gear and power tools are among the stolen items.",
        "text": """SITE VISIT REPORT
Adjuster: Peter Zbinden, Zbinden Schadenexpertisen, Thun
Instructed by: household insurer, claim 26-41-7720
Policyholder: Mr Andreas Ryser, Frutigenstrasse 88, 3600 Thun (4.5-room flat, 3rd floor)
Date of visit: 27 May 2026

1. Circumstances
In the night of 21 to 22 May 2026, unknown persons entered the basement of the apartment block and broke open eleven storage compartments, including the one belonging to Mr Ryser's flat. The caretaker discovered the damage in the morning and called the police (Kantonspolizei Bern, report 2622-118). «third»

2. Items reported missing by the policyholder (provisional)
Camping equipment (a family tent, four sleeping bags, a gas stove), a cordless drill set, a circular saw and a box of hand tools. The policyholder is still reconstructing the list. «bicycle»

3. Findings on site
The padlock of compartment 7 was cut; the wooden slats are intact. «repair» I photographed the compartment and the empty shelves.

4. Statements of the policyholder recorded during the visit
«scheduled» «sim»

5. Procedural position
«expert» «declined» «nachfrist» «recovered»

6. Next steps
The policyholder will provide purchase receipts where available. I will report on the valuation of the items once the list is complete.

P. Zbinden""",
    },
    12: {
        "form": "lawyer's letter on behalf of the policyholder",
        "context": "A graphic designer's townhouse in Schaffhausen was burgled on 6 June 2026 while she was abroad; framed art prints and a drawing tablet are among the stolen items.",
        "text": """Advokatur Meier Stamm
Vordergasse 41, 8200 Schaffhausen

Household claims
Our ref.: MS/26/311
Your policy no.: 55-2290-118 (Ms Leonie Stamm)

Schaffhausen, 19 June 2026

Burglary at Webergasse 7, Schaffhausen, 6 June 2026

Dear Sir or Madam,

We act for Ms Leonie Stamm, a self-employed graphic designer, in connection with the burglary at her townhouse at Webergasse 7.

Ms Stamm was at a design fair in Milan from 4 to 8 June 2026. On her return she found that the ground-floor window of her studio had been pushed in and the house searched. The Schaffhausen police were notified on 8 June (report SH-26-6634). Taken were, among other things, six framed limited-edition art prints, a professional drawing tablet with its stand, a pair of studio headphones and a leather portfolio case. «bicycle»

Our client's household contents insurance covers the private parts of the house; whether the studio equipment falls under the business-equipment extension of the policy will be addressed separately.

For the avoidance of doubt we confirm the following on our client's behalf: «scheduled» «third» «sim»

«repair»

As regards the procedure to date: «expert» «nachfrist» «declined» «recovered»

We would ask you to direct all further correspondence in this matter to our office.

Yours faithfully,
Dr. Martina Meier
Attorney-at-law""",
    },
    13: {
        "form": "social worker's e-mail on behalf of an elderly policyholder",
        "context": "An elderly widow's flat in Bellinzona was broken into via the balcony in July 2026 while she was in a rehabilitation clinic; a fur coat and porcelain figurines are among the stolen items.",
        "text": """From: Sara Pedrazzini, Pro Senectute Ticino, Bellinzona office
To: claims inbox
Subject: Theft at the flat of Mrs Ines Bernasconi, policy 7720-0041

Good morning,

I am the social worker responsible for Mrs Ines Bernasconi (88), Via Lugano 19, Bellinzona, and I write with her written authorisation, which I attach.

Mrs Bernasconi spent three weeks in a rehabilitation clinic after a hip operation. When her niece went to the flat on 14 July 2026 to air it, she found the balcony door open, the lock pried and the bedroom and living room searched. The police in Bellinzona took the report the same day. «third»

According to the niece, a fur coat, a collection of Capodimonte porcelain figurines and a small jewellery box are missing, among other things; Mrs Bernasconi herself has not been home yet and cannot say exactly what else is gone. «bicycle» «scheduled»

The niece has also confirmed the following to me: «sim»

Mrs Bernasconi asked me to add that she has always paid her premiums and hopes the matter can be settled simply. «expert» «repair»

Regarding your company: «declined» «nachfrist»

«recovered»

Mrs Bernasconi returns home next week. Please send any letters to her with a copy to me, as she has difficulty reading small print.

Kind regards,
Sara Pedrazzini""",
    },
    14: {
        "form": "call-centre log (time-stamped handler notes)",
        "context": "A family flat in Aarau was burgled on a Sunday afternoon in August 2026 while the family was at a football match; a home-cinema projector and vintage vinyl records are among the stolen items.",
        "text": """CALL LOG – claims hotline
Caller: Mr Daniel Hächler, policyholder, Bachstrasse 112, 5000 Aarau (4.5-room flat)
Policy: 61-338-207, household contents, sum insured CHF 110,000
Handler: R. Sutter

14:02 Caller reports a burglary on Sunday 16 August 2026 between 13:00 and 18:30. Family was at a football match in Zurich. Front door lock cylinder broken out. Police Aarau attended at 19:10, report no. AG-26-15520.
14:05 Missing so far, among other things: a home-cinema projector, a soundbar, about 300 vintage vinyl records, a children's piggy bank with cash. «bicycle» Caller still checking the children's rooms.
14:07 Asked the standard questions. «scheduled»
14:08 «third»
14:09 «sim»
14:11 «repair» Caller asks whether the lock cylinder is covered; told this will be checked.
14:13 Status of the claim explained to the caller. «nachfrist» «declined»
14:14 «expert»
14:15 «recovered» Caller will upload the police report and a list of the records with estimated values.
14:16 Call ended.""",
    },
    15: {
        "form": "handover note between two claims handlers",
        "context": "A young couple's newly rented flat in Yverdon-les-Bains was burgled in September 2026 days after they moved in, with boxes still unpacked; a gaming PC and a collection of sneakers are among the stolen items.",
        "text": """HANDOVER NOTE – household claim 26-HT-09931
From: Lucie Jaquier (leaving on parental leave)
To: Marco Ferrari
Date: 30 September 2026

Marco, here is where this one stands.

Policyholders are Ms Elodie Cuendet and Mr Samir Benali, who moved into a 3.5-room flat at Rue des Pêcheurs 6, Yverdon-les-Bains, on 15 September. Policy started on the same day (household contents CHF 70,000, deductible CHF 500). On 22 September, while both were at work, someone got in through the kitchen window, which had been left tilted, and went through the moving boxes still stacked in the hallway. Police Yverdon have the case (report VD-26-88412). «third»

What they say is gone so far: Mr Benali's gaming PC with two monitors, about twenty pairs of collector sneakers, a stand mixer and a box of kitchen knives. They are still unpacking and expect to find more missing. «bicycle»

I asked them the usual questions on Friday:
«scheduled»
«sim»
«repair»

Where we are with them:
«nachfrist» «declined» «expert»

«recovered»

They are nervous because of the timing so soon after moving in; a friendly call early next week would help. The list of items is promised for Monday.

Thanks and good luck,
Lucie""",
    },
}
