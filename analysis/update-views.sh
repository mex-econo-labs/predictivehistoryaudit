#!/usr/bin/env bash
# update-views.sh — Refresh view counts for all analyzed videos
# Usage: ./update-views.sh [--dry-run]
#
# Only modifies view data — never touches analysis content or scores.

set -euo pipefail
cd "$(dirname "$0")"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

TODAY=$(date +%Y-%m-%d)
UPDATED=0
TOTAL=0
SKIP_FILES="schema.json briefing-data.json channel-data.json channel-editorial.json"

for json_file in *.json; do
  echo "$SKIP_FILES" | grep -qw "$json_file" && continue

  VIDEO_ID=$(python3 -c "import json; print(json.load(open('$json_file'))['meta'].get('video_id', ''))" 2>/dev/null) || continue
  [[ -z "$VIDEO_ID" ]] && continue
  TOTAL=$((TOTAL + 1))

  NEW_VIEWS=$(yt-dlp --print "%(view_count)s" --skip-download "https://www.youtube.com/watch?v=$VIDEO_ID" 2>/dev/null) || continue
  [[ -z "$NEW_VIEWS" || "$NEW_VIEWS" == "NA" ]] && continue
  NEW_DURATION=$(yt-dlp --print "%(duration_string)s" --skip-download "https://www.youtube.com/watch?v=$VIDEO_ID" 2>/dev/null) || NEW_DURATION=""

  OLD_VIEWS=$(python3 -c "import json; print(json.load(open('$json_file'))['meta'].get('view_count', 0))" 2>/dev/null)

  if [[ "$NEW_VIEWS" != "$OLD_VIEWS" ]]; then
    if $DRY_RUN; then
      echo "  [dry-run] $VIDEO_ID: $OLD_VIEWS → $NEW_VIEWS"
    else
      python3 -c "
import json
d = json.load(open('$json_file'))
d['meta']['view_count'] = $NEW_VIEWS
d['meta']['view_count_updated'] = '$TODAY'
dur = '$NEW_DURATION'
if dur and dur != 'NA':
    d['meta']['duration'] = dur
json.dump(d, open('$json_file', 'w'), indent=2, ensure_ascii=False)
"
      echo "  $VIDEO_ID: $OLD_VIEWS → $NEW_VIEWS"
    fi
    UPDATED=$((UPDATED + 1))
  fi
done

echo "Checked $TOTAL videos, updated $UPDATED view counts"

if ! $DRY_RUN && [[ $UPDATED -gt 0 ]]; then
  cd "$(dirname "$0")/.."
  git add analysis/*.json 2>/dev/null || true
  git commit -m "Update view counts: ${TODAY}

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>" || true
  git push || echo "Push failed (non-fatal)"
fi
