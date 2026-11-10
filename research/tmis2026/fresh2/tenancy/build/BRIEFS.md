# Author's briefs (fresh2 tenancy)

## f2cl_03fdd7ee632bb267  (family 1, slot 1)
- de-CH / email / sender Matthias Kuhn / landlord Baugenossenschaft Sonnhalde / Brunnenrain 103, Rapperswil-Jona, 3-room flat / date 2026-09-07 / rent CHF 2210
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: two of the four radiators stay cold even when turned up fully.
- STATE (plain) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant: repeated colds and bronchitis]
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- OPEN (specialist_needed, true value False): A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist). -> say it has not yet been decided whether an expert needs to inspect the cause
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_9dc987bc1cc1d51a  (family 1, slot 2)
- en / portal / sender Eleanor Gallagher / landlord Verwaltung Emme & Söhne / Brunnenrain 40, Langenthal, 4.5-room flat / date 2026-09-18 / rent CHF 2700
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the boiler cuts out at night so that the bedrooms are cold in the morning.
- STATE (plain) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's partner: aching joints made worse by the cold]
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (implied) heating: The heating does not work properly (rooms stay cold, radiators fail).
- DENY (plain) specialist_needed: NOT so: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_6c0beb4edcdc571d  (family 1, slot 3)
- de-CH / email / sender Nicola Bosshard / landlord Erbengemeinschaft Probst (private landlord) / Ahornweg 101, Wil, 2.5-room flat / date 2026-09-03 / rent CHF 2610
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the boiler cuts out at night so that the bedrooms are cold in the morning.
- OPEN (health_effects, true value True): A household member has health problems that the tenant attributes to the defect. -> say a household member has been unwell lately but you have not yet clarified whether it has anything to do with the defect
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (passing) heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_c0e56a271156ddce the landlord's reply to the tenant about the defect: must contain ['the work the landlord proposes (a visit by the caretaker to assess the problem)', 'a proposed date for workers to access the flat (26 November 2026)']; must NOT contain: the landlord's position on the defect
- ATTACH f2att_2fe9b4271acd071a the tenancy agreement (lease contract): must contain ['the names of the landlord (Erbengemeinschaft Probst (private landlord)) and the tenant (Nicola Bosshard)', 'the address and description of the rented flat (Ahornweg 101, Wil, 2.5-room flat)', 'the agreed terms: start date 1 September 2009, net rent CHF 2610 per month and the notice period of three months']

## f2cl_d6718680d7e531ea  (family 1, slot 4)
- en / email / sender Tomasz Castellano / landlord Verwaltung Lindenhof Treuhand GmbH / Hinterfeld 102, Kreuzlingen, 4-room flat / date 2026-08-13 / rent CHF 1340
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the boiler cuts out at night so that the bedrooms are cold in the morning.
- STATE (passing) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's partner: aching joints made worse by the cold]
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (implied) heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_836d8ab7e4b0b351 the tenant's letter to the landlord reporting the defect: must contain ['the recipient: the landlord or property manager Verwaltung Lindenhof Treuhand GmbH', 'the date of the letter (2 May 2026)']; must NOT contain: a description of the defect

## f2cl_0ec7682a6943d6d0  (family 2, slot 1)
- de-CH / email / sender Brigitte Rohner / landlord Verwaltung Emme & Söhne / Bündtenweg 35, Steffisburg, 4.5-room flat / date 2026-10-04 / rent CHF 2500
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the ventilation fan in the windowless bathroom is defective and rattles loudly day and night.
- STATE (plain) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's son (8): sleep problems and headaches]
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- AVOID heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (passing) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- OPEN (deposit_considered, true value False): The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed. -> say you are not sure yet whether you will pay the rent into the official deposit account
- ATTACH f2att_82ac4dcfae871c8f the tenant's letter to the landlord reporting the defect: must contain ['a description of the defect (the ventilation fan in the windowless bathroom is defective and rattles loudly day and night)', 'the recipient: the landlord or property manager Verwaltung Emme & Söhne', 'the date of the letter (24 May 2026)']

## f2cl_fb68d264129b3c97  (family 2, slot 2)
- en / portal / sender Ingrid Ferreira / landlord Verwaltung Lindenhof Treuhand GmbH / Eichholzweg 115, Wädenswil, 5.5-room flat / date 2026-09-27 / rent CHF 2250
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the bathroom window cannot be closed because its frame is warped.
- OPEN (health_effects, true value True): A household member has health problems that the tenant attributes to the defect. -> say a household member has been unwell lately but you have not yet clarified whether it has anything to do with the defect
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- AVOID heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_3737e48aa7a56237 the landlord's reply to the tenant about the defect: must contain ['the work the landlord proposes (a visit by the caretaker to assess the problem)', 'a proposed date for workers to access the flat (16 November 2026)']; must NOT contain: the landlord's position on the defect

## f2cl_e810434504ea0100  (family 2, slot 3)
- de-CH / portal / sender Severin Rüegg / landlord Gerance Bärenplatz AG / Schulhausstrasse 62, Wettingen, 3.5-room flat / date 2026-08-19 / rent CHF 1500
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the electrical sockets in the kitchen keep failing and the oven no longer works.
- STATE (passing) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant: sleep problems and headaches]
- DENY (passing) mold: NOT so: There is mould growth or a persistent damp/moisture problem in the flat.
- DENY (plain) heating: NOT so: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_440d59612c87d177  (family 2, slot 4)
- en / email / sender Yusuf Whitaker / landlord Liegenschaften Sternen AG / Schulhausstrasse 3, Dübendorf, 3.5-room flat / date 2026-10-26 / rent CHF 2320
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the front door of the flat no longer locks properly.
- STATE (plain) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's daughter (5): sleep problems and headaches]
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- DENY (implied) heating: NOT so: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_5f74716d4add3d8e the tenancy agreement (lease contract): must contain ['the names of the landlord (Liegenschaften Sternen AG) and the tenant (Yusuf Whitaker)', 'the address and description of the rented flat (Schulhausstrasse 3, Dübendorf, 3.5-room flat)', 'the agreed terms: start date 1 March 2017, net rent CHF 2320 per month and the notice period of three months']
- ATTACH f2att_96f6bb168daa3054 the landlord's reply to the tenant about the defect: must contain ["the landlord's position on the defect (the landlord says the tenant's ventilation habits are to blame)", 'a proposed date for workers to access the flat (7 October 2026)']; must NOT contain: the work the landlord proposes

## f2cl_737d9eeb4a66c9c2  (family 3, slot 1)
- en / chat / sender Felix Volkov / landlord Domicil Plus Immobilien AG / Schulhausstrasse 82, Grenchen, 2.5-room flat / date 2026-08-20 / rent CHF 1920
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the roller shutters in the living room and bedroom are broken and cannot be raised.
- STATE (implied) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant: exhaustion from broken sleep]
- DENY (implied) mold: NOT so: There is mould growth or a persistent damp/moisture problem in the flat.
- AVOID heating: The heating does not work properly (rooms stay cold, radiators fail).
- DENY (plain) specialist_needed: NOT so: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (passing) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_22074e74e3843f8b the tenancy agreement (lease contract): must contain ['the names of the landlord (Domicil Plus Immobilien AG) and the tenant (Felix Volkov)', 'the address and description of the rented flat (Schulhausstrasse 82, Grenchen, 2.5-room flat)', 'the agreed terms: start date 1 December 2011, net rent CHF 1920 per month and the notice period of three months']

## f2cl_b14363f6152ca95c  (family 3, slot 2)
- en / phone_note / sender Kwame Solberg / landlord Wohnwerk Thur GmbH / Mühlemattstrasse 58, Wil, 2.5-room flat / date 2026-10-18 / rent CHF 1450
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the front door of the flat no longer locks properly.
- OPEN (health_effects, true value True): A household member has health problems that the tenant attributes to the defect. -> say a household member has been unwell lately but you have not yet clarified whether it has anything to do with the defect
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- AVOID heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (plain) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_163c73a321b23093 the tenant's letter to the landlord setting a deadline for the repair: must contain ['the recipient: the landlord or property manager Wohnwerk Thur GmbH', 'the statement that the tenant will pay the rent into the official deposit if the defect is not repaired by then']; must NOT contain: a firm deadline for the repair

## f2cl_d39619540633db7d  (family 3, slot 3)
- de-CH / portal / sender Tanja Portmann / landlord Immo Jura Verwaltungen AG / Schulhausstrasse 16, Kreuzlingen, 4.5-room flat / date 2026-09-12 / rent CHF 2400
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the ventilation fan in the windowless bathroom is defective and rattles loudly day and night.
- STATE (plain) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant: sleep problems and headaches]
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- AVOID heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (plain) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_66bfd0f903f8f091 the landlord's reply to the tenant about the defect: must contain ["the landlord's position on the defect (the landlord says a contractor has been informed)", 'the work the landlord proposes (repairs by a contractor in two weeks)']; must NOT contain: a proposed date for workers to access the flat

## f2cl_1e8b1451917edb48  (family 3, slot 4)
- de-CH / portal / sender Ueli Odermatt / landlord Gerance Bärenplatz AG / Bündtenweg 112, Wil, 3-room flat / date 2026-09-15 / rent CHF 2530
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the electrical sockets in the kitchen keep failing and the oven no longer works.
- STATE (plain) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's elderly mother who lives with them: sleep problems and headaches]
- OPEN (mold, true value False): There is mould growth or a persistent damp/moisture problem in the flat. -> say there are dark spots on a wall but you are not sure whether it is mould or damp at all
- AVOID heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (plain) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_16cfbfbda64306a6 the tenancy agreement (lease contract): must contain ['the names of the landlord (Gerance Bärenplatz AG) and the tenant (Ueli Odermatt)', 'the address and description of the rented flat (Bündtenweg 112, Wil, 3-room flat)', 'the agreed terms: start date 1 December 2011, net rent CHF 2530 per month and the notice period of three months']

## f2cl_a5d873ad4151b24e  (family 4, slot 1)
- en / email / sender Luca Haddad / landlord Erbengemeinschaft Probst (private landlord) / Hinterfeld 24, Langenthal, 2.5-room flat / date 2026-10-25 / rent CHF 2260
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: damp patches with black mould spots in the corner of the children's room.
- AVOID health_effects: A household member has health problems that the tenant attributes to the defect.
- STATE (passing) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- AVOID heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (passing) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_4f59fa1aab48ec46 the landlord's reply to the tenant about the defect: must contain ["the landlord's position on the defect (the landlord accepts that something is wrong but asks for patience)", 'the work the landlord proposes (a visit by the caretaker to assess the problem)', 'a proposed date for workers to access the flat (19 September 2026)']

## f2cl_8ef1d51fc9817dfc  (family 4, slot 2)
- en / portal / sender Sofia Kowalczyk / landlord Hausverwaltung Pilatus AG / Brunnenrain 46, Liestal, 4-room flat / date 2026-10-19 / rent CHF 2650
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the roller shutters in the living room and bedroom are broken and cannot be raised.
- DENY (passing) health_effects: NOT so: A household member has health problems that the tenant attributes to the defect.
- OPEN (mold, true value True): There is mould growth or a persistent damp/moisture problem in the flat. -> say there are dark spots on a wall but you are not sure whether it is mould or damp at all
- AVOID heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (implied) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_810cd5e39a4d1ae2 the tenant's letter to the landlord setting a deadline for the repair: must contain ['a firm deadline for the repair (1 October 2026)', 'the recipient: the landlord or property manager Hausverwaltung Pilatus AG']; must NOT contain: the statement that the tenant will pay the rent into the official deposit if the defect is not repaired by then

## f2cl_28bf45059d8c041c  (family 4, slot 3)
- de-CH / portal / sender Franziska Caduff / landlord Immo Jura Verwaltungen AG / Obere Gasse 12, Grenchen, 3-room flat / date 2026-10-12 / rent CHF 2620
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: condensation running down the walls and mould on the window frames.
- AVOID health_effects: A household member has health problems that the tenant attributes to the defect.
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- DENY (passing) heating: NOT so: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (implied) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_272231054ad3a4c2  (family 4, slot 4)
- de-CH / portal / sender Seraina Schnyder / landlord Liegenschaften Sternen AG / Bergstrasse 92, Muttenz, 5.5-room flat / date 2026-09-04 / rent CHF 1360
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: damp patches with black mould spots in the corner of the children's room.
- AVOID health_effects: A household member has health problems that the tenant attributes to the defect.
- STATE (implied) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- AVOID heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (plain) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_c1a0d137a646017b  (family 5, slot 1)
- de-CH / email / sender Michèle Gisler / landlord Ruth Messerli (private landlord) / Allmendstrasse 78, Steffisburg, 3.5-room flat / date 2026-08-26 / rent CHF 2620
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: condensation running down the walls and mould on the window frames and the boiler cuts out at night so that the bedrooms are cold in the morning.
- STATE (plain) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's daughter (5): asthma attacks]
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (passing) heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_822f0fb696964c93 the tenant's letter to the landlord reporting the defect: must contain ['the recipient: the landlord or property manager Ruth Messerli (private landlord)', 'the date of the letter (11 May 2026)']; must NOT contain: a description of the defect

## f2cl_5bd2806f47d7e651  (family 5, slot 2)
- en / email / sender Greta Achterberg / landlord Ruth Messerli (private landlord) / Allmendstrasse 22, Langenthal, 2.5-room flat / date 2026-10-27 / rent CHF 2490
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: mould growing behind the wardrobe and along the bedroom ceiling and the underfloor heating in the living area has stopped working.
- STATE (passing) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's son (8): persistent coughing]
- STATE (passing) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_42e6dc216d627263 the tenancy agreement (lease contract): must contain ['the names of the landlord (Ruth Messerli (private landlord)) and the tenant (Greta Achterberg)', 'the address and description of the rented flat (Allmendstrasse 22, Langenthal, 2.5-room flat)']; must NOT contain: the agreed terms: start date {lease_start}, net rent CHF {rent} per month and the notice period of three months

## f2cl_4e6b3ac31e76c8a6  (family 5, slot 3)
- en / email / sender Dmitri Ndlovu / landlord Stiftung Wohnen Zentral / Rebbergstrasse 99, Rapperswil-Jona, 3.5-room flat / date 2026-08-08 / rent CHF 2150
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: grey-green mould on the bathroom ceiling and a musty smell in the hallway and two of the four radiators stay cold even when turned up fully.
- STATE (implied) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's daughter (5): recurring sinus infections]
- STATE (passing) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- OPEN (deposit_considered, true value False): The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed. -> say you are not sure yet whether you will pay the rent into the official deposit account
- ATTACH f2att_da1988dd523aa2a1 the landlord's reply to the tenant about the defect: must contain ["the landlord's position on the defect (the landlord says a contractor has been informed)", 'the work the landlord proposes (replacement of the defective part after the supplier delivers it)', 'a proposed date for workers to access the flat (10 November 2026)']

## f2cl_f2b2cd8ecce35340  (family 5, slot 4)
- de-CH / email / sender Anita Aebischer / landlord Verwaltung Emme & Söhne / Hinterfeld 113, Kreuzlingen, 4.5-room flat / date 2026-09-16 / rent CHF 2210
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: condensation running down the walls and mould on the window frames and the boiler cuts out at night so that the bedrooms are cold in the morning.
- STATE (passing) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's elderly mother who lives with them: asthma attacks]
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (passing) heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_92ced3f75f592a85  (family 6, slot 1)
- de-CH / portal / sender Dominik Stalder / landlord Domicil Plus Immobilien AG / Zelgweg 40, Wil, 4-room flat / date 2026-10-16 / rent CHF 2110
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: two of the four radiators stay cold even when turned up fully.
- STATE (passing) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's elderly mother who lives with them: repeated colds and bronchitis]
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (plain) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_e8642372ab08ad0b the tenancy agreement (lease contract): must contain ['the names of the landlord (Domicil Plus Immobilien AG) and the tenant (Dominik Stalder)', 'the address and description of the rented flat (Zelgweg 40, Wil, 4-room flat)', 'the agreed terms: start date 1 May 2014, net rent CHF 2110 per month and the notice period of three months']

## f2cl_a6b4080171f0811d  (family 6, slot 2)
- en / email / sender Priya Petrova / landlord Stiftung Wohnen Zentral / Ahornweg 118, Brugg, 2.5-room flat / date 2026-08-13 / rent CHF 2550
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the underfloor heating in the living area has stopped working.
- STATE (plain) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant: aching joints made worse by the cold]
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (passing) heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (implied) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_b0656c8dfbbf433f  (family 6, slot 3)
- en / email / sender Samuel Voss / landlord Domicil Plus Immobilien AG / Bündtenweg 17, Wil, 3-room flat / date 2026-09-14 / rent CHF 1600
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: two of the four radiators stay cold even when turned up fully.
- STATE (passing) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's elderly mother who lives with them: aching joints made worse by the cold]
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (passing) heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (plain) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_caedb9008b001c96 the tenant's letter to the landlord reporting the defect: must contain ['a description of the defect (two of the four radiators stay cold even when turned up fully)', 'the recipient: the landlord or property manager Domicil Plus Immobilien AG']; must NOT contain: the date of the letter

## f2cl_0db56d74dbadee03  (family 6, slot 4)
- de-CH / email / sender Yvonne Wälti / landlord Domicil Plus Immobilien AG / Ahornweg 54, Kriens, 3-room flat / date 2026-09-07 / rent CHF 1340
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the electrical sockets in the kitchen keep failing and the oven no longer works.
- STATE (implied) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's daughter (5): sleep problems and headaches]
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- OPEN (heating, true value True): The heating does not work properly (rooms stay cold, radiators fail). -> say some rooms feel cold but you are not sure whether the heating is actually faulty
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (plain) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_53e2430fee3aade3 the tenancy agreement (lease contract): must contain ['the names of the landlord (Domicil Plus Immobilien AG) and the tenant (Yvonne Wälti)', 'the address and description of the rented flat (Ahornweg 54, Kriens, 3-room flat)', 'the agreed terms: start date 1 December 2018, net rent CHF 1340 per month and the notice period of three months']

## f2cl_45c1b5018d98ecf8  (family 7, slot 1)
- de-CH / portal / sender Pascal Vogt / landlord Verwaltung Lindenhof Treuhand GmbH / Bergstrasse 90, Herisau, 4.5-room flat / date 2026-10-26 / rent CHF 1930
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: condensation running down the walls and mould on the window frames and the boiler cuts out at night so that the bedrooms are cold in the morning.
- AVOID health_effects: A household member has health problems that the tenant attributes to the defect.
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (passing) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_1596c39c91a03a56  (family 7, slot 2)
- en / email / sender Rafael Mensah / landlord Immo Jura Verwaltungen AG / Bündtenweg 20, Uster, 3.5-room flat / date 2026-09-08 / rent CHF 1930
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the boiler cuts out at night so that the bedrooms are cold in the morning.
- AVOID health_effects: A household member has health problems that the tenant attributes to the defect.
- OPEN (mold, true value True): There is mould growth or a persistent damp/moisture problem in the flat. -> say there are dark spots on a wall but you are not sure whether it is mould or damp at all
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (passing) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_1239fbab4373aafd  (family 7, slot 3)
- de-CH / phone_note / sender Esther Ammann / landlord Ruth Messerli (private landlord) / Brunnenrain 23, Herisau, 5.5-room flat / date 2026-10-09 / rent CHF 1660
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: condensation running down the walls and mould on the window frames and the heating fails every few days and the flat drops to around 15 degrees.
- DENY (plain) health_effects: NOT so: A household member has health problems that the tenant attributes to the defect.
- STATE (passing) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (passing) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_4a6b1c3314c7af29 the tenancy agreement (lease contract): must contain ['the names of the landlord (Ruth Messerli (private landlord)) and the tenant (Esther Ammann)', 'the address and description of the rented flat (Brunnenrain 23, Herisau, 5.5-room flat)']; must NOT contain: the agreed terms: start date {lease_start}, net rent CHF {rent} per month and the notice period of three months

## f2cl_31ec410443027eae  (family 7, slot 4)
- en / email / sender Nadia Ortega / landlord Domicil Plus Immobilien AG / Allmendstrasse 53, Muttenz, 5.5-room flat / date 2026-09-26 / rent CHF 2330
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: grey-green mould on the bathroom ceiling and a musty smell in the hallway and the boiler cuts out at night so that the bedrooms are cold in the morning.
- OPEN (health_effects, true value False): A household member has health problems that the tenant attributes to the defect. -> say a household member has been unwell lately but you have not yet clarified whether it has anything to do with the defect
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (implied) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_597f5ba020b66604  (family 8, slot 1)
- en / email / sender Jonah Bianchi / landlord Baugenossenschaft Sonnhalde / Eichholzweg 48, Brugg, 5.5-room flat / date 2026-10-24 / rent CHF 2480
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the heating fails every few days and the flat drops to around 15 degrees.
- AVOID health_effects: A household member has health problems that the tenant attributes to the defect.
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (passing) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_aaaefc6e32fc2ed9 the tenant's letter to the landlord setting a deadline for the repair: must contain ['a firm deadline for the repair (3 September 2026)', 'the statement that the tenant will pay the rent into the official deposit if the defect is not repaired by then']; must NOT contain: the recipient: the landlord or property manager {landlord}
- ATTACH f2att_6a95f5b065eea958 the landlord's reply to the tenant about the defect: must contain ["the landlord's position on the defect (the landlord says the tenant's ventilation habits are to blame)", 'the work the landlord proposes (replacement of the defective part after the supplier delivers it)', 'a proposed date for workers to access the flat (13 November 2026)']

## f2cl_de2e994b2d16909e  (family 8, slot 2)
- en / chat / sender Owen Mehta / landlord Erbengemeinschaft Probst (private landlord) / Rebbergstrasse 107, Kreuzlingen, 4.5-room flat / date 2026-10-05 / rent CHF 2720
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the roller shutters in the living room and bedroom are broken and cannot be raised.
- AVOID health_effects: A household member has health problems that the tenant attributes to the defect.
- DENY (passing) mold: NOT so: There is mould growth or a persistent damp/moisture problem in the flat.
- OPEN (heating, true value True): The heating does not work properly (rooms stay cold, radiators fail). -> say some rooms feel cold but you are not sure whether the heating is actually faulty
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (implied) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_2c03179c96c00e31 the tenancy agreement (lease contract): must contain ['the names of the landlord (Erbengemeinschaft Probst (private landlord)) and the tenant (Owen Mehta)', 'the address and description of the rented flat (Rebbergstrasse 107, Kreuzlingen, 4.5-room flat)', 'the agreed terms: start date 1 March 2012, net rent CHF 2720 per month and the notice period of three months']
- ATTACH f2att_dfc4507cf7c89c22 the tenant's letter to the landlord setting a deadline for the repair: must contain ['a firm deadline for the repair (9 November 2026)', 'the recipient: the landlord or property manager Erbengemeinschaft Probst (private landlord)', 'the statement that the tenant will pay the rent into the official deposit if the defect is not repaired by then']

## f2cl_998f638c466cf34b  (family 8, slot 3)
- de-CH / email / sender Livia Imhof / landlord Baugenossenschaft Sonnhalde / Obere Gasse 81, Grenchen, 4.5-room flat / date 2026-08-18 / rent CHF 1920
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the heating fails every few days and the flat drops to around 15 degrees.
- AVOID health_effects: A household member has health problems that the tenant attributes to the defect.
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- OPEN (specialist_needed, true value True): A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist). -> say it has not yet been decided whether an expert needs to inspect the cause
- STATE (implied) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_54ece3b61e3f3939 the tenant's letter to the landlord reporting the defect: must contain ['a description of the defect (the heating fails every few days and the flat drops to around 15 degrees)', 'the date of the letter (9 August 2026)']; must NOT contain: the recipient: the landlord or property manager {landlord}

## f2cl_05bd14aa0f74a989  (family 8, slot 4)
- de-CH / portal / sender Fabian Zürcher / landlord Hausverwaltung Pilatus AG / Brunnenrain 80, Wädenswil, 5.5-room flat / date 2026-09-21 / rent CHF 2420
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the boiler cuts out at night so that the bedrooms are cold in the morning.
- DENY (passing) health_effects: NOT so: A household member has health problems that the tenant attributes to the defect.
- AVOID mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (implied) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (passing) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_1fd7352d76ce74a1 the tenant's letter to the landlord reporting the defect: must contain ['a description of the defect (the boiler cuts out at night so that the bedrooms are cold in the morning)', 'the recipient: the landlord or property manager Hausverwaltung Pilatus AG', 'the date of the letter (24 August 2026)']

## f2cl_f7614cea945df984  (family 9, slot 1)
- de-CH / portal / sender Jasmin Siegrist / landlord Domicil Plus Immobilien AG / Dorfbachstrasse 17, Grenchen, 5.5-room flat / date 2026-08-13 / rent CHF 1390
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: mould growing behind the wardrobe and along the bedroom ceiling and two of the four radiators stay cold even when turned up fully.
- STATE (plain) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's son (8): recurring sinus infections]
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (implied) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (implied) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_ac851a27a08a4047  (family 9, slot 2)
- de-CH / portal / sender Cédric Bachmann / landlord Erbengemeinschaft Probst (private landlord) / Allmendstrasse 77, Herisau, 3.5-room flat / date 2026-08-03 / rent CHF 2340
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: condensation running down the walls and mould on the window frames and the underfloor heating in the living area has stopped working.
- STATE (plain) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's son (8): persistent coughing]
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- AVOID deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_396d76e1bd8d0b3c the tenant's letter to the landlord reporting the defect: must contain ['a description of the defect (condensation running down the walls and mould on the window frames and the underfloor heating in the living area has stopped working)', 'the date of the letter (26 May 2026)']; must NOT contain: the recipient: the landlord or property manager {landlord}
- ATTACH f2att_5f0ef2c63a7b1626 the landlord's reply to the tenant about the defect: must contain ["the landlord's position on the defect (the landlord says a contractor has been informed)", 'a proposed date for workers to access the flat (27 October 2026)']; must NOT contain: the work the landlord proposes

## f2cl_95eee877ecc48bf1  (family 9, slot 3)
- en / email / sender Beatrix Lindqvist / landlord Verwaltung Emme & Söhne / Obere Gasse 63, Emmen, 4.5-room flat / date 2026-10-28 / rent CHF 2420
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: mould growing behind the wardrobe and along the bedroom ceiling and the boiler cuts out at night so that the bedrooms are cold in the morning.
- STATE (implied) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's partner: persistent coughing]
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (passing) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- DENY (plain) deposit_considered: NOT so: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_be3f0eb859b33907  (family 9, slot 4)
- en / chat / sender Chloe Brennan / landlord Verwaltung Lindenhof Treuhand GmbH / Schulhausstrasse 62, Liestal, 2.5-room flat / date 2026-08-06 / rent CHF 2660
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: condensation running down the walls and mould on the window frames and the underfloor heating in the living area has stopped working.
- OPEN (health_effects, true value True): A household member has health problems that the tenant attributes to the defect. -> say a household member has been unwell lately but you have not yet clarified whether it has anything to do with the defect
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (implied) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (passing) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- DENY (plain) deposit_considered: NOT so: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_7a9b01eb8ca51041 the landlord's reply to the tenant about the defect: must contain ["the landlord's position on the defect (the landlord accepts that something is wrong but asks for patience)", 'the work the landlord proposes (a visit by the caretaker to assess the problem)', 'a proposed date for workers to access the flat (15 September 2026)']
- ATTACH f2att_759c488cdf4a8871 the tenant's letter to the landlord reporting the defect: must contain ['the recipient: the landlord or property manager Verwaltung Lindenhof Treuhand GmbH', 'the date of the letter (13 May 2026)']; must NOT contain: a description of the defect

## f2cl_7dea127b55cb254f  (family 10, slot 1)
- en / email / sender Hannah Ramaswamy / landlord Immo Jura Verwaltungen AG / Bündtenweg 10, Rapperswil-Jona, 5.5-room flat / date 2026-09-24 / rent CHF 2190
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: mould growing behind the wardrobe and along the bedroom ceiling and the heating fails every few days and the flat drops to around 15 degrees.
- STATE (passing) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant: recurring sinus infections]
- STATE (implied) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (passing) heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (passing) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_353cd66635fa6c15  (family 10, slot 2)
- en / chat / sender Harriet Okafor / landlord Wohnwerk Thur GmbH / Rebbergstrasse 39, Solothurn, 4-room flat / date 2026-08-01 / rent CHF 2620
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: mould growing behind the wardrobe and along the bedroom ceiling and the underfloor heating in the living area has stopped working.
- STATE (passing) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant: asthma attacks]
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (plain) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_f20533f0786730c1 the tenant's letter to the landlord reporting the defect: must contain ['a description of the defect (mould growing behind the wardrobe and along the bedroom ceiling and the underfloor heating in the living area has stopped working)', 'the date of the letter (2 June 2026)']; must NOT contain: the recipient: the landlord or property manager {landlord}

## f2cl_69f84208279ac66e  (family 10, slot 3)
- de-CH / chat / sender Regula Christen / landlord Liegenschaften Sternen AG / Mühlemattstrasse 44, Brugg, 3.5-room flat / date 2026-09-09 / rent CHF 1980
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: damp patches with black mould spots in the corner of the children's room and the boiler cuts out at night so that the bedrooms are cold in the morning.
- STATE (passing) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's elderly mother who lives with them: recurring sinus infections]
- STATE (passing) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (implied) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_6d6b6dc27953028c  (family 10, slot 4)
- de-CH / email / sender Simon Lehmann / landlord Domicil Plus Immobilien AG / Mühlemattstrasse 73, Uster, 3.5-room flat / date 2026-10-22 / rent CHF 1540
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: damp patches with black mould spots in the corner of the children's room and two of the four radiators stay cold even when turned up fully.
- OPEN (health_effects, true value True): A household member has health problems that the tenant attributes to the defect. -> say a household member has been unwell lately but you have not yet clarified whether it has anything to do with the defect
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- AVOID specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (plain) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_6b8b77d12d83f28e the tenancy agreement (lease contract): must contain ['the names of the landlord (Domicil Plus Immobilien AG) and the tenant (Simon Lehmann)', 'the agreed terms: start date 1 December 2016, net rent CHF 1540 per month and the notice period of three months']; must NOT contain: the address and description of the rented flat
- ATTACH f2att_91bfe08cffedb560 the tenant's letter to the landlord reporting the defect: must contain ["a description of the defect (damp patches with black mould spots in the corner of the children's room and two of the four radiators stay cold even when turned up fully)", 'the recipient: the landlord or property manager Domicil Plus Immobilien AG', 'the date of the letter (11 July 2026)']

## f2cl_45b9c08ccc6e5fc4  (family 11, slot 1)
- de-CH / email / sender Karin Habegger / landlord Verwaltung Lindenhof Treuhand GmbH / Allmendstrasse 62, Solothurn, 4-room flat / date 2026-09-02 / rent CHF 2360
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: mould growing behind the wardrobe and along the bedroom ceiling.
- STATE (implied) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's son (8): persistent coughing]
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- AVOID heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- OPEN (deposit_considered, true value True): The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed. -> say you are not sure yet whether you will pay the rent into the official deposit account

## f2cl_3daad3eb95ae2c15  (family 11, slot 2)
- en / portal / sender Aoife Marchetti / landlord Hausverwaltung Pilatus AG / Hinterfeld 91, Steffisburg, 4-room flat / date 2026-10-19 / rent CHF 2410
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: grey-green mould on the bathroom ceiling and a musty smell in the hallway.
- STATE (implied) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's daughter (5): persistent coughing]
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- AVOID heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (passing) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_406a698f8b7c2aa9 the landlord's reply to the tenant about the defect: must contain ["the landlord's position on the defect (the landlord says the tenant's ventilation habits are to blame)", 'the work the landlord proposes (a visit by the caretaker to assess the problem)', 'a proposed date for workers to access the flat (8 November 2026)']

## f2cl_79ebf2751d59693f  (family 11, slot 3)
- de-CH / email / sender Jonas Kunz / landlord Immo Jura Verwaltungen AG / Ahornweg 3, Liestal, 4-room flat / date 2026-10-27 / rent CHF 1410
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: grey-green mould on the bathroom ceiling and a musty smell in the hallway.
- STATE (passing) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's daughter (5): asthma attacks]
- STATE (passing) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- AVOID heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (passing) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_a19c3f71049ae983  (family 11, slot 4)
- en / portal / sender Arjun Demir / landlord Liegenschaften Sternen AG / Schulhausstrasse 5, Liestal, 3.5-room flat / date 2026-09-28 / rent CHF 1530
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: mould growing behind the wardrobe and along the bedroom ceiling.
- STATE (plain) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's elderly mother who lives with them: recurring sinus infections]
- STATE (implied) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- AVOID heating: The heating does not work properly (rooms stay cold, radiators fail).
- OPEN (specialist_needed, true value True): A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist). -> say it has not yet been decided whether an expert needs to inspect the cause
- STATE (passing) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_26cb680af349fd00  (family 12, slot 1)
- de-CH / email / sender Kevin Rüfenacht / landlord Immo Jura Verwaltungen AG / Brunnenrain 103, Wil, 3.5-room flat / date 2026-08-08 / rent CHF 2580
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: grey-green mould on the bathroom ceiling and a musty smell in the hallway and two of the four radiators stay cold even when turned up fully.
- AVOID health_effects: A household member has health problems that the tenant attributes to the defect.
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (passing) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (implied) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_775d7303508bb928  (family 12, slot 2)
- en / chat / sender Maeve Holm / landlord Hausverwaltung Pilatus AG / Rebbergstrasse 93, Steffisburg, 3.5-room flat / date 2026-10-06 / rent CHF 1620
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: grey-green mould on the bathroom ceiling and a musty smell in the hallway and the boiler cuts out at night so that the bedrooms are cold in the morning.
- AVOID health_effects: A household member has health problems that the tenant attributes to the defect.
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (implied) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (plain) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.

## f2cl_dee066dc65128d40  (family 12, slot 3)
- de-CH / email / sender Raphael Furrer / landlord Gerance Bärenplatz AG / Eichholzweg 82, Uster, 4-room flat / date 2026-09-20 / rent CHF 1330
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: grey-green mould on the bathroom ceiling and a musty smell in the hallway and the boiler cuts out at night so that the bedrooms are cold in the morning.
- AVOID health_effects: A household member has health problems that the tenant attributes to the defect.
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (passing) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (plain) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_26cd620d6e3cfb69 the tenancy agreement (lease contract): must contain ['the names of the landlord (Gerance Bärenplatz AG) and the tenant (Raphael Furrer)', 'the address and description of the rented flat (Eichholzweg 82, Uster, 4-room flat)', 'the agreed terms: start date 1 December 2011, net rent CHF 1330 per month and the notice period of three months']

## f2cl_7672df3b1aac5c1a  (family 12, slot 4)
- en / email / sender Ibrahim Wilk / landlord Domicil Plus Immobilien AG / Allmendstrasse 95, Langenthal, 2.5-room flat / date 2026-09-28 / rent CHF 1620
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: mould growing behind the wardrobe and along the bedroom ceiling.
- AVOID health_effects: A household member has health problems that the tenant attributes to the defect.
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- OPEN (heating, true value True): The heating does not work properly (rooms stay cold, radiators fail). -> say some rooms feel cold but you are not sure whether the heating is actually faulty
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (passing) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_e86377e663eda4a8 the tenant's letter to the landlord setting a deadline for the repair: must contain ['a firm deadline for the repair (19 November 2026)', 'the recipient: the landlord or property manager Domicil Plus Immobilien AG', 'the statement that the tenant will pay the rent into the official deposit if the defect is not repaired by then']
- ATTACH f2att_c8d3a9962ff78fdb the tenancy agreement (lease contract): must contain ['the names of the landlord (Domicil Plus Immobilien AG) and the tenant (Ibrahim Wilk)', 'the address and description of the rented flat (Allmendstrasse 95, Langenthal, 2.5-room flat)', 'the agreed terms: start date 1 March 2015, net rent CHF 1620 per month and the notice period of three months']

## f2cl_b0a56cd3fe0020ca  (family 13, slot 1)
- de-CH / chat / sender Franziska Furrer / landlord Stiftung Wohnen Zentral / Brunnenrain 23, Herisau, 4.5-room flat / date 2026-09-17 / rent CHF 1730
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: grey-green mould on the bathroom ceiling and a musty smell in the hallway and the heating fails every few days and the flat drops to around 15 degrees.
- STATE (implied) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's partner: recurring sinus infections]
- STATE (plain) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (implied) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (plain) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_912ea3d79ce891d2 the tenancy agreement (lease contract): must contain ['the address and description of the rented flat (Brunnenrain 23, Herisau, 4.5-room flat)', 'the agreed terms: start date 1 March 2012, net rent CHF 1730 per month and the notice period of three months']; must NOT contain: the names of the landlord

## f2cl_a92229584ec74f86  (family 13, slot 2)
- en / portal / sender Greta Ndlovu / landlord Wohnwerk Thur GmbH / Zelgweg 33, Uster, 2.5-room flat / date 2026-09-08 / rent CHF 2330
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: the boiler cuts out at night so that the bedrooms are cold in the morning.
- STATE (plain) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's daughter (5): repeated colds and bronchitis]
- OPEN (mold, true value True): There is mould growth or a persistent damp/moisture problem in the flat. -> say there are dark spots on a wall but you are not sure whether it is mould or damp at all
- STATE (implied) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (plain) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (plain) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_d1e471e1c853aa5c the tenancy agreement (lease contract): must contain ['the names of the landlord (Wohnwerk Thur GmbH) and the tenant (Greta Ndlovu)', 'the agreed terms: start date 1 May 2022, net rent CHF 2330 per month and the notice period of three months']; must NOT contain: the address and description of the rented flat

## f2cl_ac669bf78a141b38  (family 13, slot 3)
- de-CH / phone_note / sender Dominik Christen / landlord Gerance Bärenplatz AG / Brunnenrain 21, Liestal, 4.5-room flat / date 2026-10-01 / rent CHF 1380
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: mould growing behind the wardrobe and along the bedroom ceiling and the underfloor heating in the living area has stopped working.
- STATE (plain) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's elderly mother who lives with them: asthma attacks]
- STATE (passing) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (implied) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (passing) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (passing) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_77a6daf5e671e1a1 the tenant's letter to the landlord setting a deadline for the repair: must contain ['a firm deadline for the repair (24 November 2026)', 'the recipient: the landlord or property manager Gerance Bärenplatz AG', 'the statement that the tenant will pay the rent into the official deposit if the defect is not repaired by then']
- ATTACH f2att_f0da03ecbacbf342 the landlord's reply to the tenant about the defect: must contain ["the landlord's position on the defect (the landlord accepts that something is wrong but asks for patience)", 'the work the landlord proposes (a visit by the caretaker to assess the problem)', 'a proposed date for workers to access the flat (10 September 2026)']

## f2cl_753a10b9d25479c6  (family 13, slot 4)
- en / email / sender Eleanor Kowalczyk / landlord Verwaltung Emme & Söhne / Eichholzweg 29, Muttenz, 3.5-room flat / date 2026-10-01 / rent CHF 2080
- situation: There is a defect in the rented flat that the landlord has not fixed, and the tenant wants help. Defect: condensation running down the walls and mould on the window frames and the boiler cuts out at night so that the bedrooms are cold in the morning.
- STATE (passing) health_effects: A household member has health problems that the tenant attributes to the defect. [the tenant's daughter (5): persistent coughing]
- STATE (passing) mold: There is mould growth or a persistent damp/moisture problem in the flat.
- STATE (plain) heating: The heating does not work properly (rooms stay cold, radiators fail).
- STATE (passing) specialist_needed: A technical expert inspection is needed to establish the cause of the defect (the cause is disputed or unclear and needs a building or heating specialist).
- STATE (passing) deposit_considered: The tenant intends to pay the rent into the official rent deposit (Hinterlegung) if the defect is not fixed.
- ATTACH f2att_5a537615d4e32ec0 the tenancy agreement (lease contract): must contain ['the names of the landlord (Verwaltung Emme & Söhne) and the tenant (Eleanor Kowalczyk)', 'the agreed terms: start date 1 May 2020, net rent CHF 2080 per month and the notice period of three months']; must NOT contain: the address and description of the rented flat

## f2cl_9d632e27423b34f7  (family 14, slot 1)
- de-CH / phone_note / sender Brigitte Caduff / landlord Stiftung Wohnen Zentral / Obere Gasse 106, Uster, 4-room flat / date 2026-08-25 / rent CHF 2700
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- AVOID-ROUTING termination_received: describe the dispute but do not say whether any written notice was received
- OPEN (family_home, true value False): The flat is the family home of a married couple or registered partners: the tenant's spouse or registered partner lives there too. -> say you are not sure whether the flat legally counts as your family home (for example because your spouse is officially registered elsewhere)
- STATE (implied) arrears: The termination is because of unpaid rent (rent arrears). [about CHF 5400]
- STATE (passing) retaliation_screen: The tenant believes the termination is retaliation because the tenant recently asserted tenancy rights against the landlord (for example complained about defects or challenged the rent).
- DENY (passing) extension_relevant: NOT so: The tenant wants an extension of the tenancy because moving out by the end date would be a hardship (for example a difficult housing search, children's school, illness).
- ATTACH f2att_472977d17c316a1e the tenancy agreement (lease contract): must contain ['the names of the landlord (Stiftung Wohnen Zentral) and the tenant (Brigitte Caduff)', 'the address and description of the rented flat (Obere Gasse 106, Uster, 4-room flat)', 'the agreed terms: start date 1 March 2017, net rent CHF 2700 per month and the notice period of three months']

## f2cl_9986f974eabc50c8  (family 14, slot 2)
- en / email / sender Harriet Marchetti / landlord Wohnwerk Thur GmbH / Rebbergstrasse 93, Langenthal, 3-room flat / date 2026-09-27 / rent CHF 1310
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- AVOID-ROUTING termination_received: describe the dispute but do not say whether any written notice was received
- DENY (plain) family_home: NOT so: The flat is the family home of a married couple or registered partners: the tenant's spouse or registered partner lives there too.
- STATE (plain) arrears: The termination is because of unpaid rent (rent arrears). [about CHF 3930]
- STATE (plain) retaliation_screen: The tenant believes the termination is retaliation because the tenant recently asserted tenancy rights against the landlord (for example complained about defects or challenged the rent).
- OPEN (extension_relevant, true value False): The tenant wants an extension of the tenancy because moving out by the end date would be a hardship (for example a difficult housing search, children's school, illness). -> say you have not yet decided whether you will ask for more time (an extension) before moving out
- ATTACH f2att_53359ca8fc7ed289 the landlord's earlier payment reminder setting a deadline to pay the arrears: must contain ['a deadline of 30 days to pay', 'the amount of rent claimed as unpaid (CHF 3930)', 'the warning that the lease will be terminated if the amount is not paid in time']

## f2cl_153fc1a995729f56  (family 14, slot 3)
- de-CH / portal / sender Jasmin Furrer / landlord Wohnwerk Thur GmbH / Bergstrasse 47, Wettingen, 3-room flat / date 2026-09-16 / rent CHF 1370
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- STATE (implied) termination_received: The tenant has received a written notice of termination of the lease from the landlord.
- AVOID family_home: The flat is the family home of a married couple or registered partners: the tenant's spouse or registered partner lives there too.
- STATE (plain) arrears: The termination is because of unpaid rent (rent arrears). [about CHF 2740]
- STATE (plain) retaliation_screen: The tenant believes the termination is retaliation because the tenant recently asserted tenancy rights against the landlord (for example complained about defects or challenged the rent).
- AVOID extension_relevant: The tenant wants an extension of the tenancy because moving out by the end date would be a hardship (for example a difficult housing search, children's school, illness).
- ATTACH f2att_bdac881edfc3a731 the tenancy agreement (lease contract): must contain ['the names of the landlord (Wohnwerk Thur GmbH) and the tenant (Jasmin Furrer)', 'the address and description of the rented flat (Bergstrasse 47, Wettingen, 3-room flat)', 'the agreed terms: start date 1 December 2015, net rent CHF 1370 per month and the notice period of three months']

## f2cl_ae955da9f1ff5ae1  (family 14, slot 4)
- en / chat / sender Ibrahim Volkov / landlord Wohnwerk Thur GmbH / Bergstrasse 39, Brugg, 2.5-room flat / date 2026-08-01 / rent CHF 1460
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- STATE (passing) termination_received: The tenant has received a written notice of termination of the lease from the landlord.
- AVOID family_home: The flat is the family home of a married couple or registered partners: the tenant's spouse or registered partner lives there too.
- STATE (plain) arrears: The termination is because of unpaid rent (rent arrears). [about CHF 4380]
- STATE (plain) retaliation_screen: The tenant believes the termination is retaliation because the tenant recently asserted tenancy rights against the landlord (for example complained about defects or challenged the rent).
- AVOID extension_relevant: The tenant wants an extension of the tenancy because moving out by the end date would be a hardship (for example a difficult housing search, children's school, illness).
- ATTACH f2att_05b39e03f78efc53 the tenancy agreement (lease contract): must contain ['the names of the landlord (Wohnwerk Thur GmbH) and the tenant (Ibrahim Volkov)', 'the address and description of the rented flat (Bergstrasse 39, Brugg, 2.5-room flat)']; must NOT contain: the agreed terms: start date {lease_start}, net rent CHF {rent} per month and the notice period of three months

## f2cl_8a606d2af148582c  (family 15, slot 1)
- de-CH / email / sender Severin Stalder / landlord Verwaltung Lindenhof Treuhand GmbH / Rebbergstrasse 112, Wädenswil, 3.5-room flat / date 2026-10-04 / rent CHF 1510
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- AVOID-ROUTING termination_received: describe the dispute but do not say whether any written notice was received
- AVOID family_home: The flat is the family home of a married couple or registered partners: the tenant's spouse or registered partner lives there too.
- STATE (plain) arrears: The termination is because of unpaid rent (rent arrears). [about CHF 3020]
- STATE (passing) retaliation_screen: The tenant believes the termination is retaliation because the tenant recently asserted tenancy rights against the landlord (for example complained about defects or challenged the rent).
- STATE (passing) extension_relevant: The tenant wants an extension of the tenancy because moving out by the end date would be a hardship (for example a difficult housing search, children's school, illness).
- ATTACH f2att_5602e74a74514fea the landlord's earlier payment reminder setting a deadline to pay the arrears: must contain ['the amount of rent claimed as unpaid (CHF 3020)', 'the warning that the lease will be terminated if the amount is not paid in time']; must NOT contain: a deadline of 30 days to pay
- ATTACH f2att_58476b579b905e2a the tenancy agreement (lease contract): must contain ['the address and description of the rented flat (Rebbergstrasse 112, Wädenswil, 3.5-room flat)', 'the agreed terms: start date 1 September 2023, net rent CHF 1510 per month and the notice period of three months']; must NOT contain: the names of the landlord

## f2cl_9d9b9e6660448586  (family 15, slot 2)
- de-CH / email / sender Jasmin Bosshard / landlord Stiftung Wohnen Zentral / Schulhausstrasse 65, Burgdorf, 3-room flat / date 2026-10-12 / rent CHF 2230
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- AVOID-ROUTING termination_received: describe the dispute but do not say whether any written notice was received
- AVOID family_home: The flat is the family home of a married couple or registered partners: the tenant's spouse or registered partner lives there too.
- STATE (passing) arrears: The termination is because of unpaid rent (rent arrears). [about CHF 6690]
- STATE (plain) retaliation_screen: The tenant believes the termination is retaliation because the tenant recently asserted tenancy rights against the landlord (for example complained about defects or challenged the rent).
- OPEN (extension_relevant, true value True): The tenant wants an extension of the tenancy because moving out by the end date would be a hardship (for example a difficult housing search, children's school, illness). -> say you have not yet decided whether you will ask for more time (an extension) before moving out

## f2cl_ac5bb2a29a29bde3  (family 15, slot 3)
- en / email / sender Hannah Brennan / landlord Stiftung Wohnen Zentral / Allmendstrasse 120, Muttenz, 3-room flat / date 2026-10-22 / rent CHF 2160
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- STATE (passing) termination_received: The tenant has received a written notice of termination of the lease from the landlord.
- AVOID family_home: The flat is the family home of a married couple or registered partners: the tenant's spouse or registered partner lives there too.
- STATE (plain) arrears: The termination is because of unpaid rent (rent arrears). [about CHF 4320]
- STATE (plain) retaliation_screen: The tenant believes the termination is retaliation because the tenant recently asserted tenancy rights against the landlord (for example complained about defects or challenged the rent).
- STATE (plain) extension_relevant: The tenant wants an extension of the tenancy because moving out by the end date would be a hardship (for example a difficult housing search, children's school, illness).

## f2cl_7850a89c062dfd72  (family 15, slot 4)
- en / email / sender Arjun Kowalczyk / landlord Verwaltung Emme & Söhne / Allmendstrasse 61, Kriens, 5.5-room flat / date 2026-08-20 / rent CHF 2190
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- STATE (plain) termination_received: The tenant has received a written notice of termination of the lease from the landlord.
- AVOID family_home: The flat is the family home of a married couple or registered partners: the tenant's spouse or registered partner lives there too.
- STATE (passing) arrears: The termination is because of unpaid rent (rent arrears). [about CHF 6570]
- STATE (implied) retaliation_screen: The tenant believes the termination is retaliation because the tenant recently asserted tenancy rights against the landlord (for example complained about defects or challenged the rent).
- STATE (plain) extension_relevant: The tenant wants an extension of the tenancy because moving out by the end date would be a hardship (for example a difficult housing search, children's school, illness).

## f2cl_45158e0185bd82b6  (family 16, slot 1)
- de-CH / portal / sender Michèle Siegrist / landlord Baugenossenschaft Sonnhalde / Eichholzweg 77, Muttenz, 3.5-room flat / date 2026-08-16 / rent CHF 2620
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- STATE (plain) termination_received: The tenant has received a written notice of termination of the lease from the landlord.
- STATE (plain) family_home: The flat is the family home of a married couple or registered partners: the tenant's spouse or registered partner lives there too.
- STATE (plain) arrears: The termination is because of unpaid rent (rent arrears). [about CHF 5240]
- OPEN (retaliation_screen, true value True): The tenant believes the termination is retaliation because the tenant recently asserted tenancy rights against the landlord (for example complained about defects or challenged the rent). -> say you wonder whether the termination could be a reaction to something you raised with the landlord earlier, but you have not made up your mind
- STATE (plain) extension_relevant: The tenant wants an extension of the tenancy because moving out by the end date would be a hardship (for example a difficult housing search, children's school, illness).
- ATTACH f2att_e93212db9e8fb6e8 the landlord's termination notice: must contain ["the issuing landlord's name and signature (Baugenossenschaft Sonnhalde)", 'the addressee: the tenant Michèle Siegrist', 'the date on which the tenancy ends (30 April 2027)', 'the stated ground for the termination (unpaid rent (rent arrears))', 'the statement that the notice is given on the officially approved cantonal form, with the information on how to challenge it at the conciliation authority']

## f2cl_38438bc732d1a4c3  (family 16, slot 2)
- en / portal / sender Dmitri Holm / landlord Wohnwerk Thur GmbH / Zelgweg 38, Emmen, 3.5-room flat / date 2026-09-25 / rent CHF 1790
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- STATE (passing) termination_received: The tenant has received a written notice of termination of the lease from the landlord.
- STATE (plain) family_home: The flat is the family home of a married couple or registered partners: the tenant's spouse or registered partner lives there too.
- STATE (passing) arrears: The termination is because of unpaid rent (rent arrears). [about CHF 3580]
- STATE (plain) retaliation_screen: The tenant believes the termination is retaliation because the tenant recently asserted tenancy rights against the landlord (for example complained about defects or challenged the rent).
- STATE (implied) extension_relevant: The tenant wants an extension of the tenancy because moving out by the end date would be a hardship (for example a difficult housing search, children's school, illness).
- ATTACH f2att_d6ab7d0092473469 the landlord's termination notice: must contain ["the issuing landlord's name and signature (Wohnwerk Thur GmbH)", 'the date on which the tenancy ends (31 January 2027)', 'the stated ground for the termination (unpaid rent (rent arrears))', 'the statement that the notice is given on the officially approved cantonal form, with the information on how to challenge it at the conciliation authority']; must NOT contain: the addressee: the tenant {tenant}
- ATTACH f2att_b1735b9795752d02 the tenancy agreement (lease contract): must contain ['the names of the landlord (Wohnwerk Thur GmbH) and the tenant (Dmitri Holm)', 'the address and description of the rented flat (Zelgweg 38, Emmen, 3.5-room flat)']; must NOT contain: the agreed terms: start date {lease_start}, net rent CHF {rent} per month and the notice period of three months

## f2cl_5cecc4b16db0d9d9  (family 16, slot 3)
- en / email / sender Harriet Bianchi / landlord Stiftung Wohnen Zentral / Ahornweg 48, Liestal, 4.5-room flat / date 2026-10-22 / rent CHF 2600
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- OPEN (termination_received, true value True): The tenant has received a written notice of termination of the lease from the landlord. -> say you are not sure whether what you received is a formal termination notice or whether one has actually been issued
- STATE (plain) family_home: The flat is the family home of a married couple or registered partners: the tenant's spouse or registered partner lives there too.
- STATE (passing) arrears: The termination is because of unpaid rent (rent arrears). [about CHF 7800]
- STATE (plain) retaliation_screen: The tenant believes the termination is retaliation because the tenant recently asserted tenancy rights against the landlord (for example complained about defects or challenged the rent).
- STATE (plain) extension_relevant: The tenant wants an extension of the tenancy because moving out by the end date would be a hardship (for example a difficult housing search, children's school, illness).

## f2cl_877db9914e851371  (family 16, slot 4)
- de-CH / email / sender Kevin Stalder / landlord Stiftung Wohnen Zentral / Brunnenrain 48, Steffisburg, 2.5-room flat / date 2026-08-27 / rent CHF 1540
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- AVOID-ROUTING termination_received: describe the dispute but do not say whether any written notice was received
- STATE (passing) family_home: The flat is the family home of a married couple or registered partners: the tenant's spouse or registered partner lives there too.
- STATE (passing) arrears: The termination is because of unpaid rent (rent arrears). [about CHF 3080]
- STATE (implied) retaliation_screen: The tenant believes the termination is retaliation because the tenant recently asserted tenancy rights against the landlord (for example complained about defects or challenged the rent).
- STATE (implied) extension_relevant: The tenant wants an extension of the tenancy because moving out by the end date would be a hardship (for example a difficult housing search, children's school, illness).

## f2cl_d70027e84f7be321  (family 17, slot 1)
- de-CH / email / sender Kevin Rüegg / landlord Ruth Messerli (private landlord) / Dorfbachstrasse 97, Wädenswil, 4.5-room flat / date 2026-10-15 / rent CHF 1860
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- OPEN (termination_received, true value False): The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice. -> say you are not sure whether what you received is a formal termination notice or whether one has actually been issued
- AVOID family_home: The flat is the family home of a married couple or registered partners.
- AVOID arrears: The termination the landlord announced is because of unpaid rent (rent arrears).
- AVOID retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- DENY (plain) extension_relevant: NOT so: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_df19ad9dbc6908e6  (family 17, slot 2)
- en / chat / sender Hannah Mehta / landlord Stiftung Wohnen Zentral / Ahornweg 97, Wettingen, 4-room flat / date 2026-09-17 / rent CHF 2380
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- DENY (plain) termination_received: NOT so: The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice.
- AVOID family_home: The flat is the family home of a married couple or registered partners.
- AVOID arrears: The termination the landlord announced is because of unpaid rent (rent arrears).
- AVOID retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- DENY (passing) extension_relevant: NOT so: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_d6933e639e85dfa7  (family 17, slot 3)
- de-CH / email / sender Esther Rüfenacht / landlord Verwaltung Emme & Söhne / Obere Gasse 95, Liestal, 5.5-room flat / date 2026-10-07 / rent CHF 1680
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- DENY (plain) termination_received: NOT so: The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice.
- AVOID family_home: The flat is the family home of a married couple or registered partners.
- AVOID arrears: The termination the landlord announced is because of unpaid rent (rent arrears).
- AVOID retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- AVOID extension_relevant: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_293e83fdc7fe66e2  (family 17, slot 4)
- en / email / sender Luca Achterberg / landlord Domicil Plus Immobilien AG / Bündtenweg 115, Kreuzlingen, 4.5-room flat / date 2026-10-18 / rent CHF 2740
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- DENY (plain) termination_received: NOT so: The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice.
- AVOID family_home: The flat is the family home of a married couple or registered partners.
- AVOID arrears: The termination the landlord announced is because of unpaid rent (rent arrears).
- AVOID retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- DENY (passing) extension_relevant: NOT so: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_2f66e558555d3a41  (family 18, slot 1)
- de-CH / email / sender Kevin Bachmann / landlord Liegenschaften Sternen AG / Bergstrasse 49, Solothurn, 5.5-room flat / date 2026-10-06 / rent CHF 1890
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- DENY (plain) termination_received: NOT so: The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice.
- AVOID family_home: The flat is the family home of a married couple or registered partners.
- STATE (plain) arrears: The termination the landlord announced is because of unpaid rent (rent arrears). [about CHF 3780]
- AVOID retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- DENY (passing) extension_relevant: NOT so: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_d453d1aa043aed04  (family 18, slot 2)
- en / chat / sender Arjun Ndlovu / landlord Verwaltung Lindenhof Treuhand GmbH / Eichholzweg 104, Wädenswil, 5.5-room flat / date 2026-10-08 / rent CHF 1650
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- DENY (plain) termination_received: NOT so: The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice.
- AVOID family_home: The flat is the family home of a married couple or registered partners.
- STATE (implied) arrears: The termination the landlord announced is because of unpaid rent (rent arrears). [about CHF 4950]
- AVOID retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- AVOID extension_relevant: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_09127308ca120a39  (family 18, slot 3)
- de-CH / portal / sender Seraina Imhof / landlord Immo Jura Verwaltungen AG / Bergstrasse 88, Dübendorf, 4-room flat / date 2026-09-22 / rent CHF 1670
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- DENY (plain) termination_received: NOT so: The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice.
- AVOID family_home: The flat is the family home of a married couple or registered partners.
- STATE (plain) arrears: The termination the landlord announced is because of unpaid rent (rent arrears). [about CHF 3340]
- AVOID retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- AVOID extension_relevant: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_af805d2dd545e678  (family 18, slot 4)
- en / phone_note / sender Felix Bianchi / landlord Verwaltung Emme & Söhne / Bergstrasse 120, Kriens, 5.5-room flat / date 2026-08-24 / rent CHF 2440
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- OPEN (termination_received, true value False): The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice. -> say you are not sure whether what you received is a formal termination notice or whether one has actually been issued
- AVOID family_home: The flat is the family home of a married couple or registered partners.
- STATE (implied) arrears: The termination the landlord announced is because of unpaid rent (rent arrears). [about CHF 4880]
- AVOID retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- AVOID extension_relevant: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_1c700d9656587a6d  (family 19, slot 1)
- de-CH / email / sender Jasmin Lehmann / landlord Baugenossenschaft Sonnhalde / Mühlemattstrasse 24, Kreuzlingen, 4-room flat / date 2026-09-10 / rent CHF 1350
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- DENY (implied) termination_received: NOT so: The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice.
- AVOID family_home: The flat is the family home of a married couple or registered partners.
- AVOID arrears: The termination the landlord announced is because of unpaid rent (rent arrears).
- AVOID retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- STATE (plain) extension_relevant: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_296f80eefd7d2863  (family 19, slot 2)
- de-CH / chat / sender Seraina Vogt / landlord Verwaltung Emme & Söhne / Obere Gasse 1, Uster, 5.5-room flat / date 2026-10-07 / rent CHF 1980
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- DENY (implied) termination_received: NOT so: The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice.
- AVOID family_home: The flat is the family home of a married couple or registered partners.
- DENY (implied) arrears: NOT so: The termination the landlord announced is because of unpaid rent (rent arrears).
- AVOID retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- STATE (passing) extension_relevant: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_8da32c6cda5795f7  (family 19, slot 3)
- en / portal / sender Jonah Achterberg / landlord Immo Jura Verwaltungen AG / Zelgweg 69, Langenthal, 4.5-room flat / date 2026-10-23 / rent CHF 1740
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- DENY (passing) termination_received: NOT so: The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice.
- AVOID family_home: The flat is the family home of a married couple or registered partners.
- DENY (passing) arrears: NOT so: The termination the landlord announced is because of unpaid rent (rent arrears).
- AVOID retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- STATE (plain) extension_relevant: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_617c53c57c9bea02  (family 19, slot 4)
- en / chat / sender Maeve Gallagher / landlord Gerance Bärenplatz AG / Bergstrasse 36, Uster, 2.5-room flat / date 2026-09-19 / rent CHF 2420
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- OPEN (termination_received, true value False): The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice. -> say you are not sure whether what you received is a formal termination notice or whether one has actually been issued
- DENY (implied) family_home: NOT so: The flat is the family home of a married couple or registered partners.
- DENY (passing) arrears: NOT so: The termination the landlord announced is because of unpaid rent (rent arrears).
- AVOID retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- STATE (passing) extension_relevant: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_db88646bc6e3f066  (family 20, slot 1)
- en / portal / sender Samuel Castellano / landlord Liegenschaften Sternen AG / Hinterfeld 112, Steffisburg, 4.5-room flat / date 2026-10-03 / rent CHF 2160
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- DENY (plain) termination_received: NOT so: The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice.
- STATE (plain) family_home: The flat is the family home of a married couple or registered partners.
- AVOID arrears: The termination the landlord announced is because of unpaid rent (rent arrears).
- STATE (passing) retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- AVOID extension_relevant: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_f9dc66c1522b99eb  (family 20, slot 2)
- de-CH / email / sender Esther Siegrist / landlord Baugenossenschaft Sonnhalde / Mühlemattstrasse 38, Langenthal, 4-room flat / date 2026-10-03 / rent CHF 1780
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- OPEN (termination_received, true value False): The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice. -> say you are not sure whether what you received is a formal termination notice or whether one has actually been issued
- STATE (plain) family_home: The flat is the family home of a married couple or registered partners.
- AVOID arrears: The termination the landlord announced is because of unpaid rent (rent arrears).
- STATE (passing) retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- AVOID extension_relevant: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_872528b59e47e1b3  (family 20, slot 3)
- en / chat / sender Ibrahim Achterberg / landlord Ruth Messerli (private landlord) / Bergstrasse 78, Steffisburg, 4-room flat / date 2026-09-27 / rent CHF 2340
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- DENY (passing) termination_received: NOT so: The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice.
- STATE (plain) family_home: The flat is the family home of a married couple or registered partners.
- AVOID arrears: The termination the landlord announced is because of unpaid rent (rent arrears).
- STATE (plain) retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- AVOID extension_relevant: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_a256cb8045ef1f54  (family 20, slot 4)
- de-CH / portal / sender Franziska Odermatt / landlord Erbengemeinschaft Probst (private landlord) / Obere Gasse 68, Burgdorf, 3-room flat / date 2026-10-24 / rent CHF 1300
- situation: The landlord is ending the tenant's lease and the tenant wants help to contest the termination.
- DENY (passing) termination_received: NOT so: The landlord has announced (orally or informally) that the lease will be ended, but the tenant has NOT received any written termination notice.
- STATE (plain) family_home: The flat is the family home of a married couple or registered partners.
- AVOID arrears: The termination the landlord announced is because of unpaid rent (rent arrears).
- STATE (plain) retaliation_screen: The tenant believes the announced termination is retaliation for recently asserted tenancy rights.
- AVOID extension_relevant: The tenant would need an extension of the tenancy because moving out would be a hardship.

## f2cl_54f41d88de8d2b5d  (family 21, slot 1)
- de-CH / portal / sender Nicola Habegger / landlord Ruth Messerli (private landlord) / Brunnenrain 28, Steffisburg, 5.5-room flat / date 2026-09-14 / rent CHF 2380
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- DENY (plain) claim_received: NOT so: The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification.
- DENY (plain) reference_rate: NOT so: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- AVOID renovation: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.

## f2cl_0868f24595f5f79a  (family 21, slot 2)
- en / portal / sender Aoife Achterberg / landlord Hausverwaltung Pilatus AG / Mühlemattstrasse 69, Rapperswil-Jona, 5.5-room flat / date 2026-10-19 / rent CHF 2330
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- DENY (plain) claim_received: NOT so: The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification.
- AVOID reference_rate: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- AVOID renovation: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.

## f2cl_f9d6755c60c44a8d  (family 21, slot 3)
- en / phone_note / sender Tomasz Wilk / landlord Hausverwaltung Pilatus AG / Rebbergstrasse 94, Steffisburg, 4.5-room flat / date 2026-08-24 / rent CHF 2620
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- DENY (implied) claim_received: NOT so: The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification.
- AVOID reference_rate: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- AVOID renovation: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.

## f2cl_73f3fe3323a28288  (family 21, slot 4)
- de-CH / email / sender Simon Furrer / landlord Erbengemeinschaft Probst (private landlord) / Ahornweg 17, Dübendorf, 3.5-room flat / date 2026-08-25 / rent CHF 1650
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- OPEN (claim_received, true value False): The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification. -> say you are not sure whether a formal rent-increase notification has actually been sent to you
- DENY (plain) reference_rate: NOT so: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- AVOID renovation: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.

## f2cl_201a01ca1e26f323  (family 22, slot 1)
- de-CH / email / sender Ueli Rüfenacht / landlord Immo Jura Verwaltungen AG / Zelgweg 90, Brugg, 3.5-room flat / date 2026-09-13 / rent CHF 2600
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- DENY (implied) claim_received: NOT so: The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification.
- STATE (implied) reference_rate: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- AVOID renovation: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.

## f2cl_3e1bdd7883787817  (family 22, slot 2)
- en / portal / sender Harriet Ndlovu / landlord Liegenschaften Sternen AG / Bergstrasse 92, Grenchen, 3.5-room flat / date 2026-08-27 / rent CHF 1490
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- OPEN (claim_received, true value False): The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification. -> say you are not sure whether a formal rent-increase notification has actually been sent to you
- STATE (passing) reference_rate: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- AVOID renovation: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.

## f2cl_550d580f884338ae  (family 22, slot 3)
- de-CH / email / sender Seraina Lehmann / landlord Liegenschaften Sternen AG / Brunnenrain 68, Solothurn, 3.5-room flat / date 2026-09-16 / rent CHF 2140
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- DENY (passing) claim_received: NOT so: The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification.
- STATE (plain) reference_rate: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- AVOID renovation: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.

## f2cl_4f8337eaa01ddbee  (family 22, slot 4)
- en / email / sender Jonah Ortega / landlord Immo Jura Verwaltungen AG / Mühlemattstrasse 68, Dübendorf, 2.5-room flat / date 2026-08-23 / rent CHF 1320
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- DENY (plain) claim_received: NOT so: The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification.
- STATE (implied) reference_rate: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- DENY (plain) renovation: NOT so: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.

## f2cl_57bd4c7d1979c2c8  (family 23, slot 1)
- de-CH / portal / sender Nicola Rohner / landlord Verwaltung Lindenhof Treuhand GmbH / Bündtenweg 32, Brugg, 4.5-room flat / date 2026-10-15 / rent CHF 2300
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- DENY (plain) claim_received: NOT so: The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification.
- AVOID reference_rate: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- STATE (plain) renovation: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.

## f2cl_0c4512154d36a3b4  (family 23, slot 2)
- en / chat / sender Rafael Ortega / landlord Verwaltung Emme & Söhne / Ahornweg 39, Dübendorf, 2.5-room flat / date 2026-10-03 / rent CHF 1560
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- DENY (implied) claim_received: NOT so: The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification.
- AVOID reference_rate: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- STATE (passing) renovation: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.

## f2cl_ee7deb645e03a42c  (family 23, slot 3)
- de-CH / portal / sender Regula Bachmann / landlord Ruth Messerli (private landlord) / Eichholzweg 117, Kreuzlingen, 5.5-room flat / date 2026-09-15 / rent CHF 2120
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- OPEN (claim_received, true value False): The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification. -> say you are not sure whether a formal rent-increase notification has actually been sent to you
- AVOID reference_rate: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- STATE (passing) renovation: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.

## f2cl_dfa1374f699c1317  (family 23, slot 4)
- en / phone_note / sender Jonah Brennan / landlord Stiftung Wohnen Zentral / Mühlemattstrasse 65, Herisau, 4-room flat / date 2026-10-12 / rent CHF 1470
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- DENY (passing) claim_received: NOT so: The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification.
- AVOID reference_rate: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- STATE (passing) renovation: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.

## f2cl_46b76c8c72c4d34b  (family 24, slot 1)
- en / portal / sender Hannah Gallagher / landlord Wohnwerk Thur GmbH / Schulhausstrasse 79, Steffisburg, 4-room flat / date 2026-08-28 / rent CHF 2390
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- DENY (implied) claim_received: NOT so: The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification.
- STATE (passing) reference_rate: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- STATE (plain) renovation: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.

## f2cl_7910fcff8a43fe84  (family 24, slot 2)
- de-CH / email / sender Jonas Siegrist / landlord Hausverwaltung Pilatus AG / Brunnenrain 53, Wil, 3.5-room flat / date 2026-09-17 / rent CHF 2490
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- DENY (passing) claim_received: NOT so: The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification.
- STATE (passing) reference_rate: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- STATE (passing) renovation: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.

## f2cl_16523b4063cbf4e6  (family 24, slot 3)
- de-CH / chat / sender Fabian Schnyder / landlord Ruth Messerli (private landlord) / Dorfbachstrasse 94, Kreuzlingen, 3-room flat / date 2026-08-13 / rent CHF 2170
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- DENY (plain) claim_received: NOT so: The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification.
- STATE (plain) reference_rate: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- STATE (passing) renovation: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.

## f2cl_2a5be54a2bcf17a0  (family 24, slot 4)
- en / email / sender Eleanor Ferreira / landlord Stiftung Wohnen Zentral / Schulhausstrasse 107, Uster, 5.5-room flat / date 2026-09-22 / rent CHF 1530
- situation: The landlord is raising the rent and the tenant wants help to contest the increase.
- OPEN (claim_received, true value False): The landlord has announced (orally, at a tenants' meeting or by notice board) a rent increase, but the tenant has NOT received any written rent-increase notification. -> say you are not sure whether a formal rent-increase notification has actually been sent to you
- STATE (passing) reference_rate: The landlord justifies the announced rent increase with a rise in the mortgage reference interest rate.
- STATE (passing) renovation: The landlord justifies the announced rent increase with renovation or value-enhancing investment work.
