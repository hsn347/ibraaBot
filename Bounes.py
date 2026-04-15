import cv2
import numpy as np
import time
import threading
from typing import Optional, Tuple, List, Union, Dict, Callable
import uiautomator2 as u2
from Path import run_Path , reset_Path
import logging
import subprocess
import sys

def action_for_Ottman(device, x, y):
    time.sleep(120)
    device.click(x, y)

my_custom_actions = {
    "image/Ottman.png": action_for_Ottman, # عند رؤية هذه الصورة، سيشغل دالة التمرير
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEVICE_ID = "127.0.0.1:5615"

CURRENT_DEVICE = None


outflow_import_1 = 0
outflow_import_2 = 0
attempt = 0
attempt_2 = 0

# ============================================================================
# نظام إدارة الخطوات مع إمكانية الرجوع
# ============================================================================

class TroopsManager:
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
        """
        إضافة خطوة جديدة
        
        Args:
            step_number: رقم الخطوة
            step_name: اسم الخطوة
            step_function: دالة الخطوة
            description: وصف الخطوة
            required_icons: الأيقونات المطلوبة للخطوة
        """
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


def reset_Bounes():
    global outflow_import_1 , outflow_import_2 , CURRENT_DEVICE , Bounes_manager , attempt , attempt_2

    outflow_import_1 = 0
    outflow_import_2 = 0
    attempt = 0
    attempt_2 = 0
    CURRENT_DEVICE = None
    Bounes_manager = None

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
            if 'Bounes_manager' in globals() and Bounes_manager is not None:
                return Bounes_manager.stop_execution()
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


def Attauck_Clean_fast(device):
    global attempt_2
    attempt_2 += 1
    if attempt_2 >= 6:
        attempt_2 = 0 
        return Bounes_manager.stop_execution()

    Clean_fast(device)
    result_Ring2 = wait_for_icon(device, "image/ring2.png" ,screen_region=(0, 400, 200, 900),timeout=2)
    if result_Ring2:
        return Bounes_manager.stop_execution()
    else:
        click_coordinates(device, 360 , 1230)
        result_Ring2 = wait_for_icon(device, "image/ring2.png" ,screen_region=(0, 400, 200, 900),timeout=8)
        if result_Ring2:
            return Bounes_manager.stop_execution()
        else:
            return Attauck_Clean_fast(device)

# ============================================================================
# مثال على كيفية إضافة الخطوات
# ============================================================================

def step_1_Clean_fast(device):
    global outflow_import_1 
    outflow_import_1 += 1
    if outflow_import_1 >= 10:
        outflow_import_1 = 0
        Clean_fast(device)
        return Attauck_Clean_fast(device)

    Clean_fast(device)
    result_Ring2 = wait_for_icon(device, "image/ring2.png" ,screen_region=(0, 400, 200, 900),timeout=4)
    if result_Ring2:
        click_coordinates(device, 360 , 1230)
        time.sleep(3)
        return True
    else:
        return Bounes_manager.go_to_step_and_continue(3)   
        
def step_2_Wood_Mini(device):
    result_Wood_Mini = wait_for_icon_2(device, "image/woodmini.png" ,screen_region=(0, 0, 250, 50),timeout=10)
    if result_Wood_Mini:
        return True
    else:
        Clean_fast(device)
        return Bounes_manager.go_to_step_and_continue(1)

def step_3_Preotec(device):
    global outflow_import_2
    outflow_import_2 += 1
    if outflow_import_2 >= 6:
        Clean_fast(device)
        return Bounes_manager.stop_execution()

    time.sleep(2.5)
    click_coordinates(device , 360 , 650)
    time.sleep(0.3)

    result3 = wait_for_icon_coordinates(device, "image/protect.png" ,screen_region=(300 , 450 , 620 ,800), timeout=3)
    if result3:
        time.sleep(0.5)
        x , y = result3
        click_coordinates(device , x , y)
        return True
    else:
        Clean_fast(device)
        return Bounes_manager.go_to_step_and_continue(3)
 
def step_4_Preotec(device):
    result_4_N = wait_for_icon(device, "image/CityBonus.png" ,screen_region=(260 , 40 , 460 ,100), timeout=3)
    if result_4_N:
        time.sleep(0.5)
        scroll_device(device, 350 , 1100 , 350 , 250 , 600)
        time.sleep(1)
        return True
    else:
        Clean_fast(device)
        return Bounes_manager.go_to_step_and_continue(3)

def step_5_Preotec(device):
    result5 = wait_for_icon_coordinates(device, "image/Bounes.png" , screen_region=(10 , 115 , 140 ,1280), timeout=3)
    if result5:
        time.sleep(0.5)
        x , y = result5
        click_coordinates(device , x , y)
        time.sleep(0.5)
        return True
    else:
        Clean_fast(device)
        return Bounes_manager.go_to_step_and_continue(3)

def step_6_Preotec(device):
    afw = wait_for_icon(device, "image/Remaining.png" ,screen_region=(230, 220, 380, 300),timeout=2.5)
    if afw:
        Clean_fast(device)
        return True
    else:
        time.sleep(0.5)
        click_coordinates(device, 600 , 340)
        time.sleep(0.5)
        Clean_fast(device)
        return True



Bounes_manager = None 

def run_Bounes_stage(device_id: str = None):

    global Bounes_manager , CURRENT_DEVICE
    
    try:

        if Bounes_manager is None or (device_id and (Bounes_manager.device_id != device_id)):
            Bounes_manager = TroopsManager(device_id or DEVICE_ID)
            CURRENT_DEVICE = device_id or DEVICE_ID


            Bounes_manager.add_step(1, "فتح قائمة القوات", step_1_Clean_fast, "فتح قائمة القوات من القائمة الرئيسية")
            Bounes_manager.add_step(2, "فتح قائمة القوات", step_2_Wood_Mini, "فتح قائمة القوات من القائمة الرئيسية")
            Bounes_manager.add_step(3, "فتح قائمة القوات", step_3_Preotec, "فتح قائمة القوات من القائمة الرئيسية")
            Bounes_manager.add_step(4, "فتح قائمة القوات", step_4_Preotec, "فتح قائمة القوات من القائمة الرئيسية")
            Bounes_manager.add_step(5, "فتح قائمة القوات", step_5_Preotec, "فتح قائمة القوات من القائمة الرئيسية")
            Bounes_manager.add_step(6, "فتح قائمة القوات", step_6_Preotec, "فتح قائمة القوات من القائمة الرئيسية")


        Bounes_manager.execute_all_steps()
        
        
    except Exception as e:
        return False

if __name__ == "__main__":
    run_Bounes_stage(DEVICE_ID)
    
    