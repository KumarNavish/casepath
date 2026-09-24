# Third-party notices

CasePath application source is distributed under the Apache License 2.0 in
`LICENSE`. The released datasets in `data/` carry their own licence files:
their data is under CC BY 4.0 and their code under Apache 2.0.

Third-party text in the datasets is excluded from their CC BY 4.0 grant: in
`data/casepath-theft-pairs/`, the quoted passages of insurer policy terms, a
claim form and industry model conditions (see its `SOURCES.md`); in
`data/casepath-tenancy-claims/`, the text of the official Canton of Zurich form
templates on which 34 attachments are filled in. Quoted Swiss federal law is not
protected by copyright (Article 5 of the Swiss Copyright Act).

The bundled `synthetic-dev-60` public synthetic development corpus includes its
own `LICENSE-DATA` file with SHA-256
`b0db9041285c34543d62e1c0dc3a524ca60fd0723f9a77d12f6ab0e94f506cdc`.
It states `CC-BY-4.0` and is hash-bound in the corpus manifest. The package
contains observable claims, model-visible source registries, source documents,
and public policy or authority files. It excludes the 90 held-out research
inputs, benchmark targets, and evaluator output; the complete 150-claim dataset,
with every reference, is released separately in `data/casepath-tenancy-claims/`.

Python and JavaScript dependencies retain their upstream licenses. See
`casepath-api/requirements.lock`, `casepath-api/requirements.txt`, and
`casepath-qa/package-lock.json` for the exact resolved packages.
