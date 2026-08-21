import cv2
from functools import lru_cache

@lru_cache(maxsize=None)
def cached_imread(image_path):
    return cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
import numpy as np
import time
import threading
from typing import Optional, Tuple, List, Union, Dict, Callable
import logging
import uiautomator2 as u2
from Path import run_Path , reset_Path
from Manager_Json import BotDataManager
import requests
import subprocess
import sys

def action_for_Ottman(device, x, y):
    time.sleep(120)
    device.click(x, y)
    time.sleep(30)

my_custom_actions = {
    "image/Ottman.png": action_for_Ottman, # عند رؤية هذه الصورة، سيشغل دالة التمرير
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEVICE_ID = "127.0.0.1:5665"

CURRENT_DEVICE = None


outflow_import_2 = 0 
Check_Case = 0 
attempt = 0
Current_account_email = None
try_woodmini = False
# ============================================================================
# نظام إدارة الخطوات مع إمكانية الرجوع
# ============================================================================

class TroopsManager2:
    def __init__(self, device_id: str = DEVICE_ID):

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
        
            raise
    
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
        """
        تنفيذ خطوة معينة
        
        Args:
            step_number: رقم الخطوة (إذا كان None يتم تنفيذ الخطوة الحالية)
            
        Returns:
            bool: نجح التنفيذ أم لا
        """
        if step_number is not None:
            self.current_step = step_number
        
        if self.current_step not in self.steps:
           
            return False
        
        step = self.steps[self.current_step]
      
        
        try:
            # تنفيذ دالة الخطوة
            result = step['function'](self.device)
            self.step_results[self.current_step] = result
            
            # التحقق من إيقاف التنفيذ بعد تنفيذ الخطوة
            if not self.is_running:
            
                return False
            
        
            return True
            
        except Exception as e:
       
            self.step_results[self.current_step] = False
            return False
    
    def execute_all_steps(self, start_from: int = None):

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
                # التحقق من سبب الفشل
                if not self.is_running:
                 
                    break
                else:
                   
                    break
            
            # التحقق من إيقاف التنفيذ بعد تنفيذ الخطوة
            if not self.is_running:
             
                break
            
            self.current_step = step_num + 1
        
        self.is_running = False
     
    
    def restart_from_step(self, step_number: int):
        """
        إعادة تشغيل من خطوة معينة
        
        Args:
            step_number: رقم الخطوة للبدء منها
        """
      
        self.current_step = step_number
        self.execute_all_steps(start_from=step_number)
    
    def go_to_step_and_continue(self, step_number: int):
        """
        الانتقال إلى خطوة معينة والاستمرار في تنفيذ باقي الخطوات
        
        Args:
            step_number: رقم الخطوة للانتقال إليها
        """
       
        self.current_step = step_number
        # إعادة تشغيل execute_all_steps من الخطوة الجديدة
        self.execute_all_steps(start_from=step_number)
    
    def stop_execution(self):
        """إيقاف تنفيذ الخطوات"""
        self.is_running = False

    
    def get_step_info(self, step_number: int) -> Dict:
        """
        الحصول على معلومات خطوة معينة
        
        Args:
            step_number: رقم الخطوة
            
        Returns:
            Dict: معلومات الخطوة
        """
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
        """عرض جميع الخطوات"""
     
        for step_num in sorted(self.steps.keys()):
            step = self.steps[step_num]
            result = self.step_results.get(step_num, "لم يتم التنفيذ")


def reset_Log_IN():
    global try_woodmini , CURRENT_DEVICE , outflow_import_2, Check_Case, Current_account_email, Log_IN_manager , attempt

    CURRENT_DEVICE = None
    outflow_import_2 = 0
    Check_Case = 0
    attempt = 0
    try_woodmini = False
    Current_account_email = None
    Log_IN_manager = None

# ============================================================================
# دوال مساعدة للخطوات
# ============================================================================
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

def find_icon(device, icon_paths: Union[str, List[str]], 
              screen_region: Tuple[int, int, int, int] = None,
              timeout: float = 5.0) -> Optional[Tuple[int, int]]:
    """
    البحث عن أيقونة مع timeout وثلاث عتبات للبحث
    
    Args:
        device: الجهاز المستخدم للتقاط الشاشة
        icon_paths: مسار الأيقونة أو قائمة مسارات الأيقونات
        screen_region: منطقة البحث في الشاشة (x1, y1, x2, y2) - إذا كان None يتم البحث في الشاشة كاملة
        timeout: وقت الانتظار بالثواني
        
    Returns:
        Tuple[int, int] أو None: إحداثيات الأيقونة إذا وجدت، None إذا لم توجد
        
    مثال على الاستدعاء:
        # البحث عن أيقونة واحدة في الشاشة كاملة
        coordinates = find_icon(device, "image/icon.png")
        
        # البحث عن أيقونة في منطقة محددة
        coordinates = find_icon(device, "image/icon.png", screen_region=(10, 100, 40, 400))
        
        # البحث عن عدة أيقونات مع timeout
        coordinates = find_icon(device, ["image/icon1.png", "image/icon2.png"], 
                              screen_region=(0, 0, 200, 300), timeout=3.0)
    """
    # تحويل icon_paths إلى قائمة إذا كان string
    if isinstance(icon_paths, str):
        icon_paths = [icon_paths]
        
    # متغير مشترك لتخزين النتيجة
    result = {'coordinates': None, 'found': False}
    
    def search_icon():
        try:
            # التقاط الشاشة
            screenshot = device.screenshot()
            
            # إذا كانت هناك منطقة محددة، قص الصورة
            if screen_region:
                x1, y1, x2, y2 = screen_region
                # قص الصورة حسب المنطقة المحددة
                screenshot = screenshot.crop((x1, y1, x2, y2))
            
            # تحويل إلى numpy array
            screenshot_np = np.array(screenshot)
            screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
            
            # البحث في كل أيقونة
            for icon_path in icon_paths:
                try:
                    icon = cached_imread(icon_path)
                    if icon is None:
                        
                        continue
                        
                    # البحث بثلاث عتبات
                    thresholds = [0.8, 0.7, 0.6]  # عالية، متوسطة، تحت المتوسطة
                    
                    for threshold in thresholds:
                        if result['found']:
                            break
                            
                        # البحث باستخدام template matching
                        result_match = cv2.matchTemplate(screenshot_gray, icon, cv2.TM_CCOEFF_NORMED)
                        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result_match)
                        
                        if max_val >= threshold:
                            # حساب مركز الأيقونة
                            icon_height, icon_width = icon.shape
                            center_x = max_loc[0] + icon_width // 2
                            center_y = max_loc[1] + icon_height // 2
                            
                            # إضافة offset إذا كانت هناك منطقة محددة
                            if screen_region:
                                center_x += screen_region[0]
                                center_y += screen_region[1]
                            
                            result['coordinates'] = (center_x, center_y)
                            result['found'] = True
                   
                            break
                            
                except Exception as e:
                   
                    continue
                    
        except Exception as e:
            logger.error(f"خطأ في لصورة: {e}")
    
    # إنشاء thread للبحث مع timeout
    search_thread = threading.Thread(target=search_icon)
    search_thread.daemon = True
    search_thread.start()
    
    # انتظار النتيجة مع timeout
    search_thread.join(timeout)
    
    if search_thread.is_alive():
  
        return None
        
    return result['coordinates']

def wait_for_icon(device, icon_path: str, screen_region: Tuple[int, int, int, int] = None, 
                  timeout: float = 10.0) -> bool:

    start_time = time.time()
    while time.time() - start_time < timeout:
        coordinates = find_icon(device, icon_path, screen_region)
        if coordinates:
          
            return True
        time.sleep(0.8)
    

    return False

def wait_for_icon_2(device, icon_path: str, screen_region: Tuple[int, int, int, int] = None, 
                  timeout: float = 10.0) -> bool:

    start_time = time.time()
    while time.time() - start_time < timeout:
        coordinates = find_icon(device, icon_path, screen_region)
        if coordinates:
     
            return True
        time.sleep(2)
    
    
    return False

def wait_for_icon_coordinates(device, icon_path: str, screen_region: Tuple[int, int, int, int] = None, 
                              timeout: float = 10.0) -> Optional[Tuple[int, int]]:

    start_time = time.time()
    while time.time() - start_time < timeout:
        coordinates = find_icon(device, icon_path, screen_region)
        if coordinates:
            
            return coordinates
        time.sleep(0.8)
    return None

def Clean_fast(device, target_icons: list = None, custom_actions: dict = None, max_attempts: int = 10) -> bool:

    global my_custom_actions
    if target_icons is None:
         import clean_fast_config
         target_icons = clean_fast_config.TARGET_ICONS_DEFAULT
    
    if custom_actions is None:
        custom_actions = my_custom_actions
        
    global attempt
    for attempt in range(max_attempts):
        if attempt >= max_attempts - 1:
            attempt = 0
            check_and_shutdown_if_empty(CURRENT_DEVICE)
            reset_Path()
            run_Path(CURRENT_DEVICE)
            Clean_fast(device, target_icons, custom_actions, max_attempts)
            if 'Log_IN_manager' in globals() and Log_IN_manager is not None:
                return Log_IN_manager.stop_execution()
            return False

        found_any = False
        try:
            # التقاط الشاشة مرة واحدة لجميع الصور لتوفير الموارد
            screenshot = device.screenshot()
            screenshot_np = np.array(screenshot)
            screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
            
            for icon_path in target_icons:
                try:
                    icon = cached_imread(icon_path)
                    if icon is None:
                        continue
                        
                    thresholds = [0.8, 0.7, 0.6]
                    icon_found = False
                    
                    for threshold in thresholds:
                        if icon_found:
                            break
                            
                        result_match = cv2.matchTemplate(screenshot_gray, icon, cv2.TM_CCOEFF_NORMED)
                        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result_match)
                        
                        if max_val >= threshold:
                            icon_height, icon_width = icon.shape
                            center_x = max_loc[0] + icon_width // 2
                            center_y = max_loc[1] + icon_height // 2
                            
                            found_any = True
                            icon_found = True
                            
                            if icon_path in custom_actions:
                                try:
                                    # تنفيذ الإجراء المخصص الممرر
                                    custom_actions[icon_path](device, center_x, center_y)
                                except Exception as e:
                                    logger.error(f"خطأ")
                            else:
                                # التصرف الافتراضي
                                device.click(center_x, center_y)
                                
                            time.sleep(0.5)
                except Exception as e:
                    logger.error(f"خطأ")
        except Exception as e:
            logger.error(f"خطأ")
        
        if not found_any:
            break
            
        time.sleep(0.3)
  
def click_coordinates(device, x: int, y: int) -> bool:
    """
    النقر على إحداثيات محددة
    
    Args:
        device: الجهاز
        x: الإحداثي الأفقي
        y: الإحداثي العمودي
        
    Returns:
        bool: نجح النقر أم لا
    """
    try:
        device.click(x, y)
   
        return True
    except Exception as e:
      
        return False

def long_click_coordinates(device, x: int, y: int, duration: float = 1.0) -> bool:

    try:
        # تحديد معرف الجهاز
        if hasattr(device, 'device_id'):
            device_id = device.device_id
        elif hasattr(device, 'serial'):
            device_id = device.serial
        elif isinstance(device, str):
            device_id = device
        else:
            device_id = DEVICE_ID
        
        # تحويل المدة إلى مللي ثانية
        duration_ms = int(duration * 1000)
        
        # النقر المطول باستخدام ADB
        result = subprocess.run([
            "adb", "-s", device_id, "shell", "input", "swipe",
            str(x), str(y), str(x), str(y), str(duration_ms)
        ], capture_output=True, timeout=10, check=True ,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0)
        
        return True
        
    except subprocess.TimeoutExpired:
        return False
        
    except subprocess.CalledProcessError as e:
        return False
        
    except Exception as e:
        return False

def clear_input_field(device) -> bool:
    """
    مسح حقل الإدخال المحدد حالياً
    
    Args:
        device: الجهاز
        
    Returns:
        bool: True إذا نجح المسح، False إذا فشل
    """
    try:

        
        # تحديد معرف الجهاز
        if hasattr(device, 'device_id'):
            device_id = device.device_id
        elif hasattr(device, 'serial'):
            device_id = device.serial
        elif isinstance(device, str):
            device_id = device
        else:
            device_id = DEVICE_ID
        
        # استخدام Ctrl+A لتحديد كل النص ثم Delete لحذفه
        # أو استخدام Ctrl+A ثم Backspace
        result = subprocess.run([
            "adb", "-s", device_id, "shell", "input", "keyevent", "KEYCODE_CTRL_A"
        ], capture_output=True, timeout=3, check=True ,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0)
        
        time.sleep(0.1)  # انتظار قصير
        
        result = subprocess.run([
            "adb", "-s", device_id, "shell", "input", "keyevent", "KEYCODE_DEL"
        ], capture_output=True, timeout=3, check=True , creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0)
        
        return True
        
    except subprocess.TimeoutExpired:
        return False
        
    except subprocess.CalledProcessError as e:
        return False
        
    except Exception as e:
        return False

def input_text(device, text: str) -> bool:

    try:
        if hasattr(device, 'device_id'):
            device_id = device.device_id
        elif hasattr(device, 'serial'):
            device_id = device.serial
        elif isinstance(device, str):
            device_id = device
        else:
            device_id = DEVICE_ID
        
        # تنظيف النص للاستخدام مع ADB (إزالة الأحرف الخاصة)
        clean_text = text.replace(' ', '%s').replace('&', '\\&').replace('<', '\\<').replace('>', '\\>')
        
        # كتابة النص في حقل الإدخال
        result = subprocess.run([
            "adb", "-s", device_id, "shell", "input", "text", clean_text
        ], capture_output=True, timeout=5, check=True , creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0)
        
        return True
        
    except subprocess.TimeoutExpired:
        return False
        
    except subprocess.CalledProcessError as e:
        return False
        
    except Exception as e:
        return False

def send_whatsapp_message(message: str, phone_number: str = "967778076543", api_key: str = "2386676") -> bool:
    """
    إرسال رسالة إلى واتساب عبر CallMeBot
    Args:
        message (str): نص الرسالة
        phone_number (str): رقم الهاتف مع كود الدولة (افتراضي: اليمن)
        api_key (str): مفتاح API من CallMeBot
    Returns:
        bool: True إذا نجح الإرسال، False إذا فشل
    """
    url = (
        f"https://api.callmebot.com/whatsapp.php"
        f"?phone={phone_number}&text={requests.utils.quote(message)}&apikey={api_key}"
    )
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return True
        else:
            return False
    except Exception as e:
        return False


# ============================================================================
# مثال على كيفية إضافة الخطوات
# ============================================================================

def step_1_Clean(device):
    Clean_fast(device)
    return True

def step_2_Setting(device):
    click_coordinates(device , 45 , 75)
    result_Setting = wait_for_icon_coordinates(device, "image/setting.png" ,screen_region=(580 , 1160 , 720 ,1280), timeout=3)
    if result_Setting:
        time.sleep(0.3)
        x , y = result_Setting
        click_coordinates(device , x , y)
        return True
    else:
        return Log_IN_manager.go_to_step_and_continue(1)

def step_3_Account(device):
    result_Acount = wait_for_icon_coordinates(device, "image/Acount.png" ,screen_region=(0 , 150 , 200 ,360), timeout=3)
    if result_Acount:
        time.sleep(0.3)
        x , y = result_Acount
        click_coordinates(device , x , y)
        return True
    else:
        return Log_IN_manager.go_to_step_and_continue(1)

def step_4_Onemt(device):
    result_Onemt = wait_for_icon(device, "image/Onemt.png" ,screen_region=(150 , 150 , 570 ,280), timeout=3)
    if result_Onemt:
        time.sleep(0.3)
        click_coordinates(device , 440 , 1200)
        result_Switch = wait_for_icon(device, "image/Switch.png" ,screen_region=(0 , 80 , 320 ,150), timeout=3)
        if result_Switch:
            return True
        else:
            result_warring = wait_for_icon_coordinates(device, "image/warring.png" ,screen_region=(0 , 300 , 720 ,900), timeout=2)
            if result_warring:
                time.sleep(0.3)
                x , y = result_warring
                click_coordinates(device , x , y)
            else:
                return Log_IN_manager.go_to_step_and_continue(1)
    else:
        return Log_IN_manager.go_to_step_and_continue(1)

def step_5_Log(device):
    global outflow_import_2
    outflow_import_2 += 1
    if outflow_import_2 >= 12:
        outflow_import_2 = 0
        return Log_IN_manager.go_to_step_and_continue(1)

    global Current_account_email
    Current_account_email = BotDataManager.get_bot_email_index(CURRENT_DEVICE)
    click_coordinates(device , 121 , 293)
    time.sleep(0.2)
    long_click_coordinates(device , 121 , 293)
    time.sleep(0.2)
    clear_input_field(device)
    time.sleep(0.2)
    input_text(device , Current_account_email)
    time.sleep(0.2)
    click_coordinates(device , 360 , 440)
    time.sleep(1)
    BotDataManager.increace_account_index(CURRENT_DEVICE)
    
    account_index_P_L = BotDataManager.get_account_index(CURRENT_DEVICE)
    if account_index_P_L == 0:
        BotDataManager.reset_save_counter(CURRENT_DEVICE)
    return True

def step_6_Check(device):
    global Check_Case
    if Check_Case >= 7:
        Check_Case = 0
        return Log_IN_manager.go_to_step_and_continue(1)
    
    result_LogIn =  wait_for_icon(device, "image/LogIn.png" ,screen_region=(150 , 450 , 550 ,750), timeout=8)
    if result_LogIn:
        return True

    result_Sign =  wait_for_icon(device, "image/sign.png" ,screen_region=(150 , 450 , 550 ,750), timeout=2)
    if result_Sign :
        return Log_IN_manager.go_to_step_and_continue(5)

    result_Next =  wait_for_icon(device, "image/next.png" ,screen_region=(150 , 350 , 550 ,550), timeout=2)
    if result_Next :
        return Log_IN_manager.go_to_step_and_continue(5)

    Check_Case += 1
    return Log_IN_manager.go_to_step_and_continue(5)

def step_7_Password(device):
    global Current_account_email
    Current_account_password = BotDataManager.get_bot_password_for_email(CURRENT_DEVICE , Current_account_email)
    input_text(device ,Current_account_password )
    time.sleep(1)
    click_coordinates(device , 360 , 600)
    time.sleep(2)
    return True

def step_8_Sure1(device):
    result_Sure1 = wait_for_icon(device, "image/sure1.png" ,screen_region=(120 , 20 , 620 ,288), timeout=8)
    if result_Sure1:
        return True
    else:
        global Current_account_email
        send_whatsapp_message(f"كلمة سر الحساب {Current_account_email} غير صحيحة")
        return Log_IN_manager.go_to_step_and_continue(5)

def step_9_Wood(device):
    time.sleep(3)
    result_Woodmini = wait_for_icon_2(device, "image/woodmini.png" ,screen_region=(0 , 0 , 280 ,50), timeout=40)
    if result_Woodmini:
        return True
    else:
        global Current_account_email , try_woodmini
        send_whatsapp_message(f"لم تظهر ايقونة woodmini , لقد تم ايقاف تشغيل البوت بسبب عدم تسجيل الدخول الى حساب {Current_account_email}")
        if try_woodmini:
            try_woodmini = False
            return Log_IN_manager.stop_execution()
        try_woodmini = True
        return Log_IN_manager.go_to_step_and_continue(1)

Log_IN_manager = None 

def run_Log_IN(device_id: str = None):

    global Log_IN_manager , CURRENT_DEVICE
    
    try:
        # إنشاء مدير القوات عند أول تشغيل فقط
        if Log_IN_manager is None or (device_id and (Log_IN_manager.device_id != device_id)):
            Log_IN_manager = TroopsManager2(device_id or DEVICE_ID)
            CURRENT_DEVICE = device_id or DEVICE_ID
            
            # إضافة الخطوات
            Log_IN_manager.add_step(1, "فتح قائمة القوات", step_1_Clean, "فتح قائمة القوات من القائمة الرئيسية")
            Log_IN_manager.add_step(2, "فتح قائمة القوات", step_2_Setting, "فتح قائمة القوات من القائمة الرئيسية")
            Log_IN_manager.add_step(3, "فتح قائمة القوات", step_3_Account, "فتح قائمة القوات من القائمة الرئيسية")
            Log_IN_manager.add_step(4, "فتح قائمة القوات", step_4_Onemt, "فتح قائمة القوات من القائمة الرئيسية")
            Log_IN_manager.add_step(5, "فتح قائمة القوات", step_5_Log, "فتح قائمة القوات من القائمة الرئيسية")
            Log_IN_manager.add_step(6, "فتح قائمة القوات", step_6_Check, "فتح قائمة القوات من القائمة الرئيسية")
            Log_IN_manager.add_step(7, "فتح قائمة القوات", step_7_Password, "فتح قائمة القوات من القائمة الرئيسية")
            Log_IN_manager.add_step(8, "فتح قائمة القوات", step_8_Sure1, "فتح قائمة القوات من القائمة الرئيسية")
            Log_IN_manager.add_step(9, "فتح قائمة القوات", step_9_Wood, "فتح قائمة القوات من القائمة الرئيسية")

        Log_IN_manager.execute_all_steps()
        
    except Exception as e:
        return False



if __name__ == "__main__":
    run_Log_IN(DEVICE_ID)

    
