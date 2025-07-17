import threading
import tkinter as tk
from tkinter import ttk, font
import sounddevice as sd
import numpy as np

# Retro 8‑bit style settings
tk_pixel_font = ("Courier", 16, "bold")  # swap to a pixel font if you have one
BUTTON_STYLE = {
    "background": "#444",   # dark gray
    "foreground": "#0f0",   # bright green
    "activebackground": "#666",
    "activeforeground": "#afa",
    "font": tk_pixel_font,
    "bd": 2,
    "relief": "ridge"
}

class AudioMixerApp:
    def __init__(self, root):
        self.root = root
        root.title("8‑Bit Audio Mixer")
        root.configure(bg="#222")

        # Device selection
        self.devices = sd.query_devices()
        self.device_names = [d['name'] for d in self.devices if d['max_input_channels'] > 0]

        frame = tk.Frame(root, bg="#222")
        frame.pack(padx=10, pady=10)

        tk.Label(frame, text="Input A:", fg="#0f0", bg="#222", font=tk_pixel_font)\
          .grid(row=0, column=0, sticky="e")
        self.combo_a = ttk.Combobox(frame, values=self.device_names, font=tk_pixel_font)
        self.combo_a.grid(row=0, column=1)

        tk.Label(frame, text="Input B:", fg="#0f0", bg="#222", font=tk_pixel_font)\
          .grid(row=1, column=0, sticky="e")
        self.combo_b = ttk.Combobox(frame, values=self.device_names, font=tk_pixel_font)
        self.combo_b.grid(row=1, column=1)

        # Control buttons
        btn_frame = tk.Frame(root, bg="#222")
        btn_frame.pack(pady=10)

        self.btn_start = tk.Button(btn_frame, text="START", command=self.start, **BUTTON_STYLE)
        self.btn_start.grid(row=0, column=0, padx=5)
        self.btn_stop  = tk.Button(btn_frame, text="STOP",  command=self.stop,  **BUTTON_STYLE, state="disabled")
        self.btn_stop.grid(row=0, column=1, padx=5)

        # Streaming/mixing state
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
        # pick devices
        idx_a = self.device_names.index(self.combo_a.get())
        idx_b = self.device_names.index(self.combo_b.get())
        dev_a = [i for i,d in enumerate(self.devices) if d['name']==self.device_names[idx_a]][0]
        dev_b = [i for i,d in enumerate(self.devices) if d['name']==self.device_names[idx_b]][0]

        # open mono input streams
        self.stream_a = sd.InputStream(device=dev_a,
                                       channels=1,
                                       samplerate=44100,
                                       blocksize=self.blocksize)
        self.stream_b = sd.InputStream(device=dev_b,
                                       channels=1,
                                       samplerate=44100,
                                       blocksize=self.blocksize)
        # open mono output stream
        self.output = sd.OutputStream(device=None,  # default output or loopback
                                      channels=1,
                                      samplerate=44100,
                                      blocksize=self.blocksize)

        # start streams
        self.stream_a.start()
        self.stream_b.start()
        self.output.start()

        # start mixing thread
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

        self.stream_a = None
        self.stream_b = None
        self.output   = None

        self.btn_start.config(state="normal")
        self.btn_stop .config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use('alt')  # keep it simple, retro look
    app = AudioMixerApp(root)
    root.mainloop()
