
import os
import json 
import psutil
import re
from typing import List, Dict, Optional, Tuple
import subprocess
import re

MATERIALS_KEYS = [
    ("wood", "image/supwood.png", "image/buywood.png"),
    ("qmh", "image/supqmh.png", "image/buyqmh.png"),
    ("iron", "image/supiron.png", "image/buyiron.png"),
    ("almas", "image/supalmas.png", "image/buyalmas.png"),
]


def extract_device_to_bot_mapping():
    file_path = r"C:\ProgramData\BlueStacks_nxt\bluestacks.conf"
    device_mapping = {}
    pattern = re.compile(r'bst\.instance\.(?P<name>[^.]+)\.adb_port="?([0-9]+)"?')

    bot_index = 1
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                port = match.group(2)
                device_mapping[f"127.0.0.1:{port}"] = bot_index
                bot_index += 1

    return device_mapping

DEVICE_TO_BOT_MAPPING = extract_device_to_bot_mapping()


class WhatsAppAccountParser:
    """فئة لمعالجة رسائل الواتساب وتحويلها إلى حسابات منظمة"""
    
    @staticmethod
    def parse_whatsapp_message(message: str) -> List[Dict[str, str]]:
        """تحليل رسالة الواتساب وتحويلها إلى قائمة حسابات"""
        accounts = []
        lines = [line.strip() for line in message.split('\n') if line.strip()]
        
        current_emails = []
        
        for line in lines:
            # إذا كان السطر بريد إلكتروني (يحتوي على @ و . وليس كلمة مرور)
            if '@' in line and '.' in line and not line.isdigit() and len(line) > 10:
                current_emails.append(line)
            else:
                # إذا كان السطر كلمة مرور
                if current_emails:
                    # إضافة جميع الحسابات السابقة مع كلمة المرور الحالية
                    for email in current_emails:
                        accounts.append({
                            "email": email,
                            "password": line,
                            "options": [True, True, True, True],
                            "Attauck": ["قمح", "ألماس"]
                        })
                    current_emails = []
        
        return accounts
    
    @staticmethod
    def validate_accounts(accounts: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], List[str]]:
        """
        التحقق من صحة الحسابات
        
        Args:
            accounts: قائمة الحسابات
            
        Returns:
            Tuple[List[Dict[str, str]], List[str]]: الحسابات الصحيحة وقائمة الأخطاء
        """
        valid_accounts = []
        errors = []
        
        for i, account in enumerate(accounts, 1):
            email = account.get("email", "").strip()
            password = account.get("password", "").strip()
            
            # التحقق من البريد الإلكتروني
            if not email:
                errors.append(f"الحساب {i}: البريد الإلكتروني فارغ")
                continue
                
            if not '@' in email or not '.' in email:
                errors.append(f"الحساب {i}: البريد الإلكتروني غير صحيح: {email}")
                continue
            
            # التحقق من كلمة المرور
            if not password:
                errors.append(f"الحساب {i}: كلمة المرور فارغة للبريد: {email}")
                continue
            
            # إضافة الحساب الصحيح
            valid_accounts.append(account)
        
        return valid_accounts, errors


class BotDataManager:
    """فئة لإدارة بيانات البوت من ملفات JSON، مع دعم account_index"""

    @staticmethod
    def get_icons_from_options(device, bot_number=None):
        """إرجاع أيقونات الصور بناءً على القيم المنطقية في options"""
        try:
            if bot_number is None:
                bot_number = BotDataManager.get_device_bot_number(device)

            index = BotDataManager.get_account_index(device)
            json_file = f"bot_data/bot_{bot_number}_villages.json"

            if os.path.exists(json_file):
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    villages = data.get("villages", [])
                    if not villages:
                        return None
                    
                    options = villages[index-1].get("options", [])
                    
                    # نربط true مع MATERIALS_KEYS
                    icons = [
                        MATERIALS_KEYS[i]
                        for i, val in enumerate(options)
                        if i < len(MATERIALS_KEYS) and val is True
                    ]
                    
                    return icons if icons else None
        except Exception as e:
            print(f"[خطأ] {e}")
        return None

    @staticmethod
    def get_bot_data_path(bot_idx):
        os.makedirs('bot_data', exist_ok=True)
        return os.path.join('bot_data', f'bot_{bot_idx+1}_villages.json')
    
    @staticmethod
    def save_bot_villages(bot_idx, data):
        path = BotDataManager.get_bot_data_path(bot_idx)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def load_bot_villages(bot_idx):
        path = BotDataManager.get_bot_data_path(bot_idx)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None 
    
    @staticmethod
    def process_whatsapp_accounts(bot_number: int, whatsapp_message: str) -> Dict[str, any]:
        """معالجة رسالة الواتساب وحفظ الحسابات في ملف JSON"""
        try:
            accounts = WhatsAppAccountParser.parse_whatsapp_message(whatsapp_message)
            valid_accounts, errors = WhatsAppAccountParser.validate_accounts(accounts)
            
            if not valid_accounts:
                return {"success": False, "message": "لم يتم العثور على حسابات صحيحة", "errors": errors, "accounts_count": 0}
            
            data = {"villages": valid_accounts, "period": "شهر", "account_index": 0}
            BotDataManager.save_bot_data(bot_number, data)
            
            return {"success": True, "message": f"تم حفظ {len(valid_accounts)} حساب بنجاح", "errors": errors, "accounts_count": len(valid_accounts), "accounts": valid_accounts}
            
        except Exception as e:
            return {"success": False, "message": f"خطأ في معالجة الحسابات: {str(e)}", "errors": [str(e)], "accounts_count": 0}
    
    @staticmethod
    def get_device_bot_number(device):
        """تحديد رقم البوت من اسم الجهاز"""
        return DEVICE_TO_BOT_MAPPING.get(device, 1)
    
    @staticmethod
    def _get_json_file(bot_number):
        return f"bot_data/bot_{bot_number}_villages.json"

    @staticmethod
    def load_bot_data(bot_number):
        json_file = BotDataManager._get_json_file(bot_number)
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    @staticmethod
    def save_bot_data(bot_number, data):
        json_file = BotDataManager._get_json_file(bot_number)
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def get_account_index(device, bot_number=None):
        if bot_number is None:
            bot_number = BotDataManager.get_device_bot_number(device)
        data = BotDataManager.load_bot_data(bot_number)
        return data.get("account_index", 0)

    @staticmethod
    def set_account_index(device, value, bot_number=None):
        if bot_number is None:
            bot_number = BotDataManager.get_device_bot_number(device)
        data = BotDataManager.load_bot_data(bot_number)
        data["account_index"] = value
        BotDataManager.save_bot_data(bot_number, data)

    @staticmethod
    def reset_account_index(device, bot_number=None):
        BotDataManager.set_account_index(device, 0, bot_number)
    
    @staticmethod
    def get_bot_accounts(device, bot_number=None):
        """جلب جميع حسابات البوت من ملف JSON"""
        try:
            if bot_number is None:
                bot_number = BotDataManager.get_device_bot_number(device)
            data = BotDataManager.load_bot_data(bot_number)
            villages = data.get("villages", [])
     
            return villages
        except Exception as e:
     
            return []
    
    @staticmethod
    def get_bot_email(device, bot_number=None):
        """قراءة البريد الإلكتروني من ملف JSON الخاص بالبوت"""
        try:
            if bot_number is None:
                bot_number = BotDataManager.get_device_bot_number(device)
            
            json_file = f"bot_data/bot_{bot_number}_villages.json"
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    villages = data.get("villages", [])
                    if villages:
                        email = villages[0].get("email", "")
                  
                        return email
        except Exception as e:
            print(f"[DATA E")
        return ""
      
    @staticmethod
    def get_bot_password(device, bot_number=None):
        """قراءة كلمة المرور من ملف JSON الخاص بالبوت"""
        try:
            if bot_number is None:
                bot_number = BotDataManager.get_device_bot_number(device)
            
            json_file = f"bot_data/bot_{bot_number}_villages.json"
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    villages = data.get("villages", [])
                    if villages:
                        password = villages[0].get("password", "")
                
                        return password
        except Exception as e:
            print(f"[DATA ERROR] خطأ في قراءة كلمة المرور: {e}")
        return ""
    
    @staticmethod
    def get_bot_password_for_email(device, email, bot_number=None):
        """قراءة كلمة المرور المرتبطة ببريد إلكتروني محدد"""
        try:
            if bot_number is None:
                bot_number = BotDataManager.get_device_bot_number(device)
            
            json_file = f"bot_data/bot_{bot_number}_villages.json"
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    villages = data.get("villages", [])
                    
                    # البحث عن البريد الإلكتروني المحدد
                    for village in villages:
                        if village.get("email") == email:
                            password = village.get("password", "")
                            return password
                    
                    return ""
        except Exception as e:
            print(f"[DAT ق")
        return ""

    @staticmethod
    def get_bot_email_index(device, bot_number=None):
        """قراءة البريد الإلكتروني من ملف JSON الخاص بالبوت"""
        try:
            if bot_number is None:
                bot_number = BotDataManager.get_device_bot_number(device)

            index = BotDataManager.get_account_index(device)
            
            json_file = f"bot_data/bot_{bot_number}_villages.json"
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    villages = data.get("villages", [])
                    if villages:
                        email = villages[index].get("email", "")
                  
                        return email
        except Exception as e:
            print(f"[DAبر")
        return ""
        
    @staticmethod
    def get_bot_options_index(device, bot_number=None):
        """قراءة البريد الإلكتروني من ملف JSON الخاص بالبوت"""
        try:
            if bot_number is None:
                bot_number = BotDataManager.get_device_bot_number(device)

            index = BotDataManager.get_account_index(device)
            
            json_file = f"bot_data/bot_{bot_number}_villages.json"
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    villages = data.get("villages", [])
                    if villages:
                        email = villages[index-1].get("options", "")
                  
                        return email
        except Exception as e:
            print(f"[DAبر")
        return ""
        
    @staticmethod
    def increace_account_index(device, bot_number=None):
        num_ACC = BotDataManager.get_bot_accounts(device)
        if bot_number is None:
            bot_number = BotDataManager.get_device_bot_number(device)
        data = BotDataManager.load_bot_data(bot_number)
        if len(num_ACC) -1 <= data["account_index"] :
            data["account_index"] = 0
        else:
            data["account_index"] = data["account_index"] + 1
        BotDataManager.save_bot_data(bot_number, data)

    @staticmethod
    def get_bot_custom_flag(device, bot_number=None):
        """إرجاع قيمة custom_flag من ملف JSON الخاص بالبوت حسب account_index"""
        try:
            if bot_number is None:
                bot_number = BotDataManager.get_device_bot_number(device)

            index = BotDataManager.get_account_index(device)

            json_file = f"bot_data/bot_{bot_number}_villages.json"
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    total_accounts = len(data['villages'])
                    if index == 0:
                        # إذا كان account_index = 0، استخدم آخر حساب
                        target_account_index = total_accounts - 1
                        
                    else:
                        # استخدم account_index - 1
                        target_account_index = index - 1

                    villages = data.get("villages", [])
                    if villages and 0 <= target_account_index < len(villages):
                        return villages[target_account_index].get("custom_flag", False)
        except Exception as e:
            print(f"[DEBUG] خطأ في get_bot_custom_flag: {e}")

        return False  # القيمة الافتراضية إذا لم يجد

    @staticmethod
    def get_bot_Troops(device, bot_number=None):
        """إرجاع قيمة Troops من ملف JSON الخاص بالبوت حسب account_index"""
        try:
            if bot_number is None:
                bot_number = BotDataManager.get_device_bot_number(device)

            index = BotDataManager.get_account_index(device)

            json_file = f"bot_data/bot_{bot_number}_villages.json"
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    total_accounts = len(data['villages'])
                    if index == 0:
                        # إذا كان account_index = 0، استخدم آخر حساب
                        target_account_index = total_accounts - 1
                        
                    else:
                        # استخدم account_index - 1
                        target_account_index = index - 1

                    villages = data.get("villages", [])
                    if villages and 0 <= target_account_index < len(villages):
                        return villages[target_account_index].get("Troops", False)
        except Exception as e:
            print(f"[DEBUG] خطأ في get_bot_custom_flag: {e}")

        return False  # القيمة الافتراضية إذا لم يجد

    @staticmethod
    def set_bot_custom_flag_false(device, bot_number=None):
        """تعيين custom_flag = False للحساب الحالي (حسب account_index)"""
        try:
            if bot_number is None:
                bot_number = BotDataManager.get_device_bot_number(device)

            index = BotDataManager.get_account_index(device)

            json_file = f"bot_data/bot_{bot_number}_villages.json"
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    total_accounts = len(data['villages'])
                    if index == 0:
                        # إذا كان account_index = 0، استخدم آخر حساب
                        target_account_index = total_accounts - 1
                        
                    else:
                        # استخدم account_index - 1
                        target_account_index = index - 1

                villages = data.get("villages", [])
                if villages and 0 <= target_account_index < len(villages):
                    villages[target_account_index]["custom_flag"] = False  # 👈 التغيير

                    # حفظ التعديل في نفس الملف
                    with open(json_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                    print(f"[DEBUG] تم تعيين custom_flag=False للحساب رقم {index} في bot_{bot_number}")
                    return True

        except Exception as e:
            print(f"[DEBUG] خطأ في set_bot_custom_flag_false: {e}")

        return False


    @staticmethod
    def qqqw(instance_name):
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if proc.info['name'] == 'HD-Player.exe' and instance_name in ' '.join(proc.info['cmdline']):
                return proc.info['pid']
  


def get_instances_from_metadata(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    instances = []
    for item in data.get("Organization", []):
        display_name = item.get("Name")
        instance_name = item.get("InstanceName")
        instances.append((display_name, instance_name))
    
    return instances


def extract_device_mapping():
    file_path = r"C:\ProgramData\BlueStacks_nxt\bluestacks.conf"
    device_mapping = {}
    pattern = re.compile(r'bst\.instance\.(?P<name>[^.]+)\.adb_port="?([0-9]+)"?')

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                instance_name = match.group("name")
                port = match.group(2)
                device_mapping[instance_name] = f"127.0.0.1:{port}"
    return device_mapping


def extract_ports_only():
    file_path = r"C:\ProgramData\BlueStacks_nxt\bluestacks.conf"
    ports = []
    pattern = re.compile(r'bst\.instance\.[^.]+\.status\.adb_port="?([0-9]+)"?')

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                port = match.group(1)
                ports.append(f"127.0.0.1:{port}")
    return ports


def extract_instance_numbers():
    file_path = r"C:\ProgramData\BlueStacks_nxt\bluestacks.conf"
    instance_numbers = []
    pattern = re.compile(r'bst\.instance\.(?P<name>[^.]+)\.status\.adb_port="?([0-9]+)"?')

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                name = match.group("name")
                if "_" in name:
                    number = name.split("_")[-1]
                else:
                    number = "0"
                instance_numbers.append(int(number))
    return instance_numbers


def extract_instance_names():
    file_path = r"C:\ProgramData\BlueStacks_nxt\bluestacks.conf"
    instance_names = []
    pattern = re.compile(r'bst\.instance\.(?P<name>[^.]+)\.status\.adb_port="?([0-9]+)"?')

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                name = match.group("name")   # هذا يرجع مثل Pie64_5
                instance_names.append(name)
    return instance_names







