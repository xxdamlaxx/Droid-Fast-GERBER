#!/usr/bin/env python3
"""
Gerber to PNG Converter - GUI v4.0
----------------------------------
Referans katman desteği ile doğru hizalama.
Tüm katmanlar aynı boyutta export edilir.
"""

import sys
import subprocess
import os

print("=" * 50)
print("Gerber to PNG Converter v4.0")
print("=" * 50)
print("\nBağımlılıklar kontrol ediliyor...\n")

# ===== PIP KURULUM =====
def pip_install(pkg):
    cmds = [
        [sys.executable, '-m', 'pip', 'install', pkg],
        [sys.executable, '-m', 'pip', 'install', pkg, '--user'],
        [sys.executable, '-m', 'pip', 'install', pkg, '--break-system-packages'],
    ]
    for cmd in cmds:
        try:
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except:
            continue
    return False

# PyGerber
try:
    import pygerber
    print("✓ pygerber kurulu")
except ImportError:
    print("  pygerber kuruluyor...")
    if pip_install('pygerber'):
        print("  ✓ pygerber kuruldu")
    else:
        print("  ✗ pygerber kurulamadı! -> pip install pygerber")

# Pillow
try:
    from PIL import Image
    print("✓ Pillow kurulu")
except ImportError:
    print("  Pillow kuruluyor...")
    if pip_install('Pillow'):
        print("  ✓ Pillow kuruldu")
    else:
        print("  ✗ Pillow kurulamadı! -> pip install Pillow")

print()

# ===== IMPORT'LAR =====
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import threading
import logging
import tempfile
from pathlib import Path

try:
    from pygerber.gerberx3.api import (
        ColorScheme, Rasterized2DLayer, Rasterized2DLayerParams, RGBA,
    )
    from pygerber.gerberx3.api.v2 import GerberFile
    from PIL import Image, ImageOps
    PYGERBER_OK = True
except ImportError as e:
    PYGERBER_OK = False
    print(f"✗ Import hatası: {e}")

logging.getLogger().setLevel(logging.ERROR)
print("=" * 50 + "\n")


class GerberConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Gerber to PNG Converter v4.0")
        self.root.geometry("850x700")
        
        # Değişkenler
        self.dpi = tk.IntVar(value=300)
        self.bg_color = tk.StringVar(value="#FFFFFF")
        self.fg_color = tk.StringVar(value="#000000")
        self.status = tk.StringVar(value="Hazır")
        self.progress = tk.DoubleVar(value=0)
        
        # Dosyalar
        self.files = []
        self.output_dir = tk.StringVar()
        self.mirror_h = tk.BooleanVar(value=False)
        self.mirror_v = tk.BooleanVar(value=False)
        
        # Referans katman
        self.ref_file = tk.StringVar(value="")
        self.use_ref = tk.BooleanVar(value=True)
        self.ref_bounds = None  # (min_x, min_y, max_x, max_y) in mm
        
        self.setup_ui()
    
    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        main = ttk.Frame(self.root, padding="10")
        main.pack(fill=tk.BOTH, expand=True)
        
        # Başlık
        ttk.Label(main, text="🔧 Gerber to PNG Converter", 
                  font=('Segoe UI', 16, 'bold')).pack(anchor='w')
        ttk.Label(main, text="Referans katman ile doğru hizalama", 
                  font=('Segoe UI', 9), foreground='gray').pack(anchor='w')
        
        # ===== REFERANS KATMAN =====
        ref_frame = ttk.LabelFrame(main, text=" 📐 Referans Katman (Board Outline) ", padding="10")
        ref_frame.pack(fill=tk.X, pady=10)
        
        ref_info = ttk.Label(ref_frame, 
            text="⚠️ ÖNEMLİ: Board outline/Edge cuts dosyasını seçin. Tüm katmanlar bu boyuta göre hizalanır.",
            font=('Segoe UI', 9), foreground='#CC6600', wraplength=800)
        ref_info.pack(anchor='w', pady=(0,5))
        
        ref_row = ttk.Frame(ref_frame)
        ref_row.pack(fill=tk.X)
        
        ttk.Checkbutton(ref_row, text="Referans kullan:", variable=self.use_ref, 
                        command=self.toggle_ref).pack(side=tk.LEFT)
        
        self.ref_entry = ttk.Entry(ref_row, textvariable=self.ref_file, width=50, state='readonly')
        self.ref_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.ref_btn = ttk.Button(ref_row, text="📂 Seç", command=self.select_ref)
        self.ref_btn.pack(side=tk.LEFT, padx=2)
        
        self.ref_info_btn = ttk.Button(ref_row, text="ℹ️ Bilgi", command=self.show_ref_info)
        self.ref_info_btn.pack(side=tk.LEFT, padx=2)
        
        # Referans boyut bilgisi
        self.ref_size_label = ttk.Label(ref_frame, text="", font=('Segoe UI', 9, 'bold'), foreground='#006600')
        self.ref_size_label.pack(anchor='w', pady=(5,0))
        
        # ===== DOSYA SEÇİMİ =====
        file_frame = ttk.LabelFrame(main, text=" 📁 Dönüştürülecek Dosyalar ", padding="10")
        file_frame.pack(fill=tk.BOTH, expand=True, pady=(0,10))
        
        btn_row = ttk.Frame(file_frame)
        btn_row.pack(fill=tk.X)
        
        ttk.Button(btn_row, text="📄 Dosya Ekle", command=self.add_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="📂 Klasör Ekle", command=self.add_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="🗑️ Seçiliyi Sil", command=self.remove_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="🗑️ Temizle", command=self.clear_files).pack(side=tk.LEFT, padx=2)
        
        # Liste
        list_frame = ttk.Frame(file_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.listbox = tk.Listbox(list_frame, height=8, font=('Consolas', 9), selectmode=tk.EXTENDED)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)
        
        # ===== AYARLAR =====
        settings_frame = ttk.LabelFrame(main, text=" ⚙️ Ayarlar ", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0,10))
        
        row1 = ttk.Frame(settings_frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="DPI:").pack(side=tk.LEFT)
        ttk.Combobox(row1, textvariable=self.dpi, values=[72,150,300,600,1200,2400], width=6).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row1, text="Arka Plan:").pack(side=tk.LEFT, padx=(20,0))
        self.bg_canvas = tk.Canvas(row1, width=25, height=18, bg=self.bg_color.get(), highlightthickness=1)
        self.bg_canvas.pack(side=tk.LEFT, padx=3)
        ttk.Button(row1, text="Seç", command=self.pick_bg, width=4).pack(side=tk.LEFT)
        
        ttk.Label(row1, text="Ön Plan:").pack(side=tk.LEFT, padx=(20,0))
        self.fg_canvas = tk.Canvas(row1, width=25, height=18, bg=self.fg_color.get(), highlightthickness=1)
        self.fg_canvas.pack(side=tk.LEFT, padx=3)
        ttk.Button(row1, text="Seç", command=self.pick_fg, width=4).pack(side=tk.LEFT)
        
        row2 = ttk.Frame(settings_frame)
        row2.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(row2, text="🔄 Yatay Aynala (Alt katman için)", variable=self.mirror_h).pack(side=tk.LEFT)
        ttk.Checkbutton(row2, text="🔃 Dikey Aynala", variable=self.mirror_v).pack(side=tk.LEFT, padx=20)
        
        # ===== ÇIKTI =====
        output_frame = ttk.LabelFrame(main, text=" 💾 Çıktı ", padding="10")
        output_frame.pack(fill=tk.X, pady=(0,10))
        
        out_row = ttk.Frame(output_frame)
        out_row.pack(fill=tk.X)
        
        ttk.Label(out_row, text="Klasör:").pack(side=tk.LEFT)
        ttk.Entry(out_row, textvariable=self.output_dir, width=55).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(out_row, text="Gözat", command=self.pick_output).pack(side=tk.LEFT)
        
        # ===== DÖNÜŞTÜR =====
        ttk.Button(main, text="🚀 DÖNÜŞTÜR", command=self.start_convert,
                   style='Accent.TButton').pack(fill=tk.X, ipady=10, pady=(5,0))
        
        # İlerleme
        ttk.Progressbar(main, variable=self.progress, maximum=100).pack(fill=tk.X, pady=(10,2))
        ttk.Label(main, textvariable=self.status, font=('Segoe UI', 9)).pack(anchor='w')
        
        # Style
        style.configure('Accent.TButton', font=('Segoe UI', 11, 'bold'))
    
    # ===== REFERANS KATMAN =====
    
    def toggle_ref(self):
        """Referans kullanımını aç/kapa"""
        state = 'normal' if self.use_ref.get() else 'disabled'
        self.ref_btn.config(state=state)
        self.ref_info_btn.config(state=state)
    
    def select_ref(self):
        """Referans katman seç"""
        f = filedialog.askopenfilename(
            title="Referans Katman Seç (Board Outline / Edge Cuts)",
            filetypes=[
                ("Board Outline", "*.gko *.gm1 *.gm *.boardoutline *.gbr"),
                ("Tüm Gerber", "*.gbr *.ger *.gtl *.gbl *.gts *.gbs *.gto *.gbo *.gm1 *.gko *.drl"),
                ("Tümü", "*.*")
            ]
        )
        if f:
            self.ref_file.set(f)
            self.load_ref_bounds(f)
            
            # Çıktı klasörünü ayarla
            if not self.output_dir.get():
                self.output_dir.set(str(Path(f).parent))
    
    def load_ref_bounds(self, filepath):
        """Referans katmanın boyutlarını yükle"""
        try:
            gerber = GerberFile.from_file(filepath)
            parsed = gerber.parse()
            info = parsed.get_info()
            
            self.ref_bounds = (
                float(info.min_x_mm),
                float(info.min_y_mm),
                float(info.max_x_mm),
                float(info.max_y_mm)
            )
            
            width = self.ref_bounds[2] - self.ref_bounds[0]
            height = self.ref_bounds[3] - self.ref_bounds[1]
            
            self.ref_size_label.config(
                text=f"✓ Referans boyutu: {width:.2f} x {height:.2f} mm  |  "
                     f"Koordinatlar: X({self.ref_bounds[0]:.2f} → {self.ref_bounds[2]:.2f}), "
                     f"Y({self.ref_bounds[1]:.2f} → {self.ref_bounds[3]:.2f})"
            )
            
        except Exception as e:
            self.ref_bounds = None
            self.ref_size_label.config(text=f"✗ Hata: {e}", foreground='#CC0000')
    
    def show_ref_info(self):
        """Referans katman bilgisi göster"""
        if not self.ref_file.get():
            messagebox.showinfo("Bilgi", "Önce referans katman seçin.")
            return
        
        if self.ref_bounds:
            width = self.ref_bounds[2] - self.ref_bounds[0]
            height = self.ref_bounds[3] - self.ref_bounds[1]
            
            dpi = self.dpi.get()
            px_w = int(width * dpi / 25.4)
            px_h = int(height * dpi / 25.4)
            
            msg = f"""📐 Referans Katman Bilgisi
            
Dosya: {Path(self.ref_file.get()).name}

Fiziksel Boyut:
  • Genişlik: {width:.2f} mm
  • Yükseklik: {height:.2f} mm

Koordinatlar:
  • X: {self.ref_bounds[0]:.2f} mm → {self.ref_bounds[2]:.2f} mm
  • Y: {self.ref_bounds[1]:.2f} mm → {self.ref_bounds[3]:.2f} mm

PNG Boyutu ({dpi} DPI):
  • {px_w} x {px_h} piksel

Tüm katmanlar bu boyuta göre hizalanacak."""
            
            messagebox.showinfo("Referans Katman", msg)
        else:
            messagebox.showwarning("Uyarı", "Referans boyutu okunamadı!")
    
    # ===== DOSYA İŞLEMLERİ =====
    
    def add_files(self):
        files = filedialog.askopenfilenames(filetypes=[
            ("Gerber", "*.gbr *.ger *.gtl *.gbl *.gts *.gbs *.gto *.gbo *.gm1 *.gko *.drl"),
            ("Tümü", "*.*")
        ])
        for f in files:
            if f not in self.files:
                self.files.append(f)
                self.listbox.insert(tk.END, Path(f).name)
        if files and not self.output_dir.get():
            self.output_dir.set(str(Path(files[0]).parent))
    
    def add_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            exts = {'.gbr','.ger','.gtl','.gbl','.gts','.gbs','.gto','.gbo','.gm1','.gko','.drl'}
            for f in sorted(Path(folder).iterdir()):
                if f.suffix.lower() in exts and str(f) not in self.files:
                    self.files.append(str(f))
                    self.listbox.insert(tk.END, f.name)
            if not self.output_dir.get():
                self.output_dir.set(folder)
    
    def remove_selected(self):
        selected = list(self.listbox.curselection())
        for i in reversed(selected):
            del self.files[i]
            self.listbox.delete(i)
    
    def clear_files(self):
        self.files.clear()
        self.listbox.delete(0, tk.END)
    
    def pick_output(self):
        d = filedialog.askdirectory()
        if d:
            self.output_dir.set(d)
    
    def pick_bg(self):
        c = colorchooser.askcolor(color=self.bg_color.get())[1]
        if c:
            self.bg_color.set(c)
            self.bg_canvas.config(bg=c)
    
    def pick_fg(self):
        c = colorchooser.askcolor(color=self.fg_color.get())[1]
        if c:
            self.fg_color.set(c)
            self.fg_canvas.config(bg=c)
    
    # ===== DÖNÜŞTÜRME =====
    
    def hex_to_rgba(self, hex_color):
        h = hex_color.lstrip('#')
        return RGBA(r=int(h[0:2],16), g=int(h[2:4],16), b=int(h[4:6],16), a=255)
    
    def get_gerber_bounds(self, filepath):
        """Gerber dosyasının koordinatlarını al"""
        try:
            gerber = GerberFile.from_file(filepath)
            parsed = gerber.parse()
            info = parsed.get_info()
            return (
                float(info.min_x_mm),
                float(info.min_y_mm),
                float(info.max_x_mm),
                float(info.max_y_mm)
            )
        except:
            return None
    
    def render_gerber_raw(self, filepath, fg_color):
        """Gerber'ı olduğu gibi render et"""
        fg = self.hex_to_rgba(fg_color)
        bg = self.hex_to_rgba(self.bg_color.get())
        
        colors = ColorScheme(
            background_color=bg, clear_color=bg, solid_color=fg,
            clear_region_color=bg, solid_region_color=fg
        )
        
        layer = Rasterized2DLayer(options=Rasterized2DLayerParams(
            source_path=filepath, colors=colors, dpi=self.dpi.get()
        ))
        
        result = layer.render()
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            temp_path = tmp.name
        
        result.save(temp_path)
        with Image.open(temp_path) as img:
            img_copy = img.copy().convert('RGBA')
        
        Path(temp_path).unlink(missing_ok=True)
        return img_copy
    
    def render_with_reference(self, filepath, fg_color):
        """Referans boyutuna göre render et"""
        dpi = self.dpi.get()
        px_per_mm = dpi / 25.4
        
        # Referans boyutu
        ref_width_mm = self.ref_bounds[2] - self.ref_bounds[0]
        ref_height_mm = self.ref_bounds[3] - self.ref_bounds[1]
        
        canvas_width = int(ref_width_mm * px_per_mm)
        canvas_height = int(ref_height_mm * px_per_mm)
        
        # Bu katmanın koordinatları
        layer_bounds = self.get_gerber_bounds(filepath)
        
        if not layer_bounds:
            # Koordinat alınamadıysa normal render et
            return self.render_gerber_raw(filepath, fg_color)
        
        # Katmanı render et
        fg = self.hex_to_rgba(fg_color)
        bg = RGBA(r=0, g=0, b=0, a=0)  # Şeffaf arka plan
        
        colors = ColorScheme(
            background_color=bg, clear_color=bg, solid_color=fg,
            clear_region_color=bg, solid_region_color=fg
        )
        
        layer = Rasterized2DLayer(options=Rasterized2DLayerParams(
            source_path=filepath, colors=colors, dpi=dpi
        ))
        
        result = layer.render()
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            temp_path = tmp.name
        
        result.save(temp_path)
        with Image.open(temp_path) as img:
            layer_img = img.copy().convert('RGBA')
        
        Path(temp_path).unlink(missing_ok=True)
        
        # Offset hesapla - bu katmanın referans içindeki konumu
        # Referans: min_x, min_y -> 0,0 noktası
        # Katman: layer_min_x, layer_min_y
        
        # X offset: katmanın sol kenarı referansın sol kenarından ne kadar uzakta
        x_offset_mm = layer_bounds[0] - self.ref_bounds[0]
        # Y offset: Gerber'da Y yukarı pozitif, Image'da Y aşağı pozitif
        # Katmanın üst kenarı referansın üst kenarından ne kadar uzakta
        y_offset_mm = self.ref_bounds[3] - layer_bounds[3]
        
        x_offset_px = int(x_offset_mm * px_per_mm)
        y_offset_px = int(y_offset_mm * px_per_mm)
        
        # Arka plan canvas oluştur
        bg_rgba = self.hex_to_rgba(self.bg_color.get())
        canvas = Image.new('RGBA', (canvas_width, canvas_height), (bg_rgba.r, bg_rgba.g, bg_rgba.b, bg_rgba.a))
        
        # Katmanı doğru konuma yerleştir
        canvas.paste(layer_img, (x_offset_px, y_offset_px), layer_img)
        
        return canvas
    
    def start_convert(self):
        if not PYGERBER_OK:
            messagebox.showerror("Hata", "PyGerber yüklü değil!")
            return
        if not self.files:
            messagebox.showwarning("Uyarı", "Dosya seçin!")
            return
        if not self.output_dir.get():
            messagebox.showwarning("Uyarı", "Çıktı klasörü seçin!")
            return
        if self.use_ref.get() and not self.ref_bounds:
            messagebox.showwarning("Uyarı", "Referans katman seçin veya 'Referans kullan' seçeneğini kapatın!")
            return
        
        threading.Thread(target=self.convert_thread, daemon=True).start()
    
    def convert_thread(self):
        out_dir = Path(self.output_dir.get())
        out_dir.mkdir(parents=True, exist_ok=True)
        
        total = len(self.files)
        success = 0
        failed = []
        
        use_ref = self.use_ref.get() and self.ref_bounds is not None
        
        for i, fp in enumerate(self.files):
            name = Path(fp).name
            self.status.set(f"Dönüştürülüyor: {name}")
            self.progress.set((i / total) * 100)
            self.root.update_idletasks()
            
            try:
                # Render
                if use_ref:
                    img = self.render_with_reference(fp, self.fg_color.get())
                else:
                    img = self.render_gerber_raw(fp, self.fg_color.get())
                
                # Aynalama
                if self.mirror_h.get():
                    img = ImageOps.mirror(img)
                if self.mirror_v.get():
                    img = ImageOps.flip(img)
                
                # Kaydet
                out_path = out_dir / f"{Path(fp).stem}.png"
                img.save(str(out_path), "PNG", dpi=(self.dpi.get(), self.dpi.get()))
                success += 1
                
            except Exception as e:
                failed.append(f"{name}: {e}")
                print(f"Hata ({name}): {e}")
        
        self.progress.set(100)
        
        if use_ref:
            ref_w = self.ref_bounds[2] - self.ref_bounds[0]
            ref_h = self.ref_bounds[3] - self.ref_bounds[1]
            size_info = f"\n\nTüm dosyalar {ref_w:.1f}x{ref_h:.1f} mm boyutunda"
        else:
            size_info = ""
        
        if failed:
            self.status.set(f"⚠ {success}/{total} başarılı, {len(failed)} hata")
            messagebox.showwarning("Uyarı", 
                f"✓ {success} dosya dönüştürüldü\n"
                f"✗ {len(failed)} hata\n\n"
                f"Hatalar:\n" + "\n".join(failed[:5]))
        else:
            self.status.set(f"✓ {success} dosya dönüştürüldü")
            messagebox.showinfo("Tamamlandı", 
                f"✓ {success} dosya dönüştürüldü!{size_info}\n\n"
                f"Konum: {out_dir}")


def main():
    if not PYGERBER_OK:
        print("\n" + "!"*50)
        print("HATA: PyGerber yüklenemedi!")
        print("Manuel: pip install pygerber Pillow")
        print("!"*50)
        input("\nDevam için Enter...")
    
    root = tk.Tk()
    app = GerberConverterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
