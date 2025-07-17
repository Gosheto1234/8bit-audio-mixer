import os
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import sounddevice as sd
import numpy as np

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

VB_INSTALLER = os.path.join(os.path.dirname(__file__), "VB", "VBCABLE_Setup_x64.exe")
VB_DEVICE_NAME = "CABLE Input (VB-Audio Virtual Cable)"

def check_and_install_vb():
    """If VB-Cable isn’t present, run the installer silently."""
    devices = sd.query_devices()
    outputs = [d['name'] for d in devices if d['max_output_channels'] > 0]
    if VB_DEVICE_NAME in outputs:
        return  # already installed

    if not os.path.isfile(VB_INSTALLER):
        messagebox.showerror(
            "VB‑Cable Missing",
            f"Couldn’t find installer at:\n{VB_INSTALLER}"
        )
        sys.exit(1)

    # Ask user for elevation if needed
    if not ctypes.windll.shell32.IsUserAnAdmin():
        messagebox.showinfo(
            "Admin Required",
            "VB‑Cable needs to install a driver.\n"
            "Please re-run this app as Administrator."
        )
        sys.exit(1)

    # Run silent install
    try:
        subprocess.run([VB_INSTALLER, "/S"], check=True)
    except subprocess.CalledProcessError as e:
        messagebox.showerror(
            "Install Failed",
            f"VB‑Cable installer returned error {e.returncode}"
        )
        sys.exit(1)

    messagebox.showinfo(
        "Installed",
        "VB‑Audio Virtual Cable installed successfully.\n"
        "Restarting device list…"
    )

class AudioMixerApp:
    def __init__(self, root):
        self.root = root
        root.title("8‑Bit Audio Mixer")
        root.configure(bg="#222")

        # (Re)load devices
        self.devices = sd.query_devices()
        self.input_names  = [d['name'] for d in self.devices if d['max_input_channels'] > 0]
        self.output_names = [d['name'] for d in self.devices if d['max_output_channels']> 0]

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
        # Pre-select VB‑Cable if available
        if VB_DEVICE_NAME in self.output_names:
            self.combo_out.set(VB_DEVICE_NAME)
        else:
            self.combo_out.set(self.output_names[0])

        btn_frame = tk.Frame(root, bg="#222")
        btn_frame.pack(pady=10)
        self.btn_start = tk.Button(btn_frame, text="START", command=self.start,  **BUTTON_STYLE)
        self.btn_start.grid(row=0, column=0, padx=5)
        self.btn_stop  = tk.Button(btn_frame, text="STOP",  command=self.stop, **BUTTON_STYLE, state="disabled")
        self.btn_stop.grid(row=0, column=1, padx=5)

        # State
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
        idx_a = self.input_names.index(self.combo_a.get())
        idx_b = self.input_names.index(self.combo_b.get())
        idx_o = self.output_names.index(self.combo_out.get())

        dev_a = [i for i,d in enumerate(self.devices) if d['name']==self.input_names[idx_a]][0]
        dev_b = [i for i,d in enumerate(self.devices) if d['name']==self.input_names[idx_b]][0]
        dev_o = [i for i,d in enumerate(self.devices) if d['name']==self.output_names[idx_o]][0]

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
                s.stop(); s.close()
            except:
                pass
        self.btn_start.config(state="normal")
        self.btn_stop .config(state="disabled")

if __name__ == "__main__":
    # Must import here so messagebox works before GUI
    import ctypes

    root = tk.Tk()
    # Before showing anything, ensure VB‑Cable
    check_and_install_vb()

    style = ttk.Style(root)
    style.theme_use('alt')
    app = AudioMixerApp(root)
    root.mainloop()
