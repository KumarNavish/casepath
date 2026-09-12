# Platform support

The launcher targets macOS and POSIX Linux. It requires Bash, Git, `uv`,
`lsof`, and either `lockf` or `flock`. It installs Python 3.13.9 and the pinned
Python dependencies with `uv`. The initial environment installation requires
network access; ordinary deterministic product use does not call a provider.

Run `./bin/casepath prepare` in a normal Git clone, then `./bin/casepath dev`.
The browser product is served from one localhost origin at
`http://127.0.0.1:4173/`. The listener must be available. Windows users need a
compatible Linux environment; native Windows execution is not validated.

See [setup and first claim](setup.md) for the complete fresh-clone path and
[troubleshooting](troubleshooting.md) for fail-closed launch errors.

Node.js and `npm ci --prefix casepath-qa` are needed for the JavaScript QA
programs, not for serving the application. Several historical browser gates
require a specific Ego Lite executable and the original private test setup;
they are not portable fresh-clone acceptance commands.

See [HANDOFF_VALIDATION.md](HANDOFF_VALIDATION.md) for executed platform checks.
No provider key, hosted API, Docker daemon, database server, message broker, or
cloud account is required. The local application is intended for loopback use;
authentication and multi-tenant hosting are outside this handoff.
