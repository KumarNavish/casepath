# Repair round 4: development files touched by revision 3 (second look)

DEVELOPMENT material, prepared 2026-11-12. No text was written or judged for this note and no model was called.
Evidence: `lint/verify_rev3.py` (`lint/VERIFY_REV3.json`, every supplied attachment whose items revision 3 rewords
or re-notes) and a script check of the attachment texts against the revised `checkable_as`. List and reasons:
`dev/REPAIR_R4_LIST.json`. Standing rule as in round 3: a text that differs from its design is rewritten once; a
file already rewritten once is dropped and counted; a re-checked file goes through the keep rule of
`assemble.py` (not mentioned <-> stated false with an unchanged reference).

## What revision 3 touches

| Regime | Change | Supplied attachments | Effect on stored files |
|---|---|---|---|
| tenancy | form item: graduated-rent exception; title without "(with any covering letter)" | 7 increase notices | none: the exception only widens and applies only where the file states a graduated step (ten_e4858b3af131, designed missing "reasons given"); ten_db552dbb3c23 (designed missing the form item) states none |
| theft | stolen-items list: any way of acquisition | 16 lists | none: the item only widens (a gift or inheritance is still shown); no designed missing item is this one |
| theft | policy: complete list of covers; sum agreed for the simple-theft-away cover, only where the file states the cover is included | 9 away policies | see below |
| dismissal | item notes: probation / notice-period clause left to the story in types without the fact | 13 contracts (wrongful 6, immediate 7) | immediate: none (no file mentions a probation clause; script); wrongful: 6 to re-check (each message mentions the notice period) |

Theft policies, script check (`attachments/insurance_policy.clean.txt`):

| File | Kept in round | Designed | Cover listed / included / its sum shown | Decision |
|---|---|---|---|---|
| the_0cd1b047049a | 1 | sufficient | listed, not taken, - | re-check (complete list?) |
| the_7d2b6a2bdce4 | 1 | sufficient | listed, not taken, - | re-check |
| the_1024620d6055 | 2 | sufficient | yes / yes / yes | re-check |
| the_2774fb90433e | 2 | sufficient | yes / yes / yes | re-check |
| the_819379d12c03 | 1 | missing the insured location | yes / yes / yes (headed "extract") | re-check |
| the_9355c558630a | 1 | sufficient | yes / yes / yes | re-check |
| the_c50e0bd7b054 | 1 | sufficient | yes / yes / yes | re-check |
| the_d9579f891719 | 2 | missing the list of covers | no list, no cover sum; the file states the cover is included | **dropped**: now misses two items; already rewritten once |
| the_dd72ec4e53dd | 1 | missing the sum insured | listed, not taken | **not changed, for the planner** (below) |

**the_dd72ec4e53dd (stopped, not changed).** Its designed missing item was "its sum insured". Under ruling (b) that
item applies only where the file states the cover is included; this file states it is not taken. The designed state
(insufficient) therefore no longer holds: the policy would be sufficient, and the reference for `insurance_policy`
would change from present_insufficient to present_sufficient. References are not changed here. Options for the
planner: drop the file and count it, or re-design its policy attachment (then its reference changes). The test
suite lists it in `KNOWN_STALE_MISSING`.

## Prepared

- `dev/theft/rewrite_r4/PLAN.json`: 7 re-checks, 1 drop (the_d9579f891719), no rewrite.
- `dev/dismissal/rewrite_r4/PLAN.json`: 6 re-checks (dis_188837a70acc, dis_408b774aa7db, dis_c5e1bd4a1483,
  dis_dd12420e6a78, dis_f5520e9336bd, dis_fb44c47f6ec7).
- No writer bundles: no file qualifies for a rewrite now (`rewrite_r4/bundles/` is empty by design). Rewrites of
  re-checked files that differ come from round 5 (below).
- Tenancy: no round 4.

## Commands for the planner (from `research/tmis2026/study4`)

```
for r in theft dismissal; do python3 -I -B generator/assemble.py blind-in --regime $r --round 4; done
#    expect 7 (theft) and 6 (dismissal) inputs
# blind-check session (BLIND_CHECK_TASK.md): dev/<r>/blindcheck/in/round4/ -> dev/<r>/blindcheck/out/round4/
for r in theft dismissal; do python3 -I -B generator/assemble.py compare --regime $r --round 4; done
# only if a re-checked file differs (and the keep rule does not keep it):
python3 -I -B generator/assemble.py repair-prepare --regime <r> --round 5 --from-compare 4
#    files never rewritten get rewrite bundles in dev/<r>/rewrite_r5/bundles/ (writing session: written/<id>.r5.json);
#    the_1024620d6055 and the_2774fb90433e (kept in round 2) are dropped if they differ.
python3 -I -B generator/assemble.py blind-in --regime <r> --round 5      # then blind check, then
python3 -I -B generator/assemble.py compare  --regime <r> --round 5
# decide the_dd72ec4e53dd (drop, or re-design), then
for r in tenancy theft dismissal; do python3 -I -B generator/assemble.py finalize --regime $r; done
python3 -I -B lint/verify_rev3.py
python3 -I -B generator/test_generator.py
```

## What `final/` will then contain

- tenancy: 59, unchanged.
- theft: 59 minus the_d9579f891719 (dropped now), minus any re-checked policy that differs and cannot be rewritten
  (the two round-2 files) or whose rewrite still differs; plus the planner's decision on the_dd72ec4e53dd. At most 58.
- dismissal: 58, minus any of the six whose round-5 rewrite still differs.
- References of every kept file stay byte-identical; dropped files' folders move to `dev/<regime>/dropped/`.
