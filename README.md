# Predictive History Audit

A systematic, AI-assisted content analysis of the **Predictive History** YouTube channel by Xueqin Jiang (Professor Jiang). The project applies a structured analytical framework to 143+ lectures across 7 series, extracting and scoring claims, predictions, rhetorical techniques, source usage, and civilizational framing patterns.

## What This Is

Professor Jiang's channel gained significant attention in 2024-2025 after his "Iran Trap" lectures appeared to predict several geopolitical developments. This project takes his full body of work and subjects it to rigorous content analysis — not to dismiss or promote the channel, but to give viewers the tools to evaluate its claims critically.

Each video gets a structured JSON analysis covering:

- **Synopsis and thesis extraction** — what is the lecture actually arguing?
- **Prediction tracking** — falsifiable predictions scored against real-world events with sourced status assessments (confirmed, partially confirmed, disconfirmed, untested, unfalsifiable)
- **Source auditing** — what sources are cited, how they're used, whether they're accurately represented, and what's notably omitted
- **Scoring** (1-5 scale) across seven analytical dimensions:
  - Historical accuracy
  - Argumentative rigor
  - Framing and selectivity
  - Perspective diversity
  - Normative loading
  - Determinism vs. contingency
  - Civilizational framing (with per-civilization breakdowns for China, US, Russia, the West)
- **Rhetorical technique identification** — specific persuasion patterns with timestamps and explanations
- **Notable quotes with ironic mirrors** — where a criticism of one civilization applies equally or more to another the speaker treats favorably
- **Cross-references** — how lectures build on or contradict each other across the corpus

## Corpus Coverage

| Series | Episodes | Description |
|--------|----------|-------------|
| Civilization | 60 | Historical survey from ancient civilizations to modernity |
| Secret History | 28 | Alternative narratives of major historical events |
| Game Theory | 14 | Geopolitical strategy through game theory frameworks |
| Geo-Strategy | 12 | Applied geopolitical analysis of current conflicts |
| Geo-Strategy Update | 8 | Follow-up analyses to the Geo-Strategy series |
| Great Books | 6 | Analysis through the lens of classic texts |
| Interview | 15 | Guest appearances on other channels and podcasts |

**Total: 143 analyses** from 145 transcripts.

## Key Findings

The analysis reveals consistent patterns across the corpus:

- **Prediction calibration is mixed.** Broad directional calls (escalation in Iran, Hormuz disruption, nationalism/mercantilism trends, Ukraine army age demographics) have partially or fully materialized. Specific claims about coalition composition (Saudi Arabia's role), Russian deterrence capability, and certain geopolitical dynamics have been directly falsified by events.
- **Extreme civilizational asymmetry.** China consistently receives favorable framing with minimal critical scrutiny, while the US receives almost exclusively negative framing. Russia is treated favorably. The ironic_mirror fields throughout the analyses document numerous instances where criticisms directed at one civilization apply equally or more to civilizations the speaker treats sympathetically.
- **Heavy structural determinism.** Events are presented as inevitable consequences of grand historical forces, with little room for contingency, individual agency, or alternative outcomes.
- **Source usage is impressionistic.** Legitimate scholars (Mackinder, Arrighi, Brzezinski) are cited but deployed to support predetermined conclusions rather than engaged with critically. Vague appeals to authority ("historians agree," "everyone in China knows") are frequent.

See `analysis/calibration-reference.md` for the full prediction truth table, and `analysis/predictions-status-march-2026.md` for detailed assessments with sourced verdicts.

## Project Structure

```
predictive_history/
├── README.md                  # This file
├── analyze.sh                 # Single video analysis pipeline
├── transcripts/               # YouTube auto-generated SRT subtitles (145 files)
│   └── *.en.srt
└── analysis/
    ├── schema.json            # JSON schema for all analysis files
    ├── *.json                 # Individual lecture analyses (143 files)
    ├── channel-data.json      # Aggregate channel statistics and metrics
    ├── channel-editorial.json # Editorial context on the channel creator
    ├── calibration-reference.md    # Prediction truth table (confirmed events + dates)
    ├── predictions-status-march-2026.md  # Detailed prediction assessments
    ├── geopolitical-briefing-march-2026.md  # Sourced geopolitical reference
    ├── briefing-data.json     # Structured briefing entries
    ├── batch-analyze.sh       # Batch processing for multiple transcripts
    ├── score-predictions.sh   # Prediction rescoring against current events
    ├── daily-briefing-update.sh    # Daily geopolitical tracker
    ├── monthly-scoring-run.sh      # Monthly prediction re-evaluation
    ├── score-predictions.py   # Prediction scoring logic
    ├── generate-channel-data.py    # Channel statistics aggregation
    ├── build.py               # Static HTML site generator (Jinja2)
    ├── screencap.py           # Screenshot extraction from YouTube videos
    ├── caps/                  # Extracted video screencaps
    ├── static/                # CSS and JS for generated site
    └── templates/             # Jinja2 HTML templates
```

## How It Works

### Single Video Analysis

```bash
./analyze.sh <youtube_url_or_id>
```

The pipeline:
1. Downloads the transcript via `yt-dlp`
2. Parses series, episode, and title from the YouTube filename
3. Fetches upload date and view count
4. Sends the transcript to Claude (Opus) with the analysis schema, calibration reference, and scoring rubric
5. Validates the output JSON
6. Extracts screencaps at timestamps referenced in the analysis
7. Rebuilds the static site

### Batch Analysis

```bash
cd analysis && ./batch-analyze.sh [--dry-run] [--series "Civilization"] [--limit 10]
```

Processes all unanalyzed transcripts, skipping duplicates and re-uploads.

### Prediction Scoring

```bash
cd analysis && ./score-predictions.sh
```

Re-evaluates untested predictions against the current geopolitical briefing and patches analysis files with updated statuses.

## Analysis Schema

Each analysis JSON follows `analysis/schema.json`. Key fields:

```json
{
  "meta": { "series", "episode", "title", "video_id", "upload_date", "view_count", ... },
  "synopsis": "Neutral 3-5 sentence summary",
  "thesis": {
    "central_thesis": "Core argument in one sentence",
    "supporting_claims": ["..."],
    "predictions": [
      {
        "claim": "What was predicted or claimed",
        "type": "prediction | claim",
        "timestamp": "HH:MM:SS",
        "falsifiable": true,
        "status": "confirmed | partially_confirmed | disconfirmed | untested | unfalsifiable",
        "status_note": "Evidence and reasoning for the status assignment"
      }
    ]
  },
  "sources": {
    "named_sources": [{ "name", "type", "how_used", "accurate_representation" }],
    "vague_appeals": ["Unsourced authority claims"],
    "notable_omissions": ["What a balanced treatment would include"]
  },
  "scores": {
    "historical_accuracy": { "score": 1-5, "justification": "..." },
    "civilizational_framing": { "score": 1-5, "justification": "...",
      "china_treatment": "...", "us_treatment": "...", "russia_treatment": "...", "west_treatment": "..."
    }
  },
  "rhetoric": [{ "technique", "instance", "timestamp", "effect" }],
  "notable_quotes": [{ "quote", "timestamp", "significance", "ironic_mirror" }],
  "cross_references": { "builds_on": [], "contradicts": [], "pattern_notes": "..." },
  "verdict": { "strengths", "weaknesses", "viewer_advisory" }
}
```

## Scoring Rubric

All scores use a 1-5 scale where **5 is best**:

| Dimension | 5 (Best) | 1 (Worst) |
|-----------|----------|-----------|
| Historical Accuracy | Facts, dates, figures are correct | Major factual errors |
| Argumentative Rigor | Logically sound, evidence-based | Unsupported conclusions, logical fallacies |
| Framing & Selectivity | Balanced evidence presentation | Cherry-picked, one-sided |
| Perspective Diversity | Multiple viewpoints considered | Single perspective, no engagement with counterarguments |
| Normative Loading | Neutral analytical language | Heavy evaluative/emotional language replacing analysis |
| Determinism vs. Contingency | Acknowledges contingency and uncertainty | Rigidly deterministic, no alternative scenarios |
| Civilizational Framing | Symmetric treatment of civilizations | Extreme asymmetry in how civilizations are characterized |

## Prediction Status Definitions

- **confirmed** — prediction clearly came true
- **partially_confirmed** — core direction correct but details wrong, or only part materialized
- **disconfirmed** — prediction clearly falsified by events
- **untested** — not yet testable or insufficient time has passed
- **unfalsifiable** — cannot be tested empirically

## Dependencies

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — transcript and metadata download
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-code) — AI analysis engine (Claude Opus)
- [ffmpeg](https://ffmpeg.org/) — VTT-to-SRT conversion, screencap extraction
- [Jinja2](https://jinja.palletsprojects.com/) — HTML template rendering
- Python 3.10+

## Methodology Notes

- All analyses are performed by Claude Opus with a standardized prompt, schema, and calibration reference to ensure consistency across the corpus.
- The calibration reference (`calibration-reference.md`) is a living document updated as events unfold, sourced from publicly available reporting (Al Jazeera, BBC, Reuters, NPR, CNN, Washington Post, CNBC, CRS, CSIS, Atlantic Council, Chatham House, Carnegie Endowment, Arms Control Association, and others).
- Prediction statuses are re-evaluated monthly against current events.
- The ironic_mirror field is a deliberate analytical choice: it tests whether criticisms the speaker directs at one actor apply equally to actors treated favorably, surfacing asymmetric framing that might otherwise go unnoticed.
- This is an analytical project, not an editorial one. The goal is to provide structured data that lets readers form their own conclusions. Where the analysis makes evaluative judgments (scores, verdicts), the reasoning is always explicit.

## License

The original tooling, analysis output, schema, and documentation in this repository are released under the [MIT License](LICENSE).

### Fair Use Statement

This project includes two categories of third-party material used under the fair use doctrine (17 U.S.C. Section 107):

**Transcripts.** The `transcripts/` directory contains auto-generated subtitle files downloaded from publicly available YouTube videos via YouTube's public API. These machine-generated transcripts are used solely as input for transformative scholarly analysis. They are not a substitute for the original video content — they contain no audio, video, production value, or visual presentation, and are not intended to replace or compete with the original works. The transcripts serve as raw material for a fundamentally different purpose: structured critical analysis and prediction tracking.

**Screencaps.** The `analysis/caps/` directory contains individual still frames extracted from YouTube videos at specific timestamps referenced in the analysis. Each image is a single low-resolution frame used to illustrate a specific analytical point (a quoted claim, a cited source, a rhetorical technique). The use is minimal, non-sequential, and does not reproduce any meaningful portion of the original video content.

**Four-factor analysis:**

1. **Purpose and character of the use.** This project is transformative — it subjects the original content to structured critical analysis, fact-checking, prediction scoring, rhetorical identification, and source auditing. The analyses add substantial new meaning, context, and scholarly value that does not exist in the original works. The project is non-commercial and serves research and educational purposes.

2. **Nature of the copyrighted work.** The original works are published, publicly available commentary on geopolitics and history. They are factual in nature (making claims about real-world events) rather than creative fiction, which weighs in favor of fair use.

3. **Amount and substantiality of the portion used.** Transcripts are machine-generated text lacking the production elements (delivery, visuals, editing) that constitute the creative core of the videos. Screencaps are individual frames from videos that are typically 30-120 minutes long. Neither use reproduces the heart of the original works.

4. **Effect on the market for the original work.** This project does not substitute for viewing the original videos. The analyses are complementary — they are most useful to someone who has watched or intends to watch the lectures. The project does not monetize the content or compete with the original channel for viewership or revenue.
