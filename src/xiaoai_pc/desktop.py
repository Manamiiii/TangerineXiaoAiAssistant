"""Windows tray and a small Tk settings window. Tk stays on the main thread."""
from copy import deepcopy
from io import BytesIO
import logging
import os
import queue
import re
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from PIL import Image, ImageDraw, ImageTk
import pystray

from . import __version__, config, desktop_services as services, startup
from .desktop_model import Jobs, add_app, add_site
from .runtime import configure_logging

STATES = {"starting": "正在连接音箱…", "listening": "正在监听，可以说指令", "reconnecting": "连接中断，正在自动重连…",
          "auth_required": "登录已失效，请重新扫码", "device_error": "请核对音箱选择或检查设备接口", "stopped": "已停止监听"}


def tray_image():
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((9, 15, 55, 59), fill="#f18430")
    draw.ellipse((29, 3, 48, 18), fill="#4f8d48")
    draw.line((21, 36, 27, 36, 30, 27, 35, 45, 39, 35, 45, 35), fill="white", width=4)
    return image


class QueueLog(logging.Handler):
    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs

    def emit(self, record):
        self.jobs.emit("log", self.format(record))


class Desktop:
    def __init__(self, root, directory, config_path, *, hidden=False, smoke=False):
        self.root, self.directory, self.config_path = root, directory, config_path
        self.data = config.load(config_path)
        self.jobs = Jobs()
        self.closing = False
        self.smoke = smoke
        self.smoke_ok = False
        self.device_ids = []
        self.qr_window = None
        self.qr_photo = None
        self.tray_status = "未开始监听"
        self.buttons = []
        root.title(f"橘子小爱电脑助手 {__version__}")
        root.geometry("820x660")
        root.minsize(740, 600)
        root.option_add("*Font", ("Microsoft YaHei UI", 10))
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        self.status = tk.StringVar(value="先登录并选择音箱，再保存设置、开始监听")
        outer = ttk.Frame(root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="小爱电脑助手", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w")
        ttk.Label(outer, textvariable=self.status, wraplength=750).pack(anchor="w", pady=(8, 14))
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(0, 12))
        self.start_button = self.button(bar, "开始监听", self.start_listener)
        self.stop_button = ttk.Button(bar, text="停止 / 取消", command=self.stop)
        self.stop_button.pack(side="left", padx=(0, 8))
        ttk.Button(bar, text="收起到托盘", command=self.hide).pack(side="right")
        tabs = ttk.Notebook(outer)
        tabs.pack(fill="both", expand=True)
        settings = ttk.Frame(tabs, padding=14)
        commands = ttk.Frame(tabs, padding=14)
        log = ttk.Frame(tabs, padding=10)
        tabs.add(settings, text="连接与设置")
        tabs.add(commands, text="语音命令")
        tabs.add(log, text="运行日志")
        row = ttk.Frame(settings)
        row.pack(fill="x", pady=(0, 12))
        self.button(row, "扫码登录小米", self.login)
        self.button(row, "刷新音箱", self.refresh_devices)
        self.button(row, "检查连接", self.probe)
        ttk.Label(settings, text="使用的音箱").pack(anchor="w")
        self.devices = ttk.Combobox(settings, state="readonly")
        self.devices.pack(fill="x", pady=(4, 12))
        if self.data["xiaomi"]["device_id"]:
            self.device_ids = [self.data["xiaomi"]["device_id"]]
            self.devices["values"] = ["已保存的音箱（刷新列表可查看名称）"]
            self.devices.current(0)
        ttk.Label(settings, text="触发词（多个词用逗号分隔）").pack(anchor="w")
        self.prefix = tk.StringVar(value="，".join(self.data["trigger_prefixes"]))
        ttk.Entry(settings, textvariable=self.prefix).pack(fill="x", pady=(4, 12))
        row = ttk.Frame(settings)
        row.pack(fill="x", pady=(0, 12))
        ttk.Label(row, text="检查新语音的间隔（秒）").pack(side="left")
        self.poll = tk.StringVar(value=str(self.data["poll_interval_seconds"]))
        ttk.Spinbox(row, from_=2, to=60, width=7, textvariable=self.poll).pack(side="left", padx=10)
        self.tts = tk.BooleanVar(value=self.data["tts_reply"])
        ttk.Checkbutton(settings, text="通过音箱播报简短执行结果", variable=self.tts).pack(anchor="w", pady=5)
        self.auto = tk.BooleanVar(value=bool(startup.read()))
        ttk.Checkbutton(settings, text="登录 Windows 后自动启动并监听（保存后生效）", variable=self.auto).pack(anchor="w", pady=5)
        ttk.Label(settings, text="自启仅作用于当前 Windows 账号。移动程序目录后，请重新保存自启设置。",
                  wraplength=700).pack(anchor="w", pady=(2, 10))
        ttk.Label(settings, text="修改后请点击“保存设置”。监听使用已保存的设置；关闭窗口会收起到托盘。",
                  wraplength=700).pack(anchor="w", pady=10)
        self.button(settings, "保存设置", self.save_settings)
        self.tree = ttk.Treeview(commands, columns=("phrase", "action"), show="headings", height=11)
        self.tree.heading("phrase", text="可说的命令示例（前面加触发词）")
        self.tree.heading("action", text="操作")
        self.tree.column("phrase", width=490)
        self.tree.column("action", width=140)
        self.tree.pack(fill="both", expand=True)
        row = ttk.Frame(commands)
        row.pack(fill="x", pady=12)
        self.button(row, "添加网页", self.add_website)
        self.button(row, "添加应用", self.add_application)
        self.button(row, "移除所选", self.remove_command)
        self.button(row, "补入音量 / 锁屏", self.upgrade)
        ttk.Label(commands, text="名称可作为语音别名；同名应用可重新登记路径。更改后到“连接与设置”保存。",
                  wraplength=700).pack(anchor="w")
        self.log = tk.Text(log, state="disabled", wrap="word", height=14, font=("Microsoft YaHei UI", 9))
        self.log.pack(fill="both", expand=True)
        ttk.Button(log, text="打开日志目录", command=lambda: os.startfile(str(directory))).pack(anchor="w", pady=8)
        ttk.Button(outer, text="退出助手", command=self.exit).pack(anchor="e", pady=(12, 0))
        self.refresh_commands()
        configure_logging(directory)
        self.log_handler = QueueLog(self.jobs)
        self.log_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        logging.getLogger("xiaoai_pc").addHandler(self.log_handler)
        menu = pystray.Menu(
            pystray.MenuItem(lambda item: self.tray_status, None, enabled=False),
            pystray.MenuItem("打开设置", lambda icon, item: self.jobs.emit("ui", "show"), default=True),
            pystray.MenuItem("开始监听", lambda icon, item: self.jobs.emit("ui", "start")),
            pystray.MenuItem("停止监听", lambda icon, item: self.jobs.emit("ui", "stop")),
            pystray.MenuItem("退出", lambda icon, item: self.jobs.emit("ui", "exit")),
        )
        self.icon = pystray.Icon("TangerineXiaoAiAssistant", tray_image(), "小爱电脑助手", menu)
        self.tray_ready = threading.Event()
        self.tray_thread = threading.Thread(target=self.run_tray, name="xiaoai-tray", daemon=True)
        self.tray_thread.start()
        root.protocol("WM_DELETE_WINDOW", self.hide)
        root.after(100, self.pump)
        if hidden or smoke:
            root.withdraw()
        if smoke:
            root.after(1500, self.finish_smoke)
        elif hidden:
            root.after(300, self.start_listener)

    def button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=command)
        button.pack(side="left", padx=(0, 8))
        self.buttons.append(button)
        return button

    def run_tray(self):
        try:
            def setup(icon):
                icon.visible = True
                self.tray_ready.set()
            self.icon.run(setup=setup)
        except Exception:
            self.jobs.emit("tray_error", None)

    def set_status(self, text):
        self.status.set(text)
        self.tray_status = text
        if self.tray_ready.is_set():
            try:
                self.icon.title = ("小爱电脑助手 · " + text)[:120]
                self.icon.update_menu()
            except Exception:
                self.tray_ready.clear()
                self.root.deiconify()

    def refresh_commands(self):
        self.tree.delete(*self.tree.get_children())
        labels = {"open_url": "打开网页", "launch_app": "启动应用", "set_volume": "系统音量", "lock": "锁屏"}
        for command in self.data["commands"]:
            phrases = "、".join(command["phrases"]).replace("{level}", "30")
            self.tree.insert("", "end", iid=command["id"], values=(phrases, labels[command["action"]]))

    def draft(self):
        data = deepcopy(self.data)
        data["trigger_prefixes"] = [p.strip() for p in re.split("[,，]", self.prefix.get()) if p.strip()]
        try:
            data["poll_interval_seconds"] = float(self.poll.get())
        except ValueError:
            raise config.ConfigError("轮询间隔请输入 2–60 之间的数字。") from None
        data["tts_reply"] = self.tts.get()
        index = self.devices.current()
        if index >= 0:
            data["xiaomi"]["device_id"] = self.device_ids[index]
        return config.validate(data)

    def save_settings(self):
        if self.jobs.busy:
            return
        try:
            data = self.draft()
            if self.auto.get():
                startup.command_line(self.directory, self.config_path)
            config.save(self.config_path, data)
            self.data = data
        except (config.ConfigError, RuntimeError) as error:
            messagebox.showerror("设置未保存", str(error), parent=self.root)
            return
        except OSError:
            messagebox.showerror("设置未保存", "无法写入配置，请检查目录权限。", parent=self.root)
            return
        try:
            startup.set_enabled(self.auto.get(), self.directory, self.config_path)
            self.set_status("设置已保存，可开始监听")
        except OSError:
            self.set_status("配置已保存，但自启设置未更改；请检查当前账号权限")

    def start_job(self, name, worker):
        if self.closing:
            return
        if self.jobs.start(name, worker):
            self.set_status("正在处理，请稍候…")
            self.update_buttons()

    def login(self):
        self.start_job("login", lambda stop, emit: services.login(self.directory, stop, emit))

    def refresh_devices(self):
        self.start_job("devices", lambda stop, emit: services.devices(self.directory, stop, emit))

    def probe(self):
        try:
            data = config.load(self.config_path)
        except config.ConfigError as error:
            self.set_status(str(error))
            return
        self.start_job("probe", lambda stop, emit: services.probe(self.directory, data, stop, emit))

    def start_listener(self):
        if self.jobs.busy or self.closing:
            return
        try:
            data = config.load(self.config_path)
        except config.ConfigError as error:
            self.set_status(str(error))
            return
        self.start_job("listen", lambda stop, emit: services.listen(self.directory, data, stop, emit))

    def stop(self):
        if self.jobs.busy:
            self.jobs.stop()
            self.set_status("正在停止，等待当前网络请求结束…")

    def show_devices(self, devices):
        devices = [d for d in devices if d.get("deviceID") and d.get("hardware")]
        self.device_ids = [str(d["deviceID"]) for d in devices]
        self.devices["values"] = [f"{d.get('name') or d.get('alias') or '未命名音箱'} ({d['hardware']})" for d in devices]
        saved = self.data["xiaomi"]["device_id"]
        if saved in self.device_ids:
            self.devices.current(self.device_ids.index(saved))
        elif len(devices) == 1:
            self.devices.current(0)
        else:
            self.devices.set("")

    def show_qr(self, data):
        if self.qr_window is not None:
            self.qr_window.destroy()
            self.qr_window = None
            self.qr_photo = None
        if data is None or self.closing:
            return
        try:
            image = Image.open(BytesIO(data))
            if image.width > 1024 or image.height > 1024:
                raise ValueError
            self.qr_photo = ImageTk.PhotoImage(image.resize((300, 300)))
        except Exception:
            self.jobs.stop()
            self.set_status("二维码图片无法显示，请稍后重试")
            return
        self.qr_window = tk.Toplevel(self.root)
        self.qr_window.title("米家 App 扫码登录")
        self.qr_window.resizable(False, False)
        ttk.Label(self.qr_window, image=self.qr_photo).pack(padx=20, pady=15)
        ttk.Label(self.qr_window, text="使用米家 App 扫描，在手机上确认登录").pack(padx=20, pady=(0, 15))
        self.qr_window.protocol("WM_DELETE_WINDOW", self.cancel_login)

    def cancel_login(self):
        self.stop()
        self.show_qr(None)

    def add_application(self):
        path = filedialog.askopenfilename(parent=self.root, title="选择已安装应用的 EXE", filetypes=[("Windows 应用", "*.exe")])
        if not path:
            return
        name = simpledialog.askstring("应用名称", "说“打开什么”来启动它？例如：微信", parent=self.root)
        if name:
            try:
                self.data = add_app(self.data, name, path)
                self.refresh_commands()
            except config.ConfigError as error:
                messagebox.showerror("无法登记", str(error), parent=self.root)

    def add_website(self):
        name = simpledialog.askstring("网页名称", "说“打开什么”来打开它？例如：B站", parent=self.root)
        if not name:
            return
        url = simpledialog.askstring("网页地址", "输入完整的 http:// 或 https:// 地址", parent=self.root)
        if url:
            try:
                self.data = add_site(self.data, name, url.strip())
                self.refresh_commands()
            except config.ConfigError as error:
                messagebox.showerror("无法添加", str(error), parent=self.root)

    def remove_command(self):
        selected = set(self.tree.selection())
        self.data["commands"] = [c for c in self.data["commands"] if c["id"] not in selected]
        self.refresh_commands()

    def upgrade(self):
        try:
            self.data, _ = config.add_local_commands(self.data)
            self.refresh_commands()
        except config.ConfigError as error:
            messagebox.showerror("无法补入规则", str(error), parent=self.root)

    def update_buttons(self):
        for button in self.buttons:
            button["state"] = "disabled" if self.jobs.busy or self.closing else "normal"
        self.stop_button["state"] = "normal" if self.jobs.busy and not self.closing else "disabled"

    def pump(self):
        try:
            while True:
                kind, value = self.jobs.events.get_nowait()
                if kind == "ui":
                    {"show": self.show, "start": self.start_listener, "stop": self.stop, "exit": self.exit}[value]()
                elif kind in ("status", "error") and not self.closing:
                    self.set_status(value)
                elif kind == "bridge_state" and not self.closing:
                    self.set_status(STATES.get(value, value))
                elif kind == "devices":
                    self.show_devices(value)
                elif kind == "qr":
                    self.show_qr(value)
                elif kind == "finished" and self.jobs.cancel.is_set() and not self.closing:
                    self.set_status("已停止，可以调整设置或重新开始")
                elif kind == "tray_error":
                    self.tray_ready.clear()
                    self.root.deiconify()
                    self.set_status("托盘未能启动，请保持窗口打开或退出重试")
                elif kind == "log":
                    self.log["state"] = "normal"
                    self.log.insert("end", value + "\n")
                    if int(self.log.index("end-1c").split(".")[0]) > 150:
                        self.log.delete("1.0", "2.0")
                    self.log.see("end")
                    self.log["state"] = "disabled"
        except queue.Empty:
            pass
        except Exception:
            # Keep draining future events even if a widget update fails.
            self.set_status("界面更新未完成，请停止后重试")
        self.update_buttons()
        if self.closing and not self.jobs.busy:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.tray_thread.join(timeout=3)
            logging.getLogger("xiaoai_pc").removeHandler(self.log_handler)
            self.root.destroy()
            return
        self.root.after(150, self.pump)

    def hide(self):
        if self.tray_ready.is_set():
            self.root.withdraw()
        else:
            self.set_status("托盘尚未就绪，请稍候再收起")

    def show(self):
        self.root.deiconify()
        self.root.lift()

    def exit(self):
        self.closing = True
        self.jobs.stop()
        self.show_qr(None)
        self.set_status("正在退出，等待当前连接结束…")
        self.update_buttons()

    def finish_smoke(self):
        self.smoke_ok = self.tray_ready.is_set() and self.icon.visible and bool(self.tree.get_children())
        self.exit()


def run(directory, config_path, *, hidden=False, smoke=False):
    if not config_path.exists():
        config.save(config_path, deepcopy(config.DEFAULT_CONFIG))
    root = tk.Tk()
    app = Desktop(root, directory, config_path, hidden=hidden, smoke=smoke)
    root.report_callback_exception = lambda *_: app.set_status("操作未完成，请检查设置后重试")
    root.mainloop()
    return (0 if app.smoke_ok else 2) if smoke else 0
