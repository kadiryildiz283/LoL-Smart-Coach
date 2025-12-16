from lcu_driver import Connector
from PyQt6.QtCore import QThread, pyqtSignal
import asyncio
import json
import os

class LCUWorker(QThread):
    connection_status = pyqtSignal(str)
    champ_select_update = pyqtSignal(dict) 

    def __init__(self):
        super().__init__()
        self.connector = Connector()
        self.loop = None
        self.id_map = {}
        self.load_id_map()

    def load_id_map(self):
        path = os.path.join("data", "champion_id_map.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.id_map = json.load(f)

    def get_champ_name(self, champ_id):
        return self.id_map.get(str(champ_id), "Unknown")

    # Rol isimlerini düzeltme (Client 'utility' diyor, biz 'Support' diyoruz)
    def normalize_role(self, role_str):
        mapping = {
            "top": "Top",
            "jungle": "Jungle",
            "middle": "Mid",
            "bottom": "AD Carry",
            "utility": "Support"
        }
        return mapping.get(role_str, "Unknown")

    async def on_connect(self, connection):
        self.connection_status.emit("✅ Client Bağlandı")
        
    async def on_disconnect(self, connection):
        self.connection_status.emit("❌ Client Bekleniyor...")

    async def on_champ_select(self, connection, event):
        data = event.data
        
        my_team = []
        enemy_team = []
        my_role = "Unknown"

        # Kendi takımımı ve rolümü bul
        local_cell_id = data.get('localPlayerCellId', -1)

        for member in data.get('myTeam', []):
            champ_id = member.get('championId')
            
            # Şampiyon ismini al
            champ_name = "Picking..."
            if champ_id and champ_id != 0:
                champ_name = self.get_champ_name(champ_id)
            
            my_team.append(champ_name)

            # Eğer bu oyuncu bensem, rolümü kaydet
            if member.get('cellId') == local_cell_id:
                raw_role = member.get('assignedPosition', '')
                my_role = self.normalize_role(raw_role)

        # Rakip takımı bul
        for member in data.get('theirTeam', []):
            champ_id = member.get('championId')
            champ_name = "Picking..."
            if champ_id and champ_id != 0:
                champ_name = self.get_champ_name(champ_id)
            enemy_team.append(champ_name)

        # Arayüze gönder
        info = {
            "my_team": my_team,
            "enemy_team": enemy_team,
            "my_role": my_role, # YENİ: Otomatik rol
            "phase": data.get('timer', {}).get('phase', 'Unknown')
        }
        self.champ_select_update.emit(info)

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        @self.connector.ready
        async def connect(connection): await self.on_connect(connection)

        @self.connector.close
        async def disconnect(connection): await self.on_disconnect(connection)

        @self.connector.ws.register('/lol-champ-select/v1/session', event_types=('UPDATE',))
        async def champ_select(connection, event): await self.on_champ_select(connection, event)

        self.connector.start()
