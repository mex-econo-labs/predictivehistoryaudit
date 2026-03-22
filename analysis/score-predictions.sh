#!/usr/bin/env bash
# score-predictions.sh — Score untested predictions against the briefing
# Usage: ./score-predictions.sh [--dry-run]
#
# Extracts untested predictions, sends them with the briefing to Claude,
# and patches only the files that need status changes.

set -euo pipefail

ANALYSIS_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGFILE="${ANALYSIS_DIR}/scoring.log"
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

# Step 1: Extract untested predictions into a compact worklist
WORKLIST="${ANALYSIS_DIR}/scoring-worklist.json"
python3 - "$ANALYSIS_DIR" "$WORKLIST" <<'PYEOF'
import json, glob, os, sys

analysis_dir = sys.argv[1]
outfile = sys.argv[2]

worklist = []
for f in sorted(glob.glob(os.path.join(analysis_dir, '*.json'))):
    bn = os.path.basename(f)
    if bn in ('schema.json', 'briefing-data.json', 'scoring-worklist.json', 'scoring-results.json'):
        continue
    with open(f) as fh:
        d = json.load(fh)
    for i, p in enumerate(d.get('thesis', {}).get('predictions', [])):
        if p.get('status') == 'untested':
            worklist.append({
                'file': bn,
                'index': i,
                'type': p.get('type', 'prediction'),
                'claim': p['claim'],
                'timestamp': p.get('timestamp', ''),
                'falsifiable': p.get('falsifiable', False),
                'lecture': f"{d['meta']['series']} #{d['meta'].get('episode', '?')}: {d['meta']['title']}",
                'upload_date': d['meta'].get('upload_date', ''),
            })

with open(outfile, 'w') as fh:
    json.dump(worklist, fh, indent=2, ensure_ascii=False)

print(f"Extracted {len(worklist)} untested predictions to {outfile}")
PYEOF

UNTESTED_COUNT=$(python3 -c "import json; print(len(json.load(open('${WORKLIST}'))))")
log "=== Scoring run: ${TODAY} — ${UNTESTED_COUNT} untested predictions ==="

if $DRY_RUN; then
    log "DRY RUN — would send ${UNTESTED_COUNT} predictions to Claude for scoring"
    exit 0
fi

RESULTS="${ANALYSIS_DIR}/scoring-results.json"

PROMPT="You are scoring predictions from the Predictive History lecture series against current geopolitical reality.

TODAY'S DATE: ${TODAY}

STEP 1: Read these reference files:
- ${ANALYSIS_DIR}/calibration-reference.md
- ${ANALYSIS_DIR}/geopolitical-briefing-march-2026.md
- ${ANALYSIS_DIR}/briefing-data.json

STEP 2: Read the worklist of untested predictions:
- ${WORKLIST}

STEP 3: For EACH prediction in the worklist, evaluate whether its status should change based on the briefing and calibration reference. Apply these statuses:
- confirmed: Events clearly match the prediction
- partially_confirmed: Core direction correct but details wrong, or only partly materialized
- disconfirmed: Events clearly contradict the prediction
- untested: Keep as untested if insufficient evidence either way
- unfalsifiable: Cannot be tested empirically

Be RIGOROUS:
- Only change status when the evidence is clear
- For predictions about future events that haven't happened yet, keep as untested
- For wild long-term predictions (e.g. '50 years from now'), keep as untested unless already falsified
- For claims about the Iran war, Hormuz blockade, Gulf states, Turkey, Venezuela, Cuba — check carefully against the briefing
- Include a concise status_note explaining your reasoning for any status change

STEP 4: Write ONLY the changes to ${RESULTS} as a JSON array. Each entry should have:
{\"file\": \"filename.json\", \"index\": N, \"new_status\": \"status\", \"status_note\": \"explanation\"}

Only include entries where the status CHANGES from untested. If nothing changes, write an empty array [].

Write the results file, then report how many predictions changed status."

if claude -p \
    --model opus \
    --allowedTools "Read,Write,Glob,Grep" \
    --dangerously-skip-permissions \
    "$PROMPT" < /dev/null >> "$LOGFILE" 2>&1; then

    # Validate results
    if [[ -f "$RESULTS" ]] && python3 -c "import json; json.load(open('${RESULTS}'))" 2>/dev/null; then
        # Apply changes
        CHANGED=$(python3 - "$ANALYSIS_DIR" "$RESULTS" "$TODAY" <<'PYEOF'
import json, sys, os
from collections import defaultdict

analysis_dir = sys.argv[1]
results_file = sys.argv[2]
today = sys.argv[3]

with open(results_file) as f:
    changes = json.load(f)

if not changes:
    print("0")
    sys.exit(0)

# Group changes by file
by_file = defaultdict(list)
for c in changes:
    by_file[c['file']].append(c)

changed = 0
for fname, file_changes in by_file.items():
    fpath = os.path.join(analysis_dir, fname)
    with open(fpath) as f:
        d = json.load(f)

    for c in file_changes:
        idx = c['index']
        pred = d['thesis']['predictions'][idx]
        old = pred.get('status', 'untested')
        new = c['new_status']
        if old != new:
            pred['status'] = new
            if c.get('status_note'):
                pred['status_note'] = c['status_note']
            changed += 1

    with open(fpath, 'w') as f:
        json.dump(d, f, indent=2, ensure_ascii=False)

# Update briefing-data.json
briefing_path = os.path.join(analysis_dir, 'briefing-data.json')
with open(briefing_path) as f:
    bd = json.load(f)
bd['last_scoring_date'] = today
# Add next scoring date (roughly one month)
y, m, d_num = today.split('-')
m = int(m) + 1
if m > 12:
    m = 1
    y = str(int(y) + 1)
bd['next_scoring_date'] = f"{y}-{m:02d}-{d_num}"
with open(briefing_path, 'w') as f:
    json.dump(bd, f, indent=2, ensure_ascii=False)

print(changed)
PYEOF
        )

        log "Applied ${CHANGED} status changes"

        # Rebuild site
        log "Rebuilding site..."
        python3 "${ANALYSIS_DIR}/build.py" >> "$LOGFILE" 2>&1 || log "  Build had errors (non-fatal)"
        log "Site rebuilt"
    else
        log "FAIL: scoring-results.json invalid or missing"
    fi
else
    log "FAIL: Claude CLI error"
fi

# Cleanup
rm -f "$WORKLIST" "$RESULTS"

log "=== Scoring run complete ==="
