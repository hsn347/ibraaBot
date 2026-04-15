import cv2
import numpy as np
import time
import threading
from typing import Optional, Tuple, List, Union, Dict, Callable
import logging
import uiautomator2 as u2
import requests
import subprocess
import sys
import psutil
from Manager_Json import extract_instance_names

def action_for_Ottman(device, x, y):
    time.sleep(120)
    device.click(x, y)

my_custom_actions = {
    "image/Ottman.png": action_for_Ottman, # عند رؤية هذه الصورة، سيشغل دالة التمرير
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
attempt= 0

DEVICE_ID = "127.0.0.1:5555"
CURRENT_DEVICE = None
data = extract_instance_names()

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


def reset_Path():
    global Path_manager , data , CURRENT_DEVICE ,attempt
    CURRENT_DEVICE = None
    attempt = 0 
    data = extract_instance_names()
    Path_manager = None
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
            logger.error(f"خطأ في")
    
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
        time.sleep(0.7)
    
    return False

def wait_for_icon_2(device, icon_path: str, screen_region: Tuple[int, int, int, int] = None, 
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
        time.sleep(2)
    
    return False

def wait_for_icon_coordinates(device, icon_path: str, screen_region: Tuple[int, int, int, int] = None, 
                              timeout: float = 10.0) -> Optional[Tuple[int, int]]:
    """
    انتظار ظهور أيقونة وإرجاع إحداثياتها
    
    Args:
        device: الجهاز
        icon_path: مسار الأيقونة
        screen_region: منطقة البحث في الشاشة (x1, y1, x2, y2)
        timeout: وقت الانتظار
        
    Returns:
        Tuple[int, int] أو None: إحداثيات الأيقونة إذا وجدت، None إذا لم توجد
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        coordinates = find_icon(device, icon_path, screen_region)
        if coordinates:
            return coordinates
        time.sleep(0.5)
    
    return None

def Clean_fast(device, target_icons: list = None, custom_actions: dict = None, max_attempts: int = 5) -> bool:

    global my_custom_actions
    if target_icons is None:
         target_icons = ["image/prev.png", "image/x.png", "image/prev2.png", "image/EventNew.png", "image/ok.png", "image/Ottman.png"]
    
    if custom_actions is None:
        custom_actions = my_custom_actions
        
    global attempt
    for attempt in range(max_attempts):
        if attempt >= max_attempts - 1:
            attempt = 0
            reset_Path()
            run_Path(CURRENT_DEVICE)
            Clean_fast(device, target_icons, custom_actions, max_attempts)
            if 'Path_manager' in globals() and Path_manager is not None:
                return Path_manager.stop_execution()
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

def Attauck_Clean_fast(device):
    Clean_fast(device)
    result_Ring2 = wait_for_icon(device, "image/ring2.png" ,screen_region=(0, 400, 200, 900),timeout=2)
    if result_Ring2:
        return Path_manager.stop_execution()
    else:
        click_coordinates(device, 360 , 1230)
        result_Ring2 = wait_for_icon(device, "image/ring2.png" ,screen_region=(0, 400, 200, 900),timeout=8)
        if result_Ring2:
            return Path_manager.stop_execution()
        else:
            return Attauck_Clean_fast(device)

def find_index(lst, value):
    try:
        return lst.index(value)
    except ValueError:
        return -1

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

def close_emulator_instance(idx1):
    # إغلاق LDPlayer instance عبر ldconsole.exe
    if len(data) > idx1 :
        name = data[idx1]
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] == "HD-Player.exe" and any(name in arg for arg in proc.info['cmdline']):
                subprocess.run(["taskkill", "/F", "/PID", str(proc.info['pid'])] ,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0)
                print(f"✅ Instance {name} killed.")
                return
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    print(f"❌ No instance found with name {name}")


# ============================================================================
# مثال على كيفية إضافة الخطوات
# ============================================================================

def step_1_Search(device):
    from Manager_Json import BotDataManager
    
    BotDataManager.increment_save_counter(CURRENT_DEVICE)
    
    Save_Count_P = BotDataManager.get_save_counter(CURRENT_DEVICE)

    if Save_Count_P >= 6 :
        BotDataManager.reset_save_counter(CURRENT_DEVICE)
        return exit()

    

    logger.info(f"🧀🧀🧀🧀🧀🧀🧀🧀🧀🧀🧀🧀🧀{CURRENT_DEVICE}")
    #message to Acount Error
    Result_Search = wait_for_icon(device, "image/ERR_ACOUNT.png" , screen_region=(0, 400 , 720 , 775), timeout=2)
    if Result_Search:
        click_coordinates(device, 365 , 750)
        time.sleep(300)
        return Path_manager.go_to_step_and_continue(1)

    Result_OK_ERR = wait_for_icon_coordinates(device, "image/OK_3.png", screen_region=(200, 500 , 530 , 1000) , timeout=2)
    if Result_OK_ERR:
        x , y = Result_OK_ERR
        click_coordinates(device , x , y)

     
    from HAND import run_Hand_stage ,reset_Hand
    reset_Hand()
    run_Hand_stage(CURRENT_DEVICE)


    #message to Ottman icon Error
    global Result_Ottman
    Result_STORE_OTMAN = wait_for_icon_coordinates(device, "image/STORE_OTMAN.png" , timeout=2)
    if Result_STORE_OTMAN:
        Result_Ottman = wait_for_icon_coordinates(device, "image/Ottman.png" , timeout=2)
        if Result_Ottman:
            x , y = Result_Ottman
            click_coordinates(device, x , y)
            time.sleep(4)
            Result_Wood = wait_for_icon_2(device, "image/almasMini.png" ,screen_region=[0 , 0 , 500 , 50], timeout=40)
            if Result_Wood:
                return Path_manager.stop_execution()
            return Path_manager.go_to_step_and_continue(1)
        else:
            # استيراد مؤجل لتجنب الدورة الدائرية
            from INSTALL import reset_INSTALL, run_INSTALL_stage
            reset_INSTALL()
            run_INSTALL_stage(CURRENT_DEVICE)
            return Path_manager.stop_execution()



    #message to Netowork Error
    Result_NetWork = wait_for_icon(device, "image/ERR_Netowork.png", screen_region=(0, 400 , 720 , 775) , timeout=2)
    if Result_NetWork:
        click_coordinates(device, 365 , 750)
        send_whatsapp_message(f"هناك مشكلة في اتصال الانترنت في جهاز {device}")
        return Path_manager.stop_execution()

    


    #message to Netowork_T Error
    Result_NetWork_T_1 = wait_for_icon_coordinates(device , "image/ERR_TRIN.png" , screen_region=(240, 760 , 480 , 950) , timeout=2)
    if Result_NetWork_T_1:
        x , y = Result_NetWork_T_1
        click_coordinates(device , x , y)
        Result_NetWork_T_2 = wait_for_icon(device , "image/ERR_TRIN.png" , screen_region=(240, 760 , 480 , 950) , timeout=10)
        if Result_NetWork_T_2:
            send_whatsapp_message(f"هناك مشكلة في الاتصال بالانترنت في جهاز {device} , تم ايقاف البوت ❌❌❌❌❌❌❌❌❌")
            return Path_manager.go_to_step_and_continue(1)
    

    Result_Rise = wait_for_icon_coordinates(device, "image/Rise.png" ,screen_region=(200, 670 , 530 , 800) , timeout=2)
    if Result_Rise:
        x , y = Result_Rise
        click_coordinates(device, x , y)
        time.sleep(4)
        
        result_Wood_Mini = wait_for_icon_2(device, "image/woodmini.png" ,screen_region=(0, 0, 250, 50),timeout=20)
        if result_Wood_Mini:
            Attauck_Clean_fast(device)
            return True
        Attauck_Clean_fast(device)

    result_Wait_1 = find_multiple_icons(device ,["image/Wait_1.png","image/Wait_2.png","image/Wait_3.png","image/Wait_4.png","image/Wait_5.png","image/Wait_6.png","image/Wait_7.png","image/Wait_8.png",] ,screen_region=(295, 575, 420, 695) , timeout=3 ,threshold=0.7)
    if result_Wait_1: 
        logger.info("💖💖💖💖💖💖💖💖💖💖")
        dqd = find_index(data , device)
        close_emulator_instance(dqd)  
        
    return Path_manager.stop_execution() 

    
Path_manager = None

def run_Path(device_id: str = None):

    global Path_manager , CURRENT_DEVICE
    
    try:
        if Path_manager is None or (device_id and (Path_manager.device_id != device_id)):
            Path_manager = TroopsManager(device_id or DEVICE_ID) 
            CURRENT_DEVICE = device_id        
            Path_manager.add_step(1, "البحث عن الفيالق", step_1_Search, "البحث عن الفيالق في القائمة")

        Path_manager.execute_all_steps()

    except Exception as e:
        return False


if __name__ == "__main__":
    run_Path(DEVICE_ID)
    