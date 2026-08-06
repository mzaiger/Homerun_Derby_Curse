import json
import requests
import time
import os
import re
import unicodedata
import datetime

def normalize_name(name):
    """Normalizes a player's name for robust matching (removes accents, punctuation, Jr/Sr)."""
    if not name: return ""
    name = name.lower()
    # Remove accents (e.g., José -> Jose, Ordóñez -> Ordonez)
    name = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    # Remove punctuation except spaces
    name = re.sub(r'[^\w\s]', '', name)
    # Remove common suffixes
    name = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', name)
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def get_player_id(derby_name, roster):
    """Finds a player's ID from the roster for a single season."""
    target = normalize_name(derby_name)

    # 1. Try exact match
    for p in roster:
        api_name = p.get("fullName", "")
        api_normalized = normalize_name(api_name)

        if target == api_normalized:
            # Ensure it's not a pitcher (Home Run Derby is for position players)
            pos = p.get("primaryPosition", {}).get("abbreviation", "")
            if pos != "P":
                return p["id"], api_name

    # 2. Fallback: partial match (e.g. "Vladimir Guerrero" matching "Vladimir Guerrero Jr.")
    for p in roster:
        api_name = p.get("fullName", "")
        api_normalized = normalize_name(api_name)

        if target in api_normalized or api_normalized in target:
            pos = p.get("primaryPosition", {}).get("abbreviation", "")
            if pos != "P":
                return p["id"], api_name

    return None, None

def get_half_stats(player_id, year, sit_code):
    """Fetches hitting splits for a specific situation code (preas or posas)."""
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=statSplits&group=hitting&season={year}&sitCodes={sit_code}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None

        data = response.json()
        if 'stats' in data and len(data['stats']) > 0:
            splits = data['stats'][0].get('splits', [])
            if splits:
                return splits[0].get('stat', {})
    except Exception as e:
        print(f"[-] Error fetching splits ({sit_code}) for ID {player_id} in {year}: {e}")
    return None

def load_contestants_file():
    """Contestants.json ships with a capital C, but be forgiving about casing."""
    for candidate in ('Contestants.json', 'contestants.json'):
        if os.path.exists(candidate):
            with open(candidate, 'r', encoding='utf-8') as f:
                return json.load(f)
    raise FileNotFoundError("Contestants.json not found.")

def main():
    output_file = 'derby_splits.json'
    current_year = datetime.date.today().year

    derby_data = load_contestants_file()

    # Step 1: Find this year's contestants only
    year_data = next(
        (y for y in derby_data['contestants_by_year'] if y['year'] == current_year and y.get('contestants')),
        None
    )

    if not year_data:
        print(f"No contestants listed for {current_year} yet. Nothing to update.")
        return

    contestants = year_data['contestants']

    # Step 2: Fetch the roster for the current year only
    print(f"Fetching MLB roster for {current_year}...")
    roster_url = f"https://statsapi.mlb.com/api/v1/sports/1/players?season={current_year}&fields=people,id,fullName,nameFirstLast,nameSuffix,primaryPosition,abbreviation"
    roster = []
    try:
        r = requests.get(roster_url, timeout=15)
        if r.status_code == 200:
            roster = r.json().get("people", [])
            print(f"  [+] Loaded {len(roster)} players for {current_year}")
        else:
            print(f"  [-] Failed to load roster for {current_year}. Status: {r.status_code}")
    except Exception as e:
        print(f"  [-] Error fetching roster for {current_year}: {e}")

    # Step 3: Process this year's contestants
    new_results = []
    print(f"\nStarting to process {len(contestants)} derby appearances for {current_year}...\n")

    for i, player_name in enumerate(contestants, start=1):
        print(f"[{i}/{len(contestants)}] Processing {player_name} ({current_year})...")

        player_id, api_name = get_player_id(player_name, roster)

        player_record = {
            "year": current_year,
            "derby_name": player_name,
            "api_name": api_name,
            "player_id": player_id,
            "1st_half": None,
            "2nd_half": None,
            "status": "Success"
        }

        if player_id:
            # preas = Pre All-Star (1st Half), posas = Post All-Star (2nd Half)
            time.sleep(0.2)
            first_half = get_half_stats(player_id, current_year, 'preas')
            time.sleep(0.2)
            second_half = get_half_stats(player_id, current_year, 'posas')

            if first_half or second_half:
                player_record["1st_half"] = first_half
                player_record["2nd_half"] = second_half
            else:
                player_record["status"] = "No split data available for this season"
        else:
            player_record["status"] = "Player not found in MLB API"

        new_results.append(player_record)

    # Step 4: Merge into derby_splits.json, replacing only the current year's entries
    existing_results = []
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            existing_results = json.load(f)

    carried_over = [r for r in existing_results if r.get('year') != current_year]
    merged_results = carried_over + new_results

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged_results, f, indent=4)

    print(f"\nDone! Updated {current_year} data ({len(new_results)} players) in {output_file}")

if __name__ == "__main__":
    main()
