# main.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
from PIL import Image, ImageTk
import threading

try:
    from ensemble_ocr import EnsembleOCR

    USE_ENSEMBLE = True
except ImportError:
    from ocr_processor import OCRProcessor

    USE_ENSEMBLE = False
from config_manager import ConfigManager


class OCRFormReader:
    def __init__(self, root):
        self.root = root
        self.root.title("OCR Form Okuyucu")
        self.root.geometry("1200x800")

        if USE_ENSEMBLE:
            self.ocr_processor = EnsembleOCR()
            print("Ensemble OCR aktif - Daha iyi sonuçlar için birden fazla model kullanılıyor")
        else:
            self.ocr_processor = OCRProcessor()
            print("Sadece TrOCR kullanılıyor")

        self.config_manager = ConfigManager()

        self.current_image = None
        self.image_path = None
        self.coordinates = {}
        self.selection_mode = False
        self.start_x = None
        self.start_y = None
        self.current_field = None

        self.setup_ui()
        self.load_default_config()

    def setup_ui(self):
        # Ana frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Sol panel - Kontroller
        control_frame = ttk.LabelFrame(main_frame, text="Kontroller", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))

        # Dosya yükleme
        ttk.Button(control_frame, text="Dosya Yükle", command=self.load_file).grid(row=0, column=0, columnspan=2,
                                                                                   sticky=(tk.W, tk.E), pady=5)

        # Alan seçimi
        ttk.Label(control_frame, text="Form Alanları:").grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(10, 5))

        # Alan listesi
        self.field_listbox = tk.Listbox(control_frame, height=15)
        self.field_listbox.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        self.field_listbox.bind('<<ListboxSelect>>', self.on_field_select)

        # Koordinat girişi
        coord_frame = ttk.Frame(control_frame)
        coord_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        ttk.Label(coord_frame, text="X1:").grid(row=0, column=0)
        self.x1_var = tk.StringVar()
        ttk.Entry(coord_frame, textvariable=self.x1_var, width=8).grid(row=0, column=1, padx=2)

        ttk.Label(coord_frame, text="Y1:").grid(row=0, column=2)
        self.y1_var = tk.StringVar()
        ttk.Entry(coord_frame, textvariable=self.y1_var, width=8).grid(row=0, column=3, padx=2)

        ttk.Label(coord_frame, text="X2:").grid(row=1, column=0)
        self.x2_var = tk.StringVar()
        ttk.Entry(coord_frame, textvariable=self.x2_var, width=8).grid(row=1, column=1, padx=2)

        ttk.Label(coord_frame, text="Y2:").grid(row=1, column=2)
        self.y2_var = tk.StringVar()
        ttk.Entry(coord_frame, textvariable=self.y2_var, width=8).grid(row=1, column=3, padx=2)

        # Koordinat kaydetme
        ttk.Button(control_frame, text="Koordinat Kaydet", command=self.save_coordinates).grid(row=4, column=0,
                                                                                               columnspan=2,
                                                                                               sticky=(tk.W, tk.E),
                                                                                               pady=5)

        # OCR işlemi
        ttk.Button(control_frame, text="OCR İşlemini Başlat", command=self.start_ocr_process).grid(row=5, column=0,
                                                                                                   columnspan=2,
                                                                                                   sticky=(tk.W, tk.E),
                                                                                                   pady=10)

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(control_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        # Durum etiketi
        self.status_var = tk.StringVar(value="Hazır")
        ttk.Label(control_frame, textvariable=self.status_var).grid(row=7, column=0, columnspan=2, pady=5)

        # Sağ panel - Resim görüntüleyici
        image_frame = ttk.LabelFrame(main_frame, text="Resim", padding="10")
        image_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Canvas
        self.canvas = tk.Canvas(image_frame, width=600, height=600, bg="white")
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Scrollbar'lar
        v_scrollbar = ttk.Scrollbar(image_frame, orient="vertical", command=self.canvas.yview)
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.canvas.configure(yscrollcommand=v_scrollbar.set)

        h_scrollbar = ttk.Scrollbar(image_frame, orient="horizontal", command=self.canvas.xview)
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.canvas.configure(xscrollcommand=h_scrollbar.set)

        # Mouse events
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        # Grid ağırlıkları
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        image_frame.columnconfigure(0, weight=1)
        image_frame.rowconfigure(0, weight=1)

    def load_default_config(self):
        """Varsayılan form alanlarını yükle"""
        default_fields = [
            "Ad Soyad", "Cep Telefonu Numarası", "E-Posta Adresi",
            "PARAM Hesap & Kart Numarası", "Kart üzerindeki Ad Soyad",
            "Kart Numarasının Son 4 Hanesi", "Kartın Ait Olduğu Banka",
            "IBAN Numarası", "IBAN Sahibinin Ad Soyadı", "İşlem Tarihi",
            "İşlem Tutarı", "İade Edilecek Tutar", "İptal & İade Nedeni", "Tarih"
        ]

        for field in default_fields:
            self.field_listbox.insert(tk.END, field)
            self.coordinates[field] = None

    def load_file(self):
        """Dosya yükleme"""
        file_types = [
            ("Tüm Desteklenen", "*.jpg;*.jpeg;*.png;*.pdf"),
            ("Resim Dosyaları", "*.jpg;*.jpeg;*.png"),
            ("PDF Dosyaları", "*.pdf")
        ]

        file_path = filedialog.askopenfilename(filetypes=file_types)
        if file_path:
            try:
                self.image_path = file_path
                if file_path.lower().endswith('.pdf'):
                    # PDF'yi resme dönüştür
                    self.current_image = self.ocr_processor.convert_pdf_to_image(file_path)
                else:
                    self.current_image = Image.open(file_path)

                self.display_image()
                self.status_var.set("Dosya yüklendi")

            except Exception as e:
                messagebox.showerror("Hata", f"Dosya yüklenirken hata oluştu: {str(e)}")

    def display_image(self):
        """Resmi canvas'ta göster"""
        if self.current_image:
            # Resmi canvas boyutuna uyacak şekilde ölçekle
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            if canvas_width > 1 and canvas_height > 1:
                img_copy = self.current_image.copy()
                img_copy.thumbnail((canvas_width, canvas_height), Image.Resampling.LANCZOS)

                self.photo = ImageTk.PhotoImage(img_copy)
                self.canvas.delete("all")
                self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))

                # Mevcut koordinatları göster
                self.draw_all_coordinates()

    def on_field_select(self, event):
        """Alan seçildiğinde"""
        selection = self.field_listbox.curselection()
        if selection:
            field_name = self.field_listbox.get(selection[0])
            self.current_field = field_name

            # Mevcut koordinatları göster
            if field_name in self.coordinates and self.coordinates[field_name]:
                coords = self.coordinates[field_name]
                self.x1_var.set(coords[0])
                self.y1_var.set(coords[1])
                self.x2_var.set(coords[2])
                self.y2_var.set(coords[3])
            else:
                self.x1_var.set("")
                self.y1_var.set("")
                self.x2_var.set("")
                self.y2_var.set("")

    def on_canvas_click(self, event):
        """Canvas tıklama"""
        if self.current_field:
            self.start_x = self.canvas.canvasx(event.x)
            self.start_y = self.canvas.canvasy(event.y)
            self.selection_mode = True

    def on_canvas_drag(self, event):
        """Canvas sürükleme"""
        if self.selection_mode:
            current_x = self.canvas.canvasx(event.x)
            current_y = self.canvas.canvasy(event.y)

            # Seçim alanını göster
            self.canvas.delete("selection")
            self.canvas.create_rectangle(
                self.start_x, self.start_y, current_x, current_y,
                outline="red", width=2, tags="selection"
            )

    def on_canvas_release(self, event):
        """Canvas bırakma"""
        if self.selection_mode:
            end_x = self.canvas.canvasx(event.x)
            end_y = self.canvas.canvasy(event.y)

            # Koordinatları kaydet
            x1 = int(min(self.start_x, end_x))
            y1 = int(min(self.start_y, end_y))
            x2 = int(max(self.start_x, end_x))
            y2 = int(max(self.start_y, end_y))

            # Orijinal resim boyutuna göre ölçekle
            if hasattr(self, 'photo'):
                scale_x = self.current_image.width / self.photo.width()
                scale_y = self.current_image.height / self.photo.height()

                x1 = int(x1 * scale_x)
                y1 = int(y1 * scale_y)
                x2 = int(x2 * scale_x)
                y2 = int(y2 * scale_y)

            self.x1_var.set(x1)
            self.y1_var.set(y1)
            self.x2_var.set(x2)
            self.y2_var.set(y2)

            self.selection_mode = False

    def save_coordinates(self):
        """Koordinatları kaydet"""
        if not self.current_field:
            messagebox.showwarning("Uyarı", "Lütfen bir alan seçin")
            return

        try:
            x1 = int(self.x1_var.get())
            y1 = int(self.y1_var.get())
            x2 = int(self.x2_var.get())
            y2 = int(self.y2_var.get())

            self.coordinates[self.current_field] = [x1, y1, x2, y2]
            self.draw_all_coordinates()
            self.status_var.set(f"{self.current_field} koordinatları kaydedildi")

        except ValueError:
            messagebox.showerror("Hata", "Lütfen geçerli koordinat değerleri girin")

    def draw_all_coordinates(self):
        """Tüm koordinatları çiz"""
        if not hasattr(self, 'photo'):
            return

        self.canvas.delete("coordinate_box")

        # Ölçek faktörlerini hesapla
        scale_x = self.photo.width() / self.current_image.width
        scale_y = self.photo.height() / self.current_image.height

        for field_name, coords in self.coordinates.items():
            if coords:
                x1, y1, x2, y2 = coords
                # Canvas koordinatlarına dönüştür
                canvas_x1 = x1 * scale_x
                canvas_y1 = y1 * scale_y
                canvas_x2 = x2 * scale_x
                canvas_y2 = y2 * scale_y

                color = "blue" if field_name == self.current_field else "green"
                self.canvas.create_rectangle(
                    canvas_x1, canvas_y1, canvas_x2, canvas_y2,
                    outline=color, width=2, tags="coordinate_box"
                )

    def start_ocr_process(self):
        """OCR işlemini başlat"""
        if not self.current_image:
            messagebox.showwarning("Uyarı", "Lütfen önce bir dosya yükleyin")
            return

        # Koordinatları kontrol et
        valid_coords = {k: v for k, v in self.coordinates.items() if v is not None}
        if not valid_coords:
            messagebox.showwarning("Uyarı", "Lütfen en az bir alan için koordinat tanımlayın")
            return

        # OCR işlemini thread'de çalıştır
        thread = threading.Thread(target=self.process_ocr, args=(valid_coords,))
        thread.daemon = True
        thread.start()

    def process_ocr(self, coordinates):
        """OCR işlemini gerçekleştir"""
        try:
            self.status_var.set("OCR işlemi başlatılıyor...")
            self.progress_var.set(0)

            results = {}
            total_fields = len(coordinates)

            for i, (field_name, coords) in enumerate(coordinates.items()):
                self.status_var.set(f"İşleniyor: {field_name}")

                # Bölgeyi kırp
                x1, y1, x2, y2 = coords
                cropped_image = self.current_image.crop((x1, y1, x2, y2))

                # OCR uygula - Ensemble kullan
                if USE_ENSEMBLE:
                    text = self.ocr_processor.extract_text_ensemble(cropped_image)
                else:
                    text = self.ocr_processor.extract_text(cropped_image)

                results[field_name] = text.strip()

                # Progress güncelle
                progress = ((i + 1) / total_fields) * 100
                self.progress_var.set(progress)

            # Sonuçları kaydet
            self.save_results(results)
            self.status_var.set("OCR işlemi tamamlandı")

        except Exception as e:
            self.status_var.set("Hata oluştu")
            messagebox.showerror("Hata", f"OCR işleminde hata: {str(e)}")

    def save_results(self, results):
        """Sonuçları JSON dosyasına kaydet"""
        try:
            # Dosya adını oluştur
            if self.image_path:
                base_name = os.path.splitext(os.path.basename(self.image_path))[0]
                output_path = f"{base_name}_ocr_results.json"
            else:
                output_path = "ocr_results.json"

            # JSON dosyasına kaydet
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            messagebox.showinfo("Başarılı", f"Sonuçlar {output_path} dosyasına kaydedildi")

        except Exception as e:
            messagebox.showerror("Hata", f"Sonuçlar kaydedilirken hata: {str(e)}")


def main():
    root = tk.Tk()
    app = OCRFormReader(root)
    root.mainloop()


if __name__ == "__main__":
    main()