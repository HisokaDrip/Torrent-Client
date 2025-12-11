import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, Canvas
from PIL import Image, ImageTk
import threading
import asyncio
import os
import shutil
import psutil  # For System Stats
import time
from client import TorrentClient

# ==========================================
# 🎨 ANIME CYBERPUNK THEME ENGINE
# ==========================================
THEME = {
    "bg_fallback": "#050505",
    "glass_dark": "#0A0A0A",  # 90% Opacity Black
    "glass_light": "#141414",
    "neon_pink": "#FF0055",
    "neon_cyan": "#00F0FF",
    "neon_purple": "#BD00FF",
    "neon_green": "#00FF99",
    "text_white": "#FFFFFF",
    "text_gray": "#888888",
    "danger": "#FF2222"
}

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")


# ==========================================
# 🧩 CUSTOM WIDGETS
# ==========================================

class NeonButton(ctk.CTkButton):
    def __init__(self, master, text, command, color=THEME["neon_cyan"], width=140):
        super().__init__(
            master, text=text, command=command, width=width, height=35,
            fg_color="transparent", border_width=2, border_color=color,
            text_color=THEME["text_white"], hover_color=color,
            font=("Segoe UI", 11, "bold"), corner_radius=18
        )


class GlassCard(ctk.CTkFrame):
    """Semi-transparent card container"""

    def __init__(self, master, **kwargs):
        super().__init__(
            master, fg_color=THEME["glass_light"],
            corner_radius=12, border_width=1,
            border_color="#333333", **kwargs
        )


class StatBar(ctk.CTkFrame):
    """Visualizes CPU/RAM Usage"""

    def __init__(self, master, label, color):
        super().__init__(master, fg_color="transparent")
        self.label = ctk.CTkLabel(self, text=label, font=("Consolas", 10), text_color=color, width=40, anchor="w")
        self.label.pack(side="left")
        self.progress = ctk.CTkProgressBar(self, progress_color=color, height=6, width=100)
        self.progress.pack(side="left", padx=5)
        self.progress.set(0)


class TorrentDisplayCard(GlassCard):
    """The main visual component for a download"""

    def __init__(self, master, name, size_str):
        super().__init__(master, height=120)
        self.pack(fill="x", pady=10, padx=10)

        # Grid Layout
        self.grid_columnconfigure(1, weight=1)

        # 1. Icon
        self.icon_lbl = ctk.CTkLabel(self, text="⚡", font=("Arial", 30), text_color=THEME["neon_cyan"])
        self.icon_lbl.grid(row=0, column=0, rowspan=3, padx=20)

        # 2. Title & Hash
        self.lbl_name = ctk.CTkLabel(self, text=name, font=("Segoe UI", 16, "bold"), text_color="white", anchor="w")
        self.lbl_name.grid(row=0, column=1, sticky="w", pady=(10, 0))

        self.lbl_status = ctk.CTkLabel(self, text="INITIALIZING SYSTEM...", font=("Consolas", 10),
                                       text_color=THEME["neon_purple"], anchor="w")
        self.lbl_status.grid(row=1, column=1, sticky="w")

        # 3. Stats Row
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.grid(row=2, column=1, sticky="ew", pady=5)

        self.lbl_size = ctk.CTkLabel(self.stats_frame, text=f"SIZE: {size_str}", font=("Segoe UI", 11, "bold"),
                                     text_color="gray")
        self.lbl_size.pack(side="left", padx=(0, 20))

        self.lbl_peers = ctk.CTkLabel(self.stats_frame, text="PEERS: 0", font=("Segoe UI", 11, "bold"),
                                      text_color=THEME["neon_pink"])
        self.lbl_peers.pack(side="left", padx=20)

        self.lbl_speed = ctk.CTkLabel(self.stats_frame, text="SPEED: 0 KB/s", font=("Segoe UI", 11, "bold"),
                                      text_color=THEME["neon_green"])
        self.lbl_speed.pack(side="right", padx=20)

        # 4. Progress Bar
        self.bar = ctk.CTkProgressBar(self, height=10, corner_radius=5, progress_color=THEME["neon_cyan"])
        self.bar.grid(row=3, column=0, columnspan=2, sticky="ew", padx=15, pady=(5, 15))
        self.bar.set(0)

    def update(self, pct, speed, peers, status):
        self.bar.set(pct)
        self.lbl_speed.configure(text=speed)
        self.lbl_peers.configure(text=f"PEERS: {peers}")
        self.lbl_status.configure(text=status)
        if pct >= 1.0:
            self.lbl_status.configure(text="DOWNLOAD COMPLETE", text_color=THEME["neon_green"])
            self.bar.configure(progress_color=THEME["neon_green"])


# ==========================================
# 🖥️ MAIN APPLICATION WINDOW
# ==========================================

class FluxAnimeGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FluxTorrent // ULTIMATE MAZY EDITION")
        self.geometry("1100x750")

        # State
        self.client = None
        self.is_running = False
        self.bg_ref = None

        # --- LAYER 0: Background ---
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.bg_canvas = ctk.CTkLabel(self, text="")
        self.bg_canvas.grid(row=0, column=0, sticky="nsew")
        self.load_wallpaper()

        # --- LAYER 1: UI Content Wrapper ---
        self.wrapper = ctk.CTkFrame(self, fg_color="transparent")
        self.wrapper.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.wrapper.grid_rowconfigure(1, weight=1)
        self.wrapper.grid_columnconfigure(1, weight=1)

        # === SIDEBAR (Left) ===
        self.sidebar = GlassCard(self.wrapper, width=220)
        self.sidebar.grid(row=0, column=0, rowspan=3, sticky="ns", padx=(0, 20))
        self.sidebar.pack_propagate(False)

        # Logo
        ctk.CTkLabel(self.sidebar, text="FLUX", font=("Impact", 32), text_color=THEME["neon_cyan"]).pack(pady=(30, 0))
        ctk.CTkLabel(self.sidebar, text="TORRENT", font=("Impact", 32), text_color=THEME["text_white"]).pack(
            pady=(0, 20))
        ctk.CTkLabel(self.sidebar, text="By Mazy", font=("Segoe UI", 10), text_color="gray").pack()

        # Menu Buttons
        self.btn_dash = NeonButton(self.sidebar, "DASHBOARD", lambda: None, THEME["neon_cyan"])
        self.btn_dash.pack(pady=20)

        self.btn_wall = NeonButton(self.sidebar, "SET WALLPAPER", self.change_wallpaper, THEME["neon_purple"])
        self.btn_wall.pack(pady=10)

        # System Stats Area (Bottom of Sidebar)
        self.stats_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.stats_container.pack(side="bottom", pady=30, padx=10, fill="x")

        ctk.CTkLabel(self.stats_container, text="SYSTEM DIAGNOSTICS", font=("Consolas", 10, "bold"),
                     text_color="gray").pack(anchor="w", pady=5)
        self.cpu_bar = StatBar(self.stats_container, "CPU", THEME["neon_pink"])
        self.cpu_bar.pack(pady=5)
        self.ram_bar = StatBar(self.stats_container, "RAM", THEME["neon_purple"])
        self.ram_bar.pack(pady=5)

        # === TOP BAR ===
        self.topbar = GlassCard(self.wrapper, height=60)
        self.topbar.grid(row=0, column=1, sticky="ew", pady=(0, 20))

        self.btn_add = NeonButton(self.topbar, "+ NEW MISSION", self.add_torrent, THEME["neon_green"])
        self.btn_add.pack(side="right", padx=20, pady=12)

        self.btn_pause = NeonButton(self.topbar, "PAUSE / RESUME", self.toggle_pause, THEME["text_white"])
        self.btn_pause.pack(side="right", padx=10, pady=12)

        # === CONTENT AREA ===
        self.content_area = ctk.CTkScrollableFrame(self.wrapper, fg_color="transparent")
        self.content_area.grid(row=1, column=1, sticky="nsew")

        # Placeholder Message
        self.empty_msg = ctk.CTkLabel(self.content_area, text="NO ACTIVE MISSIONS\nWAITING FOR COMMAND...",
                                      font=("Consolas", 16), text_color="gray")
        self.empty_msg.pack(pady=100)

        self.active_card = None  # Supports 1 download for this demo

        # === LOG TERMINAL (Bottom) ===
        self.terminal = GlassCard(self.wrapper, height=150)
        self.terminal.grid(row=2, column=1, sticky="ew", pady=(20, 0))

        self.log_lbl = ctk.CTkLabel(self.terminal, text="TERMINAL OUTPUT", font=("Consolas", 10, "bold"),
                                    text_color="gray", anchor="w")
        self.log_lbl.pack(fill="x", padx=10, pady=(5, 0))

        self.log_box = ctk.CTkTextbox(self.terminal, fg_color="#080808", text_color=THEME["neon_green"],
                                      font=("Consolas", 10), height=100)
        self.log_box.pack(fill="both", padx=10, pady=5)
        self.log(">> FLUX CORE ONLINE")
        self.log(">> GUI RENDERER: MAZY ENGINE V2.0")

        # Start Loops
        self.after(1000, self.update_system_stats)
        self.after(500, self.update_torrent_ui)

    # --- LOGIC ---

    def load_wallpaper(self):
        if not os.path.exists("assets"): os.makedirs("assets")
        path = "assets/bg.jpg"

        if os.path.exists(path):
            try:
                img = Image.open(path)
                # Resize to cover
                img = img.resize((1400, 900), Image.Resampling.LANCZOS)
                self.bg_ref = ctk.CTkImage(img, size=(1400, 900))
                self.bg_canvas.configure(image=self.bg_ref)
                return
            except:
                pass
        self.bg_canvas.configure(fg_color="#050505")  # Default Black

    def change_wallpaper(self):
        f = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.png")])
        if f:
            shutil.copy(f, "assets/bg.jpg")
            self.load_wallpaper()

    def log(self, msg):
        self.log_box.insert("end", f">> {msg}\n")
        self.log_box.see("end")

    def update_system_stats(self):
        # Update CPU/RAM bars
        cpu = psutil.cpu_percent() / 100
        ram = psutil.virtual_memory().percent / 100
        self.cpu_bar.progress.set(cpu)
        self.ram_bar.progress.set(ram)
        self.after(2000, self.update_system_stats)

    def add_torrent(self):
        f = filedialog.askopenfilename(filetypes=[("Torrent", "*.torrent")])
        if not f: return
        d = filedialog.askdirectory(title="Select Destination")
        if not d: return

        self.start_engine(f, d)

    def start_engine(self, f, d):
        if self.is_running: return

        self.empty_msg.pack_forget()  # Hide placeholder

        self.client = TorrentClient(f, d)
        self.is_running = True

        # Create Card
        size_mb = self.client.torrent.total_length / (1024 * 1024)
        self.active_card = TorrentDisplayCard(self.content_area, self.client.torrent.name, f"{size_mb:.2f} MB")
        self.log(f"INITIATING DOWNLOAD: {self.client.torrent.name}")

        # Start Backend
        t = threading.Thread(target=self._run_async, daemon=True)
        t.start()

    def _run_async(self):
        asyncio.run(self.client.start())

    def toggle_pause(self):
        if self.client:
            self.client.toggle_pause()
            state = "PAUSED" if self.client.is_paused else "RESUMED"
            self.log(f"OPERATION {state}")

    def update_torrent_ui(self):
        if self.client and self.is_running and self.active_card:
            # Stats Math
            completed = sum(
                (self.client.piece_manager.bitfield.field[i // 8] >> (7 - (i % 8))) & 1
                for i in range(self.client.torrent.number_of_pieces)
            )
            total = self.client.torrent.number_of_pieces
            pct = completed / total if total > 0 else 0

            peers = len(self.client.peers)

            # Simulated Speed (Byte delta calculation would be better, but this is visual)
            # In a real app, calculate (bytes_now - bytes_last_sec)
            est_speed = peers * 15  # Conservative estimate for visual
            if self.client.is_paused: est_speed = 0

            status = "DOWNLOADING PACKETS..."
            if self.client.is_paused: status = "SYSTEM PAUSED"
            if pct >= 1.0: status = "TASK COMPLETED"

            self.active_card.update(pct, f"{est_speed} KB/s", peers, status)

        self.after(800, self.update_torrent_ui)


if __name__ == "__main__":
    app = FluxAnimeGUI()
    app.mainloop()