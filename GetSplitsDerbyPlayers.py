import json
import requests
import time
import os
import re
import unicodedata
import urllib.parse

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

def get_player_id(derby_name, year, year_rosters):
    """Finds a player's ID from the cached year roster."""
    players = year_rosters.get(year, [])
    target = normalize_name(derby_name)
    
    # 1. Try exact match
    for p in players:
        api_name = p.get("fullName", "")
        api_normalized = normalize_name(api_name)
        
        if target == api_normalized:
            # Ensure it's not a pitcher (Home Run Derby is for position players)
            pos = p.get("primaryPosition", {}).get("abbreviation", "")
            if pos != "P":
                return p["id"], api_name
                
    # 2. Fallback: partial match (e.g. "Vladimir Guerrero" matching "Vladimir Guerrero Jr.")
    for p in players:
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

def main():
    input_file = 'contestants.json'
    output_file = 'derby_splits.json'
    
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        derby_data = json.load(f)

    # Step 1: Cache rosters for all unique years to avoid thousands of API calls
    unique_years = set(y['year'] for y in derby_data['contestants_by_year'] if y['contestants'])
    year_rosters = {}
    
    print(f"Fetching MLB rosters for {len(unique_years)} unique seasons...")
    for year in sorted(list(unique_years)):
        url = f"https://statsapi.mlb.com/api/v1/sports/1/players?season={year}&fields=people,id,fullName,nameFirstLast,nameSuffix,primaryPosition,abbreviation"
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                year_rosters[year] = r.json().get("people", [])
                print(f"  [+] Loaded {len(year_rosters[year])} players for {year}")
            else:
                print(f"  [-] Failed to load roster for {year}. Status: {r.status_code}")
                year_rosters[year] = []
        except Exception as e:
            print(f"  [-] Error fetching roster for {year}: {e}")
            year_rosters[year] = []
        time.sleep(0.2) # Be polite to the API

    # Step 2: Process each contestant
    results = []
    total_players = sum(len(year_data['contestants']) for year_data in derby_data['contestants_by_year'])
    processed = 0

    print(f"\nStarting to process {total_players} derby appearances...")
    print("Note: Pre-1990s data might be sparse in the API, but modern data will be highly detailed.\n")

    for year_data in derby_data['contestants_by_year']:
        year = year_data['year']
        contestants = year_data['contestants']
        
        for player_name in contestants:
            processed += 1
            print(f"[{processed}/{total_players}] Processing {player_name} ({year})...")
            
            player_id, api_name = get_player_id(player_name, year, year_rosters)
            
            player_record = {
                "year": year,
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
                first_half = get_half_stats(player_id, year, 'preas')
                time.sleep(0.2)
                second_half = get_half_stats(player_id, year, 'posas')
                
                if first_half or second_half:
                    player_record["1st_half"] = first_half
                    player_record["2nd_half"] = second_half
                else:
                    player_record["status"] = "No split data available for this season"
            else:
                player_record["status"] = "Player not found in MLB API"
                
            results.append(player_record)
            
            # Save progress incrementally in case the script is interrupted
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=4)

    print(f"\nDone! Data successfully exported to {output_file}")

if __name__ == "__main__":
    main()