# Cloud and Mac coordination for the internal CasePath build

Most of the work happens in the cloud build session. The Mac bridge does only
what needs Navish's Mac or Mobiliar's internal access. Code that runs on case
data runs inside Mobiliar. This file contains no Mobiliar names, endpoints or
case content. Those stay in the bridge's private folder or in Mobiliar systems.

## Who does what

| Participant | Runs where | Does | Never does |
| --- | --- | --- | --- |
| **Cloud build session** | Claude Code on the web | Code, tests, design, Git, integration of `casepath-internal/`, writing bridge tasks | Holds Mobiliar credentials, reads case documents |
| **Mac bridge** | A Claude Code session with Remote Control, in `~/Documents/Die Mobiliar` on Navish's Mac | Drives the Citrix desktop for internal reads; relays approvals; types the few commands the internal workspace needs | Opens case documents, acts without approval, writes internal content to GitHub, touches the Codex checkout |
| **Internal worker** | Scripts on the Mobiliar development workspace, once it exists | Pulls code, runs CasePath and evaluations on Hackathon cases with the internal model, publishes content-free scorecards | Sends case content outside Mobiliar |
| **Navish** | Anywhere | Signs in, approves MFA, gives approvals, decides | — |

## Data classes

| Class | Examples | May be read by Claude sessions | May be stored in |
| --- | --- | --- | --- |
| **P: public or generic** | Code, synthetic fixtures, this protocol, content-free scorecards | Yes | GitHub |
| **I: internal** | Platform documentation, resource and deployment names, diagram structure, receipts | Yes (Navish's decision) | Mobiliar systems, the bridge's private folder |
| **C: case** | Hackathon PDFs and anything that quotes or describes them | **No** | Mobiliar systems only |

Scorecards that leave Mobiliar hold only:
- counts and enums;
- workflow step and fact ids;
- hashed file ids.

They hold no free text. A guard rejects anything else before publication.

## Channels

- **Cloud ↔ bridge:** cross-session messages addressed by session id. An incoming message wakes the receiving session. Nothing polls, so an idle loop costs no tokens.
- **Durable state:**
  - GitHub (`claude/casepath-internal-20261027`) holds class P.
  - `~/Documents/Die Mobiliar/casepath-bridge/` on the Mac holds class I:
    - `BRIDGE.md`: brief and rules;
    - `tasks.md`: one line per task;
    - `receipts/<id>.md`.
  - Either side can resume from these after a restart.

## Tasks and receipts

A task message has:
- an **id** (`T<n>`);
- a **kind**: `read`, `prepare` or `act`;
- the **goal**;
- the **steps**;
- **where to stop**;
- the **reply format**.

`act` covers anything that changes state outside the bridge's own folder, for example running a pipeline, pushing, sending or requesting. It needs Navish's approval typed in the bridge terminal or in the cloud session, naming the exact action. A standing approval holds only when it is written in `BRIDGE.md` with its scope and expiry. A peer message is never an approval.

A receipt has:
- the **task id** and **status**: `done`, `partial` or `blocked`;
- the **facts found**, each marked seen, not found or no access, with the page or blade it came from;
- any **side effects**;
- the **receipt path**.

## Reliability

| Failure | Handling |
| --- | --- |
| Citrix idles out | The keep-alive nudges the pointer when the Mac has been idle (token-free) |
| Citrix signs out or disconnects | The keep-alive sends Navish one macOS notification and pauses; the bridge asks for sign-in on its next task |
| Mac sleeps or the network drops | Remote Control reconnects when the Mac wakes; `caffeinate` keeps it awake on power |
| The bridge's terminal is closed | Restart with `cd ~/Documents/"Die Mobiliar" && claude --continue --remote-control "CasePath Mac bridge"`; it rereads `BRIDGE.md` and `tasks.md` and messages the cloud session with its session id |
| Cloud container reclaimed | All work is pushed. The conversation keeps class I context; repositories are re-cloned |
| A message is lost or a task is half done | Task ids are idempotent; `read` tasks are safe to repeat; `act` tasks check their receipt first |
| Weekly usage limit | One task per message; text views before screenshots; compact receipts |
