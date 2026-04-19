# predictive_history pipelines

This doc describes the orchestration scripts that drive this repo — what each
one does, when it runs, what it commits, and how to debug it. CLAUDE.md has
the *conventions* (schema, scoring, ironic mirrors); this doc is about the
*mechanics*.

## Entry points

| Script | Scope | When it runs |
|---|---|---|
| `./analyze.sh <url>` | One video end-to-end | Interactive, ad hoc |
| `analysis/batch-analyze.sh` | All unanalyzed transcripts | Ad hoc catchup |
| `analysis/daily-briefing-update.sh` | Refresh briefing + calibration | Cron, daily 06:00 |
| `analysis/monthly-scoring-run.sh` | Re-score all ~593 predictions | Cron, 1st of month 07:00 |
| `analysis/score-predictions.sh` | Re-score only untested predictions | Ad hoc, after briefing updates |
| `analysis/update-views.sh` | Refresh YouTube view counts | Ad hoc |
| `analysis/generate-channel-data.py` | Rebuild aggregate channel stats | Ad hoc after bulk changes |
| `analysis/build.py` | Render static site to `dist/` | Called by the above; can run standalone |

Cron installation lives in `cron.conf` (installed on LXC 105 under user
`steve`). Changes to cron timing happen there.

## The one rule that matters

**When asked to "analyze a video", run `./analyze.sh <url_or_id>`.** Do not
write `analysis/<slug>.json` by hand. Hand-rolling skips screencaps, site
build, commit, push, and — critically — the `pipeline.log` audit trail that
makes later debugging possible.

## What analyze.sh does

```
1. Download transcript        → transcripts/<Title> [<VIDEO_ID>].en.srt
2. Parse metadata             → SERIES / EPISODE / TITLE / SLUG from filename
                                (splits on fullwidth colon ：, U+FF1A)
3. Existing-JSON prompt       → [y] re-run Claude / [n] reuse (default) / [a] abort
4. Fetch YouTube metadata     → upload_date, view_count via yt-dlp
5. Run Claude subprocess      → analysis/<slug>.json (skipped if reusing)
6. Extract screencaps         → analysis/caps/<VIDEO_ID>_*.jpg (idempotent)
7. Build static site          → dist/
8. Commit + push              → JSON, transcript, caps, social cards
```

Every phase logs a JSONL record to `analysis/pipeline.log` (gitignored) via
`analysis/log-pipeline.py`. Records include `run_id`, `phase`, ancestry
chain of parent processes, and phase-specific data. See CLAUDE.md §"Pipeline
log" for query recipes.

## Slug rules

- Series with a numeric episode: `<series-slug>-<episode>` → `civilization-15`
- Known series without episode: `<series-slug>-x-<first8videoid>` → `interview-x-abc12345`
- **Unknown series are reclassified as `Interview`.** `KNOWN_SERIES` =
  `Civilization | Secret History | Game Theory | Geo-Strategy | Geo-Strategy Update | Great Books | Interview`
- Filenames use the fullwidth colon `：` (U+FF1A). ASCII `:` will not parse.

## Publish (what happens after push)

The repo is `mex-econo-labs/predictivehistoryaudit` on GitHub, deployed by
Cloudflare Pages. Cloudflare runs `python3 build.py` at deploy time and
serves `dist/`. There is **no `wrangler.toml` in this repo** — Cloudflare
uses its dashboard settings. If deploys silently stop working (site stale
despite successful git pushes), check the Cloudflare Pages build log for
"Output directory not found" or similar — the fix is typically to add a
`wrangler.toml` pinning `pages_build_output_dir = "./dist"` (or whatever
build.py emits).

**Social cards are special.** Cloudflare's build environment has no
ImageMagick, so per-lecture social cards are generated locally and committed
as PNGs under `analysis/static/cards/`. Do not remove that directory or
stop committing the cards — the Open Graph / Twitter meta tags will 404.

## Failure modes and triage

- **`./analyze.sh` fails at step 5 (Claude)**: rare, usually a transient API
  error. Re-run; the transcript/metadata steps are idempotent.
- **`./analyze.sh` fails at step 6 (screencaps)**: `screencap.py` is
  non-fatal by design. Check the stderr; usually a missing stream URL. Safe
  to continue by re-running and answering `n` to the overwrite prompt to
  skip the Claude step.
- **`./analyze.sh` fails at step 7 (build)**: now fail-loud. The most
  common cause is `build.py` crashing on an analysis field the template
  doesn't tolerate (e.g. non-numeric timestamps — fixed in `ts_to_seconds`).
  Fix the Python, then re-run analyze.sh with `n` at the overwrite prompt
  to resume from step 6 onward.
- **`./analyze.sh` aborts at step 8 (commit with no staged changes)**:
  means the analysis and transcript were already tracked. Not a real failure.
- **Daily briefing didn't run**: check `analysis/daily-briefing.log` and
  cron (`crontab -l` on LXC 105).
- **Nothing deploys despite successful push**: Cloudflare Pages dashboard.
  See "Publish" section above.

## Files owned by these pipelines

- `analyze.sh` — per-video entry point
- `analysis/batch-analyze.sh`, `daily-briefing-update.sh`,
  `monthly-scoring-run.sh`, `score-predictions.sh`, `update-views.sh` —
  orchestration scripts; each owns its own log file
- `analysis/build.py` — static site generator, writes `dist/`
- `analysis/screencap.py` — frame extraction, idempotent
- `analysis/log-pipeline.py` — shared JSONL logger for analyze.sh
- `analysis/schema.json` — the contract. Changes cascade to templates and
  every consumer. Update at least one example analysis when changing it.
- `analysis/calibration-reference.md` — ground truth for prediction scoring.
  Update when major events land, *then* rescore.
- `cron.conf` — cron schedule (installed on LXC 105)
- `analysis/pipeline.log` — interactive-run audit trail, gitignored
