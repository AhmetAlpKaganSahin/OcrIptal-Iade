# ocr_processor.py
import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image
import pdfplumber
import cv2
import numpy as np
import re


class OCRProcessor:
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.processor = None
        self.model = None
        self.tesseract_available = False
        self.load_models()

    def load_models(self):
        """OCR modellerini yükle"""
        print("OCR modelleri yükleniyor...")

        # 1. TrOCR yükle
        try:
            model_name = "microsoft/trocr-base-printed"
            print(f"TrOCR yükleniyor: {model_name}")

            self.processor = TrOCRProcessor.from_pretrained(model_name)
            self.model = VisionEncoderDecoderModel.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()

            print(f"✓ TrOCR başarıyla yüklendi ({self.device})")

        except Exception as e:
            print(f"✗ TrOCR yüklenemedi: {e}")
            self.model = None

        # 2. Tesseract kontrol et
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            # Test et
            test_image = Image.new('RGB', (100, 30), color='white')
            pytesseract.image_to_string(test_image)
            self.tesseract_available = True
            print("✓ Tesseract hazır")
        except:
            print("✗ Tesseract bulunamadı")

    def preprocess_image(self, image):
        """Basit ve etkili ön işleme"""
        # Numpy array'e çevir
        img = np.array(image)

        # Griye çevir
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img

        # Boyut kontrolü - çok küçükse büyüt
        h, w = gray.shape
        if h < 50 or w < 150:
            scale = max(2, 50 / h, 150 / w)
            new_h, new_w = int(h * scale), int(w * scale)
            gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

        # Gürültü azalt
        denoised = cv2.medianBlur(gray, 3)

        # Kontrast artır
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        # Binary threshold
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return Image.fromarray(binary)

    def extract_text(self, image):
        """Ana OCR fonksiyonu"""
        if not image:
            return ""

        results = []

        # 1. TrOCR ile dene
        if self.model and self.processor:
            try:
                # Orijinal resimle
                result1 = self._trocr_extract(image)
                if result1.strip():
                    results.append(result1)

                # Ön işlemli resimle
                processed = self.preprocess_image(image)
                result2 = self._trocr_extract(processed)
                if result2.strip():
                    results.append(result2)

            except Exception as e:
                print(f"TrOCR hatası: {e}")

        # 2. Tesseract ile dene
        if self.tesseract_available:
            try:
                result3 = self._tesseract_extract(image)
                if result3.strip():
                    results.append(result3)
            except Exception as e:
                print(f"Tesseract hatası: {e}")

        # En iyi sonucu seç
        if not results:
            return ""

        return self._choose_best_result(results)

    def _trocr_extract(self, image):
        """TrOCR ile metin çıkar"""
        # RGB'ye çevir
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Boyut kontrolü
        if image.size[0] * image.size[1] > 1000000:
            image.thumbnail((1000, 1000), Image.Resampling.LANCZOS)

        # TrOCR işlemi
        pixel_values = self.processor(image, return_tensors="pt").pixel_values.to(self.device)

        with torch.no_grad():
            generated_ids = self.model.generate(
                pixel_values,
                max_length=100,
                num_beams=4,
                early_stopping=True
            )

        text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return self._clean_text(text)

    def _tesseract_extract(self, image):
        """Tesseract ile metin çıkar"""
        import pytesseract

        # En iyi konfigürasyonu seç
        configs = [
            r'--oem 3 --psm 8 -l tur',  # Tek kelime
            r'--oem 3 --psm 7 -l tur',  # Tek satır
            r'--oem 3 --psm 6 -l tur',  # Düzgün blok
        ]

        best_text = ""
        best_conf = 0

        for config in configs:
            try:
                text = pytesseract.image_to_string(image, config=config)
                # Basit güven hesabı
                conf = len([c for c in text if c.isalnum()]) / max(len(text), 1)

                if conf > best_conf and text.strip():
                    best_text = text
                    best_conf = conf
            except:
                continue

        return self._clean_text(best_text)

    def _clean_text(self, text):
        """Metni temizle"""
        if not text:
            return ""

        # Temel temizlik
        text = text.strip()

        # Gereksiz karakterleri kaldır
        text = re.sub(r'[^\w\säöüçğışÄÖÜÇĞIŞ\d\.\,\-\+\(\)\/\:]', ' ', text)

        # Çoklu boşlukları tek boşluk yap
        text = re.sub(r'\s+', ' ', text)

        # Türkçe karakter düzeltmeleri
        replacements = {
            'ı': 'ı', 'I': 'İ', 'ş': 'ş', 'Ş': 'Ş',
            'ğ': 'ğ', 'Ğ': 'Ğ', 'ü': 'ü', 'Ü': 'Ü',
            'ö': 'ö', 'Ö': 'Ö', 'ç': 'ç', 'Ç': 'Ç'
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text.strip()

    def _choose_best_result(self, results):
        """Sonuçlar arasından en iyisini seç"""
        if len(results) == 1:
            return results[0]

        # Basit skorlama
        scores = []
        for text in results:
            score = 0

            # Uzunluk skoru
            if 2 <= len(text.strip()) <= 50:
                score += 10

            # Türkçe karakter bonusu
            if any(c in text for c in 'çğıöşüÇĞIÖŞÜ'):
                score += 5

            # Sayı içeriği
            if any(c.isdigit() for c in text):
                score += 5

            # Temizlik skoru
            clean_ratio = len(re.sub(r'[^\w\s]', '', text)) / max(len(text), 1)
            score += clean_ratio * 5

            scores.append(score)

        # En yüksek skora sahip olanı döndür
        best_idx = scores.index(max(scores))
        return results[best_idx]

    def convert_pdf_to_image(self, pdf_path, page=0):
        """PDF'yi resme dönüştür"""
        try:
            # Önce pdfplumber dene
            with pdfplumber.open(pdf_path) as pdf:
                if page < len(pdf.pages):
                    page_obj = pdf.pages[page]
                    im = page_obj.within_bbox((0, 0, page_obj.width, page_obj.height)).to_image()
                    return im.original
        except:
            pass

        try:
            # pdf2image ile dene
            from pdf2image import convert_from_path
            images = convert_from_path(pdf_path, first_page=page + 1, last_page=page + 1, dpi=300)
            return images[0] if images else None
        except ImportError:
            print("pdf2image bulunamadı. pip install pdf2image")
            return None
        except Exception as e:
            print(f"PDF dönüştürme hatası: {e}")
            return None

    def batch_extract(self, image, coordinates_dict):
        """Birden fazla alan için toplu OCR"""
        results = {}

        for field_name, coords in coordinates_dict.items():
            if coords:
                try:
                    x1, y1, x2, y2 = coords
                    cropped = image.crop((x1, y1, x2, y2))
                    text = self.extract_text(cropped)
                    results[field_name] = text
                except Exception as e:
                    print(f"{field_name} alanı işlenirken hata: {e}")
                    results[field_name] = ""

        return results