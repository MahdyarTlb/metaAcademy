from PIL import Image, ImageDraw, ImageFont, ImageMath
from django.conf import settings
from io import BytesIO
from django.core.files.base import ContentFile
from .models import Enrollment
import os
import secrets
from io import BytesIO
import arabic_reshaper
from bidi.algorithm import get_display
try:
    from PIL.features import check as _pil_check
    HAS_RAQM = _pil_check('raqm')
except Exception:
    HAS_RAQM = False

FONT_PATH = "static/fonts/YekanBakh-VF.woff2"

def generate_unique_tracking_code():
    """کد ۷ رقمی یکتا. با حداکثر ۲۰ تلاش."""
    for _ in range(20):
        code = ''.join(secrets.choice('0123456789') for _ in range(7))
        if not Enrollment.objects.filter(tracking_code=code).exists():
            return code
    raise RuntimeError('نتونستم کد رهگیری یکتا پیدا کنم')

def to_persian_digits(text):
    return str(text).translate(
        str.maketrans(
            '0123456789',
            '۰۱۲۳۴۵۶۷۸۹'
        )
    )
    
def prepare_persian_text(text):
    """آماده‌سازی متن فارسی برای Pillow"""
    reshaped = arabic_reshaper.reshape(str(text))
    displayed = get_display(reshaped)
    if HAS_RAQM:
        return displayed[::-1]
    return displayed


def load_font(size, weight=400):
    """
    لود Yekan Bakh Variable Font
    weight:
        100 = Thin
        200 = ExtraLight
        300 = Light
        400 = Regular
        500 = Medium
        600 = SemiBold
        700 = Bold
        800 = ExtraBold
        900 = Black
    """

    font = ImageFont.truetype(
        FONT_PATH,
        size
    )

    # انتخاب وزن Variable Font
    try:
        font.set_variation_by_axes([weight])
    except Exception:
        pass

    return font


def draw_centered_text(draw, text, center_x, y, font, fill='black', direction=None):
    """
    متن را حول یک نقطه X مشخص، به صورت وسط‌چین قرار می‌دهد.
    """

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    text_width = bbox[2] - bbox[0]

    x = center_x - (text_width / 2)

    kwargs = {'fill': fill, 'font': font}
    
    if direction and HAS_RAQM:
        kwargs['direction'] = direction

    draw.text((x, y), text, **kwargs)

def generate_certificate_for_student(enrollment, base_template_path=None):
    """
    ساخت مدرک دانشجو.
    نام و کد ملی با فونت، سایز و وزن متفاوت نوشته می‌شوند.
    """
    student = enrollment.student
    bootcamp = enrollment.bootcamp
    
    if not enrollment.tracking_code:
        enrollment.tracking_code = generate_unique_tracking_code()
        enrollment.save(update_fields=['tracking_code'])

    
    if base_template_path is None:
        if bootcamp.certificate_template:
            base_template_path = bootcamp.certificate_template.path
        else:
            base_template_path = os.path.join(
                settings.MEDIA_ROOT, 'preview', 'preview_signature.jpg'
            )
            
    template = Image.open(
        base_template_path
    ).convert('RGBA')

    draw = ImageDraw.Draw(template)

    # =========================
    # فونت نام
    # =========================

    name_font = load_font(
        size=70,
        weight=800
    )

    # =========================
    # فونت کد ملی
    # =========================

    national_code_font = load_font(
        size=25,
        weight=400
    )

    # =========================
    # تنظیمات موقعیت نام
    # =========================
    name_center_x = 737
    name_y = 470


    # =========================
    # تنظیمات موقعیت کد ملی
    # =========================
    national_code_center_x = 935
    national_code_y = 672

    # =========================
    # نام دانشجو
    # =========================

    name = prepare_persian_text(student.name)

    draw_centered_text(
        draw=draw,
        text=name,
        center_x=name_center_x,
        y=name_y,
        direction='rtl',
        font=name_font
    )

    # =========================
    # کد ملی
    # =========================
    national_code = to_persian_digits(student.national_code)

    draw_centered_text(
        draw=draw,
        text=national_code,
        center_x=national_code_center_x,
        y=national_code_y,
        font=national_code_font
    )

    if enrollment.tracking_code:
        tracking_font = load_font(size=19, weight=400)
        tracking_text = prepare_persian_text("کدرهگیری: " + to_persian_digits(enrollment.tracking_code))

        draw_centered_text(
            draw=draw,
            text=tracking_text,
            center_x=210,
            y=87,
            font=tracking_font,
        )
    
    # =========================
    # ذخیره
    # =========================
    output = BytesIO()

    template.convert('RGB').save(
        output,
        format='JPEG',
        quality=95,
        optimize=True,
        subsampling=0
    )

    output.seek(0)

    filename = (
        f"cert_{enrollment.bootcamp.slug}_{student.name}.jpg"
    )

    return ContentFile(
        output.read(),
        name=filename
    )


def remove_white_background(image, threshold=240, opacity=0.5):
    """
    پسزمینه سفید (یا نزدیک به سفید) را شفاف میکند - روش جایگزین
    """
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    # دریافت دادهها
    datas = image.getdata()
    new_data = []
    
    for item in datas:
        # اگر رنگ نزدیک به سفید بود، شفاف کن
        if item[0] > threshold and item[1] > threshold and item[2] > threshold:
            new_data.append((255, 255, 255, 0))  # شفاف کامل
        else:
            new_alpha = int(item[3] * opacity)  # کاهش opacity
            new_data.append((item[0], item[1], item[2], new_alpha))
    
    image.putdata(new_data)
    return image

def preview_signature_on_template(signature_image_path, template_path='static/img/certificate_template.jpg'):
    """
    فقط امضا را روی قالب خالی مدرک می‌چسباند (بدون نام و کد ملی)
    برای پیشنمایش در پنل مدیریت
    """
    # باز کردن قالب
    template = Image.open(template_path).convert('RGBA')
    
    # باز کردن امضا
    sig = Image.open(signature_image_path).convert('RGBA')
    sig = remove_white_background(sig)
    
    # تغییر اندازه امضا (همان اندازه‌ای که در مدرک نهایی استفاده میشود)
    target_width = 220
    aspect_ratio = sig.width / sig.height
    target_height = int(target_width / aspect_ratio)
    sig = sig.resize((target_width, target_height), Image.LANCZOS)
    
    # موقعیت چپ پایین (با فاصله ۵۰ پیکسل از لبهها)
    margin_x = 180
    margin_y = 35
    position = (margin_x, template.height - sig.height - margin_y)
    
    # چسباندن امضا روی قالب
    template.paste(sig, position, sig)
    
    preview_dir = os.path.join(settings.MEDIA_ROOT, 'preview')
    os.makedirs(preview_dir, exist_ok=True)
    preview_path = os.path.join(preview_dir, 'preview_signature.jpg')
    template.convert('RGB').save(preview_path, 'JPEG', quality=90)
    
    return os.path.join(settings.MEDIA_URL, 'preview', 'preview_signature.jpg')
