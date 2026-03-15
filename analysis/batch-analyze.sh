#!/usr/bin/env bash
# batch-analyze.sh — Autonomous batch analysis of Predictive History transcripts
# Usage: ./batch-analyze.sh [--dry-run] [--series SERIES] [--limit N]
#
# Processes all unanalyzed transcripts through claude CLI, writes JSON output,
# extracts screencaps, and rebuilds the site after each batch.

set -euo pipefail

ANALYSIS_DIR="/home/steve/predictive_history/analysis"
TRANSCRIPT_DIR="/home/steve/predictive_history/transcripts"
LOGFILE="${ANALYSIS_DIR}/batch-analyze.log"
DRY_RUN=false
SERIES_FILTER=""
LIMIT=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        --series) SERIES_FILTER="$2"; shift 2 ;;
        --limit) LIMIT="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOGFILE"
}

# Python helper that does all the metadata parsing and outputs tab-separated fields
# Also handles skip logic (duplicates, re-uploads, already-analyzed)
generate_worklist() {
    python3 - "$SERIES_FILTER" <<'PYEOF'
import json, glob, os, re, sys

analysis_dir = "/home/steve/predictive_history/analysis"
transcript_dir = "/home/steve/predictive_history/transcripts"
series_filter = sys.argv[1] if len(sys.argv) > 1 else ""

# Get already-analyzed video IDs
done_ids = set()
for f in glob.glob(os.path.join(analysis_dir, "*.json")):
    if os.path.basename(f) == "schema.json":
        continue
    try:
        with open(f) as fh:
            done_ids.add(json.load(fh)["meta"]["video_id"])
    except:
        pass

# Skip list: re-uploads and known duplicates
skip_patterns = ["Re-upload", "re-upload", "AUDIO FIXED"]
skip_exact = ["Secret History #1：  How Power Works [ajFXykT9Joo].en.srt"]

for srt in sorted(glob.glob(os.path.join(transcript_dir, "*.srt"))):
    filename = os.path.basename(srt)

    # Extract video ID
    m = re.search(r'\[([A-Za-z0-9_-]+)\]\.en\.srt$', filename)
    if not m:
        continue
    video_id = m.group(1)

    # Skip if already done
    if video_id in done_ids:
        continue

    # Skip re-uploads and duplicates
    if any(p in filename for p in skip_patterns):
        continue
    if filename in skip_exact:
        continue

    # Parse series, episode, title from filename
    namepart = filename.replace(f" [{video_id}].en.srt", "")

    # Try pattern: "Series #Episode：  Title" or "Series#Episode： Title" or "Series BONUS：  Title"
    # Handle both fullwidth colon (：) and various spacing
    pattern = r'^(.+?)\s*#?\s*(\d+|END|BONUS)：\s*(.+)$'
    pm = re.match(pattern, namepart)
    if pm:
        series = pm.group(1).strip().rstrip('#').strip()
        episode = pm.group(2)
        title = pm.group(3).strip()
    else:
        # Try pattern without episode number: "Series：  Title"
        pattern2 = r'^(.+?)：\s+(.+)$'
        pm2 = re.match(pattern2, namepart)
        if pm2:
            series = pm2.group(1).strip()
            episode = "null"
            title = pm2.group(2).strip()
        else:
            series = "Standalone"
            episode = "null"
            title = namepart

    # Episode JSON representation
    if episode.isdigit():
        episode_json = episode
        ep_for_slug = episode
    elif episode == "null":
        episode_json = "null"
        ep_for_slug = "x"
    else:
        episode_json = f'"{episode}"'
        ep_for_slug = episode.lower()

    # Generate slug — use video_id suffix for standalone/duplicate slugs
    series_slug = re.sub(r'[^a-z0-9-]', '-', series.lower()).strip('-')
    series_slug = re.sub(r'-+', '-', series_slug)  # collapse multiple dashes
    slug = f"{series_slug}-{ep_for_slug}"

    # Handle slug collisions by appending video_id for ambiguous cases
    if episode in ("null",) or (episode == "BONUS"):
        slug = f"{series_slug}-{ep_for_slug}-{video_id[:8]}"

    # Apply series filter
    if series_filter and series_filter.lower() not in series.lower():
        continue

    # Output: tab-separated fields
    print(f"{filename}\t{video_id}\t{series}\t{episode}\t{episode_json}\t{title}\t{slug}")
PYEOF
}

# Main
log "=== Batch analysis starting ==="
log "Series filter: ${SERIES_FILTER:-all}"
log "Limit: ${LIMIT:-unlimited}"

PROCESSED=0
FAILED=0

while IFS=$'\t' read -r TRANSCRIPT_FILE VIDEO_ID SERIES EPISODE EPISODE_JSON TITLE SLUG; do
    # Check limit
    if [[ $LIMIT -gt 0 ]] && [[ $PROCESSED -ge $LIMIT ]]; then
        log "Limit of $LIMIT reached, stopping."
        break
    fi

    log "ANALYZING [${PROCESSED}]: ${SERIES} #${EPISODE}: ${TITLE} (${VIDEO_ID}) -> ${SLUG}.json"

    if $DRY_RUN; then
        PROCESSED=$((PROCESSED + 1))
        continue
    fi

    # Fetch upload date and view count from YouTube
    UPLOAD_DATE=$(yt-dlp --print upload_date "https://www.youtube.com/watch?v=${VIDEO_ID}" 2>/dev/null || echo "")
    VIEW_COUNT=$(yt-dlp --print view_count "https://www.youtube.com/watch?v=${VIDEO_ID}" 2>/dev/null || echo "0")
    if [[ -n "$UPLOAD_DATE" ]]; then
        UPLOAD_DATE_FMT="${UPLOAD_DATE:0:4}-${UPLOAD_DATE:4:2}-${UPLOAD_DATE:6:2}"
    else
        UPLOAD_DATE_FMT=""
    fi

    # Build the prompt
    PROMPT="You are performing a systematic content analysis of a YouTube lecture from the \"Predictive History\" channel by Jiang Xueqin. Produce a complete JSON analysis following the schema exactly.

METADATA:
- series: \"${SERIES}\"
- episode: ${EPISODE_JSON}
- title: \"${TITLE}\"
- video_id: \"${VIDEO_ID}\"
- url: \"https://www.youtube.com/watch?v=${VIDEO_ID}\"
- upload_date: \"${UPLOAD_DATE_FMT}\"
- view_count: ${VIEW_COUNT}
- transcript_file: \"${TRANSCRIPT_FILE}\"
- analyzed_by: \"claude-opus-4-6\"
- analysis_date: \"$(date +%Y-%m-%d)\"
- schema_version: \"1.0\"

INSTRUCTIONS:
1. Read the transcript at: ${TRANSCRIPT_DIR}/${TRANSCRIPT_FILE}
2. Read the calibration reference at: ${ANALYSIS_DIR}/calibration-reference.md
3. Read the schema at: ${ANALYSIS_DIR}/schema.json
4. Read one example analysis for format reference: ${ANALYSIS_DIR}/geo-strategy-08.json
5. Produce a complete JSON analysis and write it to: ${ANALYSIS_DIR}/${SLUG}.json

SCORING RUBRIC (1-5 scale, where 5 = best):
- historical_accuracy: Are facts cited correct? Are events, dates, figures accurately represented?
- argumentative_rigor: Is the argument logically sound? Are conclusions supported by evidence?
- framing_and_selectivity: Does the lecture present balanced evidence? (5 = balanced, 1 = cherry-picked)
- perspective_diversity: Are multiple viewpoints considered? (5 = diverse, 1 = single perspective)
- normative_loading: How much evaluative/emotional language replaces analysis? (5 = neutral, 1 = heavily loaded)
- determinism_vs_contingency: Does the lecture acknowledge contingency? (5 = balanced, 1 = rigidly deterministic)
- civilizational_framing: How are civilizations characterized? Include china_treatment, us_treatment, russia_treatment, west_treatment subfields where mentioned.

CRITICAL REQUIREMENTS:
- Be rigorous and critical — do not give favorable scores unless genuinely earned
- Include 8-10 rhetoric entries with specific examples and timestamps
- Include 8-10 notable quotes with timestamps
- For each notable quote, check whether the criticism or claim could equally or more aptly apply to a civilization/actor the speaker treats favorably (especially China). If so, populate the ironic_mirror field explaining the unintentional hypocrisy. Examples: criticizing Western propaganda while ignoring Chinese state media control; lamenting imperial suppression of history while China restricts discussion of Tiananmen, Tibet, or the Cultural Revolution; accusing the US of territorial ambition while omitting China's South China Sea claims. Be specific and factual.
- For each entry in the predictions array, set type to 'prediction' (forward-looking statement about future events) or 'claim' (assertion about the past, present, or analytical framework). Predictions are things like 'Trump will win', 'The US will invade Iran by 2027'. Claims are things like 'AIPAC is the most powerful lobby', 'Iran's terrain makes invasion impossible'.
- Identify ALL falsifiable predictions and set their status using the calibration reference
- For predictions about Iran/US conflict: Operation Midnight Hammer (June 2025), Twelve-Day War (June 13-24 2025), 2026 Iran War (Feb 28 2026 ongoing), Khamenei assassinated Feb 28 2026, Strait of Hormuz blockaded
- Include status_note for any prediction that is not untested or unfalsifiable
- Note cross-references to other lectures in the series
- Be specific about sources cited vs. vague appeals to authority
- Output ONLY valid JSON to the file. Do not include markdown fences or commentary in the file.

Write the complete JSON to ${ANALYSIS_DIR}/${SLUG}.json then verify it is valid JSON by reading it back."

    # Run claude in non-interactive mode
    if claude -p \
        --model opus \
        --allowedTools "Read,Write,Glob,Grep" \
        --dangerously-skip-permissions \
        "$PROMPT" < /dev/null >> "$LOGFILE" 2>&1; then

        # Validate output
        if [[ -f "${ANALYSIS_DIR}/${SLUG}.json" ]] && python3 -c "import json; json.load(open('${ANALYSIS_DIR}/${SLUG}.json'))" 2>/dev/null; then
            log "  SUCCESS: ${SLUG}.json"
            PROCESSED=$((PROCESSED + 1))

            # Site rebuild disabled — run build.py manually
            # if (( PROCESSED % 5 == 0 )); then
            #     log "  Rebuilding site (${PROCESSED} done)..."
            #     python3 "${ANALYSIS_DIR}/build.py" >> "$LOGFILE" 2>&1 || true
            # fi
        else
            log "  FAIL: ${SLUG}.json invalid or missing"
            FAILED=$((FAILED + 1))
            [[ -f "${ANALYSIS_DIR}/${SLUG}.json" ]] && mv "${ANALYSIS_DIR}/${SLUG}.json" "${ANALYSIS_DIR}/${SLUG}.json.bad"
        fi
    else
        log "  FAIL: claude CLI error for ${SLUG}"
        FAILED=$((FAILED + 1))
    fi

    sleep 3
done < <(generate_worklist)

# Final rebuild and screencaps disabled — run manually
# if ! $DRY_RUN && [[ $PROCESSED -gt 0 ]]; then
#     log "Final site rebuild..."
#     python3 "${ANALYSIS_DIR}/build.py" >> "$LOGFILE" 2>&1 || true
# fi
# if ! $DRY_RUN && [[ $PROCESSED -gt 0 ]] && [[ -f "${ANALYSIS_DIR}/screencap.py" ]]; then
#     log "Extracting screencaps..."
#     python3 "${ANALYSIS_DIR}/screencap.py" --input-dir "${ANALYSIS_DIR}" >> "$LOGFILE" 2>&1 || log "  Screencap extraction had errors (non-fatal)"
# fi

log "=== Complete: ${PROCESSED} processed, ${FAILED} failed ==="
