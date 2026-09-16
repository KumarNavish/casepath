# ICLR 2027 submission package

Canonical submission source: `main.tex`; compiled review PDF: `main.pdf`. The paper uses the official ICLR 2027 style files copied here from the conference kit. Main text ends on page 8; required/recommended statements and references begin on page 9; appendices follow the bibliography and are outside the 9-page main-text limit.

Regenerate figures/tables from committed analysis artifacts:

```bash
cd research/casepath/iclr2027
/opt/anaconda3/bin/python make_submission_assets.py
```

Compile from this directory with a LaTeX engine that supports the ICLR style. The development checkout uses Tectonic. No author-identifying repository URL appears in the paper. Submit `main.pdf` as the paper+text supplement; submit the anonymized code ZIP produced by `build_anonymous_supplement.py` as code supplementary material.

Canonical numerical sources are `../artifacts/EVALUATION_VALIDITY.json` and `../artifacts/ADJUDICATOR_ROBUSTNESS.json`. Run `../verify_artifacts.py` before any submission build.
