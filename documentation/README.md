# Documentation

Two editions of the same manual for Big_Agent (SmartCAE AI):

| Directory | Edition | Output |
| --- | --- | --- |
| `sphinx/` | reStructuredText, built with Sphinx | HTML site (and a Sphinx-rendered PDF via `make latexpdf`) |
| `latex/` | Hand-authored LaTeX | `big_agent_documentation.pdf`, a typeset A4 manual |

Both cover the same fourteen chapters and are kept in step with each other. Pick
the HTML edition for reading and searching at a desk; pick the LaTeX edition
when the manual has to be printed, attached to a report, or handed over as a
single file.

Both editions read the version from `app/version.py` at build time, so neither
can claim a version the application does not have and there is nothing to
update by hand. Sphinx reads it in `conf.py`; the LaTeX build reads the same
file itself in `latex/version.tex` (TeX opens `app/version.py`, finds the
`APP_VERSION` line and takes the text between its quotes). If that read ever
fails, the LaTeX build still finishes, prints a line saying so, and shows the
version as `unknown`.

The manual is self-contained: it does not send the reader to other files in the
repository. Everything it needs — the discipline-profile schema, the review
trigger phrases, the corpus walkthrough — is written out in the chapter that
needs it.

## Chapters

| # | Chapter | Covers |
| --- | --- | --- |
| 1 | Overview | What the system does, product variants, design rules, data policy |
| 2 | Installation | Requirements, install, run, embedding model, Ollama, OCR |
| 3 | Configuration | Every setting in `app/config.py`, with defaults and parsing rules |
| 4 | Architecture | Layer map, request lifecycle, SQLite pragmas, jobs, vector index |
| 5 | The ingestion pipeline | Hashing, parsers, selective OCR, cleaning, chunking, embeddings |
| 6 | Retrieval and answering | Search modes and scoring, retrieval versions, QA services, chat routing |
| 7 | Report review, comparison and drafting | Rules, discipline profiles, decisions, precision, comparison, drafts |
| 8 | Catalog, library and graph | Register import, catalog-to-file matching, library scan, graph |
| 9 | The CATIA mass/CG skill | Harness, sessions, LAN behaviour, endpoints, practice mode |
| 10 | HTTP API reference | Every endpoint, grouped, with the parameters that matter |
| 11 | Data model | Tables, columns, relationships, on-disk layout, adding a column |
| 12 | Operations | LAN serving, isolated instances, monitoring, backup, upgrade, security |
| 13 | Testing and QA | The pytest contract, check scripts, golden sets, synthetic corpus |
| 14 | Glossary | The project's vocabulary |

## Build the Sphinx edition

Sphinx is a documentation-only dependency and is not in `requirements.txt`.

```powershell
& '.venv\Scripts\python.exe' -m pip install -r documentation\sphinx\requirements.txt

cd documentation\sphinx
.\make.bat html
```

The site lands in `documentation\sphinx\_build\html`; open `index.html`.

Other targets: `.\make.bat latexpdf` (a Sphinx-rendered PDF, needs a LaTeX
install), `.\make.bat linkcheck`, `.\make.bat clean`. On a POSIX shell the
`Makefile` offers the same targets (`make html`).

## Build the LaTeX edition

Needs a TeX distribution — TeX Live or MiKTeX. Only packages from a default
install are used, and it builds with `pdflatex`, so no XeLaTeX/LuaLaTeX setup is
required (Turkish characters are handled through `inputenc` + `fontenc`).

```powershell
cd documentation\latex
latexmk -pdf big_agent_documentation.tex
```

`latexmk` runs the passes the table of contents and cross-references need.
Without it, run `pdflatex big_agent_documentation.tex` twice. A `Makefile` is
included for POSIX shells (`make`, `make clean`, `make distclean`).

Layout:

```text
latex/
  big_agent_documentation.tex   main file: title page, chapter list
  version.tex                   reads APP_VERSION out of app/version.py
  preamble.tex                  packages, colours, listing styles, macros
  chapters/*.tex                one file per chapter
```

Build it from `documentation/latex` (the `Makefile` does). `version.tex` looks
for `../../app/version.py` and then `app/version.py`, so a build from the
repository root also finds it; from anywhere else the version falls back to
`unknown` rather than failing the build.

## Build artefacts

Neither build's output is committed. If `.gitignore` does not already cover
them, ignore:

```text
documentation/sphinx/_build/
documentation/latex/*.aux
documentation/latex/*.log
documentation/latex/*.out
documentation/latex/*.toc
documentation/latex/*.fls
documentation/latex/*.fdb_latexmk
documentation/latex/*.pdf
```

## Keeping it accurate

The manual describes behaviour that lives in code, so a few places are worth
re-checking when that code changes:

- **Settings** — Chapter 3 mirrors `app/config.py` and `.env.example`.
- **Endpoints** — Chapter 10 mirrors the routes in `app/main.py`. The live
  instance's `/docs` is always the authority on exact schemas; the chapter is
  the map.
- **Retrieval constants** — the weights and thresholds in Chapter 6 come from
  the class constants in `app/services/search_service.py`.
- **Tables and columns** — Chapter 11 mirrors `app/db/models.py` and the
  additive-column map in `app/db/session.py`.
- **Review rules** — Chapter 7 lists the deterministic rule ids from
  `app/services/report_review_service.py`, and its profile-file schema mirrors
  the validation contract in `app/rules/profile_catalog.py`.
- **Chat trigger phrases** — the review and revision phrases quoted in
  Chapter 13 come from `DocumentIntelligenceService._detect_intent` and
  `ReportReviewService.is_revision_comparison_question`.
