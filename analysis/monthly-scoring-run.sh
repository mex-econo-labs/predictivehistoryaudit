#!/usr/bin/env bash
# monthly-scoring-run.sh — Monthly prediction scoring run
# Usage: ./monthly-scoring-run.sh [--dry-run]
#
# Re-evaluates all predictions and claims against current geopolitical reality,
# updates prediction statuses in analysis JSON files, updates calibration reference,
# and rebuilds the site.

set -euo pipefail

ANALYSIS_DIR="$(cd "$(dirname "$0")" && pwd)"
BRIEFING_FILE="${ANALYSIS_DIR}/briefing-data.json"
LOGFILE="${ANALYSIS_DIR}/monthly-scoring.log"
TODAY=$(date +%Y-%m-%d)
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOGFILE"
}

log "=== Monthly scoring run: ${TODAY} ==="

if $DRY_RUN; then
    log "DRY RUN — would query Claude for prediction re-scoring"
    exit 0
fi

PROMPT="You are performing the monthly prediction scoring run for the Predictive History Audit project.

TODAY'S DATE: ${TODAY}

STEP 1: Read context files
- ${ANALYSIS_DIR}/calibration-reference.md
- ${ANALYSIS_DIR}/geopolitical-briefing-march-2026.md
- ${ANALYSIS_DIR}/briefing-data.json (daily situation log)
- ${ANALYSIS_DIR}/schema.json

STEP 2: Search the web for the latest developments on all tracked theatres to ensure the calibration reference is current.

STEP 3: Update the calibration reference (${ANALYSIS_DIR}/calibration-reference.md) with any new confirmed events, disconfirmed claims, or contextual facts discovered.

STEP 4: Read EVERY analysis JSON file in ${ANALYSIS_DIR}/*.json (except schema.json). For each file, review all predictions and claims in thesis.predictions[]. For each prediction/claim:
- Check if the status should be updated based on current events
- If status changes: update 'status' and add/update 'status_note' explaining what happened
- Status values: confirmed, partially_confirmed, disconfirmed, untested, unfalsifiable
- Be rigorous — only change status when events clearly warrant it
- Write the updated JSON back to the same file

STEP 5: Update ${BRIEFING_FILE}:
- Set last_scoring_date to '${TODAY}'
- Set next_scoring_date to one month from now
- Add a daily_entries entry noting the scoring run and any status changes

STEP 6: Summarize changes made — which predictions changed status and why.

CRITICAL: Preserve all existing data in files. Only modify prediction statuses and notes where warranted. Output valid JSON."

if claude -p \
    --model opus \
    --allowedTools "Read,Write,Glob,Grep,WebSearch,WebFetch" \
    --dangerously-skip-permissions \
    "$PROMPT" < /dev/null >> "$LOGFILE" 2>&1; then

    log "SUCCESS: Monthly scoring complete"

    # Validate all JSON files
    INVALID=0
    for f in "${ANALYSIS_DIR}"/*.json; do
        if ! python3 -c "import json; json.load(open('${f}'))" 2>/dev/null; then
            log "  WARNING: ${f} is invalid JSON"
            INVALID=$((INVALID + 1))
        fi
    done

    if [[ $INVALID -gt 0 ]]; then
        log "  ${INVALID} invalid JSON files detected — check manually"
    fi

    # Rebuild site
    log "Rebuilding site..."
    python3 "${ANALYSIS_DIR}/build.py" >> "$LOGFILE" 2>&1 || log "  Build had errors (non-fatal)"
    log "Site rebuilt"
else
    log "FAIL: Claude CLI error"
fi

log "=== Monthly scoring run complete ==="
