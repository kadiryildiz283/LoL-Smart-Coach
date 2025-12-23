import json
import os
import glob
import re

# --- DOSYA YOLLARI ---
# Script core/ klasöründe değil, ana dizinde çalışıyor varsayıyoruz
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
MAIN_DATA_FILE = os.path.join(DATA_DIR, "tum_sampiyonlar_verisi_full.json")
BACKUP_FILE = os.path.join(DATA_DIR, "tum_sampiyonlar_verisi_full_BACKUP.json")

def clean_champion_name(name):
    """ 'Renekton (Mid)' -> 'Renekton' """
    clean = re.sub(r'\s*\(.*?\)', '', name)
    return clean.strip()

def main():
    print("🚀 Merging Process Started (Output JSONs -> Main Database)...")
    
    if not os.path.exists(MAIN_DATA_FILE):
        print(f"❌ Main data file not found: {MAIN_DATA_FILE}")
        return

    if not os.path.exists(OUTPUT_DIR):
        print(f"❌ Output directory not found: {OUTPUT_DIR}")
        return

    # 1. Load Main Data
    with open(MAIN_DATA_FILE, "r", encoding="utf-8") as f:
        main_data = json.load(f)
        
    main_lookup = {d['name'].lower(): d for d in main_data}
    print(f"📊 Loaded {len(main_data)} champions from main database.")

    # 2. Iterate Output Files
    files = glob.glob(os.path.join(OUTPUT_DIR, "*.json"))
    print(f"📂 Found {len(files)} champion analysis files in {OUTPUT_DIR}")

    merged_count = 0
    
    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                analysis = json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading {file_path}: {e}")
            continue

        raw_name = analysis.get("name", "Unknown")
        matchups = analysis.get("matchups", [])
        
        target_champ = main_lookup.get(raw_name.lower())
        
        if not target_champ:
            # Try cleaning name/title case
            target_champ = main_lookup.get(raw_name.lower().strip())
        
        if not target_champ:
            print(f"⚠️ Champion not found in main DB: {raw_name}")
            continue

        # LOGIC:
        # Score < 5.0 -> Hard Counter (Enemy beats Champion)
        # Score > 5.0 -> Easy Matchup (Champion beats Enemy)
        # Score close to 5.0 -> Neutral (Ignored for lists)
        
        hard_counters = []
        easy_matchups = []
        
        for m in matchups:
            enemy = m.get("enemy", "")
            score = m.get("score", 5.0)
            
            # Skip invalid
            if not enemy: continue
            
            # Thresholds
            if score < 5.0:
                # Enemy is strong against me
                hard_counters.append(enemy)
            elif score > 6.0: # Using 6.0 to be safe for "easy" matchups as user said > 5 but let's be strict for "Expert" lists
                 # I beat Enemy
                 easy_matchups.append(enemy)
        
        # Update Main Record
        target_champ['expert_insight'] = {
            "role_description": analysis.get('role_desc', ''),
            "hard_counters": hard_counters,
            "easy_matchups": easy_matchups
        }
        
        merged_count += 1
        # print(f"   Updated {raw_name}: {len(hard_counters)} HC / {len(easy_matchups)} EM")

    # 3. Save
    print("-" * 30)
    print(f"💾 Saving merged data to {MAIN_DATA_FILE}...")
    
    # Backup first
    try:
        if os.path.exists(MAIN_DATA_FILE):
             import shutil
             shutil.copy(MAIN_DATA_FILE, BACKUP_FILE)
    except: pass
    
    with open(MAIN_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(main_data, f, indent=4, ensure_ascii=False)
        
    print(f"🎉 SUCCESSS! {merged_count} champions updated with specific matchup data.")

if __name__ == "__main__":
    main()
