import cv2
import numpy as np
import time
import threading
from typing import Union, List, Tuple, Optional , Dict, Callable
import logging
import uiautomator2 as u2
from Path import run_Path , reset_Path

def action_for_Ottman(device, x, y):
    time.sleep(120)
    device.click(x, y)

my_custom_actions = {
    "image/Ottman.png": action_for_Ottman, # عند رؤية هذه الصورة، سيشغل دالة التمرير
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEVICE_ID = "127.0.0.1:5615"

outflow_import_Alliance = 0 
outflow_import_Alliance2 = 0
outflow_import_Alliance3 = 0
outflow_import_Alliance_4 = True
outflow_import_Alliance_5 = 0
outflow_import_Alliance_6 = 0
attempt = 0
attempt1 = 0
CURRENT_DEVICE = None


# ============================================================================
# نظام إدارة الخطوات مع إمكانية الرجوع
# ============================================================================

class TroopsManager:
    def __init__(self, device_id: str = DEVICE_ID):
        """
        مدير مرحلة القوات مع إمكانية الرجوع للخطوات
  
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

    
def reset_Alliance():
    global outflow_import_Alliance_6 ,outflow_import_Alliance_5 , attempt1 , outflow_import_Alliance_4 , CURRENT_DEVICE , outflow_import_Alliance ,outflow_import_Alliance2 , outflow_import_Alliance3 ,Alliance_manager ,attempt 

    attempt = 0
    attempt1 = 0
    outflow_import_Alliance = 0 
    outflow_import_Alliance2 = 0
    outflow_import_Alliance3 = 0
    outflow_import_Alliance_4 = True
    outflow_import_Alliance_5 = 0
    outflow_import_Alliance_6 = 0
    CURRENT_DEVICE = None
    Alliance_manager = None

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
            logger.error(f"خطأ في التقاط الشاشة")
    
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
        time.sleep(0.5)
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
            if 'Alliance_manager' in globals() and Alliance_manager is not None:
                return Alliance_manager.stop_execution()
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
    
def search_with_fallback(device, ref_icon_path: str, ref_region: Tuple[int, int, int, int],
                         ref_timeout: float, max_attempts: int = 10) -> Optional[Tuple[int, int]]:

    fallback_icons = ["image/x.png", "image/prev.png"]
    global attempt1
    for attempt1 in range(1, max_attempts + 1):
        if attempt1 >= 9:
            attempt1 = 0
            Clean_fast(device)
            return Alliance_manager.stop_execution()
            
        ref_coords = find_icon(device, ref_icon_path, screen_region=ref_region, timeout=ref_timeout)
        if ref_coords:
            return ref_coords
        

        fb_coords = find_icon(device, fallback_icons)
        if fb_coords:
    
            try:
                device.click(fb_coords[0], fb_coords[1])
                time.sleep(0.5)  # انتظار بسيط بعد النقر
            except Exception as e:
                logger.error(f"خطأ أثناء النقر على الأيقونة البديلة: {e}")
        
        time.sleep(0.3)  # تأخير بسيط بين المحاولات
    
    return None

# ============================================================================
# مثال على كيفية إضافة الخطوات
# ============================================================================

def step_1_Clean_fast(device):
    global outflow_import_Alliance 
    outflow_import_Alliance += 1
    if outflow_import_Alliance >= 8:
        outflow_import_Alliance = 0
        Clean_fast(device)
        return Alliance_manager.stop_execution()

    return Clean_fast(device)

def step_2_Alliance(device):
    click_coordinates(device , 640 , 1250)
    time.sleep(0.2)    
    results_Alliance = wait_for_icon(device ,"image/Alliance.png" ,screen_region=(296, 0, 422, 100),timeout=2)    
    if results_Alliance:
        return True
    
    results_Join_Alliance = wait_for_icon(device ,"image/Join_Alliance.png" ,screen_region=(200, 0, 600, 100),timeout=2)    
    if results_Join_Alliance:
        Clean_fast(device)
        return Alliance_manager.stop_execution()

    return Alliance_manager.go_to_step_and_continue(1)

def step_3_DONALI(device):
    results_DONALI = wait_for_icon_coordinates(device ,"image/DONALI.png" , screen_region=(200, 500, 720, 1000),timeout=2)    
    if results_DONALI:
        time.sleep(0.2) 
        x , y = results_DONALI
        click_coordinates(device , x , y)
        return True
    else:
        return Alliance_manager.go_to_step_and_continue(1)

def step_4_l(device):
    results_l = wait_for_icon(device ,"image/1.png" , screen_region=(0, 250, 84, 340),timeout=1.5)    
    if results_l:
        time.sleep(0.2) 
        Clean_fast(device)
        return Alliance_manager.stop_execution()
    else:
        time.sleep(0.2) 
        click_coordinates(device , 300 , 300)
        return True

def step_5_GoldALI(device):
    global outflow_import_Alliance_4
    results_GoldALI = wait_for_icon(device ,"image/GoldALI.png" , screen_region=(150, 840, 200, 885),timeout=2)    
    if results_GoldALI:
        return True
    else:
        if outflow_import_Alliance_4:
            click_coordinates(device , 600 , 70)
            time.sleep(0.4)
            click_coordinates(device , 300 , 430)
            time.sleep(0.4)
            outflow_import_Alliance_4 = False
            return Alliance_manager.go_to_step_and_continue(5)
        else:
            return Alliance_manager.go_to_step_and_continue(7)

def step_6_Ok(device):
    global outflow_import_Alliance_5
    outflow_import_Alliance_5 += 1
    if outflow_import_Alliance_5 >= 16:
        outflow_import_Alliance_5 = 0

        Clean_fast(device)

        return True
        
    results_Ok = wait_for_icon(device ,"image/ok.png" , screen_region=(250, 700, 480, 800),timeout=0.5)    
    if results_Ok:
        return True
    else:
        click_coordinates(device , 525 , 875)
        time.sleep(0.4)
        click_coordinates(device , 525 , 875)
        time.sleep(0.4)
        click_coordinates(device , 525 , 875)
        time.sleep(0.4)
        return Alliance_manager.go_to_step_and_continue(6)

def step_7_TreaALI(device):
    result_TreaALI = search_with_fallback(device , ref_icon_path="image/TreaALI.png" ,ref_region=(250, 625, 720, 1150) , ref_timeout=1)
    if result_TreaALI:
        time.sleep(0.2) 
        x , y = result_TreaALI
        click_coordinates(device , x , y)
        return True
    else:
        return Alliance_manager.go_to_step_and_continue(1) 

def step_8_FreeExte(device):
    global outflow_import_Alliance2
    outflow_import_Alliance2 += 1
    if outflow_import_Alliance2 >= 8:
        outflow_import_Alliance2=0
        Clean_fast(device)
        return Alliance_manager.stop_execution()

    results_FreeExte = wait_for_icon_coordinates(device ,"image/FreeExte.png" , screen_region=(480, 200, 720, 1280),timeout=3)    
    if results_FreeExte:
        x , y = results_FreeExte
        click_coordinates(device , x , y)
        time.sleep(0.5)
        click_coordinates(device , 360 , 150)
        return True
    else:
        click_coordinates(device , 360 , 150)
        return True

def step_9_Claim(device):
    global outflow_import_Alliance3
    outflow_import_Alliance3 += 1
    if outflow_import_Alliance3 >= 10:
        outflow_import_Alliance3=0
        Clean_fast(device)
        return Alliance_manager.stop_execution()

    results_Claim = wait_for_icon_coordinates(device ,"image/claim.png" , screen_region=(480, 200, 720, 1280),timeout=1.5)    
    if results_Claim:
        x , y = results_Claim
        click_coordinates(device , x , y)
        time.sleep(0.5)
        return Alliance_manager.go_to_step_and_continue(9)
    else:
        results_reqHelp = wait_for_icon_coordinates(device ,"image/reqHelp.png" , screen_region=(480, 200, 720, 1280),timeout=2)    
        if results_reqHelp:
            x , y = results_reqHelp
            click_coordinates(device , x , y)
            time.sleep(0.3)
            outflow_import_Alliance3 = 0
            click_coordinates(device , 600 , 150)
            return True
        click_coordinates(device , 600 , 150)

def step_10_Help(device):
    global outflow_import_Alliance_6
    outflow_import_Alliance_6 += 1
    if outflow_import_Alliance_6 >= 14:
        outflow_import_Alliance_6=0
        Clean_fast(device)
        return Alliance_manager.stop_execution()

    results_Claim = wait_for_icon_coordinates(device ,"image/claim.png" , screen_region=(480, 200, 720, 1280),timeout=1.5)    
    if results_Claim:
        x , y = results_Claim
        click_coordinates(device , x , y)
        time.sleep(0.5)

    results_Help = wait_for_icon_coordinates(device ,"image/Help.png" , screen_region=(518, 200, 710, 1280),timeout=1.5)    
    if results_Help:
        x , y = results_Help
        click_coordinates(device , x , y)
        time.sleep(0.8)

    Clean_fast(device)
    return True



Alliance_manager = None  

def run_Alliance_stage(device_id: str = None):

    global Alliance_manager , CURRENT_DEVICE
    
    try:
        if Alliance_manager is None or (device_id and (Alliance_manager.device_id != device_id)):
            Alliance_manager = TroopsManager(device_id)
            CURRENT_DEVICE = device_id
            
            Alliance_manager.add_step(1, "فتح قائمة القوات", step_1_Clean_fast, "فتح قائمة القوات من القائمة الرئيسية")
            Alliance_manager.add_step(2, "فتح قائمة القوات", step_2_Alliance, "فتح قائمة القوات من القائمة الرئيسية")
            Alliance_manager.add_step(3, "فتح قائمة القوات", step_3_DONALI, "فتح قائمة القوات من القائمة الرئيسية")
            Alliance_manager.add_step(4, "فتح قائمة القوات", step_4_l, "فتح قائمة القوات من القائمة الرئيسية")
            Alliance_manager.add_step(5, "فتح قائمة القوات", step_5_GoldALI, "فتح قائمة القوات من القائمة الرئيسية")
            Alliance_manager.add_step(6, "فتح قائمة القوات", step_6_Ok, "فتح قائمة القوات من القائمة الرئيسية")
            Alliance_manager.add_step(7, "فتح قائمة القوات", step_7_TreaALI, "فتح قائمة القوات من القائمة الرئيسية")
            Alliance_manager.add_step(8, "فتح قائمة القوات", step_8_FreeExte, "فتح قائمة القوات من القائمة الرئيسية")
            Alliance_manager.add_step(9, "فتح قائمة القوات", step_9_Claim, "فتح قائمة القوات من القائمة الرئيسية")
            Alliance_manager.add_step(10, "فتح قائمة القوات", step_10_Help, "فتح قائمة القوات من القائمة الرئيسية")


        Alliance_manager.execute_all_steps()

        
    except Exception as e:
        return False

if __name__ == "__main__":

    run_Alliance_stage(DEVICE_ID)

    