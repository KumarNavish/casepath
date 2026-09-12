# CasePath frontend

This directory contains the static browser workspace and its layered v20 assets
(release contract 2.2; API/pipeline 15.2). The browser displays original source
artifacts separately from extraction, interpretation, process guidance, and
journaled actions.

Run the product from the repository root with `./bin/casepath dev`. The local
launcher builds the curated static site and serves it with the API from
`http://127.0.0.1:4173`; no frontend package install is required.

Historical release metadata names hosted services, but those services run an
older source line and are not the target of this standalone package. See
[`docs/architecture-authority.md`](../docs/architecture-authority.md) before
changing source, state, or evidence behavior.
