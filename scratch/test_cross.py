import os
import sys
import difflib
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')
from model.forebet_cruce import fetch_aposta_matches, scrape_forebet_matches, normalize_team_name

def match_teams_improved(h1, a1, h2, a2):
    nh1, na1 = normalize_team_name(h1), normalize_team_name(a1)
    nh2, na2 = normalize_team_name(h2), normalize_team_name(a2)
    if not nh1 or not na1 or not nh2 or not na2:
        return False
    home_match = (nh1 == nh2) or (nh1 in nh2) or (nh2 in nh1) or (difflib.SequenceMatcher(None, nh1, nh2).ratio() >= 0.78)
    away_match = (na1 == na2) or (na1 in na2) or (na2 in na1) or (difflib.SequenceMatcher(None, na1, na2).ratio() >= 0.78)
    return home_match and away_match

fb_list = scrape_forebet_matches()
ap_list = fetch_aposta_matches()

matched = []
for fb in fb_list:
    for ap in ap_list:
        if match_teams_improved(fb['home'], fb['away'], ap['home'], ap['away']):
            matched.append((fb, ap))
            break

print(f"Total matched: {len(matched)}")
for fb, ap in matched:
    if "OFI" in fb['home']:
        print(f"MATCH: {fb['home']} vs {fb['away']} <-> {ap['home']} vs {ap['away']}")


unmatched_uel = [fb for fb in fb_list if fb.get('tournament') in ['UEL', 'ECL'] and not any(m[0] == fb for m in matched)]
print(f"\nUnmatched UEL/ECL ({len(unmatched_uel)}):")
for u in unmatched_uel:
    print(f"  FB: '{u['home']} vs {u['away']}'")
