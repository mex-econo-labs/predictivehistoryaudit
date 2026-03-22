#!/usr/bin/env bash
# daily-briefing-update.sh — Daily geopolitical situation tracker
# Usage: ./daily-briefing-update.sh [--dry-run]
#
# Runs Claude to research today's developments relevant to tracked predictions,
# updates briefing-data.json, calibration-reference.md, and geopolitical-briefing.md,
# rebuilds the site, and commits/pushes.

set -euo pipefail

ANALYSIS_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$ANALYSIS_DIR")"
BRIEFING_FILE="${ANALYSIS_DIR}/briefing-data.json"
CALIBRATION_FILE="${ANALYSIS_DIR}/calibration-reference.md"
GP_BRIEFING="${ANALYSIS_DIR}/geopolitical-briefing.md"
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

# Handle legacy filename if it exists
LEGACY_GP="${ANALYSIS_DIR}/geopolitical-briefing-march-2026.md"
if [[ -f "$LEGACY_GP" && ! -f "$GP_BRIEFING" ]]; then
    cp "$LEGACY_GP" "$GP_BRIEFING"
    log "Migrated legacy geopolitical briefing to rolling filename"
fi

PROMPT="You are performing the daily update for the Predictive History Audit project.

TODAY'S DATE: ${TODAY}

You have THREE files to update:

1. BRIEFING DATA (${BRIEFING_FILE}) — daily situation log with entries, theatre summaries, and metrics
2. CALIBRATION REFERENCE (${CALIBRATION_FILE}) — prediction truth table of confirmed/disconfirmed events
3. GEOPOLITICAL BRIEFING (${GP_BRIEFING}) — comprehensive sourced reference document

STEP 1: Read all three files plus ${ANALYSIS_DIR}/schema.json for context.

STEP 2: Search the web for TODAY's developments in these theatres:
  1. Iran / Strait of Hormuz / 2026 Iran War — strikes, blockade status, oil prices, shipping attacks, diplomatic moves
  2. GROUND INVASION INDICATORS — this is CRITICAL, track separately:
     - Any US/coalition troop movements toward Iran (Marines, Army units, staging)
     - Kharg Island developments (US targeting, naval positioning, oil export disruption)
     - Amphibious assault ship movements (USS Tripoli, Bataan, etc.)
     - Draft/conscription discussions in the US
     - Any Pentagon statements about ground operations
     - Troop buildup numbers in the region
     - Special operations activity
     - Logistical staging (fuel, ammo, medical prepositioned)
  3. Gulf States — damage, economic impact, diplomatic responses
  4. Russia-Ukraine War — frontline, negotiations, NATO/troop commitments
  5. Venezuela / Cuba / Colombia — Rodriguez govt, Maduro trial, Cuba crisis
  6. US-China — trade, Taiwan, military posturing
  7. North Korea / Korean Peninsula
  8. Countries affected by Hormuz blockade (Japan, South Korea, India, Pakistan, Bangladesh, Europe)

STEP 3: Update briefing-data.json:
  - Set briefing_date to '${TODAY}'
  - Add new daily_entries at the TOP of the array (most recent first)
  - If there are ANY ground invasion indicators, add a separate entry with tag 'Ground Invasion Tracker'
  - Update theatre summaries if situation has materially changed
  - Update metrics with current values (oil price, Hormuz traffic, casualties, etc.)
  - Update the ground_invasion_tracker object (create if not present) with fields:
    - last_updated: today's date
    - status: 'no_ground_troops' | 'staging' | 'limited_operations' | 'invasion'
    - troop_count_in_theatre: estimated total US troops in Middle East
    - key_developments: array of recent indicators
    - kharg_island: object with { status, naval_activity, notes }
    - marine_movements: array of tracked amphibious/marine deployments
    - draft_indicators: any domestic draft/conscription signals
    - assessment: 1-2 sentence current assessment
  - For each daily entry, include prediction_impact if it relates to any tracked prediction

STEP 4: Update calibration-reference.md:
  - Add any NEW confirmed events to the 'Confirmed Events' table
  - Add any newly disconfirmed claims to the 'Disconfirmed Claims' table
  - Update 'Key Contextual Facts' if material changes occurred
  - Update the date in the document header

STEP 5: Update geopolitical-briefing.md:
  - Update the date in the document header
  - Update each section with new developments
  - Add new casualty figures, oil prices, diplomatic developments
  - Preserve the overall structure and sourcing format
  - Add new sources at the bottom of each section
  - If new theatres or major developments emerge, add new sections

CRITICAL REQUIREMENTS:
- Output ONLY valid JSON to briefing-data.json
- Preserve ALL existing daily_entries — append new ones at the TOP
- Keep markdown files well-formatted
- Cite sources for all claims
- Be factual and neutral — this is a reference document, not commentary
- The ground_invasion_tracker is the most important new feature — be thorough"

if claude -p \
    --model opus \
    --allowedTools "Read,Write,Glob,Grep,WebSearch,WebFetch" \
    --dangerously-skip-permissions \
    "$PROMPT" < /dev/null >> "$LOGFILE" 2>&1; then

    # Validate JSON
    if python3 -c "import json; json.load(open('${BRIEFING_FILE}'))" 2>/dev/null; then
        log "SUCCESS: All files updated"

        # Rebuild site
        log "Rebuilding site..."
        python3 "${ANALYSIS_DIR}/build.py" >> "$LOGFILE" 2>&1 || log "  Build had errors (non-fatal)"
        log "Site rebuilt"

        # Commit and push
        log "Committing and pushing..."
        cd "$PROJECT_DIR"
        git add analysis/briefing-data.json analysis/calibration-reference.md analysis/geopolitical-briefing.md analysis/dist/ 2>/dev/null || true
        if git diff --cached --quiet 2>/dev/null; then
            log "No changes to commit"
        else
            git commit -m "Daily briefing update: ${TODAY}

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>" >> "$LOGFILE" 2>&1
            git push >> "$LOGFILE" 2>&1 || log "  Push failed (non-fatal)"
            log "Committed and pushed"
        fi
    else
        log "FAIL: briefing-data.json invalid after update"
        if git -C "$PROJECT_DIR" status &>/dev/null; then
            git -C "$PROJECT_DIR" checkout -- analysis/briefing-data.json 2>/dev/null || true
            log "Restored briefing-data.json from git"
        fi
    fi
else
    log "FAIL: Claude CLI error"
fi

log "=== Daily briefing update complete ==="
