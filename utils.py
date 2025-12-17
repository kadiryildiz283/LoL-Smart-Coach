# utils.py
import sys
import os

def get_base_path():
    """
    Programın çalıştığı ana dizini bulur.
    - .exe ise: .exe dosyasının olduğu klasörü döndürür.
    - .py ise: projenin olduğu klasörü döndürür.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller ile paketlenmiş (.exe) durumunda
        return os.path.dirname(sys.executable)
    else:
        # Normal Python betiği durumunda
        return os.path.abspath(".")

def get_data_path(filename=None):
    """
    data/ klasörünün yolunu döndürür.
    Eğer klasör yoksa OTOMATİK OLUŞTURUR.
    """
    base_path = get_base_path()
    data_dir = os.path.join(base_path, "data")
    
    # Klasör yoksa oluştur
    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir)
            print(f"📁 Data klasörü oluşturuldu: {data_dir}")
        except OSError as e:
            print(f"❌ Data klasörü oluşturulamadı: {e}")

    if filename:
        return os.path.join(data_dir, filename)
    return data_dir
