
import cv2
import numpy as np
import time
import threading
from typing import Optional, Tuple, List, Union, Dict, Callable
import logging
import uiautomator2 as u2
from Power_1 import run_Power_manager1 , REST_POWER

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


DEVICE_ID = "127.0.0.1:5615"

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
    

Correct_manager1 = None

# ============================================================================
# دوال مساعدة للخطوات
# ============================================================================

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

def wait_for_icon_2(device, icon_path: str, screen_region: Tuple[int, int, int, int] = None, 
                  timeout: float = 10.0) -> bool:
    """
    انتظار ظهور أيقونة
    
    """
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

def click_coordinates(device, x: int, y: int) -> bool:

    try:
        device.click(x, y)
        return True
    except Exception as e:
        return False

# ============================================================================
# مثال على كيفية إضافة الخطوات
# ============================================================================

def step_1_2(device):
    Result_Ottman = wait_for_icon_coordinates(device, "image/Ottman.png" , timeout=10)
    if Result_Ottman:
        x , y = Result_Ottman
        click_coordinates(device, x , y)
        time.sleep(4)
        Result_Wood = wait_for_icon_2(device, "image/almasMini.png" ,screen_region=[0 , 0 , 500 , 50], timeout=30)
        if Result_Wood:
            return True

    return True

def step_2_2(device):
    REST_POWER()
    return run_Power_manager1(DEVICE_ID)


def run_Correct_manager1(device_id: str = None):
    global Correct_manager1 , DEVICE_ID
    try:
        hb = None
        if Correct_manager1 is None or (device_id and (Correct_manager1.device_id != device_id)):
            Correct_manager1 = TroopsManager1(device_id)
            DEVICE_ID = device_id
            
            Correct_manager1.add_step(1, "مرحلة تسجيل الدخول", step_1_2, "تسجيل الحساب وتأخذ البيانات من ملف json") 
            Correct_manager1.add_step(2, "مرحلة البريد", step_2_2, "مرحلة البريد") 

        Correct_manager1.execute_all_steps()
        
        
    except Exception as e:

        return False

