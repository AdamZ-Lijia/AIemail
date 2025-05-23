import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import threading
import time
import subprocess
import sys
import os

# Debug: Log script startup
import datetime
with open("tray_debug.log", "a") as f:
    f.write(f"{datetime.datetime.now()} aiemail_tray.py 启动\n")

# # Optional: Initial debug popup
# import ctypes
# ctypes.windll.user32.MessageBoxW(0, "AI邮件托盘已启动", "调试", 1)

LAUNCHER_SCRIPT = "launcher_old.py"
PYTHON_EXEC = sys.executable

CHECK_INTERVAL = 180  # Seconds, auto polling interval

def create_image(color):
    image = Image.new('RGB', (64, 64), color)
    dc = ImageDraw.Draw(image)
    dc.ellipse((16, 16, 48, 48), fill=(255, 255, 255))
    return image

class TrayControl:
    def __init__(self):
        self.pause_event = threading.Event()
        self.pause_until = None
        self.is_running = False
        self.should_exit = False
        self.lock = threading.Lock()

        self.icon = pystray.Icon("AI邮件服务")
        self.icon.icon = create_image('green')
        self.icon.title = "AI邮件服务自动轮询"
        self.icon.menu = pystray.Menu(
            item("立即启动", self.on_run_once),
            item("暂停N分钟", self.on_input_pause_time),
            item("恢复自动运行", self.on_resume),
            item("退出", self.on_exit)
        )
        self.status_thread = threading.Thread(target=self.update_status, daemon=True)
        self.status_thread.start()
        self.worker_thread = threading.Thread(target=self.background_loop, daemon=True)
        self.worker_thread.start()

    def on_run_once(self, icon, item):
        with self.lock:
            if not self.is_running:
                threading.Thread(target=self.run_launcher, daemon=True).start()
            else:
                self.icon.title = "正在运行中，请稍候..."

    def on_resume(self, icon, item):
        self.pause_event.clear()
        self.pause_until = None
        self.icon.icon = create_image('green')
        self.icon.title = "AI邮件服务自动轮询中"

    def on_input_pause_time(self, icon, item):
        import tkinter as tk
        from tkinter.simpledialog import askinteger
        root = tk.Tk()
        root.withdraw()
        minutes = askinteger("暂停", "请输入暂停时长（分钟）：")
        root.destroy()
        if minutes:
            self.pause_event.set()
            self.pause_until = time.time() + minutes * 60
            self.icon.icon = create_image('red')
            self.icon.title = f"已暂停{minutes}分钟"

    def on_exit(self, icon, item):
        self.should_exit = True
        self.icon.stop()
        # Ensure all threads are killed immediately
        os._exit(0)

    def run_launcher(self):
        with self.lock:
            self.is_running = True
            self.icon.icon = create_image('blue')
            self.icon.title = "正在运行分类/转发..."
            try:
                # 👇👇👇 Change: Hide black window
                CREATE_NO_WINDOW = 0x08000000
                subprocess.call(
                    [PYTHON_EXEC, LAUNCHER_SCRIPT, "--uid", "0"],
                    creationflags=CREATE_NO_WINDOW
                )
            except Exception as e:
                print(f"[ERROR] 调用 launcher 出错: {e}")
            self.is_running = False
            self.icon.icon = create_image('green')
            self.icon.title = "AI邮件服务自动轮询中"

    def background_loop(self):
        while not self.should_exit:
            if self.pause_event.is_set():
                time.sleep(5)
                continue
            if not self.is_running:
                threading.Thread(target=self.run_launcher, daemon=True).start()
            for _ in range(int(CHECK_INTERVAL / 2)):
                if self.should_exit or self.pause_event.is_set():
                    break
                time.sleep(2)

    def update_status(self):
        while not self.should_exit:
            # Auto resume
            if self.pause_until and time.time() > self.pause_until:
                self.pause_event.clear()
                self.pause_until = None
                self.icon.icon = create_image('green')
                self.icon.title = "AI邮件服务自动轮询中"
            time.sleep(3)

    def run(self):
        self.icon.run()

if __name__ == "__main__":
    TrayControl().run() 
