
import cv2
import numpy as np
import time
import threading
from typing import Optional, Tuple, List, Union, Dict, Callable
import logging
import uiautomator2 as u2
from Path import run_Path , reset_Path

def action_for_Ottman(device, x, y):
    time.sleep(120)
    device.click(x, y)

my_custom_actions = {
    "image/Ottman.png": action_for_Ottman, # عند رؤية هذه الصورة، سيشغل دالة التمرير
}

CURRENT_DEVICE = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEVICE_ID = "127.0.0.1:5555"

outflow_import = 0 
outflow_import2 = 0 
attempt = 0

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

def reset_Email():
    global outflow_import, outflow_import2 ,CURRENT_DEVICE ,email_manager ,attempt

    attempt = 0
    outflow_import = 0
    outflow_import2 = 0
    CURRENT_DEVICE = None
    email_manager = None

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
            logger.error(f"القا")
    
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
    """
    انتظار ظهور أيقونة
    
    Args:
        device: الجهاز
        icon_path: مسار الأيقونة
        screen_region: منطقة البحث في الشاشة (x1, y1, x2, y2)
        timeout: وقت الانتظار
        
    Returns:
        bool: ظهرت الأيقونة أم لا
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        coordinates = find_icon(device, icon_path, screen_region)
        if coordinates:
          
            return True
        time.sleep(0.5)
    

    return False

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
            if 'email_manager' in globals() and email_manager is not None:
                return email_manager.stop_execution()
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

def wait_for_icon_coordinates(device, icon_path: str, screen_region: Tuple[int, int, int, int] = None, 
                              timeout: float = 10.0) -> Optional[Tuple[int, int]]:

    start_time = time.time()
    while time.time() - start_time < timeout:
        coordinates = find_icon(device, icon_path, screen_region)
        if coordinates:
            return coordinates
        time.sleep(1)
    
    return None

# ============================================================================
# مثال على كيفية إضافة الخطوات
# ============================================================================

def step_1_Clean_fast(device):
    global outflow_import 
    outflow_import += 1
    if outflow_import >= 7:
        outflow_import = 1
        Clean_fast(device)
        return email_manager.stop_execution()

    return Clean_fast(device)

def step_2_Email_open(device):
    click_coordinates(device, 510, 1250)
    time.sleep(0.8)
    result_Email_open = wait_for_icon(device, "image/mail22.png" ,screen_region=(300, 0, 430, 100),timeout = 2.3 + outflow_import)
    if result_Email_open == False:
        return email_manager.go_to_step_and_continue(1)
    return True

def step_3_Kass(device):
    result1_Kass = wait_for_icon_coordinates(device, "image/kass.png",screen_region=(0, 350, 350, 1050),timeout=3)
    if result1_Kass :
        x , y = result1_Kass
        time.sleep(0.2) 
        click_coordinates(device, x, y)
        return True
    else:
        return email_manager.go_to_step_and_continue(1)
 
def step_4_ReadAll(device):
    global outflow_import2 
    outflow_import2 += 1
    if outflow_import2 >= 70:
        outflow_import2 =0
        Clean_fast(device)
        return email_manager.stop_execution()
    else:
        result2 = wait_for_icon(device, "image/readall.png",screen_region=(100, 1150, 620, 1280),timeout=2.5 + outflow_import)
        if result2:
            click_coordinates(device, 360, 1245)
            
            return email_manager.go_to_step_and_continue(4)
        else:
            if outflow_import2 == 1:
          
                Clean_fast(device)
                return email_manager.stop_execution()
            else:
            
                return True
 
def step_5_ReadAll(device):
    click_coordinates(device , 660 , 1245)
    time.sleep(0.4)
    click_coordinates(device , 60 , 1245)
    time.sleep(0.4)
    click_coordinates(device , 360 , 1245)
    time.sleep(0.4)
    click_coordinates(device , 360 , 745)
    time.sleep(0.4)
    click_coordinates(device , 660 , 1245)
    time.sleep(0.4)
    result3 = wait_for_icon(device, "image/readall.png",screen_region=(100, 1150, 620, 1280),timeout=2 + outflow_import)
    if result3:
        return email_manager.go_to_step_and_continue(4)
    else:
        Clean_fast(device)
        return email_manager.stop_execution()


email_manager = None
def run_email_stage(device_id: str = None):

    global email_manager , CURRENT_DEVICE
    
    try:
        # إنشاء مدير القوات عند أول تشغيل فقط
        if email_manager is None or (device_id and (email_manager.device_id != device_id)):
            email_manager = TroopsManager(device_id or DEVICE_ID)
            CURRENT_DEVICE = device_id or DEVICE_ID
            
            # إضافة الخطوات
            email_manager.add_step(1, "فتح قائمة القوات", step_1_Clean_fast, 
                       "فتح قائمة القوات من القائمة الرئيسية")
            email_manager.add_step(2, "فتح قائمة القوات", step_2_Email_open, 
                                "فتح قائمة القوات من القائمة الرئيسية")
            email_manager.add_step(3, "فتح قائمة القوات", step_3_Kass, 
                                "فتح قائمة القوات من القائمة الرئيسية")
            email_manager.add_step(4, "فتح قائمة القوات", step_4_ReadAll, 
                                "فتح قائمة القوات من القائمة الرئيسية")
            email_manager.add_step(5, "فتح قائمة القوات", step_5_ReadAll, 
                                "فتح قائمة القوات من القائمة الرئيسية")
                       

        # تشغيل جميع الخطوات
        result = email_manager.execute_all_steps()
        
      
        return result
        
    except Exception as e:
        
        return False




if __name__ == "__main__":
    # ============================================================================
    # كيفية تشغيل البرنامج
    # ============================================================================
    run_email_stage(DEVICE_ID)
    

    
