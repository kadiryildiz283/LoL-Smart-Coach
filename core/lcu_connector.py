from lcu_driver import Connector
from PyQt6.QtCore import QThread, pyqtSignal
import asyncio
import json
import os

class LCUWorker(QThread):
    # Arayüze sinyal göndermek için (Signal-Slot yapısı)
    connection_status = pyqtSignal(str) # "Bağlandı", "Aranıyor..."
    champ_select_update = pyqtSignal(dict) # Seçim ekranı verisi

    def __init__(self):
        super().__init__()
        self.loop = None
        self.connector = None # Connector'ı burada oluşturmuyoruz!
        self.id_map = {}
        self.load_id_map()

    def load_id_map(self):
        # ID -> İsim çeviricisi (157 -> Yasuo)
        # Exe içinde çalışırken data yolunu bulabilmesi için basit kontrol
        path = os.path.join("data", "champion_id_map.json")
        if not os.path.exists(path):
            # Belki bir üst klasördedir (Geliştirme ortamı vs Exe farkı)
            path = os.path.join("..", "data", "champion_id_map.json")
            
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.id_map = json.load(f)

    def get_champ_name(self, champ_id):
        return self.id_map.get(str(champ_id), "Unknown")

    def normalize_role(self, role_str):
        mapping = {
            "top": "Top",
            "jungle": "Jungle",
            "middle": "Mid",
            "bottom": "ADC",
            "utility": "Support"
        }
        return mapping.get(role_str, "Unknown")

    # --- LCU OLAYLARI (Async) ---
    async def on_connect(self, connection):
        self.connection_status.emit("✅ Client'a Bağlandı!")
        
    async def on_disconnect(self, connection):
        self.connection_status.emit("❌ Bağlantı Koptu. Client bekleniyor...")

    async def on_champ_select(self, connection, event):
        data = event.data
        
        my_team = []
        enemy_team = []
        my_role = "Unknown"
        
        local_cell_id = data.get('localPlayerCellId', -1)

        # Mavi Takım / Benim Takımım
        for member in data.get('myTeam', []):
            champ_id = member.get('championId')
            name = self.get_champ_name(champ_id) if champ_id else "Picking..."
            my_team.append(name)
            
            if member.get('cellId') == local_cell_id:
                my_role = self.normalize_role(member.get('assignedPosition', ''))

        # Kırmızı Takım / Rakip Takım
        for member in data.get('theirTeam', []):
            champ_id = member.get('championId')
            name = self.get_champ_name(champ_id) if champ_id else "Picking..."
            enemy_team.append(name)

        # Paketi hazırla ve gönder
        info = {
            "my_team": my_team,
            "enemy_team": enemy_team,
            "my_role": my_role,
            "phase": data.get('timer', {}).get('phase', 'Unknown')
        }
        self.champ_select_update.emit(info)

    def run(self):
        """Thread başladığında çalışacak kısım"""
        try:
            # 1. Bu thread için YENİ bir Event Loop oluştur
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            # 2. Connector'ı BURADA ve ŞİMDİ oluştur (Loop hazır olduktan sonra)
            self.connector = Connector()

            # 3. Olayları Bağla
            @self.connector.ready
            async def connect(connection):
                await self.on_connect(connection)

            @self.connector.close
            async def disconnect(connection):
                await self.on_disconnect(connection)

            @self.connector.ws.register('/lol-champ-select/v1/session', event_types=('UPDATE',))
            async def champ_select(connection, event):
                await self.on_champ_select(connection, event)

            # 4. Başlat
            self.connector.start()
            self.loop.run_forever()
            
        except Exception as e:
            # Hata olursa sinyal gönder (Main.py loguna düşer)
            self.connection_status.emit(f"LCU Hatası: {str(e)}")