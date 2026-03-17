#!/usr/bin/env bash
# analyze.sh — Full pipeline for a single Predictive History video
# Usage: ./analyze.sh <youtube_url_or_id> [--no-screencaps] [--no-build]

set -euo pipefail
cd "$(dirname "$0")"

ANALYSIS_DIR="analysis"
TRANSCRIPT_DIR="transcripts"

URL="$1"
shift || { echo "Usage: $0 <youtube_url_or_id> [--no-screencaps] [--no-build]"; exit 1; }

DO_SCREENCAPS=true
DO_BUILD=true
for arg in "$@"; do
  case "$arg" in
    --no-screencaps) DO_SCREENCAPS=false ;;
    --no-build) DO_BUILD=false ;;
  esac
done

# Normalize URL → video ID
if [[ "$URL" =~ ^[a-zA-Z0-9_-]{11}$ ]]; then
  VIDEO_ID="$URL"
  URL="https://www.youtube.com/watch?v=$VIDEO_ID"
elif [[ "$URL" =~ v=([a-zA-Z0-9_-]{11}) ]]; then
  VIDEO_ID="${BASH_REMATCH[1]}"
elif [[ "$URL" =~ youtu\.be/([a-zA-Z0-9_-]{11}) ]]; then
  VIDEO_ID="${BASH_REMATCH[1]}"
else
  echo "ERROR: Cannot extract video ID from: $URL" >&2
  exit 1
fi

echo "=== Analyzing: $URL (ID: $VIDEO_ID) ==="

# --- 1. Download transcript ---
echo "[1/6] Downloading transcript..."
EXISTING_SRT=$(find "$TRANSCRIPT_DIR" -name "*\[$VIDEO_ID\]*.srt" 2>/dev/null | head -1)
if [[ -n "$EXISTING_SRT" ]]; then
  echo "  Transcript already exists: $(basename "$EXISTING_SRT")"
  TRANSCRIPT_FILE="$(basename "$EXISTING_SRT")"
else
  yt-dlp --write-auto-sub --sub-lang en --sub-format srt --skip-download \
    -o "${TRANSCRIPT_DIR}/%(title)s [%(id)s]" "$URL" 2>/dev/null
  EXISTING_SRT=$(find "$TRANSCRIPT_DIR" -name "*\[$VIDEO_ID\]*.srt" 2>/dev/null | head -1)
  if [[ -z "$EXISTING_SRT" ]]; then
    # Try VTT and convert
    EXISTING_VTT=$(find "$TRANSCRIPT_DIR" -name "*\[$VIDEO_ID\]*.vtt" 2>/dev/null | head -1)
    if [[ -n "$EXISTING_VTT" ]]; then
      SRT_OUT="${EXISTING_VTT%.vtt}.srt"
      ffmpeg -i "$EXISTING_VTT" "$SRT_OUT" 2>/dev/null && rm "$EXISTING_VTT"
      EXISTING_SRT="$SRT_OUT"
    else
      echo "ERROR: Could not download transcript for $VIDEO_ID" >&2
      exit 1
    fi
  fi
  TRANSCRIPT_FILE="$(basename "$EXISTING_SRT")"
  echo "  Downloaded: $TRANSCRIPT_FILE"
fi

# --- 2. Parse metadata from filename ---
echo "[2/6] Parsing metadata..."
NAMEPART="${TRANSCRIPT_FILE%.en.srt}"
NAMEPART="${NAMEPART% \[$VIDEO_ID\]}"

# Parse series, episode, title from filename
# Split on fullwidth colon ： for title, then split left side on # for series/episode
if [[ "$NAMEPART" == *"："* ]]; then
  LEFT="${NAMEPART%%：*}"
  TITLE="$(echo "${NAMEPART#*：}" | sed 's/^[[:space:]]*//')"
  if [[ "$LEFT" == *"#"* ]]; then
    SERIES="$(echo "${LEFT%#*}" | sed 's/[[:space:]]*$//')"
    EPISODE="$(echo "${LEFT##*#}" | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')"
  else
    SERIES="$(echo "$LEFT" | sed 's/[[:space:]]*$//')"
    EPISODE=""
  fi
else
  SERIES="Standalone"
  EPISODE=""
  TITLE="$NAMEPART"
fi

# Generate episode JSON
if [[ "$EPISODE" =~ ^[0-9]+$ ]]; then
  EPISODE_JSON="$EPISODE"
elif [[ -z "$EPISODE" ]]; then
  EPISODE_JSON="null"
else
  EPISODE_JSON="\"$EPISODE\""
fi

# Generate slug
SERIES_SLUG=$(echo "$SERIES" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | sed 's/-\+/-/g' | sed 's/^-//;s/-$//')
if [[ -n "$EPISODE" ]]; then
  EP_SLUG=$(echo "$EPISODE" | tr '[:upper:]' '[:lower:]')
  SLUG="${SERIES_SLUG}-${EP_SLUG}"
else
  SLUG="${SERIES_SLUG}-x-${VIDEO_ID:0:8}"
fi

OUTPUT_FILE="${ANALYSIS_DIR}/${SLUG}.json"

echo "  Series:  $SERIES"
echo "  Episode: ${EPISODE:-none}"
echo "  Title:   $TITLE"
echo "  Slug:    $SLUG"

# --- 3. Check if already analyzed ---
if [[ -f "$OUTPUT_FILE" ]]; then
  echo ""
  echo "WARNING: $OUTPUT_FILE already exists. Overwrite? (y/N)"
  read -r answer
  [[ "$answer" =~ ^[Yy] ]] || exit 0
fi

# --- 4. Fetch YouTube metadata ---
echo "[3/6] Fetching YouTube metadata..."
UPLOAD_DATE=$(yt-dlp --print upload_date "$URL" 2>/dev/null || echo "")
VIEW_COUNT=$(yt-dlp --print view_count "$URL" 2>/dev/null || echo "0")
if [[ ${#UPLOAD_DATE} -eq 8 ]]; then
  UPLOAD_DATE_FMT="${UPLOAD_DATE:0:4}-${UPLOAD_DATE:4:2}-${UPLOAD_DATE:6:2}"
else
  UPLOAD_DATE_FMT="$UPLOAD_DATE"
fi

echo "  Posted: $UPLOAD_DATE_FMT"
echo "  Views:  $VIEW_COUNT"

# --- 5. Run Claude analysis ---
echo "[4/6] Running Claude analysis..."

PROMPT="You are performing a systematic content analysis of a YouTube lecture from the \"Predictive History\" channel by Xueqin Jiang. Produce a complete JSON analysis following the schema exactly.

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
1. Read the transcript at: $(pwd)/${TRANSCRIPT_DIR}/${TRANSCRIPT_FILE}
2. Read the calibration reference at: $(pwd)/${ANALYSIS_DIR}/calibration-reference.md
3. Read the schema at: $(pwd)/${ANALYSIS_DIR}/schema.json
4. Read one example analysis for format reference: $(pwd)/${ANALYSIS_DIR}/geo-strategy-08.json
5. Produce a complete JSON analysis and write it to: $(pwd)/${OUTPUT_FILE}

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

Write the complete JSON to $(pwd)/${OUTPUT_FILE} then verify it is valid JSON by reading it back."

claude -p \
  --model opus \
  --allowedTools "Read,Write,Glob,Grep" \
  --dangerously-skip-permissions \
  "$PROMPT"

# Validate JSON
if ! python3 -c "import json; json.load(open('$OUTPUT_FILE'))" 2>/dev/null; then
  echo "ERROR: Generated file is not valid JSON: $OUTPUT_FILE" >&2
  exit 1
fi
echo "  Analysis written: $OUTPUT_FILE"

# --- 6. Screencaps ---
if $DO_SCREENCAPS && [[ -f "${ANALYSIS_DIR}/screencap.py" ]]; then
  echo "[5/6] Extracting screencaps..."
  python3 "${ANALYSIS_DIR}/screencap.py" --input "$OUTPUT_FILE" --caps-dir caps
else
  echo "[5/6] Skipping screencaps."
fi

# --- Build site ---
if $DO_BUILD; then
  echo "[6/6] Building site..."
  python3 "${ANALYSIS_DIR}/build.py"
else
  echo "[6/6] Skipping build."
fi

echo ""
echo "=== Done: ${SERIES} #${EPISODE}: ${TITLE} ==="
echo "Analysis: $OUTPUT_FILE"
echo "View at:  ${ANALYSIS_DIR}/dist/videos/${SLUG}.html"
