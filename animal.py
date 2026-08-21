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
import subprocess
import sys
from Manager_Json import BotDataManager

def action_for_Ottman(device, x, y):
    time.sleep(120)
    device.click(x, y)
    time.sleep(30)

my_custom_actions = {
    "image/Ottman.png": action_for_Ottman, # عند رؤية هذه الصورة، سيشغل دالة التمرير
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEVICE_ID = "127.0.0.1:5555"

CURRENT_DEVICE = None

outflow_import = 0 
outflow_import2 = 0 
outflow_import6 = 0 
attempt = 0

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

def reset_animal():
    global outflow_import , outflow_import2 , outflow_import6 , CURRENT_DEVICE , animal_manager , attempt

    attempt = 0
    CURRENT_DEVICE = None
    outflow_import = 0 
    outflow_import2 = 0 
    outflow_import6 = 0
    animal_manager = None

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


    if thresholds is None:
        thresholds = [0.8, 0.7, 0.6] 
    
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
            icon = cached_imread(icon_path)
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
            if 'animal_manager' in globals() and animal_manager is not None:
                return animal_manager.stop_execution()
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

    try:
        device.click(x, y)
        return True
    except Exception as e:
        return False

def click_coordinates_repeat(device, x: int, y: int, times: int, delay: float = 0.3) -> bool:
    """
    ينقر على الإحداثيات (x, y) عدد (times) من المرات.
    إذا كان times == 0 لا يتم النقر أبداً وتنتهي الدالة فوراً.

    Args:
        device : الجهاز المستهدف
        x      : الإحداثي الأفقي
        y      : الإحداثي الرأسي
        times  : عدد مرات النقر (0 = لا نقر)
        delay  : الانتظار بين كل نقرة والتالية بالثواني (افتراضي 0.3)

    Returns:
        bool: True إذا نجحت جميع النقرات، False إذا حدث خطأ
    """
    if times == 0:
        return True

    try:
        for _ in range(times):
            device.click(x, y)
            if _ < times - 1:
                time.sleep(delay)
        return True
    except Exception as e:
        return False


def scroll_device(device, x1: int, y1: int, x2: int, y2: int, scroll_speed: int = 1000) -> bool:

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
# ============================================================================
# مثال على كيفية إضافة الخطوات
# ============================================================================

def step_1_Clean_fast(device):
    global outflow_import 
    outflow_import += 1
    if outflow_import >= 10:
        outflow_import = 0
        Clean_fast(device)
        return animal_manager.stop_execution()

    return Clean_fast(device)

def step_2_open_loot_menu(device):
    click_coordinates(device, 20, 630)
    time.sleep(0.4)
    result2 = wait_for_icon(device, "image/sure2.png" ,screen_region=(0 , 280 , 360 ,700), timeout=4)
    if result2:
        return True
    else: 
        return animal_manager.go_to_step_and_continue(1)

def step_3_Result_Loot(device):
    global outflow_import2 
    outflow_import2 += 1
    if outflow_import2 >= 10:
        outflow_import2 = 0
        Clean_fast(device)
        return animal_manager.stop_execution()

    scroll_device(device, 250, 1000, 250, 850 , 300)
    time.sleep(1)
    click_coordinates(device , 250 , 700)
    time.sleep(0.4)

    result_loot_1 = wait_for_icon_coordinates_custom_thresholds(device ,"image/house.png" ,screen_region=(0, 100, 250, 1280) , timeout=1.5 ,thresholds=[0.7])
    if result_loot_1:
        x , y = result_loot_1
        coreTrian = wait_for_icon_coordinates(device, "image/patrolling.png", screen_region=(x+298, y+30, x+438, y+94) ,timeout=2)
        if coreTrian:
            click_coordinates(device , 445 , 1240)
            return animal_manager.stop_execution()

        coreGo = wait_for_icon_coordinates(device, "image/GoTroo2.png", screen_region=(x+298, y+30, x+438, y+94) , timeout=3)
        if coreGo:
            x1 , y1 = coreGo
            click_coordinates(device, x1, y1)
            time.sleep(1.5)
            return animal_manager.go_to_step_and_continue(4)
        else:
            return animal_manager.stop_execution()
    else:   
        return animal_manager.go_to_step_and_continue(1)

def step_4_Claim(device):
    click_coordinates(device , 360 , 640)
    time.sleep(0.5)
    result_Claim = wait_for_icon_coordinates(device,"image/pets.png", screen_region=(180, 520, 530, 860) , timeout=2)
    if result_Claim:
        x,y = result_Claim 
        time.sleep(1)
        click_coordinates(device , x , y)
        time.sleep(0.5)
        return True
    else:
        return animal_manager.stop_execution()

def step_5_Book_Loot(device):
    animal = BotDataManager.get_animal_by_device(CURRENT_DEVICE)
    animal_flag = ["deer", "lion", "falcon", "wolf", "cheetah", "bear", "elephant", "bull", "dog"]
    animal_index = animal_flag.index("deer")
    Book_Loot = wait_for_icon(device,"image/petHouse.png",screen_region=(250, 0, 470, 110) , timeout=2.5)
    if Book_Loot:
        click_coordinates_repeat(device,535, 1100, animal_index , 0.5)
        time.sleep(0.5)
        return True
    else:
        return animal_manager.go_to_step_and_continue(1)

def step_6_Begin_Loot(device):
    global outflow_import6

    outflow_import6 += 1
    if outflow_import6 >= 3:
        return animal_manager.stop_execution()

    time.sleep(0.3)
    result_Begin_Loot = wait_for_icon_coordinates(device,"image/patrol.png",screen_region=(0, 600, 150, 770) , timeout=3)
    if result_Begin_Loot:
        x , y = result_Begin_Loot
        click_coordinates(device , x , y)
        time.sleep(0.5)
        return True
    else:
        Clean_fast(device)
        return animal_manager.stop_execution()

def step_7_choose_animal(device):
    result_Choose_Goods = wait_for_icon_coordinates(device,"image/patrol_2.png",screen_region=(290, 40, 430, 110) , timeout=2)
    if result_Choose_Goods:
        click_coordinates(device , 360 , 1210 )
        time.sleep(0.3)
        Clean_fast(device)
        return animal_manager.stop_execution()
    else:
        return animal_manager.go_to_step_and_continue(6)

    
animal_manager = None 

def run_animal(device_id: str = None):

    global animal_manager , CURRENT_DEVICE
    
    try:
        # إنشاء مدير القوات عند أول تشغيل فقط
        if animal_manager is None or (device_id and (animal_manager.device_id != device_id)):
            animal_manager = TroopsManager6(device_id or DEVICE_ID)
            CURRENT_DEVICE = device_id or DEVICE_ID
            
            # إضافة الخطوات
            animal_manager.add_step(1, "فتح قائمة القوات", step_1_Clean_fast, "فتح قائمة القوات من القائمة الرئيسية")
            animal_manager.add_step(2, "فتح قائمة القوات", step_2_open_loot_menu, "فتح قائمة القوات من القائمة الرئيسية")
            animal_manager.add_step(3, "فتح قائمة القوات", step_3_Result_Loot, "فتح قائمة القوات من القائمة الرئيسية")
            animal_manager.add_step(4, "فتح قائمة القوات", step_4_Claim, "فتح قائمة القوات من القائمة الرئيسية")
            animal_manager.add_step(5, "فتح قائمة القوات", step_5_Book_Loot, "فتح قائمة القوات من القائمة الرئيسية")
            animal_manager.add_step(6, "فتح قائمة القوات", step_6_Begin_Loot, "فتح قائمة القوات من القائمة الرئيسية")
            animal_manager.add_step(7, "فتح قائمة القوات", step_7_choose_animal, "فتح قائمة القوات من القائمة الرئيسية")
        animal_manager.execute_all_steps()
            
    except Exception as e:
        return False


if __name__ == "__main__":
    run_animal(DEVICE_ID)

    