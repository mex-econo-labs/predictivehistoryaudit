#!/usr/bin/env python3
"""
score-predictions.py — Score untested predictions against the briefing.

Three-pass approach:
1. Classify each untested prediction into: scorable_now, wishful_thinking, long_term
2. Score the scorable_now ones against the briefing
3. Reclassify wishful_thinking as unfalsifiable
4. Write changes back to JSON files

Usage:
    python3 score-predictions.py --dry-run    # Show what would change
    python3 score-predictions.py              # Apply changes
"""

import json
import glob
import os
import sys
import re
from collections import defaultdict
from datetime import date

ANALYSIS_DIR = os.path.dirname(os.path.abspath(__file__))
DRY_RUN = '--dry-run' in sys.argv

# ── Keywords for topic matching against briefing coverage ──

IRAN_WAR_KW = [
    'iran', 'hormuz', 'strait', 'tehran', 'irgc', 'khamenei', 'persian gulf',
    'ground troops', 'ground invasion', 'invade iran', 'invasion of iran',
    'draft', 'conscription', 'iran war', 'bombing iran', 'strike iran',
    'us loses', 'us will lose', 'america will lose', 'lose the war',
    'iran will win', 'iran will ultimately',
]
GULF_KW = [
    'gcc', 'gulf', 'bahrain', 'dubai', 'kuwait', 'qatar', 'uae', 'saudi',
    'oman', 'petrodollar', 'oil price', 'oil $', 'oil will', 'brent',
    '$200', 'oil crisis', 'energy crisis',
]
TURKEY_KW = ['turkey', 'turkish', 'erdogan', 'incirlik', 'constantinople']
RUSSIA_UKRAINE_KW = ['ukraine', 'odessa', 'crimea', 'donbas', 'putin', 'nato troops']
VENEZUELA_LATAM_KW = ['venezuela', 'maduro', 'cuba', 'colombia', 'latin america', 'south america']
TRUMP_NEAR_TERM_KW = ['trump will visit', 'trump is visiting', 'pardon', 'martial law',
                       'national guard', 'ice agent', 'ice officer', 'delta force',
                       'praetorian', '82nd airborne', 'deployment orders']
CHINA_TESTABLE_KW = ['trump.*china.*april', 'trump.*china.*march', 'trump.*beijing',
                      'us-china rapprochement', 'china will invest in.*venezuela']

# ── Wishful thinking / conspiracy indicators ──

WISHFUL_KW = [
    'fake alien', 'alien invasion', 'microchip implant', 'microchips into people',
    'magnetic pole', 'geomagnetic', 'mini ice age',
    '90% of humanity', '99% of humanity', 'kill 99%', 'depopulation',
    'euthanasia program', 'temple of solomon', 'solomon\'s temple', 'third temple',
    'pax judaica', 'pax judeica', 'empire of israel',
    'google will move to israel', 'google will move to jerusalem',
    'nvidia.*israel', 'oracle.*israel', 'tech companies.*israel',
    'byzantine', 'greeks.*constantinople', 'retaking constantinople',
    'reserve currency.*israel', 'israel.*reserve currency',
    'secret societies', 'kabbalistic numerology', 'donmeh',
    'frankist', 'paradise lost.*secret societies', 'worship this text',
    'persians created.*jewish identity',
    'jews.*escaped.*desert.*incubated islam',
    'food rationing.*worldwide', 'deindustrialization.*deurbanization',
    'airlines.*shut down', 'flying.*too expensive.*pointless',
]


def classify_prediction(claim: str) -> str:
    """Classify a prediction as scorable_now, wishful_thinking, or long_term."""
    cl = claim.lower()

    # Check wishful thinking first
    for kw in WISHFUL_KW:
        if re.search(kw, cl):
            return 'wishful_thinking'

    # Check if scorable against current briefing
    for kw_list in [IRAN_WAR_KW, GULF_KW, TURKEY_KW, RUSSIA_UKRAINE_KW,
                     VENEZUELA_LATAM_KW, TRUMP_NEAR_TERM_KW]:
        for kw in kw_list:
            if re.search(kw, cl):
                return 'scorable_now'

    # Regex patterns for China testable
    for kw in CHINA_TESTABLE_KW:
        if re.search(kw, cl):
            return 'scorable_now'

    return 'long_term'


def score_against_briefing(claim: str, briefing_facts: dict) -> tuple:
    """
    Score a scorable prediction against known briefing facts.
    Returns (new_status, status_note) or (None, None) if no change.
    """
    cl = claim.lower()

    # ── Iran ground troops / invasion ──
    if any(kw in cl for kw in ['ground troops', 'ground invasion', 'invade iran',
                                 'ground forces', 'send.*troops.*iran', 'airdrop soldiers']):
        if 'draft' in cl or 'conscription' in cl:
            return ('disconfirmed', 'As of March 2026, the US-Iran war is air/missile only. No ground troops deployed, no draft instituted.')
        return ('disconfirmed', 'As of March 2026, the US-Iran war remains an air/missile campaign. No ground troops have been deployed to Iran.')

    # ── US will lose / Iran will win ──
    if any(kw in cl for kw in ['us will lose', 'america will lose', 'united states will lose',
                                 'iran will win', 'iran will ultimately win']):
        return ('untested', None)  # war is ongoing, can't score yet

    # ── Iran unwinnable due to geography / troops trapped ──
    if 'unwinnable' in cl and 'iran' in cl and 'geography' in cl:
        return ('partially_confirmed', 'The US has not attempted a ground invasion. Air campaign continues but Iran remains defiant and retaliating across 9+ countries. The "trap" scenario hasn\'t materialized because no ground troops were sent.')
    if 'trapped' in cl and 'iran' in cl:
        return ('disconfirmed', 'No US ground troops in Iran. The war is air/missile only. The "troops trapped" scenario is moot.')

    # ── Oil $200 ──
    if '$200' in cl and ('oil' in cl or 'barrel' in cl):
        return ('untested', 'Oil peaked at $126/bbl in March 2026. IRGC projected $200 but not yet reached. Blockade ongoing.')

    # ── Hormuz blockade effects ──
    if 'hormuz' in cl and ('closure' in cl or 'closed' in cl or 'blockade' in cl):
        if 'no return' in cl or 'collapse' in cl:
            return ('untested', 'Hormuz blockade confirmed since March 2, 2026. Devastating impact on Gulf and global energy but too early to call permanent economic restructuring.')
        if 'food' in cl and 'dubai' in cl:
            return ('untested', 'Dubai struck by Iranian attacks but food crisis not yet confirmed as of March 14, 2026.')

    # ── Dubai bankruptcy ──
    if 'dubai' in cl and ('bankrupt' in cl or 'dead' in cl):
        return ('untested', 'Dubai struck by Iranian missiles (airport, Palm Islands) and ADNOC refinery shut. Severe damage but too early to declare bankruptcy or death of the city.')

    # ── Bahrain uprising ──
    if 'bahrain' in cl and ('fall' in cl or 'rise up' in cl or 'uprising' in cl):
        return ('untested', 'Bahrain struck by Iranian drones (32+ injured, Bapco refinery hit) but no Shia uprising has occurred as of March 2026.')

    # ── GCC collapse ──
    if ('gcc' in cl or 'gulf' in cl) and ('collapse' in cl or 'destroy' in cl or 'dead' in cl or 'wither' in cl):
        return ('partially_confirmed', 'GCC states severely damaged by Iranian strikes: UAE ADNOC refinery shut, Qatar halted all gas production, Kuwait/Bahrain declared force majeure. But states have not collapsed — governments functioning, diplomacy active.')

    # ── Saudi enters war ──
    if 'saudi' in cl and ('enter' in cl or 'on behalf' in cl or 'join' in cl):
        if 'war' in cl or 'american' in cl:
            return ('disconfirmed', 'Saudi Arabia refused airspace for US/Israeli strikes on Iran and publicly condemned Israeli "aggressions." Saudi has NOT entered the war on America\'s side.')

    # ── Saudi collapse if Iran attacks oil ──
    if 'saudi' in cl and 'oil field' in cl and ('collapse' in cl or 'attack' in cl):
        return ('partially_confirmed', 'Iran attacked Saudi oil infrastructure (Ras Tanura refinery halted, Shaybah intercepted, 2-2.5M bbl/day cut). Saudi economy under severe pressure but not collapsed. Has pipeline alternatives to Red Sea.')

    # ── Europe enters war ──
    if ('europe' in cl or 'germany' in cl or 'france' in cl or 'britain' in cl) and 'war' in cl and ('iran' in cl or 'america' in cl or 'enter' in cl):
        if 'civil war' not in cl:
            return ('disconfirmed', 'European nations have not entered the Iran war. UK said it is "not at war" after RAF Akrotiri was hit. No European military participation in strikes on Iran.')

    # ── Russia/China enter Iran war ──
    if ('russia' in cl or 'china' in cl) and ('iran' in cl or 'war' in cl) and ('enter' in cl or 'side' in cl or 'world war' in cl):
        return ('disconfirmed', 'Neither Russia nor China has entered the Iran war militarily. Russia delivered weapons but did not intervene. China has maintained strategic ambiguity.')

    # ── China limited assistance to Iran ──
    if 'china' in cl and 'limited assistance' in cl and 'iran' in cl:
        return ('confirmed', 'China maintained strategic ambiguity during the 2026 Iran war, providing diplomatic support but not openly intervening militarily — exactly as predicted.')

    # ── NORK threatens South Korea during Iran war ──
    if ('north korea' in cl or 'nork' in cl or 'korea' in cl) and ('menace' in cl or 'threaten' in cl or 'exploit' in cl or 'extort' in cl):
        if 'iran' in cl or 'middle east' in cl or 'distract' in cl:
            return ('untested', 'No direct NORK military action against South Korea as of March 2026, despite the Iran war. Elevated concern but no provocation.')

    # ── Turkey ──
    if 'turkey' in cl and ('drawn into' in cl or 'collapse' in cl or 'implosion' in cl):
        if 'ukraine' in cl:
            return ('untested', 'Turkey has not been drawn into the Ukraine war. However, 3 Iranian missiles entered Turkish airspace (Mar 4-13, 2026) from the Iran war theatre.')
        return ('untested', 'Turkey hit by 3 Iranian missiles (Mar 4-13, 2026) but has not collapsed or been drawn into war. Running back-channel diplomacy.')

    # ── Odessa ──
    if 'odessa' in cl:
        return ('untested', 'No battle for Odessa as of March 2026. Frontline remains in eastern Ukraine (Kostiantynivka/Kramatorsk area).')

    # ── Trump visits China ──
    if ('trump' in cl and 'china' in cl and ('visit' in cl or 'beijing' in cl)):
        if 'april' in cl:
            return ('untested', 'No confirmation of Trump visiting China in April 2026 as of March 14.')
        if 'march' in cl:
            return ('disconfirmed', 'Trump has not visited China in March 2026. No such visit announced or scheduled.')
        return ('untested', 'No Trump-China visit confirmed as of March 2026.')

    # ── US-China rapprochement ──
    if 'us' in cl and 'china' in cl and 'rapprochement' in cl:
        return ('disconfirmed', 'No US-China rapprochement. Fragile tariff truce only. Fundamental tensions unresolved.')

    # ── Venezuela ──
    if 'venezuela' in cl or 'maduro' in cl:
        if 'attack' in cl and ('trump' in cl or 'america' in cl):
            return ('confirmed', 'US launched Operation Absolute Resolve on January 3, 2026, capturing Maduro in Caracas.')
        if 'testif' in cl and ('election' in cl or 'smartmatic' in cl or '2020' in cl):
            return ('untested', 'Maduro arraigned Jan 5, 2026 on narco-terrorism charges. Trial pending March 17. No testimony about elections yet.')
        if 'china' in cl and 'invest' in cl:
            return ('untested', 'Rodriguez government signed oil reform law (Jan 29, 2026) opening to foreign investment, but no Chinese investment deal announced yet.')

    # ── Cuba ──
    if 'cuba' in cl:
        if 'attack' in cl:
            return ('disconfirmed', 'US has not attacked Cuba. Instead, secret US-Cuba negotiations confirmed March 13, 2026. Trump pursuing diplomatic approach.')
        return None, None

    # ── Colombia ──
    if 'colombia' in cl:
        if 'attack' in cl:
            return ('disconfirmed', 'US has not attacked Colombia. Colombia resumed deportation flights under pressure. Relationship tense but not military.')
        return None, None

    # ── Iran population won't rise up ──
    if 'iran' in cl and ('population' in cl or 'people' in cl) and ('rise up' in cl or 'support' in cl or 'invader' in cl):
        return ('untested', 'No ground invasion to test this. Air campaign has killed 1,444+ Iranians and reportedly galvanized nationalism, but no occupation to trigger uprising scenario.')

    # ── Iran nuclear talks ──
    if 'iran' in cl and ('nuclear talks' in cl or 'agree to' in cl or 'willing to' in cl) and ('attack' in cl or 'struck' in cl):
        return ('disconfirmed', 'Iran refused to halt all uranium enrichment as demanded. Talks broke down before Operation Midnight Hammer. Iran was NOT willing to accept all US terms.')

    # ── Nikki Haley VP ──
    if 'nikki haley' in cl and 'vp' in cl:
        return ('disconfirmed', 'Trump chose JD Vance as VP, not Nikki Haley. This prediction is moot.')

    # ── Chauvin pardon ──
    if 'chauvin' in cl and 'pardon' in cl:
        return ('untested', 'No Chauvin pardon announced as of March 2026.')

    # ── 82nd Airborne ──
    if '82nd airborne' in cl:
        return ('untested', 'No confirmed deployment of 82nd Airborne to Iran as of March 2026.')

    # ── Martial law / National Guard all 50 states ──
    if 'martial law' in cl or ('national guard' in cl and '50 state' in cl):
        return ('untested', 'No martial law declared as of March 2026.')

    # ── Iran water supply destruction ──
    if 'iran' in cl and ('water supply' in cl or 'dam' in cl or 'reservoir' in cl or 'uninhabitable' in cl):
        return ('disconfirmed', 'US-Israeli strikes targeted nuclear, military, and leadership targets — not water infrastructure. No strategy to make Iran "uninhabitable."')

    # ── Iran fragmentation into ethnic enclaves ──
    if 'iran' in cl and ('fragment' in cl or 'ethnic enclave' in cl or 'baloch' in cl or 'kurd' in cl or 'insurgent' in cl):
        return ('untested', 'No evidence of US-backed ethnic insurgencies in Iran as of March 2026. War is air/missile campaign only.')

    # ── WW3 ──
    if 'world war' in cl or 'wwiii' in cl or 'ww3' in cl:
        return ('untested', 'The Iran war has drawn in multiple countries but has not escalated to a formal world war. Russia and China have not entered. NATO Article 5 not invoked despite Turkish incidents.')

    # ── Bombing strengthens Iran ──
    if 'bombing' in cl and 'iran' in cl and ('strengthen' in cl or 'energetic' in cl or 'cohesive' in cl or 'unite' in cl):
        return ('partially_confirmed', 'Mojtaba Khamenei elected Supreme Leader under IRGC pressure after father\'s assassination. Iran retaliating fiercely across 9+ countries. Some evidence of nationalist galvanization, but regime also weakened by leadership decapitation.')

    return None, None


def main():
    # Load all predictions
    predictions = []
    for f in sorted(glob.glob(os.path.join(ANALYSIS_DIR, '*.json'))):
        bn = os.path.basename(f)
        if bn in ('schema.json', 'briefing-data.json'):
            continue
        with open(f) as fh:
            d = json.load(fh)
        for i, p in enumerate(d.get('thesis', {}).get('predictions', [])):
            if not isinstance(p, dict):
                continue
            if p.get('status') == 'untested':
                predictions.append({
                    'file': bn,
                    'index': i,
                    'claim': p.get('claim', ''),
                    'type': p.get('type', 'prediction'),
                })

    print(f"Total untested: {len(predictions)}")

    # Classify
    classified = defaultdict(list)
    for p in predictions:
        cat = classify_prediction(p['claim'])
        p['category'] = cat
        classified[cat].append(p)

    print(f"\nClassification:")
    print(f"  Scorable now:     {len(classified['scorable_now'])}")
    print(f"  Wishful thinking: {len(classified['wishful_thinking'])}")
    print(f"  Long-term:        {len(classified['long_term'])}")

    # Score the scorable ones
    changes = []

    for p in classified['scorable_now']:
        new_status, note = score_against_briefing(p['claim'], {})
        if new_status and new_status != 'untested':
            changes.append({
                'file': p['file'],
                'index': p['index'],
                'new_status': new_status,
                'status_note': note,
                'reason': 'scored against briefing',
            })
            print(f"\n  CHANGE [{p['file']}#{p['index']}]: untested -> {new_status}")
            print(f"    Claim: {p['claim'][:120]}")
            print(f"    Note: {note}")
        elif new_status == 'untested' and note:
            # Update the note even if status unchanged
            changes.append({
                'file': p['file'],
                'index': p['index'],
                'new_status': 'untested',
                'status_note': note,
                'reason': 'added scoring note',
            })

    # Reclassify wishful thinking as unfalsifiable
    for p in classified['wishful_thinking']:
        changes.append({
            'file': p['file'],
            'index': p['index'],
            'new_status': 'unfalsifiable',
            'status_note': 'Reclassified: speculative/conspiratorial claim without empirical testability.',
            'reason': 'wishful thinking -> unfalsifiable',
        })

    # Summary
    status_changes = [c for c in changes if c['new_status'] != 'untested' and c['reason'] != 'added scoring note']
    note_additions = [c for c in changes if c['new_status'] == 'untested']
    wishful = [c for c in changes if c['reason'] == 'wishful thinking -> unfalsifiable']

    print(f"\n{'='*60}")
    print(f"Status changes:      {len(status_changes)}")
    print(f"  -> confirmed:      {sum(1 for c in status_changes if c['new_status'] == 'confirmed')}")
    print(f"  -> partially:      {sum(1 for c in status_changes if c['new_status'] == 'partially_confirmed')}")
    print(f"  -> disconfirmed:   {sum(1 for c in status_changes if c['new_status'] == 'disconfirmed')}")
    print(f"  -> unfalsifiable:  {sum(1 for c in changes if c['new_status'] == 'unfalsifiable')}")
    print(f"Notes added:         {len(note_additions)}")
    print(f"Still untested:      {len(classified['long_term'])}")

    if DRY_RUN:
        print("\n[DRY RUN — no files modified]")
        return

    # Apply changes
    by_file = defaultdict(list)
    for c in changes:
        by_file[c['file']].append(c)

    files_modified = 0
    for fname, file_changes in by_file.items():
        fpath = os.path.join(ANALYSIS_DIR, fname)
        with open(fpath) as f:
            d = json.load(f)

        modified = False
        for c in file_changes:
            pred = d['thesis']['predictions'][c['index']]
            old_status = pred.get('status', 'untested')
            if c['new_status'] != old_status or c.get('status_note'):
                pred['status'] = c['new_status']
                if c.get('status_note'):
                    pred['status_note'] = c['status_note']
                modified = True

        if modified:
            with open(fpath, 'w') as f:
                json.dump(d, f, indent=2, ensure_ascii=False)
            files_modified += 1

    print(f"\nModified {files_modified} files.")

    # Update briefing-data.json
    bd_path = os.path.join(ANALYSIS_DIR, 'briefing-data.json')
    with open(bd_path) as f:
        bd = json.load(f)
    bd['last_scoring_date'] = str(date.today())
    y, m, d = str(date.today()).split('-')
    m = int(m) + 1
    if m > 12:
        m = 1
        y = str(int(y) + 1)
    bd['next_scoring_date'] = f"{y}-{int(m):02d}-{d}"
    with open(bd_path, 'w') as f:
        json.dump(bd, f, indent=2, ensure_ascii=False)

    print("Updated briefing-data.json scoring dates.")


if __name__ == '__main__':
    main()
