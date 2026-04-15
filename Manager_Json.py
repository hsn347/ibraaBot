
import os
import json 
import psutil
import re
from typing import List, Dict, Optional, Tuple
import subprocess
import re
import sys
import threading
import time
import shutil
from datetime import datetime

# استيراد مكتبات القفل حسب نظام التشغيل
try:
    import msvcrt  # لـ Windows
except ImportError:
    msvcrt = None

try:
    import fcntl  # للأنظمة الشبيهة بـ Unix
except ImportError:
    fcntl = None

# نظام قفل الملفات للكتابة الآمنة
class FileLock:
    """نظام قفل الملفات لمنع الكتابة المتزامنة"""
    
    def __init__(self, filepath, timeout=30):
        self.filepath = filepath
        self.timeout = timeout
        self.lock_file = filepath + '.lock'
        self.locked = False
        
    def __enter__(self):
        self.acquire()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        
    def acquire(self):
        """الحصول على قفل الملف"""
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            try:
                if sys.platform.startswith("win") and msvcrt:
                    # Windows
                    self.lock_handle = open(self.lock_file, 'w')
                    msvcrt.locking(self.lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
                elif fcntl:
                    # Unix/Linux
                    self.lock_handle = open(self.lock_file, 'w')
                    fcntl.flock(self.lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    # Fallback: استخدام قفل بسيط
                    self.lock_handle = open(self.lock_file, 'w')
                    # محاولة قفل بسيط
                    self.lock_handle.write(f"{os.getpid()}\n")
                    self.lock_handle.flush()
                
                self.locked = True
                return True
                
            except (IOError, OSError):
                time.sleep(0.1)
                continue
                
        raise TimeoutError(f"فشل في الحصول على قفل الملف: {self.filepath}")
        
    def release(self):
        """إطلاق قفل الملف"""
        if self.locked:
            try:
                if sys.platform.startswith("win") and msvcrt:
                    msvcrt.locking(self.lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
                elif fcntl:
                    fcntl.flock(self.lock_handle.fileno(), fcntl.LOCK_UN)
                    
                self.lock_handle.close()
                if os.path.exists(self.lock_file):
                    os.remove(self.lock_file)
                    
            except Exception:
                pass
            finally:
                self.locked = False

# نظام النسخ الاحتياطية
class BackupManager:
    """مدير النسخ الاحتياطية للملفات JSON"""
    
    @staticmethod
    def create_backup(filepath):
        """إنشاء نسخة احتياطية من الملف"""
        try:
            if not os.path.exists(filepath):
                return False
                
            backup_dir = os.path.join(os.path.dirname(filepath), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.basename(filepath)
            backup_path = os.path.join(backup_dir, f"{filename}.backup_{timestamp}")
            
            shutil.copy2(filepath, backup_path)
            
            # الاحتفاظ بـ 5 نسخ احتياطية فقط
            BackupManager._cleanup_old_backups(backup_dir, filename)
            
            return True
            
        except Exception as e:
            print(f"[BACKUP ERROR] فشل في إنشاء نسخة احتياطية: {e}")
            return False
    
    @staticmethod
    def _cleanup_old_backups(backup_dir, filename):
        """حذف النسخ الاحتياطية القديمة (الاحتفاظ بـ 5 فقط)"""
        try:
            pattern = f"{filename}.backup_"
            backups = [f for f in os.listdir(backup_dir) if f.startswith(pattern)]
            backups.sort(reverse=True)
            
            # حذف النسخ الزائدة
            for backup in backups[5:]:
                backup_path = os.path.join(backup_dir, backup)
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                    
        except Exception as e:
            print(f"[BACKUP CLEANUP ERROR] {e}")
    
    @staticmethod
    def restore_from_backup(filepath):
        """استعادة الملف من أحدث نسخة احتياطية"""
        try:
            backup_dir = os.path.join(os.path.dirname(filepath), 'backups')
            if not os.path.exists(backup_dir):
                return False
                
            filename = os.path.basename(filepath)
            pattern = f"{filename}.backup_"
            backups = [f for f in os.listdir(backup_dir) if f.startswith(pattern)]
            
            if not backups:
                return False
                
            # أحدث نسخة احتياطية
            backups.sort(reverse=True)
            latest_backup = os.path.join(backup_dir, backups[0])
            
            # التحقق من صحة النسخة الاحتياطية
            if JSONValidator._validate_json_file(latest_backup):
                shutil.copy2(latest_backup, filepath)
                print(f"[BACKUP RESTORE] تم استعادة الملف من: {latest_backup}")
                return True
            else:
                print(f"[BACKUP RESTORE] النسخة الاحتياطية تالفة: {latest_backup}")
                return False
                
        except Exception as e:
            print(f"[BACKUP RESTORE ERROR] {e}")
            return False

# نظام التحقق من صحة JSON
class JSONValidator:
    """فئة للتحقق من صحة ملفات JSON"""
    
    @staticmethod
    def validate_json_file(filepath):
        """التحقق من صحة ملف JSON"""
        try:
            if not os.path.exists(filepath):
                return False
                
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # قبول البنية الأساسية كقاموس
            if not isinstance(data, dict):
                return False

            # قبول غياب بعض الحقول الاختيارية وعدم اعتبار الملف تالفًا بسببها
            villages = data.get('villages', None)
            if villages is None:
                # ملف بدون مفتاح villages يعتبر غير صالح للقراءة لكنه ليس تالفًا يُعاد إنشاؤه
                return False

            if not isinstance(villages, list):
                return False

            # التحقق الأساسي لكل قرية، مع التسامح في الحقول الناقصة بدل اعتبار الملف تالفًا بالكامل
            for village in villages:
                if not isinstance(village, dict):
                    return False
                # حقول مطلوبة للتشغيل، لكن غيابها لا يستدعي الكتابة فوق الملف هنا
                # سيتم تصفيتها عند الحفظ في الواجهة
            return True
            
        except (json.JSONDecodeError, UnicodeDecodeError, Exception) as e:
            print(f"[JSON VALIDATION ERROR] {e}")
            return False
    
    @staticmethod
    def repair_json_file(filepath):
        """إصلاح ملف JSON التالف"""
        try:
            print(f"[JSON REPAIR] محاولة إصلاح الملف: {filepath}")
            
            # محاولة استعادة من النسخ الاحتياطية
            if BackupManager.restore_from_backup(filepath):
                if JSONValidator.validate_json_file(filepath):
                    print(f"[JSON REPAIR] تم إصلاح الملف بنجاح من النسخة الاحتياطية")
                    return True
            
            # لا تنشئ ملفًا فارغًا تلقائيًا — تجنب مسح الحسابات دون قصد
            print("[JSON REPAIR] لم تتوفر نسخة احتياطية صالحة. سيتم ترك الملف كما هو لتجنب فقدان البيانات.")
            return False
            
        except Exception as e:
            print(f"[JSON REPAIR ERROR] {e}")
            return False
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
        """حفظ بيانات البوت مع حماية من الكتابة المتزامنة"""
        path = BotDataManager.get_bot_data_path(bot_idx)
        
        try:
            # التحقق من صحة البيانات قبل الحفظ
            if not isinstance(data, dict) or 'villages' not in data:
                raise ValueError("بيانات غير صحيحة للحفظ")
            # إذا كانت القرى الجديدة فارغة، حافظ على البيانات القديمة بدل مسحها، إلا إذا كان هناك أمر حذف صريح
            incoming_villages = data.get('villages')
            if isinstance(incoming_villages, list) and len(incoming_villages) == 0 and not data.get('__force_clear__'):
                existing = BotDataManager.load_bot_villages(bot_idx)
                if isinstance(existing, dict) and existing.get('villages'):
                    # احتفظ بالحسابات القديمة كما هي، وحدّث فقط account_index إن وُجد في الطلب
                    preserved = existing.copy()
                    if 'account_index' in data:
                        preserved['account_index'] = data.get('account_index', preserved.get('account_index', 0))
                    data = preserved
            
            # إنشاء نسخة احتياطية قبل الكتابة
            if os.path.exists(path):
                BackupManager.create_backup(path)
            
            # الحفظ مع قفل الملف
            with FileLock(path, timeout=10):
                # كتابة البيانات في ملف مؤقت أولاً
                temp_path = path + '.tmp'
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # التحقق من صحة الملف المؤقت
                if JSONValidator.validate_json_file(temp_path):
                    # استبدال الملف الأصلي بالملف المؤقت
                    shutil.move(temp_path, path)
                    print(f"[SAVE SUCCESS] تم حفظ بيانات البوت {bot_idx+1} بنجاح")
                else:
                    # حذف الملف المؤقت إذا كان تالفاً
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    raise ValueError("فشل في التحقق من صحة البيانات المحفوظة")
                    
        except Exception as e:
            print(f"[SAVE ERROR] خطأ في حفظ بيانات البوت {bot_idx+1}: {e}")
            # محاولة إصلاح الملف إذا كان تالفاً
            if os.path.exists(path) and not JSONValidator.validate_json_file(path):
                JSONValidator.repair_json_file(path)
    
    @staticmethod
    def load_bot_villages(bot_idx):
        """تحميل بيانات البوت مع حماية من القراءة المتزامنة"""
        path = BotDataManager.get_bot_data_path(bot_idx)
        
        try:
            if not os.path.exists(path):
                return None
                
            # التحقق من صحة الملف قبل القراءة
            if not JSONValidator.validate_json_file(path):
                print(f"[LOAD ERROR] ملف البوت {bot_idx+1} تالف، محاولة الإصلاح...")
                if JSONValidator.repair_json_file(path):
                    # إعادة المحاولة بعد الإصلاح
                    if JSONValidator.validate_json_file(path):
                        pass  # الملف أصبح صحيحاً
                    else:
                        print(f"[LOAD ERROR] فشل في إصلاح ملف البوت {bot_idx+1}")
                        return None
                else:
                    print(f"[LOAD ERROR] فشل في إصلاح ملف البوت {bot_idx+1}")
                    return None
            
            # القراءة مع قفل الملف
            with FileLock(path, timeout=5):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
            return data
            
        except Exception as e:
            print(f"[LOAD ERROR] خطأ في تحميل بيانات البوت {bot_idx+1}: {e}")
            # محاولة إصلاح الملف
            if os.path.exists(path):
                JSONValidator.repair_json_file(path)
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
        """تحميل بيانات البوت مع حماية من القراءة المتزامنة"""
        json_file = BotDataManager._get_json_file(bot_number)
        
        try:
            if not os.path.exists(json_file):
                return {}
                
            # التحقق من صحة الملف قبل القراءة
            if not JSONValidator.validate_json_file(json_file):
                print(f"[LOAD ERROR] ملف البوت {bot_number} تالف، محاولة الإصلاح...")
                if JSONValidator.repair_json_file(json_file):
                    # إعادة المحاولة بعد الإصلاح
                    if JSONValidator.validate_json_file(json_file):
                        pass  # الملف أصبح صحيحاً
                    else:
                        print(f"[LOAD ERROR] فشل في إصلاح ملف البوت {bot_number}")
                        return {}
                else:
                    print(f"[LOAD ERROR] فشل في إصلاح ملف البوت {bot_number}")
                    return {}
            
            # القراءة مع قفل الملف
            with FileLock(json_file, timeout=5):
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
            return data
            
        except Exception as e:
            print(f"[LOAD ERROR] خطأ في تحميل بيانات البوت {bot_number}: {e}")
            # محاولة إصلاح الملف
            if os.path.exists(json_file):
                JSONValidator.repair_json_file(json_file)
            return {}

    @staticmethod
    def save_bot_data(bot_number, data):
        """حفظ بيانات البوت مع حماية من الكتابة المتزامنة"""
        json_file = BotDataManager._get_json_file(bot_number)
        
        try:
            # التحقق من صحة البيانات قبل الحفظ
            if not isinstance(data, dict) or 'villages' not in data:
                raise ValueError("بيانات غير صحيحة للحفظ")
            # إذا كانت القرى الجديدة فارغة، لا تمسح الملف القائم؛ حافظ على الموجود مع تحديث المؤشر فقط عند الطلب
            incoming_villages = data.get('villages')
            if isinstance(incoming_villages, list) and len(incoming_villages) == 0 and not data.get('__force_clear__'):
                existing = BotDataManager.load_bot_data(bot_number)
                if isinstance(existing, dict) and existing.get('villages'):
                    preserved = existing.copy()
                    if 'account_index' in data:
                        preserved['account_index'] = data.get('account_index', preserved.get('account_index', 0))
                    data = preserved
            
            # إنشاء نسخة احتياطية قبل الكتابة
            if os.path.exists(json_file):
                BackupManager.create_backup(json_file)
            
            # الحفظ مع قفل الملف
            with FileLock(json_file, timeout=10):
                # كتابة البيانات في ملف مؤقت أولاً
                temp_path = json_file + '.tmp'
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # التحقق من صحة الملف المؤقت
                if JSONValidator.validate_json_file(temp_path):
                    # استبدال الملف الأصلي بالملف المؤقت
                    shutil.move(temp_path, json_file)
                    print(f"[SAVE SUCCESS] تم حفظ بيانات البوت {bot_number} بنجاح")
                else:
                    # حذف الملف المؤقت إذا كان تالفاً
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    raise ValueError("فشل في التحقق من صحة البيانات المحفوظة")
                    
        except Exception as e:
            print(f"[SAVE ERROR] خطأ في حفظ بيانات البوت {bot_number}: {e}")
            # محاولة إصلاح الملف إذا كان تالفاً
            if os.path.exists(json_file) and not JSONValidator.validate_json_file(json_file):
                JSONValidator.repair_json_file(json_file)

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
    def get_bot_current_email_index(device, bot_number=None):
        """قراءة البريد الإلكتروني الحالي من ملف JSON الخاص بالبوت"""
        try:
            if bot_number is None:
                bot_number = BotDataManager.get_device_bot_number(device)

            index = BotDataManager.get_account_index(device)
            
            json_file = f"bot_data/bot_{bot_number}_villages.json"
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    villages = data.get("villages", [])
                    total_accounts = len(villages)
                    if villages:
                        if index == 0:
                            target_account_index = total_accounts - 1
                        else:
                            target_account_index = index - 1
                        email = villages[target_account_index].get("email", "")
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

    # ============================================================================
    # دوال إدارة المتغير الجديد (مثل account_index)
    # ============================================================================
    
    @staticmethod
    def get_save_counter(device, bot_number=None):
        """إرجاع قيمة المتغير الجديد الحالية"""
        if bot_number is None:
            bot_number = BotDataManager.get_device_bot_number(device)
        data = BotDataManager.load_bot_data(bot_number)
        return data.get("save_counter", 0)
    
    @staticmethod
    def increment_save_counter(device, bot_number=None):
        """زيادة قيمة المتغير الجديد بقيمة 1"""
        if bot_number is None:
            bot_number = BotDataManager.get_device_bot_number(device)
        data = BotDataManager.load_bot_data(bot_number)
        current_value = data.get("save_counter", 0)
        data["save_counter"] = current_value + 1
        BotDataManager.save_bot_data(bot_number, data)
        return data["save_counter"]
    
    @staticmethod
    def reset_save_counter(device, bot_number=None):
        """جعل قيمة المتغير الجديد 0"""
        if bot_number is None:
            bot_number = BotDataManager.get_device_bot_number(device)
        data = BotDataManager.load_bot_data(bot_number)
        data["save_counter"] = 1
        BotDataManager.save_bot_data(bot_number, data)
        return 0

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
    def get_bot_bonus_run_count(device, bot_number=None):
        """إرجاع عدد مرات تشغيل البونيس للحساب الحالي في اليوم الحالي"""
        try:
            if bot_number is None:
                bot_number = BotDataManager.get_device_bot_number(device)
            index = BotDataManager.get_account_index(device, bot_number)
            data = BotDataManager.load_bot_data(bot_number)
            villages = data.get("villages", [])
            if 0 <= index < len(villages):
                account = villages[index]
                today = datetime.now().strftime("%Y-%m-%d")
                last_date = account.get("last_bonus_date", "")
                if last_date != today:
                    return 0
                return account.get("bonus_run_count", 0)
        except Exception as e:
            print(f"[DEBUG] Error in get_bot_bonus_run_count: {e}")
        return 0

    @staticmethod
    def increment_bot_bonus_run_count(device, bot_number=None):
        """زيادة عدد مرات تشغيل البونيس وتحديث التاريخ"""
        try:
            if bot_number is None:
                bot_number = BotDataManager.get_device_bot_number(device)
            index = BotDataManager.get_account_index(device, bot_number)
            data = BotDataManager.load_bot_data(bot_number)
            villages = data.get("villages", [])
            if 0 <= index < len(villages):
                account = villages[index]
                today = datetime.now().strftime("%Y-%m-%d")
                last_date = account.get("last_bonus_date", "")
                
                if last_date != today:
                    account["bonus_run_count"] = 1
                    account["last_bonus_date"] = today
                else:
                    account["bonus_run_count"] = account.get("bonus_run_count", 0) + 1
                
                BotDataManager.save_bot_data(bot_number, data)
                return account["bonus_run_count"]
        except Exception as e:
            print(f"[DEBUG] Error in increment_bot_bonus_run_count: {e}")
        return 0

    @staticmethod
    def get_bot_Not_Store(device, bot_number=None):
        """إرجاع قيمة Not_Store من ملف JSON الخاص بالبوت حسب account_index"""
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
                        return villages[target_account_index].get("Not_Store", False)
        except Exception as e:
            print(f"[DEBUG] خطأ في get_bot_Not_Store: {e}")

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
    def set_bot_Not_Store_false(device, bot_number=None):
        """تعيين Not_Store = False للحساب الحالي (حسب account_index)"""
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
                    villages[target_account_index]["Not_Store"] = False  # 👈 التغيير

                    # حفظ التعديل في نفس الملف
                    with open(json_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                    print(f"[DEBUG] تم تعيين Not_Store=False للحساب رقم {index} في bot_{bot_number}")
                    return True

        except Exception as e:
            print(f"[DEBUG] خطأ في set_bot_Not_Store_false: {e}")

        return False

    @staticmethod
    def set_bot_Not_Store(device, value, bot_number=None):
        """تعيين قيمة Not_Store للحساب الحالي (حسب account_index)"""
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
                    villages[target_account_index]["Not_Store"] = value  # 👈 التغيير

                    # حفظ التعديل في نفس الملف
                    with open(json_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                    print(f"[DEBUG] تم تعيين Not_Store={value} للحساب رقم {index} في bot_{bot_number}")
                    return True

        except Exception as e:
            print(f"[DEBUG] خطأ في set_bot_Not_Store: {e}")

        return False

    @staticmethod
    def validate_all_bot_files():
        """التحقق من جميع ملفات البوت وإصلاح التالف منها"""
        print("[VALIDATION] بدء التحقق من جميع ملفات البوت...")
        fixed_count = 0
        total_count = 0
        
        for i in range(1, 16):  # 15 بوت
            total_count += 1
            json_file = BotDataManager._get_json_file(i)
            
            if os.path.exists(json_file):
                if not JSONValidator.validate_json_file(json_file):
                    print(f"[VALIDATION] ملف البوت {i} تالف، محاولة الإصلاح...")
                    if JSONValidator.repair_json_file(json_file):
                        fixed_count += 1
                        print(f"[VALIDATION] تم إصلاح ملف البوت {i} بنجاح")
                    else:
                        print(f"[VALIDATION] فشل في إصلاح ملف البوت {i}")
                else:
                    print(f"[VALIDATION] ملف البوت {i} سليم")
            else:
                print(f"[VALIDATION] ملف البوت {i} غير موجود")
        
        print(f"[VALIDATION] انتهى التحقق: {fixed_count}/{total_count} ملف تم إصلاحه")
        return fixed_count > 0

    @staticmethod
    def create_emergency_backup():
        """إنشاء نسخة احتياطية طارئة لجميع ملفات البوت"""
        try:
            backup_dir = "bot_data/emergency_backup"
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_subdir = os.path.join(backup_dir, f"backup_{timestamp}")
            os.makedirs(backup_subdir, exist_ok=True)
            
            backed_up = 0
            for i in range(1, 16):
                source_file = BotDataManager._get_json_file(i)
                if os.path.exists(source_file):
                    filename = os.path.basename(source_file)
                    dest_file = os.path.join(backup_subdir, filename)
                    shutil.copy2(source_file, dest_file)
                    backed_up += 1
            
            print(f"[EMERGENCY BACKUP] تم إنشاء نسخة احتياطية طارئة: {backup_subdir}")
            print(f"[EMERGENCY BACKUP] تم نسخ {backed_up} ملف")
            return backup_subdir
            
        except Exception as e:
            print(f"[EMERGENCY BACKUP ERROR] {e}")
            return None


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



data = extract_ports_only()

idx1 = 0
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


def find_index(lst, value):
    try:
        return lst.index(value)
    except ValueError:
        return -1


