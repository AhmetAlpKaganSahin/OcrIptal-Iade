# ensemble_ocr.py
import easyocr
from ocr_processor import OCRProcessor
import cv2
import numpy as np
from PIL import Image
import difflib


class EnsembleOCR:
    """Birden fazla OCR motorunu birleştirerek daha iyi sonuç elde etme"""

    def __init__(self):
        self.trocr_processor = OCRProcessor()
        self.easyocr_reader = None
        self.load_easyocr()

    def load_easyocr(self):
        """EasyOCR'ı yükle"""
        try:
            # Türkçe ve İngilizce desteği
            self.easyocr_reader = easyocr.Reader(['tr', 'en'], gpu=True)
            print("EasyOCR başarıyla yüklendi")
        except Exception as e:
            print(f"EasyOCR yüklenemedi: {e}")
            try:
                # GPU olmadan dene
                self.easyocr_reader = easyocr.Reader(['tr', 'en'], gpu=False)
                print("EasyOCR CPU modunda yüklendi")
            except Exception as e2:
                print(f"EasyOCR hiç yüklenemedi: {e2}")

    def extract_text_ensemble(self, image):
        """Birden fazla OCR motoru kullanarak en iyi sonucu seç"""
        results = {}

        # 1. TrOCR sonucu
        try:
            trocr_result = self.trocr_processor.extract_text(image)
            results['trocr'] = trocr_result
            print(f"TrOCR: {trocr_result[:50]}...")
        except Exception as e:
            print(f"TrOCR hatası: {e}")
            results['trocr'] = ""

        # 2. EasyOCR sonucu
        if self.easyocr_reader:
            try:
                # PIL'i OpenCV formatına çevir
                img_array = np.array(image)
                if len(img_array.shape) == 3:
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

                easyocr_results = self.easyocr_reader.readtext(img_array, detail=0)
                easyocr_text = ' '.join(easyocr_results)
                results['easyocr'] = easyocr_text
                print(f"EasyOCR: {easyocr_text[:50]}...")
            except Exception as e:
                print(f"EasyOCR hatası: {e}")
                results['easyocr'] = ""

        # 3. Tesseract sonucu (fallback olarak)
        try:
            tesseract_result = self.trocr_processor.extract_with_tesseract(image)
            results['tesseract'] = tesseract_result
            print(f"Tesseract: {tesseract_result[:50]}...")
        except Exception as e:
            print(f"Tesseract hatası: {e}")
            results['tesseract'] = ""

        # En iyi sonucu seç
        best_result = self.choose_best_result(results)
        return best_result

    def choose_best_result(self, results):
        """Sonuçlar arasından en iyisini seç"""
        # Boş sonuçları filtrele
        valid_results = {k: v for k, v in results.items() if v.strip()}

        if not valid_results:
            return ""

        # Tek sonuç varsa onu döndür
        if len(valid_results) == 1:
            return list(valid_results.values())[0]

        # Çoklu sonuç varsa scoring yap
        scores = {}

        for method, text in valid_results.items():
            score = 0

            # Uzunluk skoru (çok kısa veya çok uzun metinler cezalandırılır)
            length = len(text.strip())
            if 3 <= length <= 100:
                score += 10
            elif length > 100:
                score += 5

            # Türkçe karakter varlığı
            turkish_chars = 'çğıöşüÇĞIÖŞÜ'
            if any(char in text for char in turkish_chars):
                score += 15

            # Sayı varlığı (form alanları için önemli)
            if any(char.isdigit() for char in text):
                score += 10

            # Özel karakterlerin azlığı (temiz metin için)
            special_chars = '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'
            special_ratio = sum(1 for char in text if char in special_chars) / len(text)
            if special_ratio < 0.1:
                score += 10

            # Kelime yapısı (anlamlı kelimeler)
            words = text.split()
            if len(words) >= 1:
                score += 5

            scores[method] = score

        # En yüksek skora sahip metni seç
        best_method = max(scores.keys(), key=lambda x: scores[x])
        best_text = valid_results[best_method]

        print(f"En iyi sonuç: {best_method} (skor: {scores[best_method]})")
        return best_text

    def extract_with_confidence(self, image):
        """Güven skoruyla birlikte metin çıkar"""
        if self.easyocr_reader:
            try:
                img_array = np.array(image)
                if len(img_array.shape) == 3:
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

                # Detaylı sonuç al (koordinat + güven skoru)
                results = self.easyocr_reader.readtext(img_array, detail=True)

                if results:
                    # En yüksek güven skoruna sahip metni al
                    best_result = max(results, key=lambda x: x[2])
                    text = best_result[1]
                    confidence = best_result[2]

                    return text, confidence

            except Exception as e:
                print(f"EasyOCR confidence hatası: {e}")

        # Fallback
        text = self.trocr_processor.extract_text(image)
        return text, 0.5