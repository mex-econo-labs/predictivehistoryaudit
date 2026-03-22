#!/usr/bin/env bash
# daily-briefing-update.sh — Daily geopolitical situation tracker
# Usage: ./daily-briefing-update.sh [--dry-run]
#
# Runs Claude to research today's developments relevant to tracked predictions,
# appends entries to briefing-data.json, and rebuilds the site.

set -euo pipefail

ANALYSIS_DIR="$(cd "$(dirname "$0")" && pwd)"
BRIEFING_FILE="${ANALYSIS_DIR}/briefing-data.json"
LOGFILE="${ANALYSIS_DIR}/daily-briefing.log"
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

log "=== Daily briefing update: ${TODAY} ==="

if $DRY_RUN; then
    log "DRY RUN — would query Claude for today's developments"
    exit 0
fi

PROMPT="You are updating the daily situation briefing for the Predictive History Audit project.

TODAY'S DATE: ${TODAY}

Read the current briefing data:
- ${BRIEFING_FILE}
- ${ANALYSIS_DIR}/calibration-reference.md
- ${ANALYSIS_DIR}/geopolitical-briefing-march-2026.md

Then search the web for today's developments in these active theatres:
1. Iran / Strait of Hormuz / 2026 Iran War — strikes, blockade status, oil prices, shipping attacks, diplomatic moves, Turkey/NATO
2. Gulf States — Bahrain, Kuwait, Qatar, UAE, Saudi Arabia, Oman — damage, economic impact, diplomatic responses
3. Russia-Ukraine War — frontline changes, peace negotiations, NATO/troop commitments
4. Venezuela / Cuba / Colombia — Rodriguez government, Maduro trial, Cuba crisis, US-Cuba talks, Colombia
5. US-China — trade, Taiwan, military posturing
6. North Korea / Korean Peninsula — any provocations or developments
7. Any other country negatively affected by the Hormuz blockade (Japan, South Korea, India, Pakistan, Bangladesh, Europe)

For each significant development found:
- Create a daily_entries entry with: date, tags (array of region/topic tags), summary (1-2 sentences), details (array of bullet points), prediction_impact (null if none, or explain how this relates to predictions in the lecture corpus), source
- Update the metrics array with current values (especially oil price, Hormuz traffic status, casualty figures)
- Update the briefing_date to today
- Update theatre summaries if the situation has materially changed

Write the updated briefing-data.json to: ${BRIEFING_FILE}

CRITICAL: Output ONLY valid JSON to the file. Preserve all existing daily_entries (append new ones at the top of the array). Do not remove historical entries. Keep the JSON structure identical to the current file."

if claude -p \
    --model opus \
    --allowedTools "Read,Write,Glob,Grep,WebSearch,WebFetch" \
    --dangerously-skip-permissions \
    "$PROMPT" < /dev/null >> "$LOGFILE" 2>&1; then

    # Validate output
    if python3 -c "import json; json.load(open('${BRIEFING_FILE}'))" 2>/dev/null; then
        log "SUCCESS: briefing-data.json updated"

        # Rebuild site
        log "Rebuilding site..."
        python3 "${ANALYSIS_DIR}/build.py" >> "$LOGFILE" 2>&1 || log "  Build had errors (non-fatal)"
        log "Site rebuilt"
    else
        log "FAIL: briefing-data.json invalid after update"
        # Restore from git if available
        if git -C "${ANALYSIS_DIR}" status &>/dev/null; then
            git -C "${ANALYSIS_DIR}" checkout -- briefing-data.json 2>/dev/null || true
            log "Restored briefing-data.json from git"
        fi
    fi
else
    log "FAIL: Claude CLI error"
fi

log "=== Daily briefing update complete ==="
