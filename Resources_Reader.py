"""
Resources_Reader.py
====================
وحدة مستقلة لقراءة موارد القرية من شاشة اللعبة وإرسالها إلى Supabase.

الخطوات:
1. التقاط صورة لشاشة اللعبة عبر uiautomator2
2. قص شريط الموارد العلوي بإحداثيات واحدة (0, 0, 660, 35)
3. تقسيم الشريط داخلياً إلى 5 مناطق فرعية (واحدة لكل مورد)
4. استخراج رقم كل مورد بـ OCR مستقل ودقيق
5. تصحيح أخطاء OCR الشائعة (B→8، نقطة ضائعة، + زائدة)
6. تحديث جدول Accounts في Supabase

الاستخدام:
    from Resources_Reader import read_and_upload_resources
    read_and_upload_resources(device, "127.0.0.1:5555")
"""

import os
import re
import threading
import numpy as np
import cv2
from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None

from Manager_Json import BotDataManager, _get_supabase_client

# ============================================================================
# إعدادات Tesseract
# ============================================================================
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

_tesseract_configured = False


def _configure_tesseract():
    """ضبط مسار Tesseract (مرة واحدة فقط)"""
    global _tesseract_configured
    if _tesseract_configured:
        return True

    if pytesseract is None:
        print("[RESOURCES] pytesseract module not installed")
        return False

    if os.path.exists(TESSERACT_CMD):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
        _tesseract_configured = True
        return True

    try:
        pytesseract.get_tesseract_version()
        _tesseract_configured = True
        return True
    except Exception:
        pass

    print(f"[RESOURCES] Tesseract not found at: {TESSERACT_CMD}")
    return False


# ============================================================================
# ترتيب الموارد وإعداداتها
# ============================================================================
RESOURCE_ORDER = ['grain', 'lumber', 'iron', 'quartz', 'gold']

RESOURCE_NAMES_AR = {
    'grain':  'القمح',
    'lumber': 'الخشب',
    'iron':   'الحديد',
    'quartz': 'الألماس',
    'gold':   'الذهب',
}

SUPABASE_COLUMN_MAP = {
    'grain':  'grain_res',
    'lumber': 'lumber_res',
    'iron':   'iron_res',
    'quartz': 'quartz_res',
    'gold':   'gold_res',
}

# ============================================================================
# مناطق النص الفرعية داخل شريط الموارد (660×35)
# ============================================================================
# كل tuple: (اسم_المورد, x_بداية, x_نهاية)
# هذه المناطق تستهدف أرقام النص فقط (بدون الأيقونات)
# تم قياسها من لقطة شاشة حقيقية للعبة عند دقة 720px
SUB_REGIONS = [
    ('grain',  60,  115),   # مثال: 2.9B
    ('lumber', 150, 225),   # مثال: 417.3M
    ('iron',   262, 340),   # مثال: 307.0M
    ('quartz', 375, 465),   # مثال: 336.3M
    ('gold',   488, 560),   # مثال: 16,810
]


# ============================================================================
# معالجة الصورة
# ============================================================================

def _preprocess_sub_region(pil_image, scale=6):
    """
    معالجة منطقة فرعية واحدة لتحسين دقة OCR.

    - تكبير 6x (لجعل النقاط العشرية واضحة)
    - عدة عتبات إضاءة للتجربة
    - بدون MORPH_OPEN (للحفاظ على النقاط)
    - حدود بيضاء واسعة

    Returns:
        list[Image]: قائمة صور معالجة بعتبات مختلفة
    """
    w, h = pil_image.size
    pil_image = pil_image.resize((w * scale, h * scale), Image.LANCZOS)
    img_np = np.array(pil_image)

    if len(img_np.shape) == 3:
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_np

    results = []
    # عدة عتبات: النص في اللعبة يتراوح بين 130-230 brightness
    for thresh_val in [120, 135, 150, 165]:
        _, binary = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)
        inverted = cv2.bitwise_not(binary)

        # فقط CLOSE (لملء الثغرات الصغيرة) - بدون OPEN (لحماية النقاط)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(inverted, cv2.MORPH_CLOSE, kernel)

        bordered = cv2.copyMakeBorder(
            cleaned, 30, 30, 30, 30,
            cv2.BORDER_CONSTANT, value=255
        )
        results.append(Image.fromarray(bordered))

    return results


# ============================================================================
# تحليل النص واستخراج الأرقام
# ============================================================================

def _clean_raw_ocr(text):
    """تنظيف النص الخام من OCR"""
    t = text.strip()
    # إزالة مسافات وأسطر
    t = t.replace(' ', '').replace('\n', '').replace('\r', '')
    # إزالة رموز ضوضاء شائعة
    t = t.replace('+', '').replace('@', '').replace('#', '')
    t = t.replace('"', '').replace("'", '').replace('(', '').replace(')', '')
    t = t.replace('[', '').replace(']', '').replace('{', '').replace('}', '')
    t = t.replace('©', '').replace('®', '').replace('*', '')
    t = t.replace('<', '').replace('>', '')
    # إزالة الفواصل (16,810 → 16810)
    t = t.replace(',', '')
    return t


def _parse_resource_value(text):
    """
    تحويل نص مورد واحد إلى رقم.
    يدعم: 2.9B, 417.3M, 307.0M, 1.2K, 16810

    Returns:
        str: الرقم كنص أو None
    """
    if not text:
        return None

    t = _clean_raw_ocr(text)
    if not t:
        return None

    # تصحيحات OCR: أحرف تشبه أرقام
    t = t.replace('O', '0').replace('o', '0')
    t = t.replace('l', '1').replace('I', '1').replace('|', '1')
    # توحيد اللواحق
    t = t.replace('b', 'B').replace('m', 'M').replace('k', 'K')

    match = re.match(r'^(\d+\.?\d*)\s*([BMK])?$', t)
    if not match:
        return None

    try:
        # User wants the text exactly as it is with letters and numbers (e.g. '2.9B', '417.3M')
        # If there's no suffix (B/M/K) but there is a dot, it's a comma misread as a dot (e.g. 16.810)
        suffix = match.group(2)
        if not suffix and '.' in t:
            t = t.replace('.', '')

        return t
    except Exception:
        return None


def _smart_parse(raw_text):
    """
    تحليل ذكي مع تصحيح أخطاء OCR الخاصة باللعبة.

    التصحيحات:
    1. محاولة مباشرة
    2. آخر رقم 8 → لاحقة B  (مثال: 298 → 29B → لا ← 2.9B)
    3. إدراج نقطة عشرية للأرقام > 999 مع لاحقة (4173M → 417.3M)
    4. إدراج نقطة + تحويل 8→B  (298 → 2.9B)
    """
    t = _clean_raw_ocr(raw_text)
    if not t:
        return None

    # توحيد اللواحق
    t = t.replace('b', 'B').replace('m', 'M').replace('k', 'K')
    t = t.replace('O', '0').replace('o', '0')
    t = t.replace('l', '1').replace('I', '1').replace('|', '1')

    # ── المحاولة 1: تحليل مباشر ──
    result = _parse_resource_value(t)
    if result:
        # تصحيح 3: إذا الرقم قبل اللاحقة >= 1000 → نقطة ضائعة
        result = _fix_missing_dot(t, result)
        return result

    # ── المحاولة 2: آخر حرف 8 → B ──
    if t.endswith('8'):
        t2 = t[:-1] + 'B'
        result = _parse_resource_value(t2)
        if result:
            result = _fix_missing_dot(t2, result)
            return result

        # المحاولة 2b: إدراج نقطة قبل B
        # مثال: 298 → 8→B → 29B → إدراج نقطة → 2.9B
        if len(t) >= 3:
            digits = t[:-1]  # e.g. "29"
            t3 = digits[:-1] + '.' + digits[-1] + 'B'  # "2.9B"
            result = _parse_resource_value(t3)
            if result:
                return result

    # ── المحاولة 3: حرف 0 في النهاية → يمكن أن يكون حرفاً ضائعاً ──
    # (لا نفعل شيئاً إضافياً هنا)

    # ── المحاولة 4: إزالة أحرف غير رقمية متبقية والتجربة ──
    digits_only = re.sub(r'[^0-9.]', '', t)
    if digits_only and digits_only != t:
        result = _parse_resource_value(digits_only)
        if result:
            return result

    return None


def _fix_missing_dot(ocr_text, parsed_result):
    """
    إصلاح النقطة العشرية الضائعة.

    في اللعبة: القيم مع لواحق (B/M/K) لا تتجاوز 999.9
    مثال: 4173M → 417.3M = 417,300,000 (وليس 4,173,000,000)
    """
    # استخراج الرقم واللاحقة
    t = ocr_text.strip()
    match = re.match(r'^(\d+)(\.?\d*)([BMK])$', t)
    if not match:
        return parsed_result

    int_part = match.group(1)
    dec_part = match.group(2)  # "" or ".X"
    suffix = match.group(3)

    # إذا الجزء الصحيح >= 1000 وليس فيه نقطة عشرية
    if len(int_part) >= 4 and not dec_part:
        # إدراج نقطة قبل آخر رقم: 4173 → 417.3
        fixed_text = int_part[:-1] + '.' + int_part[-1] + suffix
        fixed_result = _parse_resource_value(fixed_text)
        if fixed_result:
            return fixed_result

    return parsed_result


# ============================================================================
# OCR لمنطقة فرعية واحدة
# ============================================================================

def _ocr_single_resource(pil_sub_image):
    """
    قراءة قيمة مورد واحد من صورته الفرعية المقصوصة.

    يستخدم:
    - عدة عتبات معالجة
    - عدة إعدادات Tesseract (psm 7, 8, 13)
    - تحليل ذكي مع تصحيح أخطاء

    Returns:
        str: القيمة الرقمية كنص أو None
    """
    if pytesseract is None:
        return None

    processed_images = _preprocess_sub_region(pil_sub_image)

    # psm 7 (سطر واحد) أدق بكثير من psm 8 (كلمة واحدة)
    # لأنه يقرأ النقاط العشرية واللواحق B/M/K بشكل صحيح
    configs = [
        '--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789.BMK',
        '--psm 8 --oem 3 -c tessedit_char_whitelist=0123456789.BMK',
        '--psm 13 --oem 3 -c tessedit_char_whitelist=0123456789.BMK',
    ]

    for config in configs:
        candidates = []
        for proc_img in processed_images:
            try:
                raw = pytesseract.image_to_string(proc_img, config=config).strip()
            except Exception:
                continue

            if not raw:
                continue

            parsed = _smart_parse(raw)
            if parsed is not None:
                candidates.append(parsed)

        # إذا نجح هذا الإعداد في استخراج قيم، نأخذ الأكثر تكراراً ونتوقف
        if candidates:
            from collections import Counter
            counter = Counter(candidates)
            most_common = counter.most_common(1)[0][0]
            return most_common

    return None


# ============================================================================
# القراءة من الشريط الكامل
# ============================================================================

def _read_resources_from_bar(bar_image):
    """
    استخراج الموارد الخمسة من شريط الموارد.

    المنهج: تقسيم الشريط إلى 5 مناطق فرعية → OCR مستقل لكل منطقة.

    Args:
        bar_image: صورة PIL لشريط الموارد المقصوص (660×35)

    Returns:
        dict: {grain, lumber, iron, quartz, gold}
    """
    bar_width = bar_image.size[0]
    bar_height = bar_image.size[1]

    resources = {}

    for res_name, x_start, x_end in SUB_REGIONS:
        # حماية من تجاوز الحدود
        x_start = max(0, min(x_start, bar_width - 1))
        x_end = max(x_start + 1, min(x_end, bar_width))

        # قص المنطقة الفرعية
        sub_img = bar_image.crop((x_start, 0, x_end, bar_height))

        # قراءة القيمة
        value = _ocr_single_resource(sub_img)
        resources[res_name] = value

    return resources


# ============================================================================
# الدالة الرئيسية
# ============================================================================

def read_and_upload_resources(device, device_id,
                              resource_bar_region=(0, 0, 660, 35),
                              bot_number=None,
                              run_in_thread=True):
    """
    قراءة موارد القرية من شاشة اللعبة وإرسالها إلى Supabase.

    1. التقاط الشاشة → قص شريط الموارد (قص واحد)
    2. تقسيم داخلي إلى 5 مناطق (قمح، خشب، حديد، ألماس، ذهب)
    3. OCR مستقل لكل مورد مع تصحيحات ذكية
    4. تحديث Supabase: grain_res, lumber_res, iron_res, quartz_res, gold_res

    Args:
        device: كائن uiautomator2
        device_id: معرف الجهاز (مثال: "127.0.0.1:5555")
        resource_bar_region: إحداثيات الشريط (x1, y1, x2, y2) - افتراضي (0,0,660,35)
        bot_number: رقم البوت (None = تلقائي)
        run_in_thread: True = تحديث Supabase في thread منفصل

    Returns:
        dict أو None
    """
    if not _configure_tesseract():
        return None

    # ── التقاط الشاشة ──
    try:
        screenshot = device.screenshot()
        if screenshot is None:
            return None
    except Exception:
        return None

    # ── الإيميل الحالي ──
    try:
        email = BotDataManager.get_bot_current_email_index(device_id, bot_number)
        if not email:
            return None
    except Exception:
        return None

    # ── قص الشريط ──
    try:
        x1, y1, x2, y2 = resource_bar_region
        bar_image = screenshot.crop((x1, y1, x2, y2))
    except Exception:
        return None

    # ── قراءة الموارد ──
    resources = _read_resources_from_bar(bar_image)

    # ── النتائج ──
    found = sum(1 for v in resources.values() if v is not None)
    if found == 0:
        return None

    # ── تحديث Supabase ──
    if run_in_thread:
        t = threading.Thread(
            target=_update_resources_in_supabase,
            args=(email, resources),
            daemon=True,
        )
        t.start()
    else:
        _update_resources_in_supabase(email, resources)

    return resources


# ============================================================================
# تحديث Supabase
# ============================================================================

def _update_resources_in_supabase(email, resources):
    """تحديث أعمدة الموارد في جدول Accounts"""
    try:
        client = _get_supabase_client()
        if client is None:
            return False

        update_data = {}
        for res_key, col_name in SUPABASE_COLUMN_MAP.items():
            value = resources.get(res_key)
            if value is not None:
                update_data[col_name] = value

        if not update_data:
            return False

        client.table("Accounts").update(update_data).eq("Email", email).execute()
        return True

    except Exception:
        return False


# ============================================================================
# دالة تشخيصية
# ============================================================================

def debug_save_resource_bar(device,
                             resource_bar_region=(0, 0, 660, 35),
                             save_dir="debug_resources"):
    """حفظ الشريط والمناطق الفرعية والنسخ المعالجة للتشخيص"""
    os.makedirs(save_dir, exist_ok=True)

    try:
        screenshot = device.screenshot()
        screenshot.save(os.path.join(save_dir, "full_screenshot.png"))

        x1, y1, x2, y2 = resource_bar_region
        bar = screenshot.crop((x1, y1, x2, y2))
        bar.save(os.path.join(save_dir, "resource_bar_raw.png"))

        bar_width = bar.size[0]
        bar_height = bar.size[1]

        for res_name, xs, xe in SUB_REGIONS:
            xs = max(0, min(xs, bar_width - 1))
            xe = max(xs + 1, min(xe, bar_width))
            sub = bar.crop((xs, 0, xe, bar_height))
            sub.save(os.path.join(save_dir, f"{res_name}_sub_raw.png"))

            # حفظ أول نسخة معالجة
            processed_list = _preprocess_sub_region(sub)
            if processed_list:
                processed_list[0].save(
                    os.path.join(save_dir, f"{res_name}_sub_processed.png")
                )

        # محاولة القراءة
        if _configure_tesseract():
            resources = _read_resources_from_bar(bar)
            print(f"[DEBUG] Resources: {resources}")

        print(f"[DEBUG] Saved to: {os.path.abspath(save_dir)}")

    except Exception as e:
        print(f"[DEBUG] error: {e}")


# ============================================================================
# نقطة الدخول للاختبار
# ============================================================================

if __name__ == "__main__":
    import uiautomator2 as u2

    DEVICE_ID = "127.0.0.1:5555"

    print("=" * 60)
    print("  Reading Village Resources")
    print("=" * 60)

    try:
        device = u2.connect(DEVICE_ID)
        print(f"Connected to: {DEVICE_ID}")

        debug_save_resource_bar(device)

        result = read_and_upload_resources(
            device=device,
            device_id=DEVICE_ID,
            run_in_thread=False,
        )

        if result:
            print("\nFinal Results:")
            for k, v in result.items():
                ar = RESOURCE_NAMES_AR.get(k, k)
                print(f"  {ar}: {v}")
        else:
            print("\nFailed to read resources")

    except Exception as e:
        print(f"Error: {e}")
