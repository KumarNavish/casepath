# CasePath development across Mac and Codex Cloud

Use the Mac coordination chat for the product conversation and integration.
Use the published `casepath` Codex Cloud environment for `KumarNavish/casepath`
for bounded implementation, independent review, and parallel deterministic tests.
The Mac chat stays local. Each cloud task has its own workspace; reuse the
prepared environment and preserve results in Git and task artifacts.

## Choose where work runs

| Work | Owner and execution location |
| --- | --- |
| Define the outcome, split independent work, review and combine changes | Mac coordination chat |
| Repository implementation, Linux checks, independent code review | Codex Cloud `casepath` |
| Signed-in apps, local files, browser interaction, visual and accessibility review | Mac |
| Mac-specific regressions and legacy migration process inspection | Isolated normal clone on Mac; report any audit failure |
| Credentials and already-authorized hosting operations | Mac integration owner using the existing secret stores and native hosting tools |
| Durable source and review history | `KumarNavish/casepath` on GitHub |

Small changes tied to Mac inspection can be completed locally. Send independent
work to Cloud when its isolation or parallelism saves time. Local subagents
inherit their execution host; do not describe them as cloud workers.

## Establish the source before starting

The active integration branch for this workstream is
`codex/casepath-sites-hosting-20261009`. `main` remains the repository default;
it does not contain this work merely because an environment started from it.
Confirm the current owner and fetch the active branch before every task:

```sh
git fetch origin
git status --short
git rev-parse HEAD
git rev-parse origin/codex/casepath-sites-hosting-20261009
```

Record the full base commit in the handoff. Preserve an existing checkout's
uncommitted work. Give each implementation task its own `codex/` branch and
non-overlapping source scope. Only the integration owner advances the shared
integration branch. Start cloud repository work through **Work in → Cloud →
casepath**, with the intended branch selected and verified inside the task.
An app handoff between local checkouts and worktrees does not establish cloud
execution; check the task's actual host.

## Send a bounded handoff

Every task should carry enough context to work without the Mac filesystem:

```text
Repository: KumarNavish/casepath
Environment: published casepath Codex Cloud environment
Integration branch and exact base SHA: <verified values>
Outcome and acceptance evidence: <one bounded deliverable>
Worker branch and allowed source paths: <non-overlapping scope>
Other active owners and excluded paths: <current assignment>
Validation: <focused commands and required platform checks>
Return: pushed commit or PR, base SHA, changed files, commands and results,
        failures/skips, artifact locations, and unresolved constraints.
```

Read this guide and repository `AGENTS.md` in the cloud task. Use the published
environment's prepared dependencies and startup instructions. Each task must
verify its checked-out SHA before editing or testing. Use isolated deterministic
fixtures; retain the exact test command and exit status. Parallel test processes
need separate HOME, temporary, database, and artifact paths. Do not launch broad
suites merely to prove that a handoff works.

Cloud tasks may seal their own branches as required by `CONTRIBUTING.md` for
validation. The Mac integration owner regenerates the final shared
`casepath/source-manifest.json` after combining changes. A worker's seal cannot
describe another worker's files. Keep independent source scopes even though
their generated manifest diffs may overlap.

## Bring the result back to the Mac

Fetch the returned branch or PR, inspect its exact commit, confirm the agreed
base and file scope, and review the diff. Integrate only reviewed changes;
preserve another writer's work. Reconcile generated sealing metadata after
integration and run checks appropriate to the combined change.

Use a fresh normal clone for disposable Mac validation. Run `./bin/casepath
prepare`, then use `./bin/casepath dev` for browser inspection when the change
needs it. Check that port 4173 is free first and stop only the server owned by
that validation task. Routine `dev` uses deterministic mode without provider
credentials. Save screenshots and relevant logs with the task evidence.

Git commits and saved artifacts are the handoff boundary. Do not synchronize
`.runtime`, live databases, Keychain contents, environment files, or a running
server between Mac and Cloud. Review artifact contents before moving them.

## Platform and release limits

The current cloud sandbox cannot read `/proc/1/maps` for the legacy migration
audit. Those checks are unverified there; preserve the fail-closed audit and
route necessary migration validation to an isolated supported host. Do not add
blanket skips or weaken process inspection to make the cloud suite green.

The published setup includes the pinned Python environment, writable dependency
caches, and copy-mode package installation. It also documents the cloud test
runner's Node PATH constraint. Use the saved setup instructions instead of
changing product security checks or installing a second conflicting runtime.

The hosted product has its own release identity and persistent database. A new
development commit is not a deployment. Keep the local paid writer stopped
after hosted cutover; its old ledger is not a writable copy of production.
Model credentials, the production journal, original private files, and the paid
demo allowance stay outside routine cloud development. Hosting changes follow
[hosted operations](HOSTED_CASEPATH.md) and the user's authorization.

The reusable environment is prepared compute, not a continuously running shared
VM. Save durable changes and evidence before a task ends. Prefer a short task
receipt to relying on an old workspace or a remembered passing test.
