import psutil
import tkinter as tk
from tkinter import ttk, messagebox
import json
import threading
import time
import subprocess
import os
import re
import unicodedata
import traceback
import sys
import multiprocessing
from typing import Optional, Dict, Any

# ============================================================================
# إخفاء نافذة الأوامر وإيقاف جميع رسائل الطباعة
# ============================================================================
if sys.platform.startswith("win"):
    try:
        import ctypes
        # إخفاء نافذة الكونسول إذا كانت مفتوحة
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except Exception:
        pass

# إعادة توجيه stdout و stderr إلى null لإيقاف جميع رسائل الطباعة
try:
    _devnull = open(os.devnull, 'w', encoding='utf-8')
    sys.stdout = _devnull
    sys.stderr = _devnull
except Exception:
    pass


from Manager_Json import BotDataManager, extract_device_mapping, extract_instance_numbers, extract_instance_names 
from Power_1 import run_Power_manager1
from Correct import run_Correct_manager1

# ============================================================================
# إعدادات Supabase
# ============================================================================
_BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
_CONFIG_FILE     = os.path.join(_BASE_DIR, "supabase_gui_config.json")
_BOT_DATA_DIR    = os.path.join(_BASE_DIR, "bot_data")

SUPABASE_URL     = "https://api.ibraabot.online"    # ← عدّل حسب مشروعك
SUPABASE_KEY     = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJzdXBhYmFzZSIsImlhdCI6MTc3NTE1MTI0MCwiZXhwIjo0OTMwODI0ODQwLCJyb2xlIjoic2VydmljZV9yb2xlIn0.l6g3dwSSv0gK2Ut0PEEgXj7KSGkmXjZXh66zl7KL8IM"  # ← عدّل
ACCOUNTS_PER_EMULATOR = 13
AUTO_FETCH_INTERVAL   = 3600  # ثانية (= ساعة)


def _sb_load_config() -> dict:
    try:
        if os.path.exists(_CONFIG_FILE):
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"server_index": 1}


def _sb_save_config(data: dict):
    try:
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _sb_client():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _sb_check_and_reset_is_change(server_index: int) -> bool:
    """
    يفحص Is_Change في جدول Changes للصف  SERVER_NUM = server_index.
    True  → يُعيدها False ويُرجع True  (يجب الجلب)
    False → يُرجع False               (لا جلب)
    """
    try:
        client = _sb_client()
        resp = client.table("Changes").select("*").eq("SERVER_NUM", server_index).execute()
        rows = resp.data
        if not rows:
            return False
        if rows[0].get("Is_Change", False):
            client.table("Changes").update({"Is_Change": False}).eq("SERVER_NUM", server_index).execute()
            return True
        return False
    except Exception as e:
        print(f"[IS_CHANGE] {e}")
        return False


def _sb_fetch_accounts(server_index: int):
    """يجلب الحسابات: index_server=server_index AND Is_OK=true"""
    try:
        client = _sb_client()
        resp = (
            client.table("Accounts")
            .select("*")
            .eq("index_server", server_index)
            .eq("Is_OK", True)
            .order("created_at")
            .execute()
        )
        return resp.data if resp.data else []
    except Exception as e:
        return {"error": str(e)}


def _sb_to_village(account: dict) -> dict:
    """يحوّل صف Supabase إلى بنية القرية (ملفات JSON)"""
    collect = account.get("Collect_resources") or {}
    if isinstance(collect, dict):
        options = [
            bool(collect.get("wood",    False)),
            bool(collect.get("wheat",   False)),
            bool(collect.get("coal",    False)),
            bool(collect.get("diamond", False)),
        ]
    elif isinstance(collect, list) and len(collect) >= 4:
        options = [bool(v) for v in collect[:4]]
    else:
        options = [True, True, True, True]

    attack     = account.get("Attack resources") or {}
    # القيم العربية الصحيحة المقبولة في ملفات JSON
    valid_arabic = {"خشب", "قمح", "فحم", "ألماس"}
    # خريطة إنجليزي → عربي (للتوافق مع الشكل القديم dict)
    attack_map = {"wood": "خشب", "wheat": "قمح", "coal": "فحم", "diamond": "ألماس"}
    if isinstance(attack, dict):
        # الشكل القديم: {"wood": true, "diamond": true, ...}
        attauck = [attack_map[k] for k, v in attack.items() if v and k in attack_map]
    elif isinstance(attack, list):
        # البيانات تأتي مباشرةً كقائمة عربية: ["ألماس", "خشب", ...]
        attauck = [v for v in attack if v in valid_arabic]
    else:
        attauck = []

    return {
        "email"      : account.get("Email", ""),
        "password"   : account.get("password", ""),
        "options"    : options,
        "Attauck"    : attauck,
        "custom_flag": bool(account.get("Protection", False)),
        "Troops"     : bool(account.get("Troops",     False)),
        "Not_Store"  : bool(account.get("Not_store",  False)),
    }


def _sb_get_json_path(bot_index: int) -> str:
    return os.path.join(_BOT_DATA_DIR, f"bot_{bot_index}_villages.json")


def _sb_load_json(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("account_index", 1)
            data.setdefault("save_counter",  1)
            data.setdefault("villages",      [])
            return data
        except Exception:
            pass
    return {"villages": [], "account_index": 1, "save_counter": 1}


def _sb_save_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _sb_existing_bot_files() -> list:
    bots = []
    if not os.path.exists(_BOT_DATA_DIR):
        return bots
    for fname in os.listdir(_BOT_DATA_DIR):
        if fname.startswith("bot_") and fname.endswith("_villages.json"):
            try:
                bots.append(int(fname.split("_")[1]))
            except Exception:
                pass
    return sorted(bots)


def _sb_apply_accounts(accounts: list) -> list:
    """
    يوزع 12 حساباً على كل ملف JSON.
    الملفات الموجودة على القرص خارج النطاق تُفرَّغ تلقائياً.
    يُرجع [(bot_idx, count), ...]
    """
    # بناء الخريطة
    by_bot = {}
    for i, acc in enumerate(accounts):
        bot_idx = (i // ACCOUNTS_PER_EMULATOR) + 1
        by_bot.setdefault(bot_idx, []).append(acc)

    existing = _sb_existing_bot_files()
    max_idx  = max(list(by_bot.keys()) + existing) if (by_bot or existing) else 0
    results  = []

    for bot_idx in range(1, max_idx + 1):
        path     = _sb_get_json_path(bot_idx)
        existing_data = _sb_load_json(path)
        if bot_idx in by_bot:
            existing_data["villages"] = [_sb_to_village(a) for a in by_bot[bot_idx]]
        else:
            existing_data["villages"] = []        # تفريغ الملفات الزائدة
        _sb_save_json(path, existing_data)
        results.append((bot_idx, len(existing_data["villages"])))

    return results

# ------------------------------------------------------------
# Windows DPI Awareness to prevent cursor/UI offset on scaling
# ------------------------------------------------------------
if sys.platform.startswith("win"):
    try:
        import ctypes
        try:
            # Per-monitor DPI awareness (Windows 8.1+)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            # Fallback for older Windows
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    except Exception:
        pass

power_path = os.path.abspath(os.path.dirname(__file__))
if power_path not in sys.path:
    sys.path.insert(0, power_path)

BotInterface = Any 


# ============================================================================
# ثوابت الواجهة
# ============================================================================

NUM_EMULATORS = 15

# ألوان الوضعين
LIGHT_THEME = {
    'BG_COLOR': "#f4f6fb",
    'FRAME_COLOR': "#ffffff",
    'HEADER_COLOR': "#2d3e50",
    'BTN_GREEN': "#27ae60",
    'BTN_BLUE': "#3498db",
    'BTN_RED': "#e74c3c",
    'LABEL_FONT': ("Cairo", 11),
    'HEADER_FONT': ("Cairo", 13, "bold"),
    'COLUMN_HEADER_FONT': ("Cairo", 11, "bold"),
    'ICON_OK': '✅',
    'ICON_ERR': '❌',
    'ICON_WARN': '⚠️',
    'ICON_WAIT': '⏳',
}
DARK_THEME = {
    'BG_COLOR': "#23272e",
    'FRAME_COLOR': "#2d313a",
    'HEADER_COLOR': "#eaeaea",
    'BTN_GREEN': "#27ae60",
    'BTN_BLUE': "#2980b9",
    'BTN_RED': "#e74c3c",
    'LABEL_FONT': ("Cairo", 11),
    'HEADER_FONT': ("Cairo", 13, "bold"),
    'COLUMN_HEADER_FONT': ("Cairo", 11, "bold"),
    'ICON_OK': '✅',
    'ICON_ERR': '❌',
    'ICON_WARN': '⚠️',
    'ICON_WAIT': '⏳',
}

# كلمات افتراضية لكل حالة
DEFAULT_PORT = "غير محدد"
DEFAULT_WINDOW = "مغلقة"
DEFAULT_BOT = "متوقف"
DEFAULT_ERROR = "لا يوجد"
DEFAULT_UPTIME = "00:00:00"

COLUMNS = [
    ("", 4),
    ("اسم المحاكي", 12),
    ("المنفذ", 12),
    ("حالة النافذة", 16),
    ("حالة البوت", 14),
    ("مدة التشغيل", 14),
]

Contact_PORT = extract_instance_names()

number_instance = extract_instance_numbers()

MAIN_PORTS = extract_device_mapping()
# قائمة المنافذ لكل محاكي
EMULATOR_PORTS = list(MAIN_PORTS.values())

LDCONSOLE_PATH = r"C:\Program Files\BlueStacks_nxt\HD-Player.exe"  # تم التعديل حسب طلب المستخدم

class Toast(tk.Toplevel):
    def __init__(self, master, message, duration=2000):
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(bg="#222")
        label = tk.Label(self, text=message, bg="#222", fg="#fff", font=("Cairo", 10, "bold"), padx=16, pady=8)
        label.pack()
        self.after(duration, self.destroy)
        self.update_idletasks()
        x = master.winfo_rootx() + master.winfo_width() - self.winfo_width() - 40
        y = master.winfo_rooty() + master.winfo_height() - self.winfo_height() - 80
        self.geometry(f"+{x}+{y}")

class EmulatorRow:
    def __init__(self, master, idx, on_select, theme, on_start_bot, on_pause_resume_bot, on_stop_bot, get_bot_status):
        self.idx = idx
        self.selected = tk.BooleanVar()
        self.theme = theme
        self.port = EMULATOR_PORTS[idx] if idx < len(EMULATOR_PORTS) else DEFAULT_PORT
        self.is_open = False  # حالة النافذة (مفتوحة/مغلقة)
        self.checkbox = ttk.Checkbutton(master, variable=self.selected, command=on_select)
        if len(number_instance) > idx:
            self.name_label = ttk.Label(master, text= f"BlueStacks {number_instance[idx]}", font=theme['LABEL_FONT'], width=12)
        else:
            self.name_label = ttk.Label(master, text= f"BlueStacks", font=theme['LABEL_FONT'], width=12)

        self.port_label = ttk.Label(master, text=f"{self.port}", font=theme['LABEL_FONT'], width=12, foreground="#888")
        self.window_status = ttk.Label(master, text=f"{theme['ICON_ERR']} {DEFAULT_WINDOW}", font=theme['LABEL_FONT'], width=16, foreground="#e67e22")
        self.bot_status = ttk.Label(master, text=f"{theme['ICON_ERR']} {DEFAULT_BOT}", font=theme['LABEL_FONT'], width=14, foreground="#e74c3c")
        
        self.uptime_label = ttk.Label(master, text=f"{DEFAULT_UPTIME}", font=theme['LABEL_FONT'], width=14, foreground="#2980b9")
        # Bot control buttons
        self.start_bot_btn = tk.Button(master, text="تشغيل البوت", bg=theme['BTN_GREEN'], fg="white", font=theme['LABEL_FONT'], width=14, command=lambda port=self.port: on_start_bot(port))
        self.pause_resume_btn = tk.Button(master, text="إيقاف مؤقت", bg="#f1c40f", fg="#222", font=theme['LABEL_FONT'], width=10, command=lambda port=self.port: on_pause_resume_bot(port))
        self.stop_bot_btn = tk.Button(master, text="إيقاف نهائي", bg=theme['BTN_RED'], fg="white", font=theme['LABEL_FONT'], width=10, command=lambda port=self.port: on_stop_bot(port))
        self.get_bot_status = get_bot_status
        self.widgets = [self.checkbox, self.name_label, self.port_label, self.window_status, self.bot_status, self.uptime_label, self.start_bot_btn, self.pause_resume_btn, self.stop_bot_btn]

    def grid(self, master, row):
        for col, widget in enumerate(self.widgets):
            widget.grid(row=row, column=col, padx=4, pady=2, sticky="nsew")
    def is_selected(self):
        return self.selected.get()
    def update_theme(self, theme):
        self.theme = theme
        for widget in self.widgets:
            widget.config(font=theme['LABEL_FONT'])
            
    def set_open(self, is_open):
        self.is_open = is_open
        if is_open:
            self.window_status.config(text=f"{self.theme['ICON_OK']} مفتوحة", foreground="#27ae60")
        else:
            self.window_status.config(text=f"{self.theme['ICON_ERR']} مغلقة", foreground="#e67e22")
    def update_bot_status(self, status):
        if status is None or not status.get('is_running', False):
            self.bot_status.config(text=f"{self.theme['ICON_ERR']} متوقف", foreground="#e74c3c")
            self.pause_resume_btn.config(state="disabled")
            self.stop_bot_btn.config(state="disabled")
            self.start_bot_btn.config(state="normal")
        elif status.get('paused', False):
            self.bot_status.config(text=f"{self.theme['ICON_WARN']} متوقف مؤقتًا", foreground="#e67e22")
            self.pause_resume_btn.config(text="استئناف", state="normal")
            self.stop_bot_btn.config(state="normal")
            self.start_bot_btn.config(state="disabled")
        else:
            self.bot_status.config(text=f"{self.theme['ICON_OK']} يعمل", foreground="#27ae60")
            self.pause_resume_btn.config(text="إيقاف مؤقت", state="normal")
            self.stop_bot_btn.config(state="normal")
            self.start_bot_btn.config(state="disabled")

class UpdateIndicator(tk.Canvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, width=18, height=18, highlightthickness=0, **kwargs)
        self.oval = self.create_oval(4, 4, 14, 14, fill="#27ae60", outline="")
        self.hide()
    def show(self):
        self.itemconfig(self.oval, state='normal')
        self.after(700, self.hide)
    def hide(self):
        self.itemconfig(self.oval, state='hidden')

class BotVillageComponent(tk.Frame):
    def __init__(self, master, idx, on_delete, on_edit, is_bot_running_func, bg_color, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.idx = idx
        self.email_var = tk.StringVar()
        self.pass_var = tk.StringVar()
        self.show_pass_var = tk.BooleanVar(value=False)
        self.check_vars = [tk.BooleanVar() for _ in range(4)]
        self.attack_types = ["خشب", "قمح", "فحم", "ألماس"]
        self.attack_vars = [tk.BooleanVar() for _ in range(4)]
        self.is_bot_running_func = is_bot_running_func
        
        self.custom_flag = tk.BooleanVar(value=False)
        self.Troops = tk.BooleanVar(value=False)
        self.Not_Store = tk.BooleanVar(value=False)
        
        self.bg_color = bg_color
        self.configure(bg=self.bg_color)
        
        # رقم الصف
        tk.Label(self, text=str(self.idx + 1), bg=self.bg_color).grid(row=0, column=0, padx=(4, 8), pady=2, rowspan=2, sticky="n")
        
        tk.Label(self, text=f"البريد الإلكتروني:", bg=self.bg_color).grid(row=0, column=1, padx=2, pady=2)
        tk.Entry(self, textvariable=self.email_var, width=28).grid(row=0, column=2, padx=2, pady=2)
        tk.Label(self, text=f"كلمة السر:", bg=self.bg_color).grid(row=0, column=3, padx=2, pady=2)
        self.pass_entry = tk.Entry(self, textvariable=self.pass_var, width=20)
        self.pass_entry.grid(row=0, column=4, padx=2, pady=2)
        self.show_pass_cb = tk.Checkbutton(self, text="إظهار كلمة السر", variable=self.show_pass_var, command=self.toggle_password_visibility, bg=self.bg_color, activebackground=self.bg_color)
        self.show_pass_cb.grid(row=0, column=5, padx=2)
        option_labels = ["خشب", "قمح", "فحم", "الماس"]
        for i in range(4):
            tk.Checkbutton(self, text=option_labels[i], variable=self.check_vars[i], bg=self.bg_color, activebackground=self.bg_color).grid(row=0, column=6+i, padx=1)
       
        self.flag_cb = tk.Checkbutton(self, text="Protection", variable=self.custom_flag, bg=self.bg_color, activebackground=self.bg_color)
        self.flag_cb.grid(row=0, column=13, padx=4)  
        
        self.flag_cb2 = tk.Checkbutton(self, text="Troops", variable=self.Troops, bg=self.bg_color, activebackground=self.bg_color)
        self.flag_cb2.grid(row=0, column=23, padx=4)
        
        self.flag_cb3 = tk.Checkbutton(self, text="Not_Store", variable=self.Not_Store, bg=self.bg_color, activebackground=self.bg_color)
        self.flag_cb3.grid(row=0, column=24, padx=4) 
        # خيارات نوعية القرى للهجوم
        tk.Label(self, text="أنواع القرى للهجوم:", bg=self.bg_color).grid(row=1, column=1, padx=2, pady=2)
        for i in range(4):
            cb = tk.Checkbutton(self, text=self.attack_types[i], variable=self.attack_vars[i], command=self._limit_attack_selection, bg=self.bg_color, activebackground=self.bg_color)
            cb.grid(row=1, column=2+i, padx=1, sticky="w")
        self.delete_btn = tk.Button(self, text="حذف", command=lambda: on_delete(self), bg="#e74c3c", fg="white", relief='flat', borderwidth=2)
        self.delete_btn.grid(row=0, column=10, padx=4)
        self.edit_btn = tk.Button(self, text="تعديل", command=lambda: on_edit(self), bg="#f1c40f", fg="#222", relief='flat', borderwidth=2)
        self.edit_btn.grid(row=0, column=11, padx=4)
        self.update_edit_state()
    def toggle_password_visibility(self):
        if self.show_pass_var.get():
            self.pass_entry.config(show='')
        else:
            self.pass_entry.config(show='*')
    def _limit_attack_selection(self):
        # لا يسمح باختيار أكثر من نوعين
        selected = [i for i, v in enumerate(self.attack_vars) if v.get()]
        if len(selected) > 2:
            # ألغِ آخر اختيار
            self.attack_vars[selected[-1]].set(False)
    def get_data(self):
        return {
            "email": self.email_var.get(),
            "password": self.pass_var.get(),
            "options": [v.get() for v in self.check_vars],
            "Attauck": [self.attack_types[i] for i, v in enumerate(self.attack_vars) if v.get()],
            "custom_flag": self.custom_flag.get() ,  # ✅ حفظ قيمة الـ CheckBox
            "Troops": self.Troops.get(),   # ✅ حفظ قيمة الـ CheckBox
            "Not_Store": self.Not_Store.get()   # ✅ حفظ قيمة الـ CheckBox الجديد
        }
    def set_data(self, data):
        self.email_var.set(data.get("email", ""))
        self.pass_var.set(data.get("password", ""))
        for i, v in enumerate(data.get("options", [False]*4)):
            if i < 4:
                self.check_vars[i].set(v)
        # استرجاع أنواع القرى للهجوم
        att_list = data.get("Attauck", [])
        for i, t in enumerate(self.attack_types):
            self.attack_vars[i].set(t in att_list)

        self.custom_flag.set(data.get("custom_flag", False))
        self.Troops.set(data.get("Troops", False))
        self.Not_Store.set(data.get("Not_Store", False))
        
    def update_edit_state(self):
        # تعطيل زر التعديل إذا كان البوت يعمل
        if self.is_bot_running_func():
            self.edit_btn.config(state="disabled")
        else:
            self.edit_btn.config(state="normal")

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.sleep_mode = False
        self.theme = DARK_THEME  # النمط الليلي افتراضي
        self.title("واجهة إدارة بوتات")
        self.geometry("1150x700")
        self.minsize(400, 300)
        self.configure(bg=self.theme['BG_COLOR'])
        self.style = ttk.Style(self)
        self._customize_style()
        self.emulator_rows = []
        self.filtered_indices = list(range(NUM_EMULATORS))
        self.bot_tabs = []
        self.bot_villages = []  # لكل بوت قائمة بالمكونات
        self.integrated_bots: list[Optional[BotInterface]] = [None] * NUM_EMULATORS
        self.bot_threads: list[Optional[threading.Thread]] = [None] * NUM_EMULATORS
        self.speed_var = tk.StringVar(value="عادي")
        self.speed_options = {
            "سريع جدًا": 0.2,
            "سريع": 0.5,
            "عادي": 1.0,
            "بطيء": 2.0
        }
        self.bot_start_times: list[Optional[float]] = [None] * NUM_EMULATORS  # وقت بدء كل بوت
        self.bot_elapsed_times: list[int] = [0] * NUM_EMULATORS  # مجموع الثواني المنقضية لكل بوت
        self.bot_processes = [None] * NUM_EMULATORS  # قائمة العمليات لكل بوت
        self.bot_clicked_flags = [False] * NUM_EMULATORS  # لكل بوت فلاغ منطقي
        # Flags/timestamps for Fire_Stages logic
        self.user_stopped_flags = [False] * NUM_EMULATORS  # True if user clicked stop
        self.last_correct_stages_call = [0.0] * NUM_EMULATORS  # timestamp of last Correct_Stages call
        self.last_correct_stages_check = [0.0] * NUM_EMULATORS  # timestamp of last Correct_Stages check
        self.last_fire_stages_call = [0.0] * NUM_EMULATORS  # timestamp of last Fire_Stages call
        # منع تكرار فحوصات Correct_Stages المؤجلة لكل بوت
        self.pending_correct_checks = [False] * NUM_EMULATORS
        
        # تحسينات الأداء - cache للحالات
        self._status_cache = [None] * NUM_EMULATORS  # cache للحالات
        self._last_status_check = [0.0] * NUM_EMULATORS  # آخر فحص للحالة
        self._status_cache_ttl = 2.0  # 2 ثانية cache للحالة

        # ── Supabase ──
        self._sb_cfg = _sb_load_config()

        self._build_ui()

        self._start_auto_update()
        self._start_uptime_updater()  # تحديث مدة التشغيل كل ثانية
        # تم إلغاء جدولة إعادة التشغيل التلقائية كل 10 ساعات
        self.protocol("WM_DELETE_WINDOW", self._on_app_close)
        self._search_job = None
        self._search_results_map = []  # [(bot_idx, row_index_0based, email)]

        # ── بدء دورة المراقبة التلقائية لـ Supabase ──
        threading.Thread(target=self._sb_auto_fetch_loop, daemon=True).start()
        try:
            # Ensure Tk scaling is consistent to avoid pointer drift
            # 1.0 means 1 pixel per point; Tk adjusts internally for DPI-aware processes
            self.tk.call('tk', 'scaling', 1.0)
        except Exception:
            pass
        try:
            self.state('zoomed')  # تكبير النافذة تلقائيًا عند الفتح
        except:
            try:
                self.attributes('-zoomed', True)
            except:
                self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")

    def toggle_sleep_mode(self):
        self.sleep_mode = not self.sleep_mode
        if self.sleep_mode:
            # ✅ تفعيل وضع السكون داخل النافذة نفسها (وليس كنافذة منفصلة)
            self.sleep_overlay = tk.Frame(self, bg="#2c3e50")
            self.sleep_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

            # شعار النوم
            sleep_label = tk.Label(
                self.sleep_overlay,
                text="😴 وضع السكون مفعل",
                font=("Cairo", 36, "bold"),
                fg="white", bg="#2c3e50"
            )
            sleep_label.pack(expand=True)

            # زر إلغاء السكون
            exit_btn = tk.Button(
                self.sleep_overlay,
                text="🚀 إلغاء وضع السكون",
                command=self.toggle_sleep_mode,
                font=("Cairo", 14, "bold"),
                bg="#27ae60", fg="white", padx=20, pady=10
            )
            exit_btn.pack(pady=30)

            self.show_toast("✅ تم تفعيل وضع السكون")

        else:
            # ❌ إلغاء السكون
            if hasattr(self, "sleep_overlay") and self.sleep_overlay.winfo_exists():
                self.sleep_overlay.destroy()
            self.show_toast("❌ تم إلغاء وضع السكون")


    def Correct_Stages(self, idx):
        """
        هذه الدالة ستُنفذ تلقائيا إذا كان:
        1- النافذة مغلقة
        2- زر تشغيل البوت تم النقر عليه
        """
        row = self.emulator_rows[idx]
        device_id = row.port   # هذا هو المنفذ (device_id)

        self.show_toast(f"✅ Correct_Stages تعمل على LDPlayer-{idx+1}")

        try:
            # 1- إيقاف البوت
            self._stop_integrated_bot(device_id)
            time.sleep(2)

            self._close_emulator_instance(idx)
            time.sleep(4)

            self._open_emulator_instance(idx)

            time.sleep(8)
            self._Contact_emulator_instance(idx)
            # 2- تشغيل البوت من جديد
            time.sleep(5)
            
            p = multiprocessing.Process(target=run_Correct_manager1, args=(device_id,))
            p.daemon = True
            p.start()

            self.bot_clicked_flags[idx] = True
            self.bot_processes[idx] = p
            self.bot_start_times[idx] = time.time()
            self.last_correct_stages_call[idx] = time.time()
            # منع استدعاء Correct_Stages مباشرة بعد التشغيل
            self.last_correct_stages_check[idx] = time.time()
            self._clear_status_cache(idx)  # مسح cache عند إعادة تشغيل البوت
            self.show_toast(f"تم تشغيل البوت على BlueStacks-{idx+1}")
            self._update_emulator_row_status(idx)




        except Exception as e:
            self.show_toast(f"❌ خطأ أثناء Correct_Stages للبوت {idx+1}: {e}")
            print(f"[DEBUG] خطأ في Correct_Stages: {e}")


    def _customize_style(self):
        self.style.theme_use('clam')
        self.style.configure("TFrame", background=self.theme['BG_COLOR'])
        self.style.configure("Card.TFrame", background=self.theme['FRAME_COLOR'], relief="raised", borderwidth=1)
        self.style.configure("TLabel", background=self.theme['FRAME_COLOR'], font=self.theme['LABEL_FONT'])
        self.style.configure("Header.TLabel", background=self.theme['BG_COLOR'], foreground=self.theme['HEADER_COLOR'], font=self.theme['HEADER_FONT'])
        self.style.configure("ColumnHeader.TLabel", background=self.theme['BG_COLOR'], foreground=self.theme['HEADER_COLOR'], font=self.theme['COLUMN_HEADER_FONT'])
        self.style.configure("TButton", font=self.theme['LABEL_FONT'], padding=6)
        self.style.map("TButton",
            background=[('active', '#d5dbdb')],
            foreground=[('active', self.theme['HEADER_COLOR'])])
    def _build_ui(self):
        # شريط الإحصائيات
        self.stats_frame = ttk.Frame(self, style="TFrame")
        self.sleep_btn = tk.Button(
        self.stats_frame, 
        text="😴 وضع السكون", 
        command=self.toggle_sleep_mode, 
        bg="#f39c12", fg="white", 
        font=("Cairo", 10, "bold"),
        relief='flat', borderwidth=2)
        self.sleep_btn.pack(side="left", padx=8)
        self.stats_frame.pack(fill="x", padx=10, pady=(10, 0))
        self.stats_label = ttk.Label(self.stats_frame, text="", font=self.theme['HEADER_FONT'], foreground=self.theme['HEADER_COLOR'], background=self.theme['BG_COLOR'])
        self.stats_label.pack(side="right", anchor="w")
        # مؤشر التحديث
        self.update_indicator = UpdateIndicator(self.stats_frame)
        self.update_indicator.pack(side="left", padx=8)
        # مربع البحث + زر الفلتر
        search_frame = ttk.Frame(self, style="TFrame")
        search_frame.pack(fill="x", padx=10, pady=(0, 0))
        
        self.search_var = tk.StringVar()
        # إلغاء الربط السابق بالصفوف
        # self.search_var.trace_add('write', self._on_search_change)
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, font=self.theme['LABEL_FONT'], width=24,
                                    relief='flat', borderwidth=2, highlightthickness=1, highlightbackground="#d0d7e2", bg="#f8fafc")
        self.search_entry.pack(side="right", padx=4, ipady=4)
        self.search_entry.configure(insertbackground="#222")
        self.search_entry.bind("<Return>", lambda e: self._search_email_in_jsons())
        
        search_btn = tk.Button(search_frame, text="بحث", command=self._search_email_in_jsons,
                               bg=self.theme['BTN_BLUE'], fg="white", font=("Cairo", 10, "bold"),
                               relief='flat', borderwidth=2, highlightthickness=0)
        search_btn.pack(side="right", padx=(4, 8))
        
        # إطار نتائج البحث أسفل شريط البحث مباشرة
        self.search_results_frame = ttk.Frame(search_frame, style="TFrame")
        self.search_results_frame.pack(side="right", padx=(8, 0), pady=(4, 8), anchor="ne")
        self.search_results_list = tk.Listbox(
            self.search_results_frame,
            height=4,
            width=60,
            activestyle='dotbox',
            bg="#000000",
            fg="#00d5ff",
            selectbackground="#111827",
            selectforeground="#ffffff",
            highlightthickness=0,
            relief='flat'
        )
        self.search_results_list.configure(font=self.theme['LABEL_FONT'])
        self.search_results_list.pack()
        self.search_results_list.bind('<Double-Button-1>', lambda e: self._activate_search_result())
        

        # سجل الأحداث (Logs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=8)
        self.main_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="لوحة التحكم")

        # ── تبويب واحد لجميع الحسابات (بدلاً من 15 تبويب) ──
        self.accounts_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.accounts_tab, text="📋 الحسابات")

        # Canvas + Scrollbar رأسي وأفقي للصفحة الموحدة
        acc_canvas = tk.Canvas(self.accounts_tab, highlightthickness=0, bg=self.theme['BG_COLOR'])
        acc_v_scroll = tk.Scrollbar(self.accounts_tab, orient="vertical", command=acc_canvas.yview)
        acc_h_scroll = tk.Scrollbar(self.accounts_tab, orient="horizontal", command=acc_canvas.xview)
        acc_canvas.configure(yscrollcommand=acc_v_scroll.set, xscrollcommand=acc_h_scroll.set)

        acc_h_scroll.pack(side="bottom", fill="x")
        acc_v_scroll.pack(side="right", fill="y")
        acc_canvas.pack(side="left", fill="both", expand=True)

        self._accounts_inner = tk.Frame(acc_canvas, bg=self.theme['BG_COLOR'])
        self._accounts_inner_id = acc_canvas.create_window((0, 0), window=self._accounts_inner, anchor="nw")
        self._accounts_canvas = acc_canvas

        def _on_acc_frame_cfg(event):
            acc_canvas.configure(scrollregion=acc_canvas.bbox("all"))
        self._accounts_inner.bind("<Configure>", _on_acc_frame_cfg)

        def _on_acc_canvas_cfg(event):
            if self._accounts_inner.winfo_reqwidth() < acc_canvas.winfo_width():
                acc_canvas.itemconfig(self._accounts_inner_id, width=acc_canvas.winfo_width())
        acc_canvas.bind("<Configure>", _on_acc_canvas_cfg)

        # بناء قسم لكل محاكي داخل الصفحة الموحدة
        self._bot_section_frames = []  # إطارات أقسام البوتات
        for i in range(NUM_EMULATORS):
            # إطار القسم الرئيسي
            section = tk.LabelFrame(
                self._accounts_inner,
                text=f"  📱 بوت {i+1}  ",
                font=("Cairo", 11, "bold"),
                bg=self.theme['BG_COLOR'],
                fg=self.theme['HEADER_COLOR'],
                relief="groove", bd=2,
                padx=5, pady=5
            )
            section.pack(fill="x", padx=10, pady=(8, 2))
            self._bot_section_frames.append(section)

            # إطار الحسابات داخل القسم
            villages_frame = tk.Frame(section, bg=self.theme['BG_COLOR'])
            villages_frame.pack(fill="x", expand=True)

            # شريط أزرار لكل بوت
            btn_bar = tk.Frame(section, bg=self.theme['BG_COLOR'])
            btn_bar.pack(fill="x", pady=(4, 2))

            tk.Button(btn_bar, text="➕ اضف قرية",
                      command=lambda idx=i: self.add_village(idx),
                      bg="#10b981", fg="white", font=("Cairo", 9, "bold"),
                      relief='flat', borderwidth=1).pack(side="left", padx=2)

            tk.Button(btn_bar, text="💾 حفظ",
                      command=lambda idx=i: self.save_villages(idx),
                      bg="#3b82f6", fg="white", font=("Cairo", 9, "bold"),
                      relief='flat', borderwidth=1).pack(side="left", padx=2)

            tk.Button(btn_bar, text="💾 حفظ بدون تغيير",
                      command=lambda idx=i: self.save_villages_preserve_index(idx),
                      bg="#6366f1", fg="white", font=("Cairo", 9, "bold"),
                      relief='flat', borderwidth=1).pack(side="left", padx=2)

            tk.Button(btn_bar, text="🔄 تحديث",
                      command=lambda idx=i: self._update_bot_interface(idx),
                      bg="#f59e0b", fg="white", font=("Cairo", 9, "bold"),
                      relief='flat', borderwidth=1).pack(side="left", padx=2)

            tk.Button(btn_bar, text="🗑 حذف الكل",
                      command=lambda idx=i: self.delete_all_villages(idx),
                      bg="#e74c3c", fg="white", font=("Cairo", 9, "bold"),
                      relief='flat', borderwidth=1).pack(side="left", padx=2)

            self.bot_villages.append({
                "frame": villages_frame,
                "components": []
            })
            self.load_villages(i)
        # محتوى لوحة التحكم
        # --- Scrollbar أفقي ورأسي لجدول المحاكيات ---
        table_canvas = tk.Canvas(self.main_tab, highlightthickness=0, bg=self.theme['BG_COLOR'])
        table_canvas.pack(fill="both", padx=0, pady=0, expand=True, side="top")
        h_scroll = tk.Scrollbar(self.main_tab, orient="horizontal", command=table_canvas.xview)
        h_scroll.pack(fill="x", side="top")
        v_scroll = tk.Scrollbar(self.main_tab, orient="vertical", command=table_canvas.yview)
        v_scroll.pack(fill="y", side="right")
        table_canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        self.top_frame = ttk.Frame(table_canvas, style="TFrame")
        self.top_frame_id = table_canvas.create_window((0, 0), window=self.top_frame, anchor="nw")
        def _on_frame_configure(event):
            table_canvas.configure(scrollregion=table_canvas.bbox("all"))
            # إذا كان عرض العناصر أكبر من عرض الكانفس، فعّل الاسكرول
            if self.top_frame.winfo_reqwidth() > table_canvas.winfo_width():
                table_canvas.config(width=table_canvas.winfo_width())
        self.top_frame.bind("<Configure>", _on_frame_configure)
        def _on_canvas_configure(event):
            # اجعل عرض الـ Frame مساوي للـ Canvas إذا كان أصغر
            if self.top_frame.winfo_reqwidth() < table_canvas.winfo_width():
                table_canvas.itemconfig(self.top_frame_id, width=table_canvas.winfo_width())
        table_canvas.bind("<Configure>", _on_canvas_configure)
        # دالة عامة للتمرير الأفقي أو الرأسي حسب Shift
        def global_mousewheel(event):
            widget = event.widget
            while widget is not None:
                if isinstance(widget, tk.Canvas):
                    # خطوة ناعمة مع حركة صغيرة جدًا لكل حدث عجلة
                    step_dir = -1 if getattr(event, 'delta', 0) > 0 else 1
                    steps = 0.1  # عدد الخطوات الصغيرة لكل حدث عجلة (أبطأ وأقل مسافة)
                    if event.state & 0x0001:  # Shift للتمرير الأفقي
                        self._smooth_scroll_canvas(widget, 'x', step_dir * steps, 24)
                    else:
                        self._smooth_scroll_canvas(widget, 'y', step_dir * steps, 60)
                    return "break"
                widget = widget.master
        self.bind_all("<MouseWheel>", global_mousewheel)
        for col, (title, width) in enumerate(COLUMNS):
            lbl = ttk.Label(self.top_frame, text=title, style="ColumnHeader.TLabel", width=width, anchor="center")
            lbl.grid(row=0, column=col, padx=4, pady=(0, 4), sticky="nsew")


        self.emulator_rows = []
        for i in range(NUM_EMULATORS):
            row = EmulatorRow(
                self.top_frame, i, self._update_buttons, self.theme,
                on_start_bot=self._start_integrated_bot,
                on_pause_resume_bot=self._pause_resume_integrated_bot,
                on_stop_bot=self._stop_integrated_bot,
                get_bot_status=lambda idx=i: self._get_integrated_bot_status(idx)
            )
            row.grid(self.top_frame, i+1)
            self.emulator_rows.append(row)


        btn_frame = ttk.Frame(self.main_tab, style="TFrame")
        btn_frame.pack(pady=10, fill="x")
        self.open_btn = tk.Button(btn_frame, text="فتح المحدد", bg=self.theme['BTN_GREEN'], fg="white", font=self.theme['LABEL_FONT'], width=10, command=self.open_selected, state="disabled", activebackground="#229954",
                                  relief='flat', borderwidth=2, highlightthickness=0)
        self.open_btn.grid(row=0, column=0, padx=8, sticky="ew")

        self.open1_btn = tk.Button(btn_frame, text="اتصال ADB محدد", bg=self.theme['BTN_BLUE'], fg="white", font=self.theme['LABEL_FONT'], width=7, command=self.Contact_selected, state="disabled", activebackground="#229954",
                    relief='flat', borderwidth=2, highlightthickness=0)
        self.open1_btn.grid(row=0, column=1, padx=8, sticky="ew")

        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        status_header = ttk.Label(self.main_tab, text="حالة جميع البوتات", style="Header.TLabel")
        status_header.pack(anchor="w", padx=18, pady=(10, 0))
        self.status_frame = ttk.Frame(self.main_tab, style="TFrame")
        self.status_frame.pack(fill="both", expand=True, padx=0, pady=8)
        self.status_text = tk.Text(self.status_frame, height=6, state="disabled", bg=self.theme['FRAME_COLOR'], fg=self.theme['HEADER_COLOR'], font=self.theme['LABEL_FONT'], relief="flat")
        self.status_text.pack(fill="both", expand=True, padx=4, pady=4)

        # ================================================================
        # ── قسم Supabase ── رقم السيرفر + زر الجلب + عداد تنازلي
        # ================================================================
        sb_frame = tk.Frame(self.stats_frame, bg="#1e293b", padx=6, pady=2)
        sb_frame.pack(side="left", padx=10)

        tk.Label(sb_frame, text="🖥 سيرفر:", bg="#1e293b", fg="#94a3b8",
                 font=("Cairo", 9, "bold")).pack(side="left")

        minus_sb = tk.Button(sb_frame, text="−", width=2,
                             bg="#ef4444", fg="white", font=("Cairo", 10, "bold"),
                             relief="flat", command=self._sb_decrement_server)
        minus_sb.pack(side="left", padx=1)

        self._sb_server_var = tk.IntVar(value=self._sb_cfg.get("server_index", 1))
        self._sb_server_lbl = tk.Label(sb_frame, textvariable=self._sb_server_var,
                                       bg="#3b82f6", fg="white",
                                       font=("Cairo", 11, "bold"), width=3)
        self._sb_server_lbl.pack(side="left", padx=2)

        plus_sb = tk.Button(sb_frame, text="+", width=2,
                            bg="#10b981", fg="white", font=("Cairo", 10, "bold"),
                            relief="flat", command=self._sb_increment_server)
        plus_sb.pack(side="left", padx=1)

        self._sb_fetch_btn = tk.Button(sb_frame, text="☁ جلب Supabase",
                                       bg="#3b82f6", fg="white",
                                       font=("Cairo", 9, "bold"),
                                       relief="flat", padx=6,
                                       command=self._sb_on_fetch_click)
        self._sb_fetch_btn.pack(side="left", padx=4)

        self._sb_countdown_lbl = tk.Label(sb_frame, text="⏱--:--:--",
                                          bg="#1e293b", fg="#64748b",
                                          font=("Cairo", 9))
        self._sb_countdown_lbl.pack(side="left", padx=2)
        
        # زر تصدير واستيراد
 
        # دعم السحب والإفلات (يتطلب مكتبة خارجية مثل tkinterDnD)
        # self.status_text.drop_target_register('DND_Files')
        # self.status_text.dnd_bind('<<Drop>>', self.on_drop_file)
        # اجعل التبويبات تتمدد مع تغيير الحجم (فقط باستخدام pack)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=8)

    def _update_buttons(self):
        any_selected = any(r.is_selected() for r in self.emulator_rows)
        state = "normal" if any_selected else "disabled"
        self.open_btn.config(state=state)
        self.open1_btn.config(state=state)
    def show_toast(self, message, duration=2000):
        Toast(self, message, duration)

    def _on_app_close(self):
        """حفظ الإعدادات عند الإغلاق"""
        self._sb_cfg["server_index"] = self._sb_server_var.get()
        _sb_save_config(self._sb_cfg)
        self.destroy()

    # ================================================================
    # ── دوال Supabase ──
    # ================================================================

    def _sb_increment_server(self):
        v = self._sb_server_var.get()
        self._sb_server_var.set(v + 1)
        self._sb_cfg["server_index"] = v + 1
        _sb_save_config(self._sb_cfg)
        self.show_toast(f"🔢 رقم السيرفر → {v + 1}")

    def _sb_decrement_server(self):
        v = self._sb_server_var.get()
        if v > 1:
            self._sb_server_var.set(v - 1)
            self._sb_cfg["server_index"] = v - 1
            _sb_save_config(self._sb_cfg)
            self.show_toast(f"🔢 رقم السيرفر → {v - 1}")

    def _sb_on_fetch_click(self):
        """جلب يدوي عند الضغط على الزر"""
        self._sb_fetch_btn.config(state="disabled", text="⏳ جاري السحب...")
        self._append_status(f"[Supabase] جاري سحب البيانات (سيرفر {self._sb_server_var.get()}) ...")
        threading.Thread(target=self._sb_fetch_worker, daemon=True).start()

    def _sb_fetch_worker(self, auto: bool = False):
        """العامل الفعلي – يُستدعى يدوياً أو تلقائياً"""
        server_idx = self._sb_server_var.get()
        result     = _sb_fetch_accounts(server_idx)

        def _finish():
            self._sb_fetch_btn.config(state="normal", text="☁ جلب Supabase")

            if isinstance(result, dict) and "error" in result:
                msg = f"[Supabase] ❌ خطأ: {result['error']}"
                self._append_status(msg)
                if not auto:
                    self.show_toast(msg, 4000)
                return

            if not result:
                self._append_status("[Supabase] ⚠️ لا توجد حسابات مطابقة (index_server + Is_OK=True)")
                # أفرغ الملفات الموجودة
                _sb_apply_accounts([])
                return

            self._append_status(f"[Supabase] ✅ تم جلب {len(result)} حساب")
            applied = _sb_apply_accounts(result)
            for bot_idx, count in applied:
                if count > 0:
                    self._append_status(f"[Supabase] 💾 بوت {bot_idx}: {count} حساب")
                    # تحديث الواجهة للبوت المعني
                    try:
                        self._update_bot_interface(bot_idx - 1)
                    except Exception:
                        pass
                else:
                    self._append_status(f"[Supabase] 🗑 بوت {bot_idx}: تم التفريغ")

            if not auto:
                self.show_toast(f"✅ {len(result)} حساب موزَّع على {sum(1 for _, c in applied if c > 0)} بوت", 3000)

            # ── تشغيل البوتات الخاملة تلقائياً بعد الجلب ──
            threading.Thread(target=self._auto_start_idle_bots, daemon=True).start()

        self.after(0, _finish)

    def _sb_auto_fetch_loop(self):
        """
        يعمل في thread منفصل:
        1. عند بدء التشغيل: يجلب البيانات فوراً
        2. ثم يبدأ العداد التنازلي (AUTO_FETCH_INTERVAL ثانية)
        3. عند انتهاء العداد: يفحص Is_Change ويجلب إذا لزم
        """
        # ── جلب فوري عند بدء التشغيل ──
        self._append_status_threadsafe("[Supabase] 🚀 جلب أولي عند بدء التشغيل ...")
        self.after(0, lambda: self._sb_fetch_btn.config(state="disabled", text="⏳ جاري السحب..."))
        self._sb_fetch_worker(auto=True)

        # ── بدء دورة العداد التنازلي ──
        while True:
            remaining = AUTO_FETCH_INTERVAL
            # عداد تنازلي
            while remaining > 0:
                h, rem  = divmod(int(remaining), 3600)
                m, s    = divmod(rem, 60)
                txt     = f"⏱{h:02d}:{m:02d}:{s:02d}"
                self.after(0, lambda t=txt: self._sb_countdown_lbl.config(text=t))
                time.sleep(1)
                remaining -= 1

            # وقت الفحص
            self.after(0, lambda: self._sb_countdown_lbl.config(text="⏱ فحص ..."))
            self._append_status_threadsafe("[Supabase] ⏰ فحص Is_Change ...")

            try:
                should = _sb_check_and_reset_is_change(self._sb_server_var.get())
            except Exception as e:
                should = False
                self._append_status_threadsafe(f"[Supabase] ⚠️ خطأ Is_Change: {e}")

            if should:
                self._append_status_threadsafe("[Supabase] ✅ Is_Change=True → جاري الجلب التلقائي")
                self.after(0, lambda: self._sb_fetch_btn.config(state="disabled", text="⏳ جاري السحب..."))
                self._sb_fetch_worker(auto=True)
            else:
                self._append_status_threadsafe("[Supabase] 🔕 Is_Change=False → انتظار ساعة أخرى")


    def _append_status_threadsafe(self, msg: str):
        self.after(0, lambda: self._append_status(msg))

    # ── قفل لمنع تشغيل _auto_start_idle_bots بالتوازي ──
    _idle_bots_running = False

    def _auto_start_idle_bots(self):
        """
        يُنفَّذ بعد كل جلب من Supabase (في thread منفصل).
        يفحص ملفات JSON ويشغّل البوتات الخاملة (2+ حساب + بوت غير شغّال)
        بشكل تدريجي (فاصل 30 ثانية بين كل بوت) لحفظ موارد النظام.
        """
        # منع التشغيل المتوازي
        if MainApp._idle_bots_running:
            return
        MainApp._idle_bots_running = True

        try:
            # انتظار بسيط لتأكد اكتمال حفظ ملفات JSON
            time.sleep(3)

            # جمع البوتات المؤهلة (2+ حساب + بوت غير شغّال)
            candidates = []
            for idx, row in enumerate(self.emulator_rows):
                try:
                    bot_number = idx + 1
                    path = _sb_get_json_path(bot_number)
                    if not os.path.exists(path):
                        continue
                    data = _sb_load_json(path)
                    villages = data.get("villages", [])
                    if len(villages) < 2:
                        continue  # أقل من حسابين → تخطَّ

                    # فحص هل البوت شغّال؟
                    proc = self.bot_processes[idx]
                    bot_running = (proc is not None and proc.is_alive())
                    if bot_running:
                        continue  # البوت شغّال → لا نتدخل

                    candidates.append(idx)
                except Exception:
                    continue

            if not candidates:
                self._append_status_threadsafe("[AutoStart] ℹ️ لا توجد بوتات خاملة تحتاج تشغيل")
                return

            self._append_status_threadsafe(
                f"[AutoStart] 🚀 {len(candidates)} بوت خامل سيتم تشغيلهم تدريجياً"
            )

            # تشغيل البوتات بشكل تدريجي (30 ثانية بين كل بوت)
            for i, idx in enumerate(candidates):
                try:
                    row = self.emulator_rows[idx]
                    device_id = row.port

                    # تأكد من أن البوت ما زال خاملاً وقت التشغيل الفعلي
                    proc = self.bot_processes[idx]
                    if proc is not None and proc.is_alive():
                        self._append_status_threadsafe(
                            f"[AutoStart] ⏭ بوت {idx+1}: بدأ التشغيل بشكل مستقل، تخطي"
                        )
                        continue

                    self._append_status_threadsafe(
                        f"[AutoStart] ▶ تشغيل بوت {idx+1} ({device_id}) ..."
                    )

                    # ── 1: فتح المحاكي ──
                    instance_name = None
                    mapping = extract_device_mapping()
                    for inst, port in mapping.items():
                        if port == device_id:
                            instance_name = inst
                            break

                    if instance_name:
                        subprocess.Popen(
                            [LDCONSOLE_PATH, "--instance", instance_name],
                            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
                        )
                        self._append_status_threadsafe(f"[AutoStart] 🖥 فتح المحاكي: {instance_name}")
                        time.sleep(30)  # انتظار بدء المحاكي
                    else:
                        self._append_status_threadsafe(
                            f"[AutoStart] ⚠️ بوت {idx+1}: لم يُعثر على instance name، تخطي"
                        )
                        continue

                    # ── 2: اتصال ADB ──
                    try:
                        subprocess.run(
                            ["adb", "connect", device_id],
                            timeout=10,
                            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0,
                            capture_output=True
                        )
                        self._append_status_threadsafe(f"[AutoStart] 🔌 ADB connect: {device_id}")
                        time.sleep(5)
                    except Exception:
                        pass

                    # ── 3: تشغيل Correct ──
                    p = multiprocessing.Process(target=run_Correct_manager1, args=(device_id,))
                    p.daemon = True
                    p.start()

                    # تحديث حالة الـ GUI (من الـ thread الرئيسي)
                    def _update_gui(i=idx, proc=p):
                        self.bot_processes[i] = proc
                        self.bot_clicked_flags[i] = True
                        self.bot_start_times[i] = time.time()
                        self.last_correct_stages_check[i] = time.time()
                        self.last_correct_stages_call[i] = time.time()
                        self.user_stopped_flags[i] = False
                        self.emulator_rows[i].set_open(True)
                        self._update_emulator_row_status(i)
                        self._append_status(f"[AutoStart] ✅ بوت {i+1} يعمل الآن")

                    self.after(0, _update_gui)

                    # انتظار 60 ثانية قبل البوت التالي (إلا إذا كان آخر واحد)
                    if i < len(candidates) - 1:
                        self._append_status_threadsafe(
                            f"[AutoStart] ⏳ انتظار 60 ثانية قبل تشغيل البوت التالي ..."
                        )
                        time.sleep(60)

                except Exception as e:
                    self._append_status_threadsafe(f"[AutoStart] ❌ خطأ في تشغيل بوت {idx+1}: {e}")
                    continue

            self._append_status_threadsafe("[AutoStart] ✅ اكتمل تشغيل البوتات الخاملة")

        except Exception as e:
            self._append_status_threadsafe(f"[AutoStart] ❌ خطأ عام: {e}")
        finally:
            MainApp._idle_bots_running = False

    def _start_auto_update(self):
        def update_loop():
            while True:
                if self.sleep_mode == True:
                    time.sleep(20)
                else:
                    time.sleep(8)
                self.event_generate('<<AutoUpdate>>', when='tail')
        threading.Thread(target=update_loop, daemon=True).start()
        self.bind('<<AutoUpdate>>', lambda e: self._auto_update())

    def _auto_update(self):
        # فقط فحص الشرطين Correct_Stages
        self._update_emulator_states_from_adb()
        now_ts = time.time()

        # ── فحص ملفات الإيقاف الآمن (shutdown flags) من البوتات ──
        for idx, row in enumerate(self.emulator_rows):
            device_id = row.port
            shutdown_flag = f'shutdown_{device_id}.flag'
            if os.path.exists(shutdown_flag):
                try:
                    os.remove(shutdown_flag)
                except Exception:
                    pass
                # تنفيذ نفس منطق "الإيقاف النهائي"
                proc = self.bot_processes[idx]
                if proc is not None and proc.is_alive():
                    try:
                        proc.terminate()
                        proc.join(timeout=5)
                    except Exception:
                        pass
                self.bot_processes[idx] = None
                self.bot_start_times[idx] = None
                self.bot_elapsed_times[idx] = 0
                self._clear_status_cache(idx)
                self.bot_clicked_flags[idx] = False
                self.user_stopped_flags[idx] = True
                # حذف ملف الإيقاف المؤقت
                try:
                    pause_file = f'pause_{device_id}.flag'
                    if os.path.exists(pause_file):
                        os.remove(pause_file)
                except Exception:
                    pass
                self._update_emulator_row_status(idx)
                self._append_status(f"[Shutdown] ✅ تم إيقاف بوت {idx+1} تلقائياً (حسابات غير كافية)")
                print(f"[_auto_update] ✅ shutdown flag detected → بوت {idx+1} أُوقف بأمان")

                # ── إغلاق المحاكي من الـ GUI (أكثر أماناً من البوت) ──
                def _delayed_close_emulator(emulator_idx=idx, port=device_id):
                    try:
                        time.sleep(5)  # انتظار حتى يكتمل إيقاف البوت
                        # البحث عن instance name الصحيح من المنفذ مباشرة
                        from Manager_Json import extract_device_mapping
                        mapping = extract_device_mapping()  # {instance_name: "127.0.0.1:port"}
                        target_name = None
                        for inst_name, inst_port in mapping.items():
                            if inst_port == port:
                                target_name = inst_name
                                break
                        if target_name:
                            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                                try:
                                    pname = proc.info.get('name')
                                    cmdline = proc.info.get('cmdline') or []
                                    if (
                                        pname == "HD-Player.exe"
                                        and any((isinstance(arg, str) and target_name in arg) for arg in cmdline)
                                    ):
                                        subprocess.run(
                                            ["taskkill", "/F", "/PID", str(proc.info['pid'])],
                                            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
                                        )
                                        print(f"[_auto_update] ✅ تم إغلاق المحاكي {emulator_idx+1} ({target_name})")
                                        self.after(0, lambda i=emulator_idx: self.emulator_rows[i].set_open(False))
                                        self.after(0, lambda: self._append_status(f"[Shutdown] ✅ تم إغلاق المحاكي {emulator_idx+1}"))
                                        return
                                except (psutil.AccessDenied, psutil.NoSuchProcess):
                                    continue
                            print(f"[_auto_update] ❌ لم يُعثر على عملية المحاكي: {target_name}")
                        else:
                            print(f"[_auto_update] ❌ لم يُعثر على instance name للمنفذ: {port}")
                    except Exception as e:
                        print(f"[_auto_update] ❌ خطأ في إغلاق المحاكي {emulator_idx+1}: {e}")
                threading.Thread(target=_delayed_close_emulator, daemon=True).start()

        for idx, row in enumerate(self.emulator_rows):
            # تخطي الفحص إذا لم يمر 60 ثانية منذ آخر فحص
            if (now_ts - self.last_correct_stages_check[idx]) < 60.0:
                continue
                
            # فحص سريع: إذا لم يتم النقر على تشغيل البوت، تخطي
            if not self.bot_clicked_flags[idx]:
                continue
                
            # فحص حالة البوت مع cache محسّن
            status = self._get_integrated_bot_status(idx)
            is_running = bool(status and status.get('is_running', False))
            user_stopped = self.user_stopped_flags[idx]
            
            # الشرط الأصلي: المحاكي مغلق + تم النقر على تشغيل البوت
            original_condition = not row.is_open and self.bot_clicked_flags[idx]
            
            # الشرط الجديد: البوت غير شغال + المستخدم لم يضغط على إيقاف + تم النقر على تشغيل البوت
            new_condition = (not is_running) and self.bot_clicked_flags[idx]
            
            if original_condition:
                # تنفيذ Correct_Stages مباشرة دون التحقق من is_running (تشغيلها في خيط منفصل)
                self.last_correct_stages_check[idx] = now_ts
                threading.Thread(target=self.Correct_Stages, args=(idx,), daemon=True).start()
            elif new_condition:
                # نفس السلوك الحالي: جدولة تحقق مؤجل مع التحقق من is_running
                self.last_correct_stages_check[idx] = now_ts
                if not self.pending_correct_checks[idx]:
                    self.pending_correct_checks[idx] = True
                    def _delayed_correct_check(i=idx):
                        try:
                            time.sleep(10)
                            # إعادة التحقق من حالة البوت بعد الانتظار
                            status2 = self._get_integrated_bot_status(i)
                            is_running2 = bool(status2 and status2.get('is_running', False))
                            if (not is_running2) and self.bot_clicked_flags[i]:
                                # تحديث الطابع الزمني ثم تنفيذ Correct_Stages في خيط منفصل
                                self.last_correct_stages_check[i] = time.time()
                                threading.Thread(target=self.Correct_Stages, args=(i,), daemon=True).start()
                            # إذا كان يعمل، لا نفعل شيئًا
                        finally:
                            self.pending_correct_checks[i] = False
                    threading.Thread(target=_delayed_correct_check, daemon=True).start()
        # Fire_Stages trigger conditions
        # 1) is_running == False
        # 2) user didn't click Stop (user_stopped_flags[idx] is False)
        # 3) is_open == True
        # 4) Correct_Stages not called in last 15 seconds
        if self.sleep_mode == False :
            # الوضع العادي (كما هو)
            for bot_idx, bot in enumerate(self.bot_villages):
                for comp in bot["components"]:
                    comp.update_edit_state()
            for idx, row in enumerate(self.emulator_rows):
                status = self._get_integrated_bot_status(idx)
                row.update_bot_status(status)

            self.update_indicator.show()
        else:
            return


    def _update_emulator_states_from_adb(self):
        # جلب الأجهزة المتصلة عبر adb
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
            )
            lines = result.stdout.strip().splitlines()
            connected = set()
            for line in lines[1:]:
                if line.strip() and "device" in line:
                    device = line.split()[0]
                    connected.add(device)
            for row in self.emulator_rows:
                is_open = row.port in connected
                row.set_open(is_open)
        except subprocess.TimeoutExpired:
            print("[MAIN GUI] انتهت مهلة جلب قائمة الأجهزة")
            for row in self.emulator_rows:
                row.set_open(False)
        except Exception as e:
            print(f"[MAIN GUI] خطأ في جلب قائمة الأجهزة: {e}")
            for row in self.emulator_rows:
                row.set_open(False)
    # الحد الأقصى لعدد البوتات التي تعمل في نفس الوقت
    MAX_RUNNING_BOTS = 15

    def _get_running_bots_count(self):
        # استخدام is_alive لأننا نستخدم multiprocessing.Process وليس subprocess.Popen
        return sum(1 for p in self.bot_processes if p is not None and p.is_alive())

    def _start_integrated_bot(self, device_id):
        idx = None
        for i, row in enumerate(self.emulator_rows):
            if row.port == device_id:
                idx = i
                break

        if idx is None:
            self.show_toast(f"لم يتم العثور على المحاكي: {device_id}")
            return

        # ✅ تسجيل أن زر تشغيل البوت تم النقر عليه
        self.bot_clicked_flags[idx] = True
        # clear user stopped since user is starting again
        self.user_stopped_flags[idx] = False

        if not self.emulator_rows[idx].is_open:
            self.show_toast(f"المحاكي غير مفتوح: {device_id}")
            return

        # تحقق: إذا البوت شغال بالفعل
        if self.bot_processes[idx] is not None and self.bot_processes[idx].is_alive():
            self.show_toast(f"البوت يعمل بالفعل على LDPlayer-{idx+1}")
            return

        # إزالة أي ملفات إيقاف مؤقت متبقية قبل التشغيل
        try:
            pause_file = f'pause_{device_id}.flag'
            if os.path.exists(pause_file):
                os.remove(pause_file)
        except Exception:
            pass

        # تنظيف مرجع عملية قديمة إذا كانت غير نشطة
        if self.bot_processes[idx] is not None and not self.bot_processes[idx].is_alive():
            self.bot_processes[idx] = None

        # تشغيل البوت في Process مستقل
        try:
            p = multiprocessing.Process(target=run_Power_manager1, args=(device_id,))
            p.daemon = True
            p.start()

            self.bot_processes[idx] = p
            self.bot_start_times[idx] = time.time()
            # منع استدعاء Correct_Stages مباشرة بعد التشغيل
            self.last_correct_stages_check[idx] = time.time()
            self._clear_status_cache(idx)  # مسح cache عند بدء البوت
            self.show_toast(f"تم تشغيل البوت على LDPlayer-{idx+1}")
            self._update_emulator_row_status(idx)

            # تحقق لاحق سريع للتأكد من أن العملية اشتغلت فعلاً
            def _verify_bot_started():
                try:
                    time.sleep(6)
                    proc = self.bot_processes[idx]
                    if proc is None or not proc.is_alive():
                        # العملية لم تبدأ بشكل صحيح
                        self.bot_processes[idx] = None
                        self.bot_start_times[idx] = None
                        self.bot_elapsed_times[idx] = 0
                        self._clear_status_cache(idx)
                        # إعادة تعيين فلاغ التشغيل لأن التشغيل فشل
                        self.bot_clicked_flags[idx] = False
                        self.show_toast(f"فشل تشغيل البوت على LDPlayer-{idx+1}، سيتم إبقاء الحالة متوقفة")
                        self._update_emulator_row_status(idx)
                        return
                    # فحص حالة الإيقاف المؤقت إن وُجدت
                    status = self._get_integrated_bot_status(idx)
                    if status and status.get('paused', False):
                        self.show_toast(f"البوت على LDPlayer-{idx+1} في وضع الإيقاف المؤقت")
                        self._update_emulator_row_status(idx)
                except Exception:
                    pass

            threading.Thread(target=_verify_bot_started, daemon=True).start()

        except Exception as e:
            self.show_toast(f"خطأ في تشغيل البوت {idx+1}: {e}")
    
    def _pause_resume_integrated_bot(self, device_id):
        idx = None
        for i, row in enumerate(self.emulator_rows):
            if row.port == device_id:
                idx = i
                break
        if idx is None:
            self.show_toast(f"لم يتم العثور على المحاكي: {device_id}")
            return
        pause_file = f'pause_{device_id}.flag'
        proc = self.bot_processes[idx]
        if proc is not None and proc.is_alive():
            if os.path.exists(pause_file):
                os.remove(pause_file)
                self.show_toast(f"تم استئناف البوت على LDPlayer-{idx+1}")
            else:
                with open(pause_file, 'w') as f:
                    f.write('pause')
                self.show_toast(f"تم إيقاف البوت مؤقتًا على LDPlayer-{idx+1}")
        else:
            self.show_toast(f"البوت غير مشغل على LDPlayer-{idx+1}")
        self._update_emulator_row_status(idx)

    def _stop_integrated_bot(self, device_id):
        idx = None
        for i, row in enumerate(self.emulator_rows):
            if row.port == device_id:
                idx = i
                break

        if idx is None:
            self.show_toast(f"لم يتم العثور على المحاكي: {device_id}")
            return

        proc = self.bot_processes[idx]

        if proc is not None and proc.is_alive():
            try:
                proc.terminate()   # إيقاف العملية
                proc.join(timeout=2)  # انتظار قصير حتى تنتهي
                self.bot_processes[idx] = None
                self.bot_start_times[idx] = None
                self.bot_elapsed_times[idx] = 0
                self._clear_status_cache(idx)  # مسح cache عند إيقاف البوت

                # ✅ إعادة الفلاغ إلى False عند الإيقاف
                self.bot_clicked_flags[idx] = False
                # mark user stopped explicitly
                self.user_stopped_flags[idx] = True

                self.show_toast(f"تم إيقاف البوت على LDPlayer-{idx+1}")
            except Exception as e:
                self.show_toast(f"خطأ في إيقاف البوت {idx+1}: {e}")
        else:
            self.show_toast(f"لا يوجد بوت يعمل على LDPlayer-{idx+1}")

        # إزالة أي ملف إيقاف مؤقت حتى لا يؤثر على تشغيل لاحق
        try:
            pause_file = f'pause_{device_id}.flag'
            if os.path.exists(pause_file):
                os.remove(pause_file)
        except Exception:
            pass

        # تحديث حالة الصف في الواجهة
        self._update_emulator_row_status(idx)


    def _get_integrated_bot_status(self, idx):
        now = time.time()
        
        # استخدام cache إذا كان حديث
        if (self._status_cache[idx] is not None and 
            now - self._last_status_check[idx] < self._status_cache_ttl):
            return self._status_cache[idx]
        
        device_id = self.emulator_rows[idx].port
        status_file = f'status_{device_id}.json'
        pause_file = f'pause_{device_id}.flag'
        
        # فحص العملية أولاً (أسرع)
        proc = self.bot_processes[idx]
        if proc is None or not proc.is_alive():
            status = {'is_running': False, 'status': 'متوقف'}
            self._status_cache[idx] = status
            self._last_status_check[idx] = now
            return status
        
        # فحص ملف الحالة مع heartbeat
        if os.path.exists(status_file):
            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    status = json.load(f)
                
                # فحص heartbeat (30 ثانية نافذة السماح)
                heartbeat_ts = status.get('heartbeat_ts', 0)
                if heartbeat_ts > 0:
                    time_since_heartbeat = now - float(heartbeat_ts)
                    if time_since_heartbeat > 30:  # 30 ثانية بدون heartbeat = متوقف
                        status = {'is_running': False, 'status': 'متوقف (انقطاع heartbeat)'}
                        self._status_cache[idx] = status
                        self._last_status_check[idx] = now
                        return status
                # فرض حقول الحالة بناءً على الواقع: العملية تعمل، ووقف مؤقت يعتمد على وجود ملف الإيقاف
                status['is_running'] = True
                status['paused'] = os.path.exists(pause_file)
                # حفظ في cache
                self._status_cache[idx] = status
                self._last_status_check[idx] = now
                return status
            except Exception:
                # إذا فشل قراءة الملف، اعتبر البوت متوقفًا لتمكين الاستعادة التلقائية
                status = {'is_running': False, 'status': 'متوقف (فشل قراءة الحالة)', 'paused': os.path.exists(pause_file)}
                self._status_cache[idx] = status
                self._last_status_check[idx] = now
                return status
        
        # إذا لم يوجد ملف حالة، اعتبر البوت متوقفًا لتمكين الاستعادة التلقائية
        status = {'is_running': False, 'status': 'متوقف (لا يوجد ملف حالة)', 'paused': os.path.exists(pause_file)}
        self._status_cache[idx] = status
        self._last_status_check[idx] = now
        return status
    
    def _clear_status_cache(self, idx):
        """مسح cache الحالة للبوت المحدد"""
        self._status_cache[idx] = None
        self._last_status_check[idx] = 0.0
    
    def _update_emulator_row_status(self, idx):
        if idx < len(self.emulator_rows):
            status = self._get_integrated_bot_status(idx)
            self.emulator_rows[idx].update_bot_status(status)
    def open_selected(self):
        for row in self.emulator_rows:
            if row.is_selected():
                if not row.is_open:
                    self._open_emulator_instance(row.idx)
                    row.set_open(True)
                row.selected.set(False)

    def Contact_selected(self):
        for row in self.emulator_rows:
            if row.is_selected():
                if not row.is_open:
                    self._Contact_emulator_instance(row.idx)
                row.selected.set(False)

    def close_selected(self):
        if messagebox.askyesno("تأكيد الإغلاق", "هل أنت متأكد من إغلاق المحاكيات المحددة وواجهات البوت الخاصة بها؟"):
            for row in self.emulator_rows:
                if row.is_selected():
                    self._close_emulator_instance(row.idx)
                    row.set_open(False)
                    self._append_status(f"تم إغلاق LDPlayer-{row.idx+1} ({row.port})")
                    self.show_toast(f"تم إغلاق LDPlayer-{row.idx+1}")
                    row.selected.set(False)

    def _open_emulator_instance(self, idx):
        """فتح محاكي عبر HD-Player.exe --instance"""
        device_id = self.emulator_rows[idx].port if idx < len(self.emulator_rows) else None
        mapping = extract_device_mapping()
        name = next((inst for inst, port in mapping.items() if port == device_id), None)
        if name:
            subprocess.Popen(
                [LDCONSOLE_PATH, "--instance", name],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
            )
            print(f"[Open] Started instance: {name}")
        else:
            print(f"[Open] No instance found for {device_id}")

    def _Contact_emulator_instance(self, idx):
        """اتصال ADB بمحاكي"""
        device_id = self.emulator_rows[idx].port if idx < len(self.emulator_rows) else None
        if device_id:
            try:
                subprocess.run(
                    ["adb", "connect", device_id],
                    timeout=10,
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
                )
                print(f"[ADB] Connected: {device_id}")
            except Exception as e:
                print(f"[ADB] Error connecting {device_id}: {e}")

    def _close_emulator_instance(self, idx):
        """إغلاق محاكي عبر taskkill بناءً على port->instance mapping"""
        device_id = self.emulator_rows[idx].port if idx < len(self.emulator_rows) else None
        mapping = extract_device_mapping()
        name = next((inst for inst, port in mapping.items() if port == device_id), None)

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                pname = proc.info.get('name')
                cmdline = proc.info.get('cmdline') or []
                if (
                    pname == "HD-Player.exe"
                    and name is not None
                    and any((isinstance(arg, str) and name in arg) for arg in cmdline)
                ):
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(proc.info['pid'])],
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
                    )
                    print(f"[Close] Instance {name} killed.")
                    return
            except (psutil.AccessDenied, psutil.NoSuchProcess, KeyError):
                continue
            except Exception:
                continue
        print(f"[Close] No instance found for {device_id} (name={name})")

    def _append_status(self, msg):
        self.status_text.config(state="normal")
        self.status_text.insert("end", msg + "\n")
        self.status_text.see("end")
        self.status_text.config(state="disabled")


    def add_village(self, bot_idx):
        def is_bot_running():
            # يعتبر البوت شغال إذا كان المحاكي مفتوحاً
            return self.emulator_rows[bot_idx].is_open if bot_idx < len(self.emulator_rows) else False
        row_index = len(self.bot_villages[bot_idx]["components"])
        bg_color = "#f2f2f2" if row_index % 2 == 0 else "#ffffff"
        v = BotVillageComponent(
            self.bot_villages[bot_idx]["frame"],
            row_index,
            on_delete=lambda comp: self.delete_village(bot_idx, comp),
            on_edit=lambda comp: self.edit_village(bot_idx, comp),
            is_bot_running_func=is_bot_running,
            bg_color=bg_color
        )
        v.pack(fill="x", expand=True, pady=2)
        
        self.bot_villages[bot_idx]["components"].append(v)
    def delete_village(self, bot_idx, comp):
        if messagebox.askyesno("تأكيد الحذف", "هل أنت متأكد من حذف بيانات هذه القرية؟"):
            comp.destroy()
            self.bot_villages[bot_idx]["components"].remove(comp)
            self.save_villages(bot_idx)  # حفظ البيانات بعد الحذف
    def edit_village(self, bot_idx, comp):
        if comp.is_bot_running_func():
            self.show_toast("لا يمكن التعديل أثناء تشغيل البوت!")
            return
        # التعديل هنا يعني السماح بتغيير الحقول (هي editable دائماً في Tkinter)
        self.save_villages(bot_idx)
        self.show_toast("تم تعديل بيانات القرية وحفظها")
    def save_villages(self, bot_idx):
        all_villages = [v.get_data() for v in self.bot_villages[bot_idx]["components"]]
        # تصفية القرى التي بريدها أو كلمة سرها فارغة
        valid_villages = [v for v in all_villages if v["email"].strip() and v["password"].strip()]
        skipped = len(all_villages) - len(valid_villages)
        
        # الحصول على القيمة الحالية للمتغير الجديد وزيادتها
        device_id = self.emulator_rows[bot_idx].port if bot_idx < len(self.emulator_rows) else f"127.0.0.1:{5555 + bot_idx}"
        new_counter_value = BotDataManager.increment_save_counter(device_id, bot_idx + 1)
        
        data = {
            "villages": valid_villages,
            "account_index": 0,
            "save_counter": new_counter_value
        }
        BotDataManager.save_bot_villages(bot_idx, data)
        if skipped > 0:
            self.show_toast(f"تم تجاهل {skipped} حساب بدون بريد أو كلمة سر")
        self.show_toast(f"تم حفظ بيانات بوت {bot_idx+1} - العداد: {new_counter_value}")
    def save_villages_preserve_index(self, bot_idx):
        all_villages = [v.get_data() for v in self.bot_villages[bot_idx]["components"]]
        valid_villages = [v for v in all_villages if v["email"].strip() and v["password"].strip()]
        skipped = len(all_villages) - len(valid_villages)
        # احتفاظ بقيمة account_index الحالية من الملف المحفوظ
        existing = BotDataManager.load_bot_villages(bot_idx) or {}
        current_index = existing.get("account_index", 0)
        data = {
            "villages": valid_villages,
            "account_index": current_index
        }
        BotDataManager.save_bot_villages(bot_idx, data)
        if skipped > 0:
            self.show_toast(f"تم تجاهل {skipped} حساب بدون بريد أو كلمة سر")
        self.show_toast(f"تم حفظ بيانات بوت {bot_idx+1} بدون تغيير المؤشر")
    def load_villages(self, bot_idx):
        data = BotDataManager.load_bot_villages(bot_idx)
        if data:
            for vdata in data.get("villages", []):
                row_index = len(self.bot_villages[bot_idx]["components"])
                bg_color = "#89CFF0" if row_index % 2 == 0 else "#ffffff"
                v = BotVillageComponent(self.bot_villages[bot_idx]["frame"], row_index,
                                       lambda comp: self.delete_village(bot_idx, comp),
                                       lambda comp: self.edit_village(bot_idx, comp),
                                       lambda: self.emulator_rows[bot_idx].is_open if bot_idx < len(self.emulator_rows) else False,
                                       bg_color=bg_color)
                v.set_data(vdata)
                v.pack(fill="x", pady=2)
                self.bot_villages[bot_idx]["components"].append(v)
            # حذف دعم تحديد المدة: لم نعد نقرأ أو نعرض قيمة period


    def _open_emulator_instance(self, idx):
        # تشغيل LDPlayer instance عبر ldconsole.exe
        if len(Contact_PORT) > idx :
            name = Contact_PORT[idx]

        if not os.path.exists(LDCONSOLE_PATH):
            self.show_toast("لم يتم العثور على ldconsole.exe! عدل المسار في الكود.")
            return
        try:
            subprocess.Popen([LDCONSOLE_PATH, "--instance", name], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            self.show_toast(f"خطأ في تشغيل المثيل: {e}")

    def _Contact_emulator_instance(self, idx):
        # تشغيل LDPlayer instance عبر ldconsole.exe
        if len(Contact_PORT) > idx :
            name = Contact_PORT[idx]

        value11 = MAIN_PORTS[name]
        command = f"adb connect {value11}"
 
        try:
            subprocess.run(command, shell=True, capture_output=True, text=True , creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0)
        except Exception as e:
            self.show_toast(f"خطأ في تشغيل المثيل: {e}")

    def _start_uptime_updater(self):
        def update_uptime_loop():
            while True:
                time.sleep(1)
                self.event_generate('<<UptimeUpdate>>', when='tail')
        threading.Thread(target=update_uptime_loop, daemon=True).start()
        self.bind('<<UptimeUpdate>>', lambda e: self._update_all_uptimes())


    def _update_all_uptimes(self):
        for idx, row in enumerate(self.emulator_rows):
            start_time = self.bot_start_times[row.idx] if row.idx < len(self.bot_start_times) else None
            elapsed_total = self.bot_elapsed_times[row.idx] if row.idx < len(self.bot_elapsed_times) else 0
            status = self._get_integrated_bot_status(row.idx)

            if status and status.get('is_running', False):
                if start_time:
                    elapsed = elapsed_total + int(time.time() - start_time)
                else:
                    elapsed = elapsed_total

                days = elapsed // 86400  # ✅ حساب الأيام فقط
                row.uptime_label.config(text=f"{days} يوم")

            elif status and status.get('paused', False):
                elapsed = elapsed_total
                days = elapsed // 86400
                row.uptime_label.config(text=f"{days} يوم")

            else:
                row.uptime_label.config(text=DEFAULT_UPTIME)


    def show_whatsapp_parser_window(self):
        """عرض نافذة معالجة رسائل الواتساب"""
        whatsapp_window = tk.Toplevel(self)
        whatsapp_window.title("معالج رسائل الواتساب")
        whatsapp_window.geometry("800x600")
        whatsapp_window.configure(bg=LIGHT_THEME['BG_COLOR'])
        
        # جعل النافذة مركزية
        whatsapp_window.transient(self)
        whatsapp_window.grab_set()
        
        # إطار العنوان
        title_frame = tk.Frame(whatsapp_window, bg=LIGHT_THEME['HEADER_COLOR'])
        title_frame.pack(fill="x", pady=(0, 10))
        
        title_label = tk.Label(title_frame, text="معالج رسائل الواتساب", 
                              font=LIGHT_THEME['HEADER_FONT'], 
                              fg="white", bg=LIGHT_THEME['HEADER_COLOR'])
        title_label.pack(pady=10)
        
        # إطار المحتوى الرئيسي
        main_frame = tk.Frame(whatsapp_window, bg=LIGHT_THEME['BG_COLOR'])
        main_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # اختيار رقم البوت
        bot_frame = tk.Frame(main_frame, bg=LIGHT_THEME['BG_COLOR'])
        bot_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(bot_frame, text="اختر رقم البوت:", 
                font=LIGHT_THEME['LABEL_FONT'], 
                bg=LIGHT_THEME['BG_COLOR']).pack(side="left")
        
        bot_var = tk.StringVar(value="1")
        bot_combo = ttk.Combobox(bot_frame, textvariable=bot_var, 
                                values=[str(i) for i in range(1, 16)], 
                                state="readonly", width=10)
        bot_combo.pack(side="left", padx=(10, 0))
        
        # منطقة إدخال رسالة الواتساب
        message_frame = tk.Frame(main_frame, bg=LIGHT_THEME['BG_COLOR'])
        message_frame.pack(fill="both", expand=True, pady=(0, 15))
        
        tk.Label(message_frame, text="أدخل رسالة الواتساب:", 
                font=LIGHT_THEME['LABEL_FONT'], 
                bg=LIGHT_THEME['BG_COLOR']).pack(anchor="w")
        
        message_text = tk.Text(message_frame, height=15, font=("Cairo", 10),
                              bg="white", fg="black", relief="solid", bd=1)
        message_text.pack(fill="both", expand=True, pady=(5, 0))
        
        # شريط التمرير
        scrollbar = tk.Scrollbar(message_text)
        scrollbar.pack(side="right", fill="y")
        message_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=message_text.yview)
        
        # اختصارات لوحة المفاتيح
        message_text.bind("<Control-v>", lambda e: message_text.event_generate("<<Paste>>"))
        message_text.bind("<Control-V>", lambda e: message_text.event_generate("<<Paste>>"))
        
        # أزرار التحكم
        button_frame = tk.Frame(main_frame, bg=LIGHT_THEME['BG_COLOR'])
        button_frame.pack(fill="x", pady=(0, 15))
        
        def process_message():
            """معالجة رسالة الواتساب المحسنة مع حماية من الأخطاء"""
            try:
                bot_number = int(bot_var.get())
                raw_message = message_text.get("1.0", tk.END)
                
                # تنظيف النص من الرموز الضارة والأحرف غير المرغوب فيها
                # إزالة الأحرف غير المرئية والتحكم
                cleaned_message = ''.join(char for char in raw_message 
                                        if unicodedata.category(char)[0] != 'C' or char in '\n\r\t ')
                
                # تنظيف إضافي للنص
                cleaned_message = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', cleaned_message)
                cleaned_message = cleaned_message.strip()
                
                if not cleaned_message:
                    messagebox.showwarning("تحذير", "يرجى إدخال رسالة الواتساب")
                    return
                
                # عرض معاينة للنص المنظف
                preview_lines = cleaned_message.split('\n')[:5]
                preview = '\n'.join(preview_lines)
                if len(preview_lines) == 5:
                    preview += "\n..."
                
                # تأكيد من المستخدم قبل المعالجة
                confirm = messagebox.askyesno("تأكيد المعالجة", 
                    f"هل تريد معالجة النص التالي؟\n\n{preview[:200]}{'...' if len(preview) > 200 else ''}")
                
                if not confirm:
                    return
                
                
                # معالجة الرسالة مع تحسينات إضافية
                result = BotDataManager.process_whatsapp_accounts(bot_number, cleaned_message)
                
                if result["success"]:
                    # التحقق من صحة البيانات المحفوظة
                    try:
                        saved_data = BotDataManager.load_bot_villages(bot_number - 1)
                        if not saved_data or not saved_data.get("villages"):
                            raise ValueError("فشل في حفظ البيانات بشكل صحيح")
                        
                        # التحقق من صحة كل حساب محفوظ
                        for i, village in enumerate(saved_data.get("villages", [])):
                            email = village.get("email", "").strip()
                            password = village.get("password", "").strip()
                            
                            if not email or not password:
                                raise ValueError(f"بيانات غير صحيحة في الحساب {i+1}")
                            
                            # التحقق من صحة البريد الإلكتروني
                            if not '@' in email or not '.' in email or len(email) < 5:
                                raise ValueError(f"بريد إلكتروني غير صحيح: {email}")
                            
                            # التحقق من عدم وجود رموز خاصة ضارة في البريد
                            if re.search(r'[<>\"\'\\]', email):
                                raise ValueError(f"بريد إلكتروني يحتوي على رموز غير صحيحة: {email}")
                        
                        show_results_window(result, bot_number)
                        messagebox.showinfo("نجح", f"تم حفظ {result['accounts_count']} حساب بنجاح في البوت {bot_number}")
                        
                        # تحديث واجهة البوت المعنية
                        self._update_bot_interface(bot_number - 1)
                        
                    except Exception as validation_error:
                        messagebox.showerror("خطأ في التحقق", 
                            f"تم اكتشاف خطأ في البيانات المحفوظة: {validation_error}\n"
                            "يرجى المحاولة مرة أخرى أو التحقق من صحة النص المدخل.")
                        return
                
                else:
                    error_details = "\n".join(result.get("errors", []))
                    messagebox.showerror("خطأ في المعالجة", 
                        f"{result['message']}\n\nتفاصيل الأخطاء:\n{error_details}")
                    
            except json.JSONDecodeError as json_error:
                messagebox.showerror("خطأ في JSON", 
                    f"خطأ في تنسيق البيانات: {json_error}\n"
                    "يرجى التأكد من صحة النص المدخل.")
            except UnicodeDecodeError as unicode_error:
                messagebox.showerror("خطأ في الترميز", 
                    f"خطأ في ترميز النص: {unicode_error}\n"
                    "يرجى التأكد من أن النص يحتوي على أحرف صحيحة.")
            except Exception as e:
                error_trace = traceback.format_exc()
                print(f"خطأ مفصل: {error_trace}")
                messagebox.showerror("خطأ غير متوقع", 
                    f"حدث خطأ غير متوقع أثناء المعالجة:\n{str(e)}\n\n"
                    "يرجى المحاولة مرة أخرى أو الاتصال بالدعم الفني.")

        def clear_message():
            """مسح رسالة الواتساب"""
            message_text.delete("1.0", tk.END)
        
        
        # أزرار التحكم
        tk.Button(button_frame, text="معالجة الرسالة", command=process_message,
                 bg=LIGHT_THEME['BTN_GREEN'], fg="white", font=LIGHT_THEME['LABEL_FONT'], 
                 relief="flat", padx=20, pady=5).pack(side="left", padx=(0, 10))
        
        tk.Button(button_frame, text="صاق", command=lambda: message_text.event_generate("<<Paste>>"),
                 bg="#3498db", fg="white", font=LIGHT_THEME['LABEL_FONT'], 
                 relief="flat", padx=20, pady=5).pack(side="left", padx=(0, 10))
        

        
        tk.Button(button_frame, text="مسح", command=clear_message,
                 bg="#95a5a6", fg="white", font=LIGHT_THEME['LABEL_FONT'], 
                 relief="flat", padx=20, pady=5).pack(side="left", padx=(0, 10))
        
        tk.Button(button_frame, text="إغلاق", command=whatsapp_window.destroy,
                 bg=LIGHT_THEME['BTN_RED'], fg="white", font=LIGHT_THEME['LABEL_FONT'], 
                 relief="flat", padx=20, pady=5).pack(side="right")
        
        def show_results_window(result, bot_number):
            """عرض نافذة النتائج"""
            results_window = tk.Toplevel(whatsapp_window)
            results_window.title(f"نتائج معالجة البوت {bot_number}")
            results_window.geometry("700x500")
            results_window.configure(bg=LIGHT_THEME['BG_COLOR'])
            
            # إطار العنوان
            title_frame = tk.Frame(results_window, bg=LIGHT_THEME['HEADER_COLOR'])
            title_frame.pack(fill="x", pady=(0, 10))
            
            title_label = tk.Label(title_frame, text=f"نتائج معالجة البوت {bot_number}", 
                                  font=LIGHT_THEME['HEADER_FONT'], 
                                  fg="white", bg=LIGHT_THEME['HEADER_COLOR'])
            title_label.pack(pady=10)
            
            # إطار المحتوى
            content_frame = tk.Frame(results_window, bg=LIGHT_THEME['BG_COLOR'])
            content_frame.pack(fill="both", expand=True, padx=20, pady=10)
            
            # معلومات عامة
            info_frame = tk.Frame(content_frame, bg=LIGHT_THEME['BG_COLOR'])
            info_frame.pack(fill="x", pady=(0, 15))
            
            tk.Label(info_frame, text=f"عدد الحسابات المعالجة: {result['accounts_count']}", 
                    font=LIGHT_THEME['LABEL_FONT'], 
                    bg=LIGHT_THEME['BG_COLOR']).pack(anchor="w")
            
            if result.get('errors'):
                tk.Label(info_frame, text=f"عدد الأخطاء: {len(result['errors'])}", 
                        font=LIGHT_THEME['LABEL_FONT'], 
                        fg="red", bg=LIGHT_THEME['BG_COLOR']).pack(anchor="w")
            
            # قائمة الحسابات
            accounts_frame = tk.Frame(content_frame, bg=LIGHT_THEME['BG_COLOR'])
            accounts_frame.pack(fill="both", expand=True, pady=(0, 15))
            
            tk.Label(accounts_frame, text="الحسابات المعالجة:", 
                    font=LIGHT_THEME['LABEL_FONT'], 
                    bg=LIGHT_THEME['BG_COLOR']).pack(anchor="w")
            
            # إطار للقائمة مع شريط التمرير
            list_frame = tk.Frame(accounts_frame, bg="white", relief="solid", bd=1)
            list_frame.pack(fill="both", expand=True, pady=(5, 0))
            
            accounts_text = tk.Text(list_frame, font=("Cairo", 9),
                                   bg="white", fg="black", relief="flat")
            accounts_text.pack(fill="both", expand=True, side="left")
            
            scrollbar = tk.Scrollbar(list_frame)
            scrollbar.pack(side="right", fill="y")
            accounts_text.config(yscrollcommand=scrollbar.set)
            scrollbar.config(command=accounts_text.yview)
            
            # إضافة الحسابات إلى النص
            for i, account in enumerate(result.get('accounts', []), 1):
                accounts_text.insert(tk.END, f"{i}. البريد: {account['email']}\n")
                accounts_text.insert(tk.END, f"   كلمة المرور: {account['password']}\n")
                accounts_text.insert(tk.END, f"   الخيارات: {account['options']}\n")
                accounts_text.insert(tk.END, f"   الهجوم: {account['Attauck']}\n\n")
            
            accounts_text.config(state="disabled")
            
            # عرض الأخطاء إذا وجدت
            if result.get('errors'):
                errors_frame = tk.Frame(content_frame, bg=LIGHT_THEME['BG_COLOR'])
                errors_frame.pack(fill="both", expand=True, pady=(0, 15))
                
                tk.Label(errors_frame, text="الأخطاء:", 
                        font=LIGHT_THEME['LABEL_FONT'], 
                        fg="red", bg=LIGHT_THEME['BG_COLOR']).pack(anchor="w")
                
                errors_text = tk.Text(errors_frame, height=5, font=("Cairo", 9),
                                     bg="white", fg="red", relief="solid", bd=1)
                errors_text.pack(fill="both", expand=True, pady=(5, 0))
                
                for error in result['errors']:
                    errors_text.insert(tk.END, f"• {error}\n")
                
                errors_text.config(state="disabled")
            
            # أزرار التحكم
            button_frame = tk.Frame(content_frame, bg=LIGHT_THEME['BG_COLOR'])
            button_frame.pack(fill="x")
            
            tk.Button(button_frame, text="إغلاق", 
                     command=results_window.destroy,
                     bg=LIGHT_THEME['BTN_RED'], fg="white",
                     font=LIGHT_THEME['LABEL_FONT'], 
                     relief="flat", padx=20, pady=5).pack(side="right")

    def _update_bot_interface(self, bot_idx):
        """تحديث واجهة البوت بعد إضافة حسابات جديدة"""
        try:
            # مسح الحسابات القديمة
            for comp in self.bot_villages[bot_idx]["components"]:
                comp.destroy()
            self.bot_villages[bot_idx]["components"].clear()
            
            # تحميل الحسابات الجديدة
            self.load_villages(bot_idx)
            
            # الانتقال إلى تبويب الحسابات
            self.notebook.select(1)  # تبويب الحسابات الموحد
            
        except Exception as e:
            print(f"خطأ في تحديث واجهة البوت {bot_idx + 1}: {e}")

    def delete_all_villages(self, bot_idx):
        """حذف جميع الحسابات من البوت المحدد (أمر صريح فقط)."""
        try:
            # تأكيد الحذف
            result = messagebox.askyesno("تأكيد الحذف", 
                                       f"هل أنت متأكد من حذف جميع الحسابات من البوت {bot_idx + 1}؟\n\nهذا الإجراء لا يمكن التراجع عنه!")
            
            if result:
                # مسح جميع المكونات من الواجهة
                for comp in self.bot_villages[bot_idx]["components"]:
                    comp.destroy()
                self.bot_villages[bot_idx]["components"].clear()
                
                # حذف جميع الحسابات من ملف JSON — هذا أمر صريح ومقصود
                data = {"villages": [], "account_index": 0, "__force_clear__": True}
                BotDataManager.save_bot_villages(bot_idx, data)
                
                # عرض رسالة نجاح
                self.show_toast(f"تم حذف جميع الحسابات من البوت {bot_idx + 1}")
                messagebox.showinfo("نجح", f"تم حذف جميع الحسابات من البوت {bot_idx + 1}")
                
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ أثناء حذف الحسابات: {str(e)}")
            print(f"خطأ في حذف جميع الحسابات من البوت {bot_idx + 1}: {e}")

    def Fire_Stages(self, idx):
        """تشغيل مرحلة Fire_Stages وفق الشروط المذكورة. لاحقًا ستضيف المنطق المطلوب."""
        row = self.emulator_rows[idx]
        device_id = row.port   # هذا هو المنفذ (device_id)

        self.show_toast(f"✅ FIRE_Stages تعمل على -{idx+1}")

        try:
            # 1- تشغيل البوت
            self._start_integrated_bot(device_id)
            time.sleep(2)

            self.bot_clicked_flags[idx] = True
            self.bot_start_times[idx] = time.time()
            self.last_correct_stages_call[idx] = time.time()
            # منع استدعاء Correct_Stages مباشرة بعد التشغيل
            self.last_correct_stages_check[idx] = time.time()
            self.show_toast(f"تم تشغيل البوت على BlueStacks-{idx+1}")
            self._update_emulator_row_status(idx)

        except Exception as e:
            self.show_toast(f"❌ خطأ أثناء Fire_Stages للبوت {idx+1}: {e}")
            print(f"[DEBUG] خطأ في Fire_Stages: {e}")

    def _search_email_in_jsons(self):
        try:
            query = self.search_var.get().strip().lower()
            # تجهيز قائمة النتائج
            self.search_results_list.delete(0, tk.END)
            self._search_results_map = []
            if not query:
                self.search_results_list.insert(tk.END, "أدخل بريدًا للبحث")
                return
            results = []  # (bot_number, row_index, email)
            for bot_idx in range(NUM_EMULATORS):
                data = BotDataManager.load_bot_villages(bot_idx)
                villages = data.get("villages", []) if data else []
                for i, v in enumerate(villages, start=1):
                    email = str(v.get("email", "")).strip()
                    if query in email.lower():
                        results.append((bot_idx + 1, i, email))
            if not results:
                self.search_results_list.insert(tk.END, "لا توجد نتائج مطابقة في ملفات البوت")
                return
            for bot_num, row_num, email in results:
                self.search_results_list.insert(tk.END, f"بوت: {bot_num} | صف: {row_num} | {email}")
                # حفظ خريطة الانتقال (bot_idx 0-based, row_index 0-based)
                self._search_results_map.append((bot_num - 1, row_num - 1, email))
        except Exception as e:
            # عرض الخطأ داخل النتائج بدل النوافذ المنبثقة
            self.search_results_list.delete(0, tk.END)
            self.search_results_list.insert(tk.END, f"خطأ أثناء البحث: {str(e)}")

    def _smooth_scroll_canvas(self, canvas, orientation: str, amount_units: int = 6, delay_ms: int = 8):
        try:
            # ألغِ أي حركة سابقة قيد التنفيذ لهذا الـ Canvas
            if hasattr(canvas, '_scroll_job') and canvas._scroll_job is not None:
                try:
                    self.after_cancel(canvas._scroll_job)
                except Exception:
                    pass
        except Exception:
            pass
        steps = abs(amount_units)
        step_dir = 1 if amount_units > 0 else -1
        def do_step(remaining):
            if remaining <= 0:
                try:
                    canvas._scroll_job = None
                except Exception:
                    pass
                return
            try:
                if orientation == 'x':
                    canvas.xview_scroll(step_dir, "units")
                else:
                    canvas.yview_scroll(step_dir, "units")
            except Exception:
                return
            try:
                canvas._scroll_job = self.after(delay_ms, lambda: do_step(remaining - 1))
            except Exception:
                pass
        do_step(steps)

    def _activate_search_result(self):
        try:
            sel = self.search_results_list.curselection()
            if not sel:
                return
            idx = sel[0]
            if idx < 0 or idx >= len(self._search_results_map):
                return
            bot_idx, row_index, email = self._search_results_map[idx]
            # الانتقال لتبويب الحسابات الموحد
            try:
                self.notebook.select(1)
            except Exception:
                pass
            # التمرير لقسم البوت المعني
            try:
                section = self._bot_section_frames[bot_idx]
                self._accounts_canvas.update_idletasks()
                # حساب موقع القسم داخل الـ canvas
                y = section.winfo_y()
                canvas_h = self._accounts_canvas.winfo_height()
                scroll_h = self._accounts_inner.winfo_reqheight()
                if scroll_h > canvas_h:
                    self._accounts_canvas.yview_moveto(y / scroll_h)
            except Exception:
                pass
            # إعلام بالمكان الذي تم الانتقال إليه
            self.show_toast(f"تم الانتقال إلى بوت {bot_idx + 1}، صف {row_index + 1}")
        except Exception:
            pass

if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        app = MainApp()
        app.mainloop()
    except Exception as e:
        error_msg = f"حدث خطأ أثناء بدء الواجهة:\n{e}\n{traceback.format_exc()}"
        print(error_msg)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("خطأ", error_msg)
        except Exception:
            pass