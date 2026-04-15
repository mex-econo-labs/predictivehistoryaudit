# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Systematic content analysis of the "Predictive History" YouTube channel (Xueqin Jiang / Professor Jiang). The repo holds 145 SRT transcripts, 143 per-lecture JSON analyses conforming to `analysis/schema.json`, a living geopolitical briefing used to score predictions, and a Jinja2 static-site generator that publishes the audit. Read `README.md` for methodology, scoring rubric, and prediction-status definitions before editing analysis content.

## Common commands

```bash
# Analyze a single video end-to-end (transcript → Claude JSON → screencaps → site → commit/push)
./analyze.sh <youtube_url_or_id> [--no-screencaps] [--no-build]

# Batch-analyze all unanalyzed transcripts
cd analysis && ./batch-analyze.sh [--dry-run] [--series "Civilization"] [--limit N]

# Re-score untested predictions against the current briefing (patches analysis files in place)
cd analysis && ./score-predictions.sh [--dry-run]

# Daily: refresh briefing-data.json, calibration-reference.md, geopolitical-briefing.md
cd analysis && ./daily-briefing-update.sh

# Monthly: full re-evaluation of all ~593 predictions across 143 lectures
cd analysis && ./monthly-scoring-run.sh

# Rebuild the static site only
cd analysis && python3 build.py [--output-dir docs]

# Regenerate aggregate channel stats / refresh view counts
cd analysis && python3 generate-channel-data.py
cd analysis && ./update-views.sh

# Extract screencaps for one analysis file
cd analysis && python3 screencap.py --input <file>.json --caps-dir caps

# Validate a generated analysis JSON
python3 -c "import json; json.load(open('analysis/<slug>.json'))"
```

Cron schedule lives in `cron.conf` (installed on LXC 105 under user `steve`): daily briefing at 06:00, monthly rescore on the 1st at 07:00.

## Architecture

**Data flow.** `analyze.sh` (and `batch-analyze.sh`) drive a fixed pipeline: yt-dlp pulls the SRT into `transcripts/`, the filename is parsed into `series / episode / title / video_id`, metadata is fetched, then `claude -p --model opus` is shelled out with a prompt that passes the schema, one reference analysis (`geo-strategy-08.json`), and the calibration reference. The CLI writes JSON directly to `analysis/<slug>.json`; the script then validates it, extracts screencaps, rebuilds the site, and commits. Adding a new pipeline stage almost always means editing `analyze.sh`, `batch-analyze.sh`, and possibly `build.py` in lockstep.

**Slug convention.** Episodes in a known series → `<series-slug>-<episode>` (e.g. `civilization-15`). Interviews / guest appearances with no episode → `interview-x-<first8videoid>`. Any filename whose left-of-colon component is not in the `KNOWN_SERIES` list (`Civilization|Secret History|Game Theory|Geo-Strategy|Geo-Strategy Update|Great Books|Interview`) is reclassified as `Interview`. Filenames use the **fullwidth colon `：` (U+FF1A)**, not ASCII `:` — the parser splits on `：`.

**Schema is load-bearing.** `analysis/schema.json` defines the contract every analysis must satisfy. `build.py`, `score-predictions.py`, `generate-channel-data.py`, and all Jinja templates index into specific fields (`meta.video_id`, `thesis.predictions[*].status`, `scores.<dim>.score`, `notable_quotes[*].ironic_mirror`, `cross_references.*`). Breaking the schema silently breaks the dashboard, patterns, and mirrors pages. When adding fields, update the schema and at least one example analysis.

**Prediction status lifecycle.** Predictions start `untested` or `unfalsifiable`. `score-predictions.sh` extracts only untested predictions into a worklist, sends them with `geopolitical-briefing.md` + `calibration-reference.md` to Claude, and patches only files with status changes. `calibration-reference.md` is the ground-truth table of confirmed real-world events (Op Midnight Hammer June 2025, Twelve-Day War June 13–24 2025, 2026 Iran War from Feb 28 2026, Hormuz blockade, etc.) — update it first when new events land, then rescore.

**Site generator.** `build.py` reads every `analysis/*.json` (skipping `schema.json`, `briefing-data.json`, worklist/results files), aggregates into dashboard / patterns / mirrors / channel / briefing pages via `templates/*.html`, and writes to `dist/` by default. Social cards live as committed PNGs under `analysis/static/cards/` — Cloudflare Pages has no ImageMagick, so card generation happens locally and the PNGs must be checked in.

**Shared infra.** The repo runs inside LXC 105 on the Proxmox host (see `/home/steve/.claude/CLAUDE.md` knowledge base). NFS-shared Claude memory at `/mnt/claude-memory` is not part of this project and should not be modified from here.

## Pipeline log

Every `./analyze.sh` invocation appends structured JSONL records to `analysis/pipeline.log` (gitignored). One record per phase transition: `start / transcript / metadata / claude_done / screencaps / built / committed / pushed / exit`. Each record carries `run_id` (joins a single invocation's phases), `host`, `user`, `tty`, `pid/ppid`, `cwd`, and — critically for debugging — an **`ancestry` chain** of parent processes up to init, with 80 chars of each cmdline. The chain identifies whether a run came from an interactive shell, a Claude Code session, `claude-remote-control`, cron, tmux, ssh, etc. Also captures `SSH_CONNECTION` and `CLAUDE_SESSION_ID` if set.

Common queries:

```bash
# Last 20 starts with invoker context
jq -c 'select(.phase == "start") | {ts, argv, ancestry: .ancestry[0:3]}' \
   analysis/pipeline.log | tail -20

# Failed runs (exit code != 0)
jq -c 'select(.phase == "exit" and (.code | tonumber) != 0)' analysis/pipeline.log

# All phases of one run
jq -c --arg id "<run-id>" 'select(.run_id == $id)' analysis/pipeline.log
```

The log is intentionally local only (not committed) — it can contain ambient env info and grows per-run. `analysis/log-pipeline.py` is the helper that writes it; if `analyze.sh` grows new phases, call `log_phase <name> key=val ...` from there.

Batch/daily/monthly scripts still write to their own named logs (`batch-analyze.log`, `daily-briefing.log`, `monthly-scoring.log`). Only `analyze.sh` (the interactive single-video pipeline) writes to `pipeline.log`. Unifying them all into `pipeline.log` would be a reasonable next step; not done yet.

## Conventions specific to this repo

- The `ironic_mirror` field on notable quotes is a deliberate analytical instrument, not decoration — populate it whenever a criticism aimed at one civilization applies equally or more to one the speaker favors (typically China, Russia). Leave it empty only when there is genuinely no mirror.
- `type: "prediction"` is forward-looking; `type: "claim"` is past/present/analytical. Do not conflate.
- `status_note` is required for any status other than `untested` or `unfalsifiable`, and should cite the calibration event or briefing entry that justifies the verdict.
- Rhetoric and notable-quotes arrays target 8–10 entries each, all with timestamps.
- Scoring is 1–5 with **5 = best** across every dimension, including `normative_loading` (5 = neutral) and `civilizational_framing` (5 = symmetric). Do not invert.
- Always back up the database before starting a sprint with database changes (global rule from user CLAUDE.md — not currently relevant since this project has no database, but applies if one is added).
