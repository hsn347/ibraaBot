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
import subprocess
import sys


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


DEVICE_ID = "127.0.0.1:5565"

CURRENT_DEVICE = None

import_Flow_1 = 0 
import_Flow_2 = 0 
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

def reset_INSTALL():
    global import_Flow_1 , import_Flow_2 , CURRENT_DEVICE , INSTALL_manager , attempt

    attempt = 0
    CURRENT_DEVICE = None
    import_Flow_1 = 0 
    import_Flow_2 = 0 
    INSTALL_manager = None

# ============================================================================
# دوال مساعدة للخطوات
# ============================================================================

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

def wait_for_icon_coordinates(device, icon_path: str, screen_region: Tuple[int, int, int, int] = None, 
                              timeout: float = 10.0) -> Optional[Tuple[int, int]]:

    start_time = time.time()
    while time.time() - start_time < timeout:
        coordinates = find_icon(device, icon_path, screen_region)
        if coordinates:
            return coordinates
        time.sleep(1)
    
    return None

def Clean_fast(device, target_icons: list = None, custom_actions: dict = None, max_attempts: int = 5) -> bool:
    global my_custom_actions
    if target_icons is None:
         target_icons = ["image/prev.png", "image/x.png", "image/disable.png", "image/prev2.png", "image/EventNew.png", "image/ok.png", "image/Ottman.png"]
    
    if custom_actions is None:
        custom_actions = my_custom_actions
        
    global attempt
    for attempt in range(max_attempts):
        if attempt >= max_attempts - 1:
            attempt = 0
            reset_Path()
            run_Path(CURRENT_DEVICE)
            Clean_fast(device, target_icons, custom_actions, max_attempts)
            if 'INSTALL_manager' in globals() and INSTALL_manager is not None:
                return INSTALL_manager.stop_execution()
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
                    icon = cached_imread(icon_path)
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
# مثال على كيفية إضافة الخطوات
# ============================================================================

def step_1_Clean_fast(device):
    return True

def step_2(device):
    click_coordinates(device, 630 , 80)
    time.sleep(2)
    input_text(device, "Days of Empire")
    time.sleep(9)
    click_coordinates(device, 560 , 125)

def step_3(device):
    global import_Flow_1
    import_Flow_1 += 1
    if import_Flow_1 >= 4:
        Clean_fast(device)
        import_Flow_1 = 0
        return INSTALL_manager.stop_execution()
    scroll_device(device, 1140 , 500 , 1140 , 400 , 1000)
    time.sleep(3)
    Result_OTMAN2 = find_multiple_icons(device, ["image/OTMAN2.png"], timeout=3.5 ,threshold=0.8 )
    if Result_OTMAN2:
        icon_path1, coordinates =Result_OTMAN2
        click_coordinates(device, coordinates[0] , coordinates[1])
        time.sleep(0.4)
        return True
    else:

        return INSTALL_manager.go_to_step_and_continue(3)

def step_4(device):
    Result_PLAY = wait_for_icon_coordinates(device, "image/PLAY.png" , timeout=7)
    if Result_PLAY:
        x , y = Result_PLAY
        click_coordinates(device, x , y)
        time.sleep(0.4)
    else:
        return INSTALL_manager.go_to_step_and_continue(3)

    Result_INSTALL = wait_for_icon_coordinates(device, "image/INSTALL.png" , timeout=7)
    if Result_INSTALL:
        x , y = Result_INSTALL
        click_coordinates(device, x , y)
        time.sleep(300)
        return True
    else:
        return INSTALL_manager.go_to_step_and_continue(4)

def step_5(device):
    global import_Flow_2
    import_Flow_2 += 1
    if import_Flow_2 >= 30:
        Clean_fast(device)
        import_Flow_2 = 0
        return exit()

    logger.info("🥂🥂🥂🥂🥂🥂🥂🥂🥂🥂🥂🥂")
    Result_Cancel = wait_for_icon_coordinates(device, "image/Cancel@.png" , timeout=6)
    if Result_Cancel:
        logger.info("💔💔💔💔💔💔💔💔💔💔💔💔💔💔")
        time.sleep(70)
        return INSTALL_manager.go_to_step_and_continue(5)
    else:
        logger.info("💖💖💖💖💖💖💖💖💖💖💖💖💖💖")
        return exit()

INSTALL_manager = None 

def run_INSTALL_stage(device_id: str = None):

    global INSTALL_manager , CURRENT_DEVICE
    
    try:
        if INSTALL_manager is None or (device_id and (INSTALL_manager.device_id != device_id)):
            INSTALL_manager = TroopsManager6(device_id or DEVICE_ID)
            CURRENT_DEVICE = device_id or DEVICE_ID
            
            INSTALL_manager.add_step(1, "فتح قائمة القوات", step_1_Clean_fast, "فتح قائمة القوات من القائمة الرئيسية")
            INSTALL_manager.add_step(2, "فتح قائمة القوات", step_2, "فتح قائمة القوات من القائمة الرئيسية")
            INSTALL_manager.add_step(3, "فتح قائمة القوات", step_3, "فتح قائمة القوات من القائمة الرئيسية")
            INSTALL_manager.add_step(4, "فتح قائمة القوات", step_4, "فتح قائمة القوات من القائمة الرئيسية")
            INSTALL_manager.add_step(5, "فتح قائمة القوات", step_5, "فتح قائمة القوات من القائمة الرئيسية")
        INSTALL_manager.execute_all_steps()
        
    except Exception as e:
        return False


if __name__ == "__main__":
    run_INSTALL_stage(DEVICE_ID)

    