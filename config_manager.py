# config_manager.py
import json
import os
from typing import Dict, List, Optional


class ConfigManager:
    def __init__(self, config_file="form_config.json"):
        self.config_file = config_file
        self.default_fields = [
            "Ad Soyad",
            "Cep Telefonu Numarası",
            "E-Posta Adresi",
            "PARAM Hesap & Kart Numarası",
            "Kart üzerindeki Ad Soyad",
            "Kart Numarasının Son 4 Hanesi",
            "Kartın Ait Olduğu Banka",
            "IBAN Numarası",
            "IBAN Sahibinin Ad Soyadı",
            "İşlem Tarihi",
            "İşlem Tutarı",
            "İade Edilecek Tutar",
            "İptal & İade Nedeni",
            "Tarih"
        ]

    def create_default_config(self) -> Dict:
        """Varsayılan konfigürasyon oluştur"""
        config = {
            "form_fields": {},
            "ocr_settings": {
                "model_type": "trocr",
                "language": "tur+eng",
                "preprocess": True,
                "confidence_threshold": 0.5
            },
            "output_settings": {
                "format": "json",
                "encoding": "utf-8",
                "pretty_print": True
            }
        }

        # Her alan için boş koordinat
        for field in self.default_fields:
            config["form_fields"][field] = {
                "coordinates": None,
                "required": True,
                "data_type": "text"
            }

        return config

    def load_config(self) -> Dict:
        """Konfigürasyon dosyasını yükle"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Konfigürasyon yükleme hatası: {e}")
                return self.create_default_config()
        else:
            return self.create_default_config()

    def save_config(self, config: Dict) -> bool:
        """Konfigürasyonu dosyaya kaydet"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except IOError as e:
            print(f"Konfigürasyon kaydetme hatası: {e}")
            return False

    def update_field_coordinates(self, field_name: str, coordinates: List[int]) -> bool:
        """Alan koordinatlarını güncelle"""
        config = self.load_config()

        if field_name in config["form_fields"]:
            config["form_fields"][field_name]["coordinates"] = coordinates
            return self.save_config(config)
        return False

    def get_field_coordinates(self, field_name: str) -> Optional[List[int]]:
        """Alan koordinatlarını al"""
        config = self.load_config()

        if field_name in config["form_fields"]:
            return config["form_fields"][field_name]["coordinates"]
        return None

    def get_all_coordinates(self) -> Dict[str, List[int]]:
        """Tüm koordinatları al"""
        config = self.load_config()
        coordinates = {}

        for field_name, field_config in config["form_fields"].items():
            if field_config["coordinates"]:
                coordinates[field_name] = field_config["coordinates"]

        return coordinates

    def add_custom_field(self, field_name: str, required: bool = True, data_type: str = "text") -> bool:
        """Özel alan ekle"""
        config = self.load_config()

        config["form_fields"][field_name] = {
            "coordinates": None,
            "required": required,
            "data_type": data_type
        }

        return self.save_config(config)

    def remove_field(self, field_name: str) -> bool:
        """Alan sil"""
        config = self.load_config()

        if field_name in config["form_fields"]:
            del config["form_fields"][field_name]
            return self.save_config(config)
        return False

    def get_ocr_settings(self) -> Dict:
        """OCR ayarlarını al"""
        config = self.load_config()
        return config.get("ocr_settings", {})

    def update_ocr_settings(self, settings: Dict) -> bool:
        """OCR ayarlarını güncelle"""
        config = self.load_config()
        config["ocr_settings"].update(settings)
        return self.save_config(config)

    def export_template(self, template_name: str, coordinates: Dict[str, List[int]]) -> bool:
        """Koordinat şablonu dışa aktar"""
        template_file = f"{template_name}_template.json"
        template_data = {
            "template_name": template_name,
            "created_date": "",
            "form_fields": {}
        }

        import datetime
        template_data["created_date"] = datetime.datetime.now().isoformat()

        for field_name, coords in coordinates.items():
            template_data["form_fields"][field_name] = {
                "coordinates": coords,
                "required": True,
                "data_type": "text"
            }

        try:
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, ensure_ascii=False, indent=2)
            return True
        except IOError as e:
            print(f"Şablon dışa aktarma hatası: {e}")
            return False

    def import_template(self, template_file: str) -> bool:
        """Şablon içe aktar"""
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                template_data = json.load(f)

            config = self.load_config()

            # Şablondaki alanları mevcut konfigürasyona ekle
            for field_name, field_config in template_data["form_fields"].items():
                config["form_fields"][field_name] = field_config

            return self.save_config(config)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Şablon içe aktarma hatası: {e}")
            return False