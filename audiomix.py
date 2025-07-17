import os
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import sounddevice as sd
import numpy as np

# Helper to find bundled resources in onefile EXE
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller --onefile."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

# Paths to VB‑Cable installer and icon, inside the bundled VB/ folder
VB_INSTALLER   = resource_path(os.path.join("VB", "VBCABLE_Setup_x64.exe"))
VB_ICON_PATH   = resource_path(os.path.join("VB", "icon.ico"))
VB_DEVICE_NAME = "CABLE Input (VB-Audio Virtual Cable)"

# Retro 8‑bit style
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
    """If VB‑Cable isn’t present among outputs, run its silent installer (requires Admin)."""
    devices = sd.query_devices()
    outputs = [d["name"] for d in devices if d["max_output_channels"] > 0]
    if VB_DEVICE_NAME in outputs:
        return  # already there

    # Confirm installer is bundled
    if not os.path.isfile(VB_INSTALLER):
        messagebox.showerror(
            "VB‑Cable Missing",
            f"Installer not found at:\n{VB_INSTALLER}"
        )
        sys.exit(1)

    # Check admin rights
    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():
        messagebox.showinfo(
            "Admin Required",
            "VB‑Cable installation requires Administrator privileges.\n"
            "Please restart this app as Administrator."
        )
        sys.exit(1)

    # Run silent install
    try:
        subprocess.run([VB_INSTALLER, "/S"], check=True)
    except subprocess.CalledProcessError as e:
        messagebox.showerror(
            "Install Failed",
            f"VB‑Cable installer returned error code {e.returncode}."
        )
        sys.exit(1)

    messagebox.showinfo(
        "Installed",
        "VB‑Audio Virtual Cable installed successfully.\n"
        "Please restart the app to refresh device list."
    )
    sys.exit(0)

class AudioMixerApp:
    def __init__(self, root):
        self.root = root
        root.title("8‑Bit Audio Mixer")
        # If you want to set the window icon:
        # root.iconbitmap(VB_ICON_PATH)

        root.configure(bg="#222")

        # Load devices
        self.devices      = sd.query_devices()
        self.input_names  = [d["name"] for d in self.devices if d["max_input_channels"] > 0]
        self.output_names = [d["name"] for d in self.devices if d["max_output_channels"] > 0]

        # UI
        frame = tk.Frame(root, bg="#222")
        frame.pack(padx=10, pady=10)

        tk.Label(frame, text="Input A:", fg="#0f0", bg="#222", font=tk_pixel_font)\
          .grid(row=0, column=0, sticky="e")
        self.combo_a = ttk.Combobox(frame, values=self.input_names, font=tk_pixel_font)
        self.combo_a.grid(row=0, column=1)

        tk.Label(frame, text="Input B:", fg="#0f0", bg="#222", font=tk_pixel_font)\
          .grid(row=1, column=0, sticky="e")
        self.combo_b = ttk.Combobox(frame, values=self.input_names, font=tk_pixel_font)
        self.combo_b.grid(row=1, column=1)

        tk.Label(frame, text="Output:", fg="#0f0", bg="#222", font=tk_pixel_font)\
          .grid(row=2, column=0, sticky="e")
        self.combo_out = ttk.Combobox(frame, values=self.output_names, font=tk_pixel_font)
        self.combo_out.grid(row=2, column=1)
        # Pre‑select VB‑Cable if present, else first
        if VB_DEVICE_NAME in self.output_names:
            self.combo_out.set(VB_DEVICE_NAME)
        else:
            self.combo_out.set(self.output_names[0])

        btn_frame = tk.Frame(root, bg="#222")
        btn_frame.pack(pady=10)
        self.btn_start = tk.Button(btn_frame, text="START",  command=self.start, **BUTTON_STYLE)
        self.btn_start.grid(row=0, column=0, padx=5)
        self.btn_stop  = tk.Button(btn_frame, text="STOP",   command=self.stop,  **BUTTON_STYLE, state="disabled")
        self.btn_stop.grid(row=0, column=1, padx=5)

        # Mixing state
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
            mixed = ((data_a + data_b) / 2).astype(np.float32)
            self.output.write(mixed)

    def start(self):
        # Resolve device indices
        ia = self.input_names.index(self.combo_a.get())
        ib = self.input_names.index(self.combo_b.get())
        io = self.output_names.index(self.combo_out.get())

        dev_a = next(i for i,d in enumerate(self.devices) if d["name"] == self.input_names[ia])
        dev_b = next(i for i,d in enumerate(self.devices) if d["name"] == self.input_names[ib])
        dev_o = next(i for i,d in enumerate(self.devices) if d["name"] == self.output_names[io])

        # Open streams
        self.stream_a = sd.InputStream(device=dev_a, channels=1,
                                       samplerate=44100, blocksize=self.blocksize)
        self.stream_b = sd.InputStream(device=dev_b, channels=1,
                                       samplerate=44100, blocksize=self.blocksize)
        self.output   = sd.OutputStream(device=dev_o, channels=1,
                                        samplerate=44100, blocksize=self.blocksize)

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
    # Ensure VB‑Cable is installed before showing UI
    check_and_install_vb()

    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use("alt")
    app = AudioMixerApp(root)
    root.mainloop()
