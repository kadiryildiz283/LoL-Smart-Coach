from lcu_driver import Connector
from PyQt6.QtCore import QThread, pyqtSignal
import asyncio
import json
import os
import sys

class LCUWorker(QThread):
    connection_status = pyqtSignal(str)     # Örn: "Bağlandı", "Aranıyor..."
    champ_select_update = pyqtSignal(dict)  # Seçim ekranı verilerini GUI'ye taşır

    def __init__(self):
        super().__init__()
        self.loop = None
        self.connector = None 
        self.id_map = {}
        # Sınıf başlatılırken haritayı yüklemeyi dene
        self.load_id_map()

    def get_resource_path(self, relative_path):
        """
        Windows 11 ve PyInstaller uyumlu dosya yolu bulucu.
        Scriptin çalıştırıldığı yeri değil, dosyanın fiziksel konumunu baz alır.
        """
        try:
            # 1. Eğer .exe haline getirilmişse (PyInstaller temp klasörü)
            base_path = sys._MEIPASS
        except AttributeError:
            # 2. Eğer normal .py olarak çalışıyorsa (Dosyanın bulunduğu klasör)
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        return os.path.join(base_path, relative_path)

    def load_id_map(self):
        """champion_id_map.json dosyasını yükler."""
        # 'data' klasörü içindeki dosyayı hedefler
        target_path = self.get_resource_path(os.path.join("data", "champion_id_map.json"))
        
        # Geliştirme ortamı hatalarına karşı alternatif yollar
        possible_paths = [
            target_path,
            os.path.join("data", "champion_id_map.json"),
            "champion_id_map.json"
        ]

        found = False
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        self.id_map = json.load(f)
                    
                    print(f"✅ ID Map Başarıyla Yüklendi: {len(self.id_map)} şampiyon.")
                    found = True
                    break
                except Exception as e:
                    print(f"⚠️ Dosya bulundu ama okunamadı ({path}): {e}")

        if not found:
            print(f"❌ KRİTİK HATA: 'champion_id_map.json' bulunamadı!")
            print(f"🔍 Aranan (Base) yol: {target_path}")
            # Boş da olsa hata vermemesi için initialize et
            self.id_map = {}

    def get_champ_name(self, champ_id):
        """Verilen ID'nin şampiyon ismini döndürür."""
        if champ_id == 0:
            return "Picking..."
            
        # JSON anahtarları string olduğu için çeviriyoruz
        name = self.id_map.get(str(champ_id))
        
        if name:
            return name
        else:
            if len(self.id_map) > 0:
                print(f"⚠️ Bilinmeyen ID: {champ_id}")
            return "Unknown"

    def normalize_role(self, role_str):
        """Client'tan gelen ham rol isimlerini okunabilir hale getirir."""
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
        print("🔌 LCU Bağlantısı sağlandı.")
        
    async def on_disconnect(self, connection):
        self.connection_status.emit("❌ Bağlantı Koptu. Client bekleniyor...")
        print("🔌 LCU Bağlantısı koptu.")

    async def on_champ_select(self, connection, event):
        """Şampiyon seçim ekranı verilerini işler."""
        data = event.data
        
        my_team = []
        enemy_team = []
        my_role = "Unknown"
        
        # Yerel oyuncunun hücre ID'sini al (kendi rolümüzü bulmak için)
        local_cell_id = data.get('localPlayerCellId', -1)

        # --- Mavi Takım (Bizim Takım) ---
        for member in data.get('myTeam', []):
            champ_id = member.get('championId', 0)
            name = self.get_champ_name(champ_id)
            my_team.append(name)
            
            # Eğer bu oyuncu bensem, rolümü kaydet
            if member.get('cellId') == local_cell_id:
                raw_role = member.get('assignedPosition', '')
                my_role = self.normalize_role(raw_role)

        # --- Kırmızı Takım (Rakip) ---
        for member in data.get('theirTeam', []):
            champ_id = member.get('championId', 0)
            name = self.get_champ_name(champ_id)
            enemy_team.append(name)

        # Arayüze gönderilecek paket
        info = {
            "my_team": my_team,
            "enemy_team": enemy_team,
            "my_role": my_role,
            "phase": data.get('timer', {}).get('phase', 'Unknown')
        }
        
        self.champ_select_update.emit(info)

    def stop(self):
        """Thread'i ve event loop'u güvenli şekilde durdurur (RESET sızıntı düzeltmesi)."""
        self._stopping = True
        loop = self.loop
        connector = self.connector
        if loop is not None and loop.is_running():
            async def _shutdown():
                try:
                    if connector is not None:
                        await connector.stop()
                except Exception:
                    pass
                loop.stop()
            try:
                import asyncio as _aio
                _aio.run_coroutine_threadsafe(_shutdown(), loop)
            except Exception:
                loop.call_soon_threadsafe(loop.stop)
        self.wait(3000)

    def run(self):
        """Thread başladığında çalışacak ana döngü."""
        self._stopping = False
        try:
            # Her thread için taze bir event loop şarttır
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            self.connector = Connector()

            # --- Event Tanımlamaları ---
            @self.connector.ready
            async def connect(connection):
                await self.on_connect(connection)

            @self.connector.close
            async def disconnect(connection):
                await self.on_disconnect(connection)

            # Sadece şampiyon seçimi güncellemesini dinle
            @self.connector.ws.register('/lol-champ-select/v1/session', event_types=('UPDATE',))
            async def champ_select(connection, event):
                await self.on_champ_select(connection, event)

            # Başlat
            self.connector.start()
            self.loop.run_forever()
            
        except Exception as e:
            err_msg = f"LCU Hatası: {str(e)}"
            print(err_msg)
            self.connection_status.emit(err_msg)