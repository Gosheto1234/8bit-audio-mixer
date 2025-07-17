import os
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import sounddevice as sd
import numpy as np

def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

VB_INSTALLER   = resource_path(os.path.join("VB", "VBCABLE_Setup_x64.exe"))
VB_ICON_PATH   = resource_path(os.path.join("VB", "icon.ico"))
VB_DEVICE_NAME = "CABLE Input (VB-Audio Virtual Cable)"

tk_pixel_font = ("Courier", 16, "bold")
BUTTON_STYLE = {
    "background": "#444",
    "foreground": "#0f0",
    "activebackground": "#666",
    "activeforeground": "#afa",
    "font": tk_pixel_font,
    "bd": 2,
    "relief": "ridge"
}

def check_and_install_vb():
    devices = sd.query_devices()
    outputs = [d["name"] for d in devices if d["max_output_channels"] > 0]
    if VB_DEVICE_NAME in outputs:
        return

    if not os.path.isfile(VB_INSTALLER):
        messagebox.showerror("VB‑Cable Missing", f"Installer not found at:\n{VB_INSTALLER}")
        sys.exit(1)

    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():
        messagebox.showinfo("Admin Required", "Please restart this app as Administrator.")
        sys.exit(1)

    try:
        subprocess.run([VB_INSTALLER, "/S"], check=True)
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Install Failed", f"Installer error code: {e.returncode}")
        sys.exit(1)

    messagebox.showinfo("Installed", "VB‑Audio Virtual Cable installed.\nRestart the app.")
    sys.exit(0)

class AudioMixerApp:
    def __init__(self, root):
        self.root = root
        root.title("8‑Bit Audio Mixer")
        # root.iconbitmap(VB_ICON_PATH)  # Optional

        root.configure(bg="#222")

        self.devices      = sd.query_devices()
        self.input_names  = [d["name"] for d in self.devices if d["max_input_channels"] > 0]
        self.output_names = [d["name"] for d in self.devices if d["max_output_channels"] > 0]

        frame = tk.Frame(root, bg="#222")
        frame.pack(padx=10, pady=10)

        tk.Label(frame, text="Input A:", fg="#0f0", bg="#222", font=tk_pixel_font).grid(row=0, column=0, sticky="e")
        self.combo_a = ttk.Combobox(frame, values=self.input_names, font=tk_pixel_font)
        self.combo_a.grid(row=0, column=1)

        tk.Label(frame, text="Input B:", fg="#0f0", bg="#222", font=tk_pixel_font).grid(row=1, column=0, sticky="e")
        self.combo_b = ttk.Combobox(frame, values=self.input_names, font=tk_pixel_font)
        self.combo_b.grid(row=1, column=1)

        tk.Label(frame, text="Output:", fg="#0f0", bg="#222", font=tk_pixel_font).grid(row=2, column=0, sticky="e")
        self.combo_out = ttk.Combobox(frame, values=self.output_names, font=tk_pixel_font)
        self.combo_out.grid(row=2, column=1)

        if VB_DEVICE_NAME in self.output_names:
            self.combo_out.set(VB_DEVICE_NAME)
        else:
            self.combo_out.set(self.output_names[0])

        # Volume sliders
        tk.Label(frame, text="Volume A:", fg="#0f0", bg="#222", font=tk_pixel_font).grid(row=3, column=0, sticky="e")
        self.vol_a = tk.Scale(frame, from_=0, to=100, orient="horizontal", bg="#333", fg="#0f0",
                              troughcolor="#555", font=tk_pixel_font)
        self.vol_a.set(100)
        self.vol_a.grid(row=3, column=1, sticky="we")

        tk.Label(frame, text="Volume B:", fg="#0f0", bg="#222", font=tk_pixel_font).grid(row=4, column=0, sticky="e")
        self.vol_b = tk.Scale(frame, from_=0, to=100, orient="horizontal", bg="#333", fg="#0f0",
                              troughcolor="#555", font=tk_pixel_font)
        self.vol_b.set(100)
        self.vol_b.grid(row=4, column=1, sticky="we")

        # Meters
        self.meter_a = ttk.Progressbar(frame, orient="horizontal", length=200, mode="determinate")
        self.meter_a.grid(row=5, column=0, columnspan=2, sticky="we", pady=(10, 0))
        self.meter_b = ttk.Progressbar(frame, orient="horizontal", length=200, mode="determinate")
        self.meter_b.grid(row=6, column=0, columnspan=2, sticky="we")

        btn_frame = tk.Frame(root, bg="#222")
        btn_frame.pack(pady=10)
        self.btn_start = tk.Button(btn_frame, text="START",  command=self.start, **BUTTON_STYLE)
        self.btn_start.grid(row=0, column=0, padx=5)
        self.btn_stop  = tk.Button(btn_frame, text="STOP",   command=self.stop,  **BUTTON_STYLE, state="disabled")
        self.btn_stop.grid(row=0, column=1, padx=5)

        self.blocksize = 1024
        self.running   = False
        self.thread    = None
        self.stream_a  = None
        self.stream_b  = None
        self.output    = None

    def mix_loop(self):
        while self.running:
            data_a, _ = self.stream_a.read(self.blocksize)
            data_b, _ = self.stream_b.read(self.blocksize)

            vol_a = self.vol_a.get() / 100
            vol_b = self.vol_b.get() / 100

            data_a *= vol_a
            data_b *= vol_b

            level_a = np.linalg.norm(data_a) * 10
            level_b = np.linalg.norm(data_b) * 10
            self.meter_a["value"] = min(level_a, 100)
            self.meter_b["value"] = min(level_b, 100)

            mixed = ((data_a + data_b) / 2).astype(np.float32)
            self.output.write(mixed)

    def start(self):
        ia = self.input_names.index(self.combo_a.get())
        ib = self.input_names.index(self.combo_b.get())
        io = self.output_names.index(self.combo_out.get())

        dev_a = next(i for i,d in enumerate(self.devices) if d["name"] == self.input_names[ia])
        dev_b = next(i for i,d in enumerate(self.devices) if d["name"] == self.input_names[ib])
        dev_o = next(i for i,d in enumerate(self.devices) if d["name"] == self.output_names[io])

        self.stream_a = sd.InputStream(device=dev_a, channels=1, samplerate=44100, blocksize=self.blocksize)
        self.stream_b = sd.InputStream(device=dev_b, channels=1, samplerate=44100, blocksize=self.blocksize)
        self.output   = sd.OutputStream(device=dev_o, channels=1, samplerate=44100, blocksize=self.blocksize)

        self.stream_a.start()
        self.stream_b.start()
        self.output.start()

        self.running = True
        self.thread  = threading.Thread(target=self.mix_loop, daemon=True)
        self.thread.start()

        self.btn_start.config(state="disabled")
        self.btn_stop .config(state="normal")

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.thread.join()

        for s in (self.stream_a, self.stream_b, self.output):
            try:
                s.stop()
                s.close()
            except:
                pass

        self.btn_start.config(state="normal")
        self.btn_stop .config(state="disabled")

if __name__ == "__main__":
    check_and_install_vb()
    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use("alt")
    app = AudioMixerApp(root)
    root.mainloop()
