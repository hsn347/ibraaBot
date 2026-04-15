import cv2
import numpy as np
import time
import threading
from typing import Optional, Tuple, List, Union, Dict, Callable
import logging
import uiautomator2 as u2
from Path import run_Path , reset_Path
import subprocess
import sys
from Manager_Json import BotDataManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def action_for_Ottman(device, x, y):
    time.sleep(120)
    device.click(x, y)

my_custom_actions = {
    "image/Ottman.png": action_for_Ottman, # عند رؤية هذه الصورة، سيشغل دالة التمرير
}


DEVICE_ID = "127.0.0.1:5565"

CURRENT_DEVICE = None

attempt = 0

step_Logic = []
Icon_Gree = ""

import_Flow_1 = 0
import_Flow_2 = 0
import_Flow_3 = 0

Logic_Dream = True

new_list = []

last_list = []

output = []
output2 = []

data_tuples = [
    ('wood', 'image/supwood.png', 'image/buywood.png'),
    ('qmh', 'image/supqmh.png', 'image/buyqmh.png'),
    ('iron', 'image/supiron.png', 'image/buyiron.png'),
    ('almas', 'image/supalmas.png', 'image/buyalmas.png')
]

# ============================================================================
# نظام إدارة الخطوات مع إمكانية الرجوع
# ============================================================================

class TroopsManager6:
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
        """
        الانتقال إلى خطوة معينة
        
        Args:
            step_number: رقم الخطوة المطلوبة
        """
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
        """
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
        """عرض جميع الخطوات"""
        for step_num in sorted(self.steps.keys()):
            step = self.steps[step_num]
            result = self.step_results.get(step_num, "لم يتم التنفيذ")

def reset_Dream():
    global CURRENT_DEVICE , Icon_Gree , Dream_manager , attempt , new_list,step_Logic,import_Flow_1 , import_Flow_2,import_Flow_3,Logic_Dream,last_list,output , output2

    step_Logic = []

    import_Flow_1 = 0
    import_Flow_2 = 0
    import_Flow_3 = 0
    Logic_Dream = True
    new_list = []
    last_list = []
    output = []
    output2 = []
    Icon_Gree = ""

    attempt = 0
    CURRENT_DEVICE = None
    Dream_manager = None

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
            logger.error(f"خطأ")
    
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
        time.sleep(1)
    
    return False

def wait_for_icon_coordinates(device, icon_path: str, screen_region: Tuple[int, int, int, int] = None, 
                              timeout: float = 10.0) -> Optional[Tuple[int, int]]:

    start_time = time.time()
    while time.time() - start_time < timeout:
        coordinates = find_icon(device, icon_path, screen_region)
        if coordinates:
            return coordinates
        time.sleep(1)
    
    return None

def wait_for_icon_coordinates_custom_thresholds(device, icon_path: str, 
                                               screen_region: Tuple[int, int, int, int] = None, 
                                               timeout: float = 10.0,
                                               thresholds: List[float] = None) -> Optional[Tuple[int, int]]:
    """
    انتظار ظهور أيقونة وإرجاع إحداثياتها مع عتبات بحث مخصصة
    
    Args:
        device: الجهاز
        icon_path: مسار الأيقونة
        screen_region: منطقة البحث في الشاشة (x1, y1, x2, y2)
        timeout: وقت الانتظار
        thresholds: قائمة عتبات البحث (افتراضي: [0.8, 0.7, 0.6])
        
    Returns:
        Tuple[int, int] أو None: إحداثيات الأيقونة إذا وجدت، None إذا لم توجد
    """
    # استخدام العتبات الافتراضية إذا لم يتم تحديد عتبات مخصصة
    if thresholds is None:
        thresholds = [0.8, 0.7, 0.6]  # عالية، متوسطة، تحت المتوسطة
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
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
            
            # قراءة الأيقونة
            icon = cv2.imread(icon_path, cv2.IMREAD_GRAYSCALE)
            if icon is None:
                time.sleep(0.5)
                continue
            
            # البحث بكل عتبة
            for threshold in thresholds:
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
                    
                    coordinates = (center_x, center_y)
                    return coordinates
            
            time.sleep(0.5)
            
        except Exception as e:
            time.sleep(0.5)
    
    return None

def Clean_fast(device, target_icons: list = None, custom_actions: dict = None, max_attempts: int = 10) -> bool:

    global my_custom_actions
    if target_icons is None:
         target_icons = ["image/prev.png", "image/x.png", "image/prev2.png", "image/TryAgainGreen.png", "image/ok.png", "image/Ottman.png"]
    
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
            if 'Dream_manager' in globals() and Dream_manager is not None:
                return Dream_manager.stop_execution()
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

def scroll_device(device, x1: int, y1: int, x2: int, y2: int, scroll_speed: int = 1000) -> bool:
    """
    دالة التمرير على الجهاز باستخدام ADB
    
    Args:
        device: كائن الجهاز أو معرف الجهاز
        x1: الإحداثي X للنقطة البداية
        y1: الإحداثي Y للنقطة البداية  
        x2: الإحداثي X للنقطة النهائية
        y2: الإحداثي Y للنقطة النهائية
        scroll_speed: سرعة التمرير (بالمللي ثانية) - القيمة الافتراضية 1000
        
    Returns:
        bool: True إذا نجح التمرير، False إذا فشل
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
        ], capture_output=True, timeout=3, check=True , creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0)
        
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

def extract_third(main_list, filter_list):
    result = []
    for item in main_list:
        # item[1] هو العمود الثاني
        # item[2] هو العمود الثالث
        if item[1] in filter_list:
            result.append(item[2])
    return result

def extract_third_Refrence(main_list, filter_list):
    result = []
    for item in main_list:
        # item[1] هو العمود الثاني
        # item[2] هو العمود الثالث
        if item[2] in filter_list:
            result.append(item[1])
    return result

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


# ============================================================================
# الدوال المختصرة
# ============================================================================


# ============================================================================
# مثال على كيفية إضافة الخطوات
# ============================================================================
def step_1_Clean_fast(device):
    data = BotDataManager.get_icons_from_options(CURRENT_DEVICE)
    global new_list
    new_list = [item[1] for item in data]
    if data is None:
        return Dream_manager.stop_execution()
    Clean_fast(device)
    return True

def stpe_2_aglh(device):
    global import_Flow_1
    import_Flow_1 += 1
    if import_Flow_1 >= 7:
        import_Flow_1 = 0
        Clean_fast(device)
        return Dream_manager.stop_execution()

    time.sleep(0.3)
    result_aglh = find_multiple_icons(device ,["image/aglh.png", "image/aglh2.png"] ,screen_region=(0, 250, 720, 1100),timeout=2 , threshold=0.7)    
    if result_aglh:
        icon_path, coordinates = result_aglh
        click_coordinates(device , coordinates[0] , coordinates[1])
        return True
    else:
        Clean_fast(device)
        return Dream_manager.go_to_step_and_continue(2)

def step_3_Support(device):
    time.sleep(0.4)
    Result_support = wait_for_icon_coordinates(device, "image/support.png" ,screen_region=(100, 500 , 600 , 1060) , timeout=2)
    if Result_support:
        x , y = Result_support
        click_coordinates(device, x , y)
        time.sleep(0.5)
        return True
    else:
        Clean_fast(device)
        return Dream_manager.go_to_step_and_continue(2)

def step_4_SURE(device):
    Result_SURE = wait_for_icon(device, "image/BUY.png" ,screen_region=(150, 30 , 650 , 110) , timeout=2.5)
    if Result_SURE:
        return True
    else:
        Clean_fast(device)
        time.sleep(0.3)
        return Dream_manager.go_to_step_and_continue(2)

def step_5_berbst(device):
    global new_list , Icon_Gree
    if len(new_list) == 0 :
        return Dream_manager.go_to_step_and_continue(7)
    ref = find_multiple_icons(device , new_list ,timeout= 2 , threshold= 0.7 ,screen_region=(480, 100, 720, 800))
    if ref:
        icon_path, coordinates = ref
        Icon_Gree = icon_path
        time.sleep(0.3)
        click_coordinates(device , coordinates[0] , coordinates[1])
        new_list.remove(icon_path)
        return True
    else:
        return Dream_manager.go_to_step_and_continue(7)
        
def step_6_BUY(device):
    Result_supOk = wait_for_icon_coordinates(device, "image/supOk.png" ,screen_region=(360, 650 , 700 , 830) , timeout=2.5)
    if Result_supOk:
        x , y = Result_supOk
        click_coordinates(device , x , y)
        Result_SURE = wait_for_icon(device, "image/Resources_OP.png" ,screen_region=(130, 255 , 580 , 310) , timeout=4)
        if Result_SURE:
            return Dream_manager.go_to_step_and_continue(5)
        return Dream_manager.go_to_step_and_continue(5)
    else:
        click_coordinates(device ,444 , 1245)
        step_Logic.append(Icon_Gree)
        time.sleep(0.2)
        return Dream_manager.go_to_step_and_continue(5)
        
def step_7_qer(device):
    Clean_fast(device)

    from Manager_Json import BotDataManager
    Stor_Boolean = BotDataManager.get_bot_Not_Store(CURRENT_DEVICE)
    if Stor_Boolean :
        return Dream_manager.stop_execution()
        
    if len(step_Logic) == 0:
        return Dream_manager.stop_execution()
    else:
        return True

def step_8_ALI(device):
    global import_Flow_2
    import_Flow_2 += 1
    if import_Flow_2 >= 7:
        import_Flow_2 = 0
        Clean_fast(device)
        return Dream_manager.stop_execution()

    click_coordinates(device , 640 , 1225)
    time.sleep(0.3)
    results_Alliance = wait_for_icon(device ,"image/Alliance.png" ,screen_region=(296, 0, 422, 100),timeout=2.5)    
    if results_Alliance:
        return True
    
    results_Join_Alliance = wait_for_icon(device ,"image/Join_Alliance.png" ,screen_region=(200, 0, 600, 100),timeout=2.5)    
    if results_Join_Alliance:
        Clean_fast(device)
        return Dream_manager.stop_execution()

    return Dream_manager.go_to_step_and_continue(8)

def step_9_Store(device):
    time.sleep(0.2)
    results_Store = wait_for_icon_coordinates(device ,"image/Store.png" ,screen_region=(296, 500, 720, 1150),timeout=2.5)    
    if results_Store:
        x , y = results_Store
        click_coordinates(device , x , y)
        return True
    else:
        return Dream_manager.go_to_step_and_continue(8)

def step_10_STORE_Check(device):
    global step_Logic , output
    output = extract_third(data_tuples, step_Logic)
    results_STORE_OP = wait_for_icon(device ,"image/STORE_OP.png" ,screen_region=(200, 40, 550, 105),timeout=2.5)    
    if results_STORE_OP:
        return True
    else:
        return Dream_manager.go_to_step_and_continue(8)

def step_11_STORE_OP(device):
    global output , Logic_Dream , last_list

    if len(output) == 0:
        Clean_fast(device)
        return True

    result_aglh = find_multiple_icons(device , output ,screen_region=(0, 200, 720, 1200),timeout=2.5 , threshold=0.7)    
    if result_aglh:
        icon_path1, coordinates = result_aglh

        Result_Donate = wait_for_icon_coordinates_custom_thresholds(device, "image/Donate.png" , screen_region=(150, 600 , 550 , 850), timeout=2 , thresholds=[0.7])
        if Result_Donate:
            Clean_fast(device)
            return True

        last_list.append(icon_path1)
        time.sleep(0.4)
        click_coordinates(device , coordinates[0]+168 , coordinates[1]+45)
        time.sleep(0.4)
        click_coordinates(device , 570 , 712)
        time.sleep(0.4)
        click_coordinates(device , 570 , 760)
        time.sleep(0.4)
        click_coordinates(device , 570 , 712)
        time.sleep(0.4)
        long_click_coordinates(device, 570 , 712 ,duration=0.6)
        time.sleep(0.4)
        clear_input_field(device)
        time.sleep(0.4)
        input_text(device , "10")
        time.sleep(0.6)
        click_coordinates(device , 570 , 760)
        time.sleep(0.4)
        click_coordinates(device , 360 , 800)
        time.sleep(0.4)
        Logic_Dream = True
        output.remove(icon_path1)
        return Dream_manager.go_to_step_and_continue(11)
    
    else:
        if Logic_Dream :
            Logic_Dream = False
            scroll_device(device , 361 , 800 , 361 , 500 , 600)
            time.sleep(1.5)
            return Dream_manager.go_to_step_and_continue(11)
        else:
            Clean_fast(device)
            return True
   
def step_12_last_list(device):
    global last_list , output2
    output2 = extract_third_Refrence(data_tuples, last_list)
    if len(last_list) == 0:
        return Dream_manager.stop_execution()
    return True

def stpe_13_aglh_ِAGI(device):
    global import_Flow_3
    import_Flow_3 += 1
    if import_Flow_3 >= 7:
        import_Flow_3 = 0
        Clean_fast(device)
        return Dream_manager.stop_execution()

    time.sleep(0.2)
    result_aglh = find_multiple_icons(device ,["image/aglh.png", "image/aglh2.png"] ,screen_region=(0, 250, 720, 1100),timeout=2 , threshold=0.7)    
    if result_aglh:
        icon_path, coordinates = result_aglh
        click_coordinates(device , coordinates[0] , coordinates[1])
        return True
    else:
        Clean_fast(device)
        return Dream_manager.go_to_step_and_continue(13)

def step_14_Support_ِAGI(device):
    time.sleep(0.4)
    Result_support = wait_for_icon_coordinates(device, "image/support.png" ,screen_region=(100, 500 , 600 , 1060) , timeout=2)
    if Result_support:
        x , y = Result_support
        click_coordinates(device, x , y)
        time.sleep(0.2)
        return True
    else:
        Clean_fast(device)
        return Dream_manager.go_to_step_and_continue(13)

def step_15_SURE_ِAGI(device):
    Result_SURE = wait_for_icon(device, "image/BUY.png" ,screen_region=(150, 30 , 650 , 110) , timeout=2.5)
    if Result_SURE:
        return True
    else:
        Clean_fast(device)
        time.sleep(0.3)
        return Dream_manager.go_to_step_and_continue(13)

def step_16_berbst_ِAGI(device):
    global output2
    
    if len(output2) == 0:

        Clean_fast(device)
        return Dream_manager.stop_execution()

    ref = find_multiple_icons(device , output2 ,timeout= 2 , threshold= 0.7 ,screen_region=(480, 100, 720, 800))
    if ref:
        icon_path12, coordinates = ref
        time.sleep(0.3)
        click_coordinates(device , coordinates[0] , coordinates[1])
        output2.remove(icon_path12)
        return True
    else:

        Clean_fast(device)
        return Dream_manager.stop_execution()
        
def step_17_BUY_ِAGI(device):

    Result_supOk = wait_for_icon_coordinates(device, "image/supOk.png" ,screen_region=(360, 650 , 700 , 830) , timeout=2)
    if Result_supOk:
        x , y = Result_supOk
        click_coordinates(device , x , y)
 
        Result_SURE = wait_for_icon(device, "image/Resources_OP.png" ,screen_region=(130, 255 , 580 , 310) , timeout=4)
        if Result_SURE:
            return Dream_manager.go_to_step_and_continue(16)
        return Dream_manager.go_to_step_and_continue(16)
    else:
        click_coordinates(device ,444 , 1245)
        time.sleep(0.2)
        return Dream_manager.go_to_step_and_continue(16)
    


Dream_manager = None 

def run_Dream_stage(device_id: str = None):

    global Dream_manager , CURRENT_DEVICE
    
    try:
        # إنشاء مدير القوات عند أول تشغيل فقط
        if Dream_manager is None or (device_id and (Dream_manager.device_id != device_id)):
            Dream_manager = TroopsManager6(device_id or DEVICE_ID)
            CURRENT_DEVICE = device_id or DEVICE_ID
            
            # إضافة الخطوات
            Dream_manager.add_step(1, "فتح قائمة القوات", step_1_Clean_fast, "فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(2, "فتح قائمة القوات", stpe_2_aglh, "فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(3, "فتح قائمة القوات", step_3_Support, "فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(4, "فتح قائمة القوات", step_4_SURE, "فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(5, "فتح قائمة القوات", step_5_berbst, "فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(6, "فتح قائمة القوات", step_6_BUY, "فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(7, "فتح قائمة القوات",  step_7_qer ,"فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(8, "فتح قائمة القوات",  step_8_ALI ,"فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(9, "فتح قائمة القوات",  step_9_Store ,"فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(10, "فتح قائمة القوات",  step_10_STORE_Check ,"فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(11, "فتح قائمة القوات",  step_11_STORE_OP ,"فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(12, "فتح قائمة القوات",  step_12_last_list ,"فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(13, "فتح قائمة القوات",  stpe_13_aglh_ِAGI ,"فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(14, "فتح قائمة القوات",  step_14_Support_ِAGI ,"فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(15, "فتح قائمة القوات",  step_15_SURE_ِAGI ,"فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(16, "فتح قائمة القوات",  step_16_berbst_ِAGI ,"فتح قائمة القوات من القائمة الرئيسية")
            Dream_manager.add_step(17, "فتح قائمة القوات",  step_17_BUY_ِAGI ,"فتح قائمة القوات من القائمة الرئيسية")

        # تشغيل جميع الخطوات
        result = Dream_manager.execute_all_steps()
        
        return result
        
    except Exception as e:
        return False


if __name__ == "__main__":
    run_Dream_stage(DEVICE_ID)

    