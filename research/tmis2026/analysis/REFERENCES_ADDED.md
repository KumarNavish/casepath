# References added (verified 2026-11-11)

New entries are in `paper/references_added.bib`. `paper/references.bib` was not
edited. Every entry below was confirmed from a metadata record fetched on
2026-11-11. The "relevance" sentence comes only from the abstract in that
metadata. Where no abstract was available, the line says "abstract not read".
Services used: Crossref, arXiv API, OpenReview API, Semantic Scholar (batch
endpoint), OMG and EUR-Lex. DBLP returned a bot challenge and OpenAlex returned
a rate-limit error, so neither was used.

## New entries

- `sein2011action`: https://api.crossref.org/works?query.bibliographic=Action+Design+Research+Sein+Henfridsson+Purao+Rossi+Lindgren (DOI 10.2307/23043488). Relevance: proposes action design research, in which building the IT artifact, intervening in the organization and evaluating it happen concurrently, because artifacts are shaped by their organizational context.
- `dellermann2019hybrid`: https://api.crossref.org/works?query.bibliographic=Hybrid+Intelligence+Dellermann+Ebel+Sollner+Leimeister (DOI 10.1007/s12599-019-00595-2). Abstract not read. The Semantic Scholar abstract field contains the article's opening text, not an abstract.
- `dietvorst2015algorithm`: https://api.crossref.org/works/10.1037/xge0000033. Abstract not read.
- `parasuraman2010complacency`: https://api.crossref.org/works?query.bibliographic=Complacency+and+bias+in+human+use+of+automation+attentional+integration (DOI 10.1177/0018720810376055). Relevance: automation bias produces omission and commission errors with imperfect decision aids, affects both naive and expert users, and cannot be prevented by training or instructions.
- `hull2008artifact`: https://api.crossref.org/works/10.1007/978-3-540-88873-4_17 (book: https://api.crossref.org/works/10.1007/978-3-540-88873-4). Abstract not read.
- `pesic2006declarative`: https://api.crossref.org/works/10.1007/11837862_18 (book: https://api.crossref.org/works/10.1007/11837862). Abstract not read.
- `bruns1999model`: https://api.crossref.org/works/10.1007/3-540-48683-6_25 (book: https://api.crossref.org/works/10.1007/3-540-48683-6). Abstract not read.
- `famelis2012partial`: https://api.crossref.org/works?query.bibliographic=Partial+models+towards+modeling+and+reasoning+with+uncertainty+Famelis (DOI 10.1109/icse.2012.6227159). Abstract not read.
- `reiter1980logic`: https://api.crossref.org/works?query.bibliographic=A+logic+for+default+reasoning+Reiter (DOI 10.1016/0004-3702(80)90014-4). Abstract not read.
- `gordon2007carneades`: https://api.crossref.org/works?query.bibliographic=Carneades+model+of+argument+and+burden+of+proof+Gordon+Prakken+Walton (DOI 10.1016/j.artint.2007.04.010). Abstract not read.
- `kuhn2023semantic`: https://api.openreview.net/notes/search?term=Semantic+Uncertainty+Linguistic+Invariances&limit=3 (forum VD-AYtP0dve, venueid ICLR.cc/2023/Conference) and https://export.arxiv.org/api/query?id_list=2302.09664. Relevance: introduces semantic entropy, which measures LLM uncertainty over meanings rather than surface strings and predicts question-answering accuracy better than comparable baselines.
- `farquhar2024detecting`: https://api.crossref.org/works?query.bibliographic=Detecting+hallucinations+in+large+language+models+using+semantic+entropy (DOI 10.1038/s41586-024-07421-0). Relevance: entropy-based uncertainty estimators computed at the level of meaning detect confabulations, which are arbitrary and incorrect LLM generations, across datasets and tasks without task-specific data.
- `gao2023enabling`: https://api.crossref.org/works?query.bibliographic=Enabling+Large+Language+Models+to+Generate+Text+with+Citations+Gao+Yen+Yu+Chen (DOI 10.18653/v1/2023.emnlp-main.398) and https://export.arxiv.org/api/query?id_list=2305.14627. Relevance: introduces ALCE, a benchmark with automatic metrics for fluency, correctness and citation quality of LLM answers that cite retrieved evidence.
- `howard1966information`: https://api.crossref.org/works?query.bibliographic=Information+value+theory+Howard+1966 (DOI 10.1109/tssc.1966.300074). Abstract not read.
- `eu2024aiact`: https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689 (also https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng). This is a legal text, so it has no abstract. Insurance provisions, read in the official text:
  - Annex III, point 5(c) lists as high-risk "AI systems intended to be used for risk assessment and pricing in relation to natural persons in the case of life and health insurance".
  - Article 27(1) requires deployers of the systems in Annex III points 5(b) and (c) to carry out a fundamental rights impact assessment before deployment.

## Already in references.bib (confirmed, not duplicated)

- Hevner et al. 2004 is `hevner2004design`. Its MISQ 28(1):75-106 and DOI 10.2307/25148625 match Crossref. Relevance: gives a conceptual framework and guidelines for executing and evaluating design-science research in IS.
- Gregor and Hevner 2013 is `gregor2013positioning`. Its MISQ 37(2):337-355 and DOI 10.25300/MISQ/2013/37.2.01 match Crossref. Relevance: proposes the DSR knowledge contribution framework and a DSR communication schema.
- Peffers et al. 2007 is `peffers2007design`. Its JMIS 24(3):45-77 and DOI 10.2753/MIS0742-1222240302 match Crossref. Abstract not read.
- Guha et al. 2023 is `guha2023legalbench`. Its NeurIPS 36, pp. 44123-44279 and DOI 10.52202/075280-1915 match Crossref. Relevance (arXiv 2308.11462): presents 162 legal-reasoning tasks covering six types of legal reasoning, built with legal professionals.
- CMMN is `omg2016cmmn`. The page https://www.omg.org/spec/CMMN/ lists version 1.1 as the latest formal version: December 2016, document formal/16-12-01, with 1.0 dated May 2014. This matches the existing entry.

## Correction for an existing entry (not applied)

- `saeidi2018sharc`: https://api.crossref.org/works?query.bibliographic=Interpretation+of+Natural+Language+Rules+in+Conversational+Machine+Reading gives:
  - pages 2087-2097;
  - DOI 10.18653/v1/D18-1233;
  - publisher Association for Computational Linguistics.

  The authors, title and booktitle match the existing entry. Suggested change: add `pages = {2087--2097}` and `doi = {10.18653/v1/D18-1233}`, and keep or drop the arXiv note. Relevance (arXiv 1809.01494): reading regulations to answer "Can I...?" questions requires interpreting rules and applying background knowledge, and underspecified questions require asking clarification questions.

## Not confirmed

- FINMA 2024 AI guidance: left out. https://www.finma.ch/en/documentation/finma-guidance/ and https://www.finma.ch/en/news/ were fetched, but both load their document lists dynamically. The site's list API needs a POST request, and that request was not permitted in this session. The title, number and date were therefore not confirmed from an official page.
