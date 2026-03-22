#!/usr/bin/env python3
"""
build.py — Static site generator for Predictive History Audit.
Reads analysis JSON files and renders them to HTML via Jinja2 templates.

Usage:
    python3 build.py                    # Build to dist/
    python3 build.py --output-dir docs  # Build to docs/
"""

import argparse
import json
import glob
import os
import re
import shutil
from collections import Counter, defaultdict
from jinja2 import Environment, FileSystemLoader


# --- Config ---
SCORE_KEYS = [
    'historical_accuracy', 'argumentative_rigor', 'framing_and_selectivity',
    'perspective_diversity', 'normative_loading', 'determinism_vs_contingency',
    'civilizational_framing'
]

SCORE_SHORT = ['acc', 'rig', 'fra', 'div', 'nor', 'det', 'civ']

SCORE_LABELS = {
    'historical_accuracy': 'Historical Accuracy',
    'argumentative_rigor': 'Argumentative Rigor',
    'framing_and_selectivity': 'Framing & Selectivity',
    'perspective_diversity': 'Perspective Diversity',
    'normative_loading': 'Normative Loading',
    'determinism_vs_contingency': 'Determinism vs. Contingency',
    'civilizational_framing': 'Civilizational Framing',
}

SCORE_TIPS = {
    'historical_accuracy': 'Are facts, dates, and events correct? 5 = solid, 1 = major errors',
    'argumentative_rigor': 'Is reasoning logically sound? 5 = rigorous, 1 = fallacious',
    'framing_and_selectivity': 'Is evidence balanced or cherry-picked? 5 = balanced, 1 = selective',
    'perspective_diversity': 'Are competing viewpoints engaged? 5 = diverse, 1 = single narrative',
    'normative_loading': 'How much moral judgment replaces analysis? 5 = neutral, 1 = prescriptive',
    'determinism_vs_contingency': 'Is history shown as inevitable or contingent? 5 = balanced, 1 = deterministic',
    'civilizational_framing': 'Are civilizations characterized fairly? 5 = even-handed, 1 = biased',
}


def parse_advisory_points(text: str) -> list:
    """Split viewer_advisory text into bullet points.
    Handles patterns like '(1) Point one. (2) Point two.'
    Drops the preamble before (1) if it's just an intro clause."""
    # Split on numbered markers like (1), (2), etc.
    parts = re.split(r'\(\d+\)\s*', text)
    result = []
    for i, p in enumerate(parts):
        p = p.strip()
        if not p:
            continue
        # First part (before any number) is usually preamble — skip if short/intro
        if i == 0 and (p.endswith(':') or len(p) < 120):
            continue
        # Clean trailing period duplication
        p = p.rstrip('.').strip() + '.'
        result.append(p)
    # If no numbered points found, return the whole text as one item
    if not result:
        return [text.strip()]
    return result


def ts_to_seconds(ts: str) -> int:
    """Convert HH:MM:SS or MM:SS timestamp to seconds for YouTube links."""
    ts = ts.strip().split(',')[0]  # strip SRT millis
    parts = ts.split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0


def clean_title(data: dict) -> str:
    """Strip redundant series/episode prefix from title if present."""
    title = data['meta']['title']
    series = data['meta']['series']
    ep = str(data['meta'].get('episode', ''))
    # Remove patterns like "Civilization #1: ", "Civilization #END: ", "Geo-Strategy #8: "
    prefixes = [
        f"{series} #{ep}：  ",  # fullwidth colon + double space (from YouTube)
        f"{series} #{ep}: ",
        f"{series}#{ep}：  ",
        f"{series}#{ep}: ",
        f"{series} #{ep} ",
    ]
    for prefix in prefixes:
        if title.startswith(prefix):
            return title[len(prefix):]
    return title


def make_slug(data: dict) -> str:
    """Generate a URL-safe slug from series + episode."""
    series = data['meta']['series'].lower().replace(' ', '-').replace('/', '-')
    ep = data['meta'].get('episode')
    if ep is None:
        # No episode number — use video_id prefix for uniqueness
        vid = data['meta'].get('video_id', 'x')[:8]
        return f"{series}-{vid}"
    return f"{series}-{str(ep).lower().replace(' ', '-')}"


SITE_URL = 'https://predictivehistoryaudit.pages.dev'


def compute_avg(data: dict) -> float:
    """Compute average score across all axes."""
    vals = [data['scores'][k]['score'] for k in SCORE_KEYS]
    return sum(vals) / len(vals)


def sort_episode_key(ep):
    """Return a sortable numeric key for episodes."""
    if ep is None:
        return 9999
    if isinstance(ep, int):
        return ep
    # Handle 'END', 'BONUS', etc.
    special = {'END': 9998, 'BONUS': 9997}
    return special.get(str(ep).upper(), 9999)


def load_analyses(base_dir: str) -> list:
    """Load all analysis JSON files."""
    analyses = []
    for path in sorted(glob.glob(os.path.join(base_dir, '*.json'))):
        if os.path.basename(path) in ('schema.json', 'briefing-data.json', 'channel-data.json', 'channel-editorial.json'):
            continue
        with open(path) as f:
            data = json.load(f)
        data['slug'] = make_slug(data)
        data['avg'] = compute_avg(data)
        data['sort_episode'] = sort_episode_key(data['meta'].get('episode'))
        data['display_title'] = clean_title(data)
        analyses.append(data)

    # Sort by upload_date descending (newest first)
    analyses.sort(key=lambda d: d['meta'].get('upload_date', ''), reverse=True)
    return analyses


def build(base_dir: str, output_dir: str):
    """Build the static site."""

    print(f"Building from: {base_dir}")
    print(f"Output to: {output_dir}")

    # Load data
    analyses = load_analyses(base_dir)
    print(f"Loaded {len(analyses)} analyses")

    if not analyses:
        print("No analyses found. Nothing to build.")
        return

    # Setup Jinja2
    template_dir = os.path.join(base_dir, 'templates')
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=False)
    env.filters['ts_to_seconds'] = ts_to_seconds
    env.filters['commafy'] = lambda v: f'{int(v):,}' if v else '0'
    env.filters['footnotes'] = lambda text: re.sub(
        r'\[(\d+)\]',
        r'<sup class="fn-ref"><a href="#fn-\1" id="fn-ref-\1">[\1]</a></sup>',
        str(text)
    )

    # Create output directories
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'lectures'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'static'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'caps'), exist_ok=True)

    # Copy static assets
    static_src = os.path.join(base_dir, 'static')
    for f in glob.glob(os.path.join(static_src, '*')):
        if os.path.isfile(f):
            shutil.copy2(f, os.path.join(output_dir, 'static', os.path.basename(f)))

    # Copy social cards
    cards_src = os.path.join(base_dir, 'static', 'cards')
    if os.path.isdir(cards_src):
        cards_dst = os.path.join(output_dir, 'cards')
        os.makedirs(cards_dst, exist_ok=True)
        for f in glob.glob(os.path.join(cards_src, '*.png')):
            shutil.copy2(f, os.path.join(cards_dst, os.path.basename(f)))
        print(f"Copied {len(glob.glob(os.path.join(cards_src, '*.png')))} social cards")

    # Copy screencaps
    caps_src = os.path.join(base_dir, 'caps')
    if os.path.isdir(caps_src):
        for f in glob.glob(os.path.join(caps_src, '*.jpg')):
            shutil.copy2(f, os.path.join(output_dir, 'caps', os.path.basename(f)))
        print(f"Copied {len(glob.glob(os.path.join(caps_src, '*.jpg')))} screencaps")

    # --- Compute aggregate data ---
    all_series = sorted(set(d['meta']['series'] for d in analyses))
    avg_overall = sum(d['avg'] for d in analyses) / len(analyses)

    total_predictions = sum(len(d['thesis'].get('predictions', [])) for d in analyses)
    total_sources = sum(len(d['sources'].get('named_sources', [])) for d in analyses)
    total_rhetoric = sum(len(d.get('rhetoric', [])) for d in analyses)

    # Prediction & claim stats
    all_predictions = []
    prediction_stats = Counter()
    claim_stats = Counter()
    for d in analyses:
        for p in d['thesis'].get('predictions', []):
            status = p.get('status', 'untested')
            ptype = p.get('type', 'prediction')
            entry = {
                'claim': p['claim'],
                'type': ptype,
                'timestamp': p.get('timestamp', ''),
                'status': status,
                'status_note': p.get('status_note', ''),
                'falsifiable': p.get('falsifiable', False),
                'lecture_slug': d['slug'],
                'lecture_title': f"{d['meta']['series']} #{d['meta']['episode']}: {d['display_title']}",
                'upload_date': d['meta'].get('upload_date', ''),
            }
            all_predictions.append(entry)
            if ptype == 'prediction':
                prediction_stats[status] += 1
            else:
                claim_stats[status] += 1

    # Rhetoric frequency
    rhetoric_counter = Counter()
    for d in analyses:
        for r in d.get('rhetoric', []):
            rhetoric_counter[r['technique']] += 1
    rhetoric_freq = rhetoric_counter.most_common()

    # Series stats
    series_groups = defaultdict(list)
    for d in analyses:
        series_groups[d['meta']['series']].append(d)

    series_stats = []
    for name in all_series:
        group = series_groups[name]
        axis_avgs = []
        for key in SCORE_KEYS:
            axis_avgs.append(sum(d['scores'][key]['score'] for d in group) / len(group))
        overall = sum(axis_avgs) / len(axis_avgs)
        series_stats.append({
            'name': name,
            'count': len(group),
            'axis_avgs': axis_avgs,
            'overall': overall,
        })

    # Civilizational mentions
    civ_mentions = defaultdict(list)
    for d in analyses:
        cf = d['scores'].get('civilizational_framing', {})
        for key in ['china_treatment', 'us_treatment', 'russia_treatment', 'west_treatment']:
            text = cf.get(key)
            if text:
                civ_mentions[key].append({
                    'slug': d['slug'],
                    'title': f"{d['meta']['series']} #{d['meta']['episode']}: {d['display_title']}",
                    'text': text,
                })

    # --- Render pages ---
    common = {
        'score_keys': SCORE_KEYS,
        'score_short': SCORE_SHORT,
        'score_labels': SCORE_LABELS,
        'score_tips': SCORE_TIPS,
    }

    # Dashboard
    tmpl = env.get_template('dashboard.html')
    html = tmpl.render(
        page='dashboard',
        root='',
        lectures=analyses,
        all_series=all_series,
        series_count=len(all_series),
        avg_overall=avg_overall,
        total_predictions=total_predictions,
        total_sources=total_sources,
        total_rhetoric=total_rhetoric,
        **common,
    )
    with open(os.path.join(output_dir, 'index.html'), 'w') as f:
        f.write(html)
    print("  Built: index.html")

    # Methodology
    tmpl = env.get_template('methodology.html')
    html = tmpl.render(page='methodology', root='')
    with open(os.path.join(output_dir, 'methodology.html'), 'w') as f:
        f.write(html)
    print("  Built: methodology.html")

    # Patterns
    tmpl = env.get_template('patterns.html')
    html = tmpl.render(
        page='patterns',
        root='',
        lectures=analyses,
        series_stats=series_stats,
        all_predictions=all_predictions,
        prediction_stats=prediction_stats,
        claim_stats=claim_stats,
        rhetoric_freq=rhetoric_freq,
        civ_mentions=civ_mentions,
        **common,
    )
    with open(os.path.join(output_dir, 'patterns.html'), 'w') as f:
        f.write(html)
    print("  Built: patterns.html")

    # Briefing
    briefing_path = os.path.join(base_dir, 'briefing-data.json')
    if os.path.exists(briefing_path):
        with open(briefing_path) as f:
            briefing = json.load(f)
        tmpl = env.get_template('briefing.html')
        html = tmpl.render(
            page='briefing',
            root='',
            briefing_date=briefing.get('briefing_date', 'Unknown'),
            last_scoring_date=briefing.get('last_scoring_date'),
            next_scoring_date=briefing.get('next_scoring_date'),
            daily_entries=briefing.get('daily_entries', []),
            theatres=briefing.get('theatres', []),
            metrics=briefing.get('metrics', []),
            ground_invasion=briefing.get('ground_invasion_tracker'),
        )
        with open(os.path.join(output_dir, 'briefing.html'), 'w') as f:
            f.write(html)
        print("  Built: briefing.html")

    # Channel analysis
    channel_path = os.path.join(base_dir, 'channel-data.json')
    if os.path.exists(channel_path):
        with open(channel_path) as f:
            channel_data = json.load(f)

        # Compute channel-wide score averages
        channel_scores = {}
        for key in SCORE_KEYS:
            channel_scores[key] = sum(d['scores'][key]['score'] for d in analyses) / len(analyses)

        channel_scores_list = [channel_scores[k] for k in SCORE_KEYS]
        score_labels_list = [SCORE_LABELS[k] for k in SCORE_KEYS]

        # Percentage of lectures scoring 1 on perspective_diversity
        pct_div_1 = round(100 * sum(1 for d in analyses if d['scores']['perspective_diversity']['score'] == 1) / len(analyses))

        tmpl = env.get_template('channel.html')
        html = tmpl.render(
            page='channel',
            root='',
            cd=channel_data,
            total_lectures=len(analyses),
            series_count=len(all_series),
            avg_overall=avg_overall,
            channel_scores=channel_scores,
            channel_scores_list=channel_scores_list,
            score_labels_list=score_labels_list,
            pct_div_1=pct_div_1,
            series_stats=series_stats,
            zip=zip,
            **common,
        )
        with open(os.path.join(output_dir, 'channel.html'), 'w') as f:
            f.write(html)
        print("  Built: channel.html")

    # Individual lecture pages
    tmpl = env.get_template('lecture.html')
    for d in analyses:
        advisory_points = parse_advisory_points(d.get('verdict', {}).get('viewer_advisory', ''))
        card_url = f"{SITE_URL}/cards/{d['slug']}.png"
        html = tmpl.render(
            page='lecture',
            root='../',
            d=d,
            avg=d['avg'],
            card_url=card_url,
            advisory_points=advisory_points,
            **common,
        )
        out_path = os.path.join(output_dir, 'lectures', f"{d['slug']}.html")
        with open(out_path, 'w') as f:
            f.write(html)
        print(f"  Built: lectures/{d['slug']}.html")

    print(f"\nDone. {len(analyses) + 3} pages built to {output_dir}/")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build Predictive History Audit static site')
    parser.add_argument('--output-dir', default='dist', help='Output directory (default: dist)')
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, args.output_dir)
    build(base_dir, output_dir)
