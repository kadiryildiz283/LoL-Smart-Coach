import sys
import os
import shutil
import json

def get_base_path():
    """PyInstaller ve Development ortamı için base path'i döndürür."""
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.abspath(".")

def ensure_data_directory():
    """
    Data klasörünün çalıştırılabilir dosyanın yanında olup olmadığını kontrol eder.
    Eğer yoksa (ilk çalıştırılma veya silinme durumu), iç build'den dışarıya kopyalar.
    Böylece kullanıcı verileri görebilir ve düzenleyebilir.
    """
    # Exe'nin çalıştığı gerçek dizin (veya script'in olduğu yer)
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.abspath(".")

    target_data_dir = os.path.join(application_path, "data")
    
    # Internal data dir (PyInstaller temp klasörü veya proje kökü)
    internal_data_dir = os.path.join(get_base_path(), "data")

    # Eğer hedef dizinde data yoksa
    if not os.path.exists(target_data_dir):
        print(f"⚠️ Data klasörü bulunamadı: {target_data_dir}")
        print("ℹ️ Varsayılan veriler dışarı aktarılıyor...")
        try:
            # Eğer development ortamındaysak ve zaten oradaysak kopyalamaya gerek yok
            if os.path.normpath(target_data_dir) == os.path.normpath(internal_data_dir):
                print("ℹ️ Development ortamı: Zaten yerinde.")
            else:
                shutil.copytree(internal_data_dir, target_data_dir)
                print("✅ Data klasörü başarıyla oluşturuldu.")
        except Exception as e:
            print(f"❌ Data kopyalama hatası: {e}")
    else:
        print(f"✅ Data klasörü mevcut ve KORUNDU: {target_data_dir}")
        print("ℹ️ Mevcut veriler/ayarlar kullanılıyor.")

    # Check for config.json specific persistence (Migrate ai_config.json if needed)
    config_path = os.path.join(target_data_dir, "config.json")
    ai_config_path = os.path.join(target_data_dir, "ai_config.json")
    
    if not os.path.exists(config_path) and os.path.exists(ai_config_path):
        try:
            shutil.copy(ai_config_path, config_path)
            print("✅ config.json oluşturuldu (ai_config.json'dan kopyalandı).")
        except: pass

    return target_data_dir

def get_resource_path(relative_path):
    """
    Dosya yolunu döndürür. Önce kullanıcının düzenleyebileceği 'data' klasörüne bakar.
    """
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
        
    full_path = os.path.join(base_path, relative_path)
    return full_path
