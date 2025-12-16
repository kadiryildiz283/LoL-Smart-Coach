import requests
import json
import os

def create_id_map():
    # Riot'un en son sürüm numarasını al
    versions = requests.get("https://ddragon.leagueoflegends.com/api/versions.json").json()
    latest = versions[0]
    print(f"Versiyon: {latest}")

    # Şampiyon verisini çek
    url = f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/champion.json"
    data = requests.get(url).json()

    id_map = {}
    for champ_id, champ_data in data['data'].items():
        # Key: ID (Str), Value: Name
        key = champ_data['key']
        name = champ_data['name']
        id_map[key] = name

    # Klasör yoksa oluştur
    if not os.path.exists("data"):
        os.makedirs("data")

    with open("data/champion_id_map.json", "w", encoding="utf-8") as f:
        json.dump(id_map, f, indent=4)
        
    print(f"✅ {len(id_map)} şampiyon ID'si haritalandı.")

if __name__ == "__main__":
    create_id_map()
