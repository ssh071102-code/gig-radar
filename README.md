# gig-radar

![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue) ![tested](https://img.shields.io/badge/tests-pytest-brightgreen)

An automated freelance lead-generation pipeline: it watches multiple job boards, scores every
lead against your positioning with an LLM, drafts a tailored proposal for your best matches, and
pushes the results straight to Telegram.

## What it does

Every run, gig-radar:

1. **Ingests** fresh listings from pluggable sources (RSS feeds, Reddit "hiring" boards, an
   Upwork saved-search scrape).
2. **Deduplicates** against everything it has already seen, so re-running never produces repeats.
3. **Triages** each new lead with a cheap LLM call, scoring it against your positioning for fit,
   budget signal, and client legitimacy.
4. **Drafts** a tailored, channel-appropriate pitch (Reddit comment, cold email, Upwork cover
   letter, or DM) for only the top-N highest-scoring leads, using a stronger model.
5. **Pushes** each drafted lead as a formatted Telegram message, ready to review and send.
6. **Persists** state to SQLite so failures never get lost — a lead that fails to score is
   retried next run instead of silently dropped, and a lead that fails to push is never marked
   as sent.

## Architecture

```
sources (RSS / Reddit / Upwork) --> ingest + dedup --> LLM triage --> top N --> LLM draft --> Telegram push
                                          |                  |                       |
                                          v                  v                       v
                                     SQLite store      score + category        opening + draft
```

Design choices worth calling out:

- **Pluggable source adapters.** Every source implements one `fetch() -> list[RawItem]`
  method (`gig_radar/adapters/`). Adding a new board means writing one adapter, not touching
  the pipeline.
- **Structured LLM I/O.** Prompts ask for a fixed, delimited text format rather than free-form
  chat, and responses are parsed defensively — a malformed response degrades a single lead
  instead of crashing the run.
- **Graceful degradation everywhere.** A single source failing (`gig_radar/pipeline.py::ingest`)
  never blocks the others. A single lead failing to score or draft is marked and retried, never
  silently dropped. A single Telegram push failing never blocks the rest of the batch, and the
  token-bearing URL is never logged.
- **Cost control by design.** Every fresh lead gets a cheap triage pass; only the leads that
  clear both `min_score_to_push` and the `top_n` cutoff get a full drafting pass on a more
  expensive model. Cheap filtering happens as early as possible — keyword matching runs at fetch
  time before anything reaches the LLM at all.

## Tech

Python · [httpx](https://www.python-httpx.org/) · [feedparser](https://feedparser.readthedocs.io/)
· [pydantic](https://docs.pydantic.dev/) · [typer](https://typer.tiangolo.com/) · Anthropic SDK ·
SQLite · pytest

## Quickstart

```bash
# install
pip install -e ".[dev]"

# configure
cp secrets/.env.example secrets/.env
# fill in ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
# edit config/positioning.md with your own case studies and rate

# preview without pushing anything
gig-radar dry-run

# run for real
gig-radar run
```

Source and score thresholds live in `config/sources.yaml` and `config/settings.yaml` — enable or
disable adapters, tune `top_n` and `min_score_to_push`, and swap models per step.

## Tests

```bash
pytest
```

Coverage spans every layer of the pipeline: source adapters (RSS, Reddit, Upwork), the SQLite
store, config loading, LLM-facing triage and drafting logic (with a fake LLM client, no network
calls), Telegram push formatting, and full pipeline integration tests covering isolation,
deduplication, and dry-run behavior.
