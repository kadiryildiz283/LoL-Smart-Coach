import json
import os

# Bu script çalıştığında expert_data.txt dosyasını okur
INPUT_TEXT_FILE = "expert_data.txt"
OUTPUT_JSON_FILE = "data/expert_knowledge.json" # Data klasörüne kaydetsin

def parse_expert_data(text):
    data = []
    current_champ = {}
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        if ":" in line and not any(line.startswith(x) for x in ["Rol", "Counter", "Anti-Counter"]):
            if current_champ:
                data.append(current_champ)
            name_part = line.split(":")[0].strip().split("(")[0].strip()
            current_champ = {
                "name": name_part,
                "role_desc": "",
                "hard_counters": [],
                "easy_matchups": []
            }
        elif line.startswith("Rol:"):
            if current_champ:
                current_champ["role_desc"] = line.replace("Rol:", "").strip()
        elif line.startswith("Counter (Onu Yenen):"):
            if current_champ:
                content = line.replace("Counter (Onu Yenen):", "").strip().rstrip(".")
                champs = [c.strip() for c in content.split(",") if c.strip()]
                current_champ["hard_counters"] = champs
        elif line.startswith("Anti-Counter (Onun Yendiği):"):
            if current_champ:
                content = line.replace("Anti-Counter (Onun Yendiği):", "").strip().rstrip(".")
                champs = [c.strip() for c in content.split(",") if c.strip()]
                current_champ["easy_matchups"] = champs

    if current_champ:
        data.append(current_champ)
    return data

def main():
    # Data klasörü yoksa oluştur
    if not os.path.exists("data"):
        os.makedirs("data")

    if not os.path.exists(INPUT_TEXT_FILE):
        print(f"⚠️ HATA: '{INPUT_TEXT_FILE}' bulunamadı! Lütfen uzun metni bu isimle kaydet.")
        return

    with open(INPUT_TEXT_FILE, "r", encoding="utf-8") as f:
        text_content = f.read()

    parsed_data = parse_expert_data(text_content)
    
    with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(parsed_data, f, indent=4, ensure_ascii=False)
        
    print(f"✅ Uzman verisi '{OUTPUT_JSON_FILE}' dosyasına dönüştürüldü.")

if __name__ == "__main__":
    main()
