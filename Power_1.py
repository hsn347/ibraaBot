import time
import threading
from typing import List, Dict, Callable
import logging
import uiautomator2 as u2
import json 
import os
from Manager_Json import BotDataManager
from datetime import datetime
from supabase import create_client, Client

from SUM import run_SUM_stage , reset_SUM
from Dream import run_Dream_stage , reset_Dream
from Try import run_Try_stage , reset_Try
from Alliance1 import run_Alliance_stage , reset_Alliance
from Attauck1 import run_attack_stage ,reset_Attauck 
from bot_stage_email1 import run_email_stage ,reset_Email
from Hammer1 import run_Hammer_stage ,reset_Hammer
from Log_IN import run_Log_IN ,reset_Log_IN
from Loot1 import run_loot_stage ,reset_Loot
from protection1 import run_Protection_stage ,reset_Protection
from Troops1 import run_troops_stage, reset_Troops
from Treasure import run_treasure_stage , reset_Treasure
from Bounes import run_Bounes_stage , reset_Bounes

# ============================================================================
# Supabase Client
# ============================================================================

SUPABASE_URL = "https://api.ibraabot.online"   # <-- ضع رابط مشروعك هنا
SUPABASE_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJzdXBhYmFzZSIsImlhdCI6MTc3NTE1MTI0MCwiZXhwIjo0OTMwODI0ODQwLCJyb2xlIjoic2VydmljZV9yb2xlIn0.l6g3dwSSv0gK2Ut0PEEgXj7KSGkmXjZXh66zl7KL8IM"               # <-- ضع مفتاحك هنا

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================================
# دالة مساعدة لتعديل قيمة عمود في Supabase بناءً على شرط تساوي عمود آخر
# ============================================================================

def update_supabase_column(
    table: str,
    update_column: str,
    update_value,
    condition_column: str,
    condition_value
) -> bool:
    """
    تعديل قيمة عمود معين في جدول Supabase بناءً على شرط.

    Args:
        table           : اسم الجدول في Supabase
        update_column   : اسم العمود المراد تعديله
        update_value    : القيمة الجديدة التي سيأخذها العمود
        condition_column: اسم العمود المستخدم في الشرط (مثل user_id)
        condition_value : القيمة التي يجب أن يساويها عمود الشرط

    Returns:
        True  إذا نجحت العملية
        False إذا حدث خطأ

    مثال:
        update_supabase_column(
            table="Accounts",
            update_column="Protection",
            update_value=True,
            condition_column="user_id",
            condition_value="abc-123"
        )
    """
    try:
        response = (
            supabase
            .table(table)
            .update({update_column: update_value})
            .eq(condition_column, condition_value)
            .execute()
        )
        return True
    except Exception as e:
        return False


def fetch_supabase_data(
    table: str,
    condition_column: str,
    condition_value,
    select_columns: str = "*"
) -> list:
    """
    جلب بيانات من جدول Supabase بناءً على شرط تساوي عمود معين لقيمة معينة.

    Args:
        table            : اسم الجدول في Supabase
        condition_column : اسم العمود المستخدم في الشرط (مثل user_id)
        condition_value  : القيمة التي يجب أن يساويها عمود الشرط
        select_columns   : الأعمدة المراد جلبها (افتراضي "*" أي كل الأعمدة)
                           مثال: "user_id, Protection, Alliance"

    Returns:
        قائمة (list) من القواميس تمثل الصفوف المطابقة للشرط
        قائمة فارغة [] في حالة عدم وجود نتائج أو حدوث خطأ

    أمثلة:
        # جلب كل بيانات الصف الذي user_id يساوي "abc-123"
        rows = fetch_supabase_data(
            table="Accounts",
            condition_column="user_id",
            condition_value="abc-123"
        )

        # جلب عمودين فقط
        rows = fetch_supabase_data(
            table="Accounts",
            condition_column="user_id",
            condition_value="abc-123",
            select_columns="Protection, Alliance"
        )

        if rows:
            print(rows[0]["Protection"])
    """
    try:
        response = (
            supabase
            .table(table)
            .select(select_columns)
            .eq(condition_column, condition_value)
            .execute()
        )
        data = response.data or []
        return data
    except Exception as e:
        return []


def action_for_Ottman(device, x, y):
    time.sleep(120)
    device.click(x, y)

my_custom_actions = {
    "image/Ottman.png": action_for_Ottman, # عند رؤية هذه الصورة، سيشغل دالة التمرير
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEVICE_ID = "" 

outflow_import = 0 

now = None

# ===============================
# Heartbeat helper (lightweight)
# ===============================
class HeartbeatWriter:
    def __init__(self, device_id: str, interval_sec: float = 6.0):
        self.device_id = device_id
        self.interval_sec = max(3.0, float(interval_sec))
        self._stop = False
        self._thread = None

    def _atomic_write_json(self, path: str, data: dict) -> None:
        try:
            tmp_path = f"{path}.tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            try:
                os.replace(tmp_path, path)
            except Exception:
                # Fallback non-atomic
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def _loop(self):
        status_path = f"status_{self.device_id}.json"
        pause_flag = f"pause_{self.device_id}.flag"
        while not self._stop:
            try:
                paused = os.path.exists(pause_flag)
                payload = {
                    'is_running': True,
                    'paused': bool(paused),
                    'heartbeat_ts': time.time(),
                    'status': 'متوقف مؤقتاً' if paused else 'يعمل'
                }
                self._atomic_write_json(status_path, payload)
            except Exception:
                pass
            # نوم بسيط لتقليل استهلاك الموارد
            time.sleep(self.interval_sec)

    def start(self):
        if self._thread is not None:
            return
        self._stop = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self, final_running: bool = False, error_msg: str | None = None):
        # إيقاف حلقة heartbeat
        self._stop = True
        try:
            if self._thread is not None and self._thread.is_alive():
                self._thread.join(timeout=1.0)
        except Exception:
            pass
        # كتابة حالة نهائية
        try:
            status_path = f"status_{self.device_id}.json"
            payload = {
                'is_running': bool(final_running),
                'paused': False,
                'heartbeat_ts': time.time(),
                'last_error': error_msg,
                'status': 'يعمل' if final_running else 'متوقف'
            }
            self._atomic_write_json(status_path, payload)
        except Exception:
            pass

# ============================================================================
# نظام إدارة الخطوات مع إمكانية الرجوع
# ============================================================================

class TroopsManager1:
    def __init__(self, device_id: str = DEVICE_ID):
        """
        مدير مرحلة القوات مع إمكانية الرجوع للخطوات
        
        Args:
            device_id: معرف الجهاز
        """
        self.device_id = device_id
        self.device = None
        self.current_step = 0
        self.steps = {}
        self.step_results = {}
        self.is_running = False
        
        # تهيئة الجهاز
        self._init_device()
        
    def _init_device(self):
        """تهيئة الجهاز"""
        try:
            self.device = u2.connect(self.device_id)
        except Exception as e:
            logger.error(f"خطأ")
    
    def add_step(self, step_number: int, step_name: str, step_function: Callable, 
                 description: str = "", required_icons: List[str] = None):

        self.steps[step_number] = {
            'name': step_name,
            'function': step_function,
            'description': description,
            'required_icons': required_icons or []
        }
        
    
    def go_to_step(self, step_number: int):

        if step_number not in self.steps:
        
            return False
        
        self.current_step = step_number
        return True
    
    def execute_step(self, step_number: int = None) -> bool:

        if step_number is not None:
            self.current_step = step_number
        
        if self.current_step not in self.steps:
       
            return False
        
        step = self.steps[self.current_step]
        
        try:
            # تنفيذ دالة الخطوة
            result = step['function'](self.device)
            self.step_results[self.current_step] = result
            
            return True
            
        except Exception as e:
            self.step_results[self.current_step] = False
            return False
    
    def execute_all_steps(self, start_from: int = None):
        """
        تنفيذ جميع الخطوات من خطوة معينة
        
        Args:
            start_from: رقم الخطوة للبدء منها (إذا كان None يبدأ من الخطوة الأولى)
        """
        if start_from is not None:
            self.current_step = start_from
        
        self.is_running = True
        sorted_steps = sorted(self.steps.keys())

        
        for step_num in sorted_steps:
            if step_num < self.current_step:
                continue
                
            if not self.is_running:
                break
            
            success = self.execute_step(step_num)
            if not success:
                break
            
            # التحقق من إيقاف التنفيذ بعد تنفيذ الخطوة
            if not self.is_running:
                break
            
            self.current_step = step_num + 1
        
        self.is_running = False
    
    def restart_from_step(self, step_number: int):

        self.current_step = step_number
        self.execute_all_steps(start_from=step_number)
    
    def go_to_step_and_continue(self, step_number: int):

        self.current_step = step_number
        # إعادة تشغيل execute_all_steps من الخطوة الجديدة
        self.execute_all_steps(start_from=step_number)
    
    def stop_execution(self):
        """إيقاف تنفيذ الخطوات"""
        self.is_running = False

    
    def get_step_info(self, step_number: int) -> Dict:

        if step_number not in self.steps:
            return {}
        
        step = self.steps[step_number]
        return {
            'number': step_number,
            'name': step['name'],
            'description': step['description'],
            'required_icons': step['required_icons'],
            'result': self.step_results.get(step_number, None)
        }
    
    def list_all_steps(self):
        for step_num in sorted(self.steps.keys()):
            step = self.steps[step_num]
            result = self.step_results.get(step_num, "لم يتم التنفيذ")
    
def check_and_shutdown_if_empty(device_id: str):
    """
    فحص ملف JSON المرتبط بالمحاكي:
    - إذا كان يحتوي على 2+ حساب → خروج بدون فعل شيء
    - إذا كان يحتوي على 0 أو 1 حساب → كتابة shutdown flag ليقوم الـ GUI بالإيقاف الآمن

    الـ GUI (_auto_update) يتكفل بـ:
    1. إيقاف البوت (terminate + flags)
    2. إغلاق المحاكي (بعد 5 ثوانٍ من إيقاف البوت)

    Args:
        device_id: منفذ المحاكي مثل "127.0.0.1:5555"
    """
    import os
    from Manager_Json import BotDataManager

    try:
        # 1) تحديد رقم البوت من المنفذ
        bot_number = BotDataManager.get_device_bot_number(device_id)
        if bot_number is None:
            print(f"[check_and_shutdown] لم يُعثر على رقم بوت للمنفذ: {device_id}")
            return

        # 2) تحميل ملف JSON وفحص عدد الحسابات
        data = BotDataManager.load_bot_data(bot_number)
        villages = data.get("villages", []) if data else []
        accounts_count = len(villages)

        print(f"[check_and_shutdown] بوت {bot_number} ({device_id}): عدد الحسابات = {accounts_count}")

        if accounts_count >= 2:
            # يوجد حسابان أو أكثر → خروج بدون فعل شيء
            return

        # ═══════════════════════════════════════════════════
        # 0 أو 1 حساب → كتابة shutdown flag
        # الـ GUI سيقوم بإيقاف البوت + إغلاق المحاكي
        # ═══════════════════════════════════════════════════

        print(f"[check_and_shutdown] ⚠️ حسابات غير كافية ({accounts_count}) → إرسال إشارة إيقاف للـ GUI")

        shutdown_flag = f'shutdown_{device_id}.flag'
        try:
            with open(shutdown_flag, 'w') as f:
                f.write('shutdown')
            print(f"[check_and_shutdown] ✅ تم كتابة ملف الإيقاف: {shutdown_flag}")
        except Exception as e:
            print(f"[check_and_shutdown] ❌ فشل كتابة ملف الإيقاف: {e}")

    except Exception as e:
        print(f"[check_and_shutdown] ❌ خطأ عام: {e}")


def REST_POWER():
    global now , Power_manager1 , email1 , supabase

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)    
    Power_manager1 = None
    now = None

Power_manager1 = None

# ============================================================================
# مثال على كيفية إضافة الخطوات
# ============================================================================

def step_1_2(device):
    reset_Log_IN()
    run_Log_IN(DEVICE_ID)
    time.sleep(1.5)

    current_timestamp = int(time.time())
    email2 = BotDataManager.get_bot_current_email_index(DEVICE_ID)
    update_supabase_column(
            table="Accounts",
            update_column="check_bot",
            update_value=current_timestamp,
            condition_column="Email",
            condition_value=email2
        )

    return True

def step_2_2(device):
    reset_Treasure()
    run_treasure_stage(DEVICE_ID)
    return True

def step_3_2(device):
    reset_Email()
    run_email_stage(DEVICE_ID)
    return True

def step_4_2(device):
    reset_Try()
    run_Try_stage(DEVICE_ID)

    reset_Dream()
    run_Dream_stage(DEVICE_ID)

def step_5_2(device):
    reset_SUM()
    run_SUM_stage(DEVICE_ID)
    return True

def step_6_2(device):
    reset_Hammer()
    run_Hammer_stage(DEVICE_ID)
    return True

def step_7_2(device):

    reset_Alliance()
    run_Alliance_stage(DEVICE_ID)

    TroopsBooleane = BotDataManager.get_bot_Troops(DEVICE_ID)
    if TroopsBooleane:
        reset_Troops()
        run_troops_stage(DEVICE_ID)
        return True

def step_8_2(device):
    current_hour = datetime.now().hour
    
    if 8 <= current_hour <= 23:
        reset_Loot()
        run_loot_stage(DEVICE_ID)
        return True
    else:
        return True

def step_9_1(device):
    # الحصول على عدد المرات التي تم فيها تشغيل البونيس اليوم لهذا الحساب
    run_count = BotDataManager.get_bot_bonus_run_count(DEVICE_ID)
    
    if run_count < 4:
        reset_Bounes()
        run_Bounes_stage(DEVICE_ID)
        # زيادة العداد بعد التشغيل الناجح
        BotDataManager.increment_bot_bonus_run_count(DEVICE_ID)

    return True

def step_9_2(device):
    reset_Attauck()
    run_attack_stage(DEVICE_ID)
    return True

def step_10_2(device):
    global supabase

    ProtectionBooleane = BotDataManager.get_bot_custom_flag(DEVICE_ID)
    if ProtectionBooleane:
        BotDataManager.set_bot_custom_flag_false(DEVICE_ID)
        reset_Protection()
        run_Protection_stage(DEVICE_ID)

        email1 = BotDataManager.get_bot_current_email_index(DEVICE_ID)

        update_supabase_column(
            table="Accounts",
            update_column="Protection",
            update_value=False,
            condition_column="Email",
            condition_value=email1
        )

    return True
           

def run_Power_manager1(device_id: str = None):

    global Power_manager1 , DEVICE_ID
    
    try:
        hb = None
        if Power_manager1 is None or (device_id and (Power_manager1.device_id != device_id)):
            Power_manager1 = TroopsManager1(device_id)
            DEVICE_ID = device_id

            Power_manager1.add_step(1, "مرحلة البريد", step_1_2, "مرحلة البريد") 
            Power_manager1.add_step(2, "مرحلة البريد", step_2_2, "مرحلة البريد") 
            Power_manager1.add_step(3, "مرحلة الشراء", step_3_2, "مرحلة الشراء")
            Power_manager1.add_step(4, "مرحلة جمع الموارد", step_4_2, "مرحلة جمع الموارد")  
            Power_manager1.add_step(5, "مرحلة المطرقة", step_5_2, "مرحلة المطرقة")   
            Power_manager1.add_step(6, "مرحلة التحالف", step_6_2, "مرحلة التحالف")
            Power_manager1.add_step(7, "مرحلة الجنود", step_7_2, "مرحلة تدريب الجنود")                    
            Power_manager1.add_step(8, "مرحلة Loot", step_8_2, "مرحلة Loot")
            Power_manager1.add_step(9, "مرحلة البونيس", step_9_1, "مرحلة البونيس")  
            Power_manager1.add_step(10,"مرحلة الهجوم", step_9_2,"مرحلة الهجوم")  
            Power_manager1.add_step(11, "الاعادة", step_10_2, "الاعادة")  
                
        hb = HeartbeatWriter(DEVICE_ID, interval_sec=6.0)
        hb.start()

        Power_manager1.execute_all_steps()
        
        while Power_manager1.step_results.get(11) is True:
            Power_manager1.step_results.clear()
            time.sleep(1)
            Power_manager1.execute_all_steps(start_from=1)
        
        if hb:
            hb.stop(final_running=False)
        
    except Exception as e:
        try:
            if 'hb' in locals() and hb:
                hb.stop(final_running=False, error_msg=str(e))
        except Exception:
            pass
        return False


if __name__ == "__main__":
    run_Power_manager1(DEVICE_ID)

    