import cv2
import numpy as np
import time
import threading
from typing import Optional, Tuple, List, Union, Dict, Callable
import logging
import uiautomator2 as u2
from Manager_Json import BotDataManager
from Path import run_Path , reset_Path
import sys
import subprocess

def action_for_Ottman(device, x, y):
    time.sleep(120)
    device.click(x, y)

my_custom_actions = {
    "image/Ottman.png": action_for_Ottman, # عند رؤية هذه الصورة، سيشغل دالة التمرير
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEVICE_ID = "127.0.0.1:5615"
scroll_Attempts = 0
outflow_import = 0 
outflow_import2 = 0 
outflow_import8 = 0
index_Att = 0 
level_Att = 6
Continue_Attempts = 0 

CURRENT_DEVICE = None
attempt = 0
attempt_4 = 0

# ============================================================================
# نظام إدارة الخطوات مع إمكانية الرجوع
# ============================================================================

class TroopsManager:
    def __init__(self, device_id: str = DEVICE_ID):

        self.device_id = device_id
        self.device = None
        self.current_step = 0
        self.steps = {}
        self.step_results = {}
        self.is_running = False
        
        self._init_device()
        
    def _init_device(self):
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

        if step_number is not None:
            self.current_step = step_number
        
        if self.current_step not in self.steps:
            return False
        
        step = self.steps[self.current_step]
        
        try:
            result = step['function'](self.device)
            self.step_results[self.current_step] = result
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
                break
    
            if not self.is_running:
                break
    
            self.current_step = step_num + 1
        
        self.is_running = False
    
    def restart_from_step(self, step_number: int):
        self.current_step = step_number
        self.execute_all_steps(start_from=step_number)
    
    def go_to_step_and_continue(self, step_number: int):
        self.current_step = step_number
        self.execute_all_steps(start_from=step_number)
    
    def stop_execution(self):
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


def reset_Attauck():
    global attempt_4 , outflow_import8, outflow_import , outflow_import2 , CURRENT_DEVICE , index_Att , level_Att , Attauck_manager , scroll_Attempts ,Continue_Attempts , attempt

    attempt = 0
    attempt_4 = 0
    scroll_Attempts = 0
    Continue_Attempts = 0
    outflow_import = 0 
    outflow_import2 = 0 
    outflow_import8 = 0
    index_Att = 0 
    level_Att = 6
    CURRENT_DEVICE = None
    Attauck_manager = None

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
                    icon = cv2.imread(icon_path, cv2.IMREAD_GRAYSCALE)
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
            logger.error(f"خطأ في التقاط الشاشة أو معالجة الصورة: {e}")
    
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
        time.sleep(0.7)
    
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
        time.sleep(0.7)
    
    return None

def Clean_fast(device, target_icons: list = None, custom_actions: dict = None, max_attempts: int = 10) -> bool:

    global my_custom_actions
    if target_icons is None:
         target_icons = ["image/prev.png", "image/x.png", "image/disable.png", "image/prev2.png", "image/TryAgainGreen.png", "image/ok.png", "image/Ottman.png"]
    
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
            if 'Attack_manager' in globals() and Attack_manager is not None:
                return Attack_manager.stop_execution()
            return False

        found_any = False
        try:
            # التقاط الشاشة مرة واحدة لجميع الصور لتوفير الموارد
            screenshot = device.screenshot()
            screenshot_np = np.array(screenshot)
            screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
            
            for icon_path in target_icons:
                try:
                    icon = cv2.imread(icon_path, cv2.IMREAD_GRAYSCALE)
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

    try:
        device.click(x, y)
        return True
    except Exception as e:
        return False

def long_click_coordinates(device, x: int, y: int, duration: float = 1.0) -> bool:
    """
    النقر المطول على إحداثيات محددة باستخدام ADB
    
    Args:
        device: الجهاز
        x: الإحداثي الأفقي
        y: الإحداثي العمودي
        duration: مدة النقر بالثواني (افتراضي: 1.0 ثانية)
        
    Returns:
        bool: نجح النقر المطول أم لا
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
        
        # تحويل المدة إلى مللي ثانية
        duration_ms = int(duration * 1000)
        
        # النقر المطول باستخدام ADB
        result = subprocess.run([
            "adb", "-s", device_id, "shell", "input", "swipe",
            str(x), str(y), str(x), str(y), str(duration_ms)
        ], capture_output=True, timeout=10, check=True , creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0)
        
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
    """
    كتابة نص في حقل الإدخال المحدد حالياً
    
    Args:
        device: الجهاز
        text: النص المراد إدخاله
        
    Returns:
        bool: True إذا نجح الإدخال، False إذا فشل
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

def scroll_device(device, x1: int, y1: int, x2: int, y2: int, scroll_speed: int = 1000) -> bool:
    """
    دالة التمرير على الجهاز باستخدام ADB
    
    """
    try:
        # تحديد معرف الجهاز
        if hasattr(device, 'device_id'):
            # إذا كان device كائن TroopsManager
            device_id = device.device_id
        elif hasattr(device, 'serial'):
            # إذا كان device كائن u2.Device
            device_id = device.serial
        elif isinstance(device, str):
            # إذا كان device معرف الجهاز كسلسلة نصية
            device_id = device
        else:
            # استخدام المعرف الافتراضي
            device_id = DEVICE_ID
        
        # تنفيذ أمر التمرير عبر ADB
        result = subprocess.run([
            "adb", "-s", device_id, "shell", "input", "swipe",
            str(x1), str(y1), str(x2), str(y2), str(scroll_speed)
        ], capture_output=True, timeout=5, check=True , creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0)
        

        return True
        
    except subprocess.TimeoutExpired:
 
        return False
        
    except subprocess.CalledProcessError as e:
 
        return False
        
    except Exception as e:
     
        return False


def find_multiple_icons(device, icon_paths: List[str], 
                       timeout: float = 10.0,
                       threshold: float = 0.7,
                       screen_region: Tuple[int, int, int, int] = None) -> Optional[Tuple[str, Tuple[int, int]]]:
    """
    البحث عن عدة أيقونات في نفس الوقت وإرجاع أول أيقونة توجد
    
    Args:
        device: الجهاز المستخدم للتقاط الشاشة
        icon_paths: قائمة مسارات الأيقونات للبحث عنها
        timeout: المدة المحددة للبحث بالثواني
        threshold: العتبة المستخدمة في البحث (افتراضي: 0.7)
        screen_region: منطقة البحث في الشاشة (x1, y1, x2, y2) - إذا كان None يتم البحث في الشاشة كاملة
        
    Returns:
        Tuple[str, Tuple[int, int]] أو None: (مسار الأيقونة, إحداثيات الأيقونة) إذا وجدت، None إذا لم توجد
    """
    # متغير مشترك لتخزين النتيجة
    result = {'found_icon': None, 'coordinates': None, 'found': False}
    
    def search_multiple_icons():
        try:
            # التقاط الشاشة
            screenshot = device.screenshot()
            
            # إذا كانت هناك منطقة محددة، قص الصورة
            if screen_region:
                x1, y1, x2, y2 = screen_region
                screenshot = screenshot.crop((x1, y1, x2, y2))
            
            # تحويل إلى numpy array
            screenshot_np = np.array(screenshot)
            screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
            
            # البحث في كل أيقونة
            for icon_path in icon_paths:
                if result['found']:  # إذا وُجدت أيقونة بالفعل، توقف عن البحث
                    break
                    
                try:
                    icon = cv2.imread(icon_path, cv2.IMREAD_GRAYSCALE)
                    if icon is None:
                        continue
                    
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
                        
                        result['found_icon'] = icon_path
                        result['coordinates'] = (center_x, center_y)
                        result['found'] = True
                        break
                        
                except Exception as e:
                    continue
                    
        except Exception as e:
            logger.error(f"خطأ في البحث عن الأيقونات: {e}")
    
    # البحث مع timeout
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if result['found']:
            break
            
        # إنشاء thread للبحث
        search_thread = threading.Thread(target=search_multiple_icons)
        search_thread.daemon = True
        search_thread.start()
        search_thread.join(0.5)  # فحص كل 0.5 ثانية
        
        if result['found']:
            break
            
        time.sleep(0.1)  # انتظار قصير قبل المحاولة التالية
    
    if result['found']:
        return (result['found_icon'], result['coordinates'])
    else:
        return None

# ============================================================================
# دالة قراءة أنواع القرى للهجوم من ملف JSON
# ============================================================================

def get_attack_village_types_for_account(device) -> List[str]:

    try:
        import json
        import os
        
        # تحديد رقم البوت من معرف الجهاز
        bot_number = BotDataManager.get_device_bot_number(device)
        # مسار ملف JSON
        json_file_path = f"bot_data/bot_{bot_number}_villages.json"
        
        # التحقق من وجود الملف
        if not os.path.exists(json_file_path):
            return []
        
        # قراءة ملف JSON
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        # الحصول على account_index من الملف
        account_index = data.get('account_index', 0)
        
        # حساب الحساب المطلوب
        if 'villages' in data:
            total_accounts = len(data['villages'])
            if account_index == 0:
                # إذا كان account_index = 0، استخدم آخر حساب
                target_account_index = total_accounts - 1
               
            else:
                # استخدم account_index - 1
                target_account_index = account_index - 1
            
            # التحقق من وجود الحساب
            if 0 <= target_account_index < total_accounts:
                village = data['villages'][target_account_index]
                if 'Attauck' in village and isinstance(village['Attauck'], list):
                    attack_types = village['Attauck']
                    
                    return attack_types
                else:
                    
                    return []
            else:
                
                return []
        else:
          
            return []
        
    except Exception as e:
        return []

def get_attack_village_image_paths(device) -> List[str]:
    """
    قراءة مسارات صور القرى للهجوم للحساب الحالي من ملف JSON
    
    Args:
        device: الجهاز أو معرف الجهاز
        
    Returns:
        List[str]: قائمة بمسارات صور القرى للهجوم للحساب الحالي
    """
    try:
        # الحصول على أسماء القرى
        village_names = get_attack_village_types_for_account(CURRENT_DEVICE)
        
        if not village_names:
            return []
        
        # قاموس تحويل أسماء القرى إلى مسارات الصور
        village_to_image_mapping = {
            "خشب": "image/woodAtt.png",
            "قمح": "image/qmhAtt.png", 
            "فحم": "image/ironAtt.png",
            "ألماس": "image/almasAtt.png",  # اسم بديل للماس
        }
        
        # تحويل أسماء القرى إلى مسارات الصور
        image_paths = []
        for village_name in village_names:
            if village_name in village_to_image_mapping:
                image_path = village_to_image_mapping[village_name]
                image_paths.append(image_path)
        return image_paths
        
    except Exception as e:
        return []

def Attauck_Clean_fast(device):
    global attempt_4
    attempt_4 += 1
    if attempt_4 >= 4:
        attempt_4 = 0 
        return exit()
    Clean_fast(device)
    result_Ring2 = wait_for_icon(device, "image/ring2.png" ,screen_region=(0, 400, 200, 900),timeout=2)
    if result_Ring2:
        return Attauck_manager.stop_execution()
    else:
        click_coordinates(device, 360 , 1230)
        result_Ring2 = wait_for_icon(device, "image/ring2.png" ,screen_region=(0, 400, 200, 900),timeout=8)
        if result_Ring2:
            return Attauck_manager.stop_execution()
        else:
            return Attauck_Clean_fast(device)

# ============================================================================
# مثال على كيفية إضافة الخطوات
# ============================================================================

def step_1_Clean_fast(device):
    out = get_attack_village_image_paths(device)
    if len(out) == 0:
        return Attauck_manager.stop_execution()

    global outflow_import 
    outflow_import += 1
    if outflow_import >= 7:
        outflow_import = 0
        Clean_fast(device)
        return Attauck_Clean_fast(device)

    Clean_fast(device)
    time.sleep(0.2) 
    result_Ring2 = wait_for_icon(device, "image/ring2.png" ,screen_region=(0, 400, 200, 900),timeout=3)
    if result_Ring2:
        click_coordinates(device, 360 , 1230)
        time.sleep(3)
        return True
    else:
        return Attauck_manager.go_to_step_and_continue(3)
        
def step_2_Wood_Mini(device):
    result_Wood_Mini = wait_for_icon_2(device, "image/woodmini.png" ,screen_region=(0, 0, 250, 50),timeout=10)
    if result_Wood_Mini:
        return True
    else:
        Clean_fast(device)
        return Attauck_manager.go_to_step_and_continue(1)
        
def step_3_Blood(device):
    result_Blood = wait_for_icon_coordinates(device, "image/blood1.png"  ,screen_region=(400, 800, 780, 1280),timeout=1.7)
    if result_Blood:
        x,y = result_Blood
        time.sleep(0.4) 
        click_coordinates(device , x , y)
        result_clock = wait_for_icon_coordinates(device ,"image/clock.png" ,screen_region=(200, 1100, 720, 1280),timeout=2)
        if result_clock:
            x , y = result_clock 
            click_coordinates(device , x , y)
            time.sleep(0.4)
            Clean_fast(device)
        else:
            Clean_fast(device)
        return True
    else:
        return True

def step_4_Search(device):
    global outflow_import2 
    outflow_import2 += 1
    if outflow_import2 >= 15:
        outflow_import2 = 0
        Clean_fast(device)
        return Attauck_Clean_fast(device)

    result_Search = wait_for_icon_coordinates(device,"image/search.png",screen_region=(300, 800, 780, 1280),timeout=5)
    if result_Search:
        x,y = result_Search
        click_coordinates(device , x , y)
        result_Search2 = wait_for_icon_coordinates(device,"image/search2.png",screen_region=(230, 1130, 530, 1280),timeout=3)
        if result_Search2 is None:
            return Attauck_manager.go_to_step_and_continue(4)
        return True
    else:
        return Attauck_manager.go_to_step_and_continue(4)

def step_5_Search(device):
    global outflow_import8 
    outflow_import8 += 1
    if outflow_import8 >= 15:
        outflow_import8 = 0
        Clean_fast(device)
        return Attauck_Clean_fast(device)

    global index_Att
    global level_Att  
    if level_Att == 2 :
        return Attauck_Clean_fast(device)

    scroll_device(device , 640 , 840 , 240 , 840 , 800)
    time.sleep(0.6)
    a = get_attack_village_image_paths(device)
    result_Att = wait_for_icon_coordinates(device ,f"{a[index_Att]}"  , screen_region=(0, 800, 780, 1000) , timeout=2)
    if result_Att:
        x,y = result_Att
        click_coordinates(device , x , y)
        time.sleep(0.3)
        click_coordinates(device , 564 , 1087)
        time.sleep(0.3)
        click_coordinates(device , 600 , 1200)
        time.sleep(0.3)
        click_coordinates(device , 564 , 1087)
        time.sleep(0.3)
        long_click_coordinates(device, 564 , 1087 ,duration=0.6)
        time.sleep(0.3)
        clear_input_field(device)
        time.sleep(0.3)
        input_text(device , str(level_Att))
        time.sleep(0.3)
        click_coordinates(device , 600 , 1200)
        result_Search2 = wait_for_icon_coordinates(device,"image/search2.png",screen_region=(230, 1130, 530, 1280),timeout=4)
        if result_Search2:
            x,y = result_Search2
            click_coordinates(device , x , y)
            time.sleep(1)
            result_Level = wait_for_icon_coordinates(device,"image/messegeAttERR.png",screen_region=(100, 240, 620, 320),timeout=2)
            if result_Level:
                level_Att -= 2
                return Attauck_manager.go_to_step_and_continue(4)
        else:
            return Attauck_manager.go_to_step_and_continue(4)
        
        if len(a) == 2 :
            if index_Att >= 1: 
                index_Att = 0 
            else:
                index_Att += 1
        return True
    else:
        global scroll_Attempts
        scroll_Attempts += 1
        if scroll_Attempts >= 7 :
            return Attauck_manager.go_to_step_and_continue(4)
        scroll_device(device , 640 , 840 , 240 , 840 , 800)
        time.sleep(0.5)
        return Attauck_manager.go_to_step_and_continue(5)

def step_6_Zone(device):
    time.sleep(1)
    click_coordinates(device , 360 , 625)
    result_Search_Sure = wait_for_icon_coordinates(device , "image/SearchSure.png" , screen_region=(200, 100, 530, 680) , timeout=2.5)
    if result_Search_Sure is None:
        Clean_fast(device)
        return Attauck_manager.go_to_step_and_continue(4)
        
    time.sleep(1.4)
    click_coordinates(device , 530 , 640)

    result_VIP = wait_for_icon_coordinates(device , "image/VIP.png" , screen_region=(200, 660, 550, 800) , timeout=2)
    if result_VIP:
        return Attauck_Clean_fast(device)

    result_Zone = wait_for_icon_coordinates(device , "image/TargetZone.png" , screen_region=(150, 0, 600, 120) , timeout=2.5)
    if result_Zone:
        time.sleep(0.5)
        click_coordinates(device , 580 , 1225)

        result_Continue_NOTASS = find_multiple_icons(device , ["image/Continue.png" , "image/NoTASSI.png"] , screen_region=(100, 650, 700, 850) , timeout=2)
        if result_Continue_NOTASS:
            icon_path1, coordinates = result_Continue_NOTASS

            if icon_path1 == "image/Continue.png":
                global Continue_Attempts
                Continue_Attempts +=1 
                if Continue_Attempts >= 4 :
                    Continue_Attempts = 0
                    click_coordinates(device , 200 , 750)
                    return Attauck_Clean_fast(device)
                else:
                    click_coordinates(device , 200 , 750)
                    return Attauck_manager.go_to_step_and_continue(4)
            else:
                click_coordinates(device , coordinates[0] , coordinates[1])
                Clean_fast(device)
                return Attauck_manager.go_to_step_and_continue(4)
        
        result_More_Troops = wait_for_icon_coordinates(device , "image/More_Troops.png" , screen_region=(0, 430, 720, 650) , timeout=2)
        if result_More_Troops:
            Clean_fast(device)
            return Attauck_Clean_fast(device)

        
        Continue_Attempts = 0


        result_Heroes = wait_for_icon_coordinates(device , "image/Heroes.png" , screen_region=(50, 460, 680, 660) , timeout=1.5)
        if result_Heroes:
            time.sleep(0.2)
            click_coordinates(device , 500 , 780)
            Clean_fast(device)
            return Attauck_manager.go_to_step_and_continue(4)
        Clean_fast(device)
        return Attauck_manager.go_to_step_and_continue(4)
    

    result_New2 = wait_for_icon_coordinates(device , "image/New2.png" , screen_region=(40, 500, 640, 600) , timeout=2)
    if result_New2:
        time.sleep(0.2)
        click_coordinates(device , 360 , 750)
        return Attauck_Clean_fast(device)


    Clean_fast(device)
    return Attauck_manager.go_to_step_and_continue(4)
    
 
Attauck_manager = None

def run_attack_stage(device_id: str = None):

    global Attauck_manager , CURRENT_DEVICE
    
    try:
        if Attauck_manager is None or (device_id and (Attauck_manager.device_id != device_id)):
            Attauck_manager = TroopsManager(device_id or DEVICE_ID)
            CURRENT_DEVICE = device_id or DEVICE_ID

            Attauck_manager.add_step(1, "فتح قائمة القوات", step_1_Clean_fast, 
                       "فتح قائمة القوات من القائمة الرئيسية")
            Attauck_manager.add_step(2, "فتح قائمة القوات", step_2_Wood_Mini, 
                                "فتح قائمة القوات من القائمة الرئيسية")
            Attauck_manager.add_step(3, "فتح قائمة القوات", step_3_Blood, 
                                "فتح قائمة القوات من القائمة الرئيسية")
            Attauck_manager.add_step(4, "فتح قائمة القوات", step_4_Search, 
                                "فتح قائمة القوات من القائمة الرئيسية")
            Attauck_manager.add_step(5, "فتح قائمة القوات", step_5_Search, 
                                "فتح قائمة القوات من القائمة الرئيسية")
            Attauck_manager.add_step(6, "فتح قائمة القوات", step_6_Zone, 
                                "فتح قائمة القوات من القائمة الرئيسية")
        
        Attauck_manager.execute_all_steps()
          
    except Exception as e:

        return False

if __name__ == "__main__":
    run_attack_stage(DEVICE_ID)

    