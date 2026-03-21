#!/usr/bin/env python3
"""
generate-channel-data.py — Compute channel-level aggregate data from per-lecture
analysis JSONs and merge with editorial content to produce channel-data.json.

Run periodically (not on every lecture publish) to refresh calibration stats,
civilizational framing percentages, engagement rankings, etc.

Usage:
    python3 generate-channel-data.py
"""

import json
import glob
import os
import re
from collections import Counter, defaultdict
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKIP_FILES = {'schema.json', 'briefing-data.json', 'channel-data.json', 'channel-editorial.json'}

SCORE_KEYS = [
    'historical_accuracy', 'argumentative_rigor', 'framing_and_selectivity',
    'perspective_diversity', 'normative_loading', 'determinism_vs_contingency',
    'civilizational_framing'
]

# --- Civilizational framing classification ---
FAVORABLE_WORDS = ['favorable', 'positive', 'praised', 'sympathetic', 'model', 'victim',
                   'benign', 'meritocratic', 'peaceful', 'rising', 'superior']
CRITICAL_WORDS = ['critical', 'negative', 'imperial', 'corrupt', 'decline', 'aggressive',
                  'propaganda', 'hubris', 'arrogant', 'doomed', 'conspiracy', 'evil',
                  'bully', 'mafia', 'paper tiger', 'ponzi', 'parasit']


def classify_treatment(text):
    """Classify a civilizational treatment string as favorable/neutral/critical."""
    if not text:
        return None
    text_lower = text.lower()
    fav_score = sum(1 for w in FAVORABLE_WORDS if w in text_lower)
    crit_score = sum(1 for w in CRITICAL_WORDS if w in text_lower)
    if fav_score > crit_score:
        return 'favorable'
    elif crit_score > fav_score:
        return 'critical'
    return 'neutral'


def classify_prediction_topic(claim_text, topic_keywords):
    """Match a prediction claim to a topic based on keywords."""
    claim_lower = claim_text.lower()
    for topic, keywords in topic_keywords.items():
        if any(kw in claim_lower for kw in keywords):
            return topic
    return None


def load_analyses():
    """Load all analysis JSON files."""
    analyses = []
    for path in sorted(glob.glob(os.path.join(BASE_DIR, '*.json'))):
        if os.path.basename(path) in SKIP_FILES:
            continue
        with open(path) as f:
            data = json.load(f)
        if 'meta' not in data or 'scores' not in data:
            continue
        analyses.append(data)
    analyses.sort(key=lambda d: d['meta'].get('upload_date', ''), reverse=True)
    return analyses


def compute_prediction_calibration(analyses, topic_keywords):
    """Compute prediction calibration stats from all analyses."""
    total_predictions = 0
    total_claims = 0
    status_counts = Counter()
    type_counts = Counter()

    # Per-topic tracking
    topic_confirmed = Counter()
    topic_disconfirmed = Counter()

    key_hits = []
    key_misses = []

    ground_invasion_count = 0
    ground_invasion_confirmed = 0

    for d in analyses:
        for p in d['thesis'].get('predictions', []):
            ptype = p.get('type', 'prediction')
            status = p.get('status', 'untested')
            claim = p.get('claim', '')

            if ptype == 'prediction':
                total_predictions += 1
            else:
                total_claims += 1

            status_counts[status] += 1
            type_counts[ptype] += 1

            # Topic classification
            topic = classify_prediction_topic(claim, topic_keywords)
            if topic and status in ('confirmed', 'partially_confirmed'):
                topic_confirmed[topic] += 1
            elif topic and status in ('disconfirmed',):
                topic_disconfirmed[topic] += 1

            # Ground invasion tracking
            claim_lower = claim.lower()
            if any(kw in claim_lower for kw in ['ground invasion', 'ground troops',
                    'boots on the ground', 'infantry', 'occupy iran',
                    'national draft', '500,000', '500000', 'million soldiers',
                    'million troops', 'ground war']):
                ground_invasion_count += 1
                if status == 'confirmed':
                    ground_invasion_confirmed += 1

    # Compute calibration
    confirmed = status_counts.get('confirmed', 0)
    disconfirmed = status_counts.get('disconfirmed', 0)
    resolved = confirmed + disconfirmed
    overall_calibration = round(100 * confirmed / resolved, 1) if resolved > 0 else 0

    # By-topic calibration
    all_topics = sorted(set(list(topic_confirmed.keys()) + list(topic_disconfirmed.keys())),
                        key=lambda t: list(topic_keywords.keys()).index(t)
                        if t in topic_keywords else 999)

    by_topic = []
    for topic in all_topics:
        c = topic_confirmed.get(topic, 0)
        dc = topic_disconfirmed.get(topic, 0)
        total = c + dc
        cal = round(100 * c / total, 1) if total > 0 else 0
        by_topic.append({
            'topic': topic,
            'confirmed': c,
            'disconfirmed': dc,
            'calibration': cal
        })

    return {
        'total_predictions': total_predictions,
        'total_claims': total_claims,
        'confirmed': confirmed,
        'partially_confirmed': status_counts.get('partially_confirmed', 0),
        'disconfirmed': disconfirmed,
        'untested': status_counts.get('untested', 0),
        'unfalsifiable': status_counts.get('unfalsifiable', 0),
        'overall_calibration': overall_calibration,
        'by_topic': by_topic,
        'ground_invasion_count': ground_invasion_count,
        'ground_invasion_confirmed': ground_invasion_confirmed,
    }


def compute_civ_framing(analyses):
    """Compute civilizational framing percentages from all analyses."""
    actors = {
        'china': {'field': 'china_treatment', 'mentioned': 0, 'favorable': 0, 'neutral': 0, 'critical': 0},
        'us': {'field': 'us_treatment', 'mentioned': 0, 'favorable': 0, 'neutral': 0, 'critical': 0},
        'russia': {'field': 'russia_treatment', 'mentioned': 0, 'favorable': 0, 'neutral': 0, 'critical': 0},
        'west': {'field': 'west_treatment', 'mentioned': 0, 'favorable': 0, 'neutral': 0, 'critical': 0},
    }

    for d in analyses:
        cf = d['scores'].get('civilizational_framing', {})
        for actor, info in actors.items():
            text = cf.get(info['field'])
            if text:
                info['mentioned'] += 1
                classification = classify_treatment(text)
                if classification:
                    info[classification] += 1

    result = {}
    for actor, info in actors.items():
        m = info['mentioned']
        if m > 0:
            result[actor] = {
                'mentioned': m,
                'favorable_pct': round(100 * info['favorable'] / m, 1),
                'neutral_pct': round(100 * info['neutral'] / m, 1),
                'critical_pct': round(100 * info['critical'] / m, 1),
            }
        else:
            result[actor] = {'mentioned': 0, 'favorable_pct': 0, 'neutral_pct': 0, 'critical_pct': 0}

    return result


def compute_top_videos(analyses, n=10):
    """Get top N videos by view count."""
    sorted_by_views = sorted(analyses, key=lambda d: d['meta'].get('view_count', 0), reverse=True)
    top = []
    for d in sorted_by_views[:n]:
        meta = d['meta']
        ep = meta.get('episode', '')
        series_ep = f"{meta['series']} #{ep}" if ep else meta['series']
        top.append({
            'title': meta.get('title', ''),
            'series': series_ep,
            'views': meta.get('view_count', 0),
        })
    return top


def compute_key_predictions(analyses):
    """Extract key confirmed and disconfirmed predictions with status_notes."""
    hits = []
    misses = []

    for d in analyses:
        for p in d['thesis'].get('predictions', []):
            status = p.get('status', 'untested')
            claim = p.get('claim', '')
            note = p.get('status_note', '')

            if status == 'confirmed' and note:
                hits.append({'claim': claim, 'note': note,
                             'series': d['meta']['series'],
                             'episode': d['meta'].get('episode', '')})
            elif status == 'disconfirmed' and note:
                misses.append({'claim': claim, 'note': note,
                               'series': d['meta']['series'],
                               'episode': d['meta'].get('episode', '')})

    # Deduplicate by claim similarity (take first occurrence)
    seen_hits = set()
    unique_hits = []
    for h in hits:
        key = h['claim'][:80].lower()
        if key not in seen_hits:
            seen_hits.add(key)
            unique_hits.append(f"{h['claim']} ({h['note']})")

    seen_misses = set()
    unique_misses = []
    for m in misses:
        key = m['claim'][:80].lower()
        if key not in seen_misses:
            seen_misses.add(key)
            unique_misses.append(f"{m['claim']} ({m['note']})")

    # Sort by significance (longer notes tend to be more important)
    unique_hits.sort(key=len, reverse=True)
    unique_misses.sort(key=len, reverse=True)

    return unique_hits[:8], unique_misses[:8]


def main():
    print("Loading analyses...")
    analyses = load_analyses()
    print(f"  Loaded {len(analyses)} analyses")

    print("Loading editorial content...")
    editorial_path = os.path.join(BASE_DIR, 'channel-editorial.json')
    with open(editorial_path) as f:
        editorial = json.load(f)

    topic_keywords = editorial.get('prediction_topic_keywords', {})

    # --- Compute all data ---
    print("Computing prediction calibration...")
    calibration = compute_prediction_calibration(analyses, topic_keywords)

    print("Computing civilizational framing...")
    civ_framing = compute_civ_framing(analyses)

    print("Computing top videos...")
    top_videos = compute_top_videos(analyses)

    print("Extracting key predictions...")
    key_hits, key_misses = compute_key_predictions(analyses)

    # Ground invasion fixation text
    gi_count = calibration['ground_invasion_count']
    gi_text = (
        f"The single most repeated prediction across the entire corpus: a US ground "
        f"invasion of Iran requiring 500K-2M troops and a national draft. Predicted "
        f"{gi_count} separate times across Game Theory, Geo-Strategy, and Interview "
        f"series. The entire causal chain depends on it: ground troops trapped "
        f"\u2192 draft \u2192 civil war \u2192 empire collapses. The US-Iran conflict "
        f"has been exclusively air/missile-based. This prediction was never corrected "
        f"or acknowledged as wrong in subsequent lectures."
    )

    # Engagement title analysis
    total_views = sum(d['meta'].get('view_count', 0) for d in analyses)
    iran_views = [d['meta'].get('view_count', 0) for d in analyses
                  if 'iran' in d['meta'].get('title', '').lower()
                  or 'trap' in d['meta'].get('title', '').lower()]
    civ_views = [d['meta'].get('view_count', 0) for d in analyses
                 if d['meta']['series'] == 'Civilization']
    iran_avg = int(sum(iran_views) / len(iran_views)) if iran_views else 0
    civ_avg = int(sum(civ_views) / len(civ_views)) if civ_views else 0

    title_analysis = (
        f"Provocative titles (\"Evil,\" \"Trap,\" \"War,\" \"Doomed,\" \"Collapse\") "
        f"outperform neutral academic titles by 3-5x within the same series. "
        f"Iran-related content averages {iran_avg:,} views vs {civ_avg:,} for "
        f"Civilization series academic lectures."
    )

    # --- Assemble channel-data.json ---
    channel_data = {
        'generated_date': date.today().isoformat(),
        'subject': editorial['subject'],
        'timeline': editorial['timeline'],
        'expulsion_paradox': editorial['expulsion_paradox'],
        'credential_issues': editorial['credential_issues'],
        'triple_standard': {
            'summary': f"Across {len(analyses)} analyzed lectures, Jiang operates with a consistent triple standard in civilizational framing.",
            'china': {
                'favorable_pct': civ_framing['china']['favorable_pct'],
                'neutral_pct': civ_framing['china']['neutral_pct'],
                'critical_pct': civ_framing['china']['critical_pct'],
                'characterization': editorial['triple_standard_characterizations']['china'],
                'key_quotes': editorial['triple_standard_characterizations']['china_quotes'],
            },
            'us_west': {
                'favorable_pct': civ_framing['us']['favorable_pct'],
                'neutral_pct': civ_framing['us']['neutral_pct'],
                'critical_pct': civ_framing['us']['critical_pct'],
                'characterization': editorial['triple_standard_characterizations']['us_west'],
                'key_quotes': editorial['triple_standard_characterizations']['us_west_quotes'],
            },
            'russia': {
                'favorable_pct': civ_framing['russia']['favorable_pct'],
                'neutral_pct': civ_framing['russia']['neutral_pct'],
                'critical_pct': civ_framing['russia']['critical_pct'],
                'characterization': editorial['triple_standard_characterizations']['russia'],
                'key_quotes': editorial['triple_standard_characterizations']['russia_quotes'],
            },
        },
        'ironic_mirrors_curated': editorial['ironic_mirrors_curated'],
        'prediction_calibration': {
            'total_predictions': calibration['total_predictions'],
            'total_claims': calibration['total_claims'],
            'confirmed': calibration['confirmed'],
            'partially_confirmed': calibration['partially_confirmed'],
            'disconfirmed': calibration['disconfirmed'],
            'untested': calibration['untested'],
            'unfalsifiable': calibration['unfalsifiable'],
            'overall_calibration': calibration['overall_calibration'],
            'by_topic': calibration['by_topic'],
            'key_hits': key_hits,
            'key_misses': key_misses,
            'ground_invasion_fixation': gi_text,
        },
        'propaganda_analysis': editorial['propaganda_analysis'],
        'engagement_patterns': {
            'top_10_videos': top_videos,
            'title_analysis': title_analysis,
            'growth_trajectory': "Near-zero to viral overnight. Channel gained 100K subscribers in 3 days when Iran predictions materialized (June 2025). Current growth: ~28K subscribers/day, ~837K/month. Substack reached #1 in \"world politics\" category within 6 months of launch.",
        },
        'eschatological_context': editorial['eschatological_context'],
        'footnotes': editorial.get('footnotes', []),
        'published_works': editorial.get('published_works', {}),
    }

    # Write output
    output_path = os.path.join(BASE_DIR, 'channel-data.json')
    with open(output_path, 'w') as f:
        json.dump(channel_data, f, indent=2, ensure_ascii=False)

    print(f"\nGenerated: {output_path}")
    print(f"  Lectures: {len(analyses)}")
    print(f"  Predictions: {calibration['total_predictions']} predictions + {calibration['total_claims']} claims")
    print(f"  Calibration: {calibration['overall_calibration']}% ({calibration['confirmed']} confirmed / {calibration['confirmed'] + calibration['disconfirmed']} resolved)")
    print(f"  Ground invasion predictions: {gi_count} ({calibration['ground_invasion_confirmed']} confirmed)")
    print(f"  Civ framing — China: {civ_framing['china']['favorable_pct']}% fav / {civ_framing['china']['critical_pct']}% crit")
    print(f"  Civ framing — US: {civ_framing['us']['favorable_pct']}% fav / {civ_framing['us']['critical_pct']}% crit")
    print(f"  Civ framing — Russia: {civ_framing['russia']['favorable_pct']}% fav / {civ_framing['russia']['critical_pct']}% crit")
    print(f"  Top video: {top_videos[0]['title']} ({top_videos[0]['views']:,} views)")


if __name__ == '__main__':
    main()
