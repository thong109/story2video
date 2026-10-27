"""Font choices shared by subtitle preview and video export."""
from pathlib import Path
from PIL import ImageFont

ROOT = Path(__file__).resolve().parent
FONTS = {
    'arial_italic': ('Arial đậm nghiêng', 'arialbi.ttf'),
    'arial': ('Arial', 'arial.ttf'),
    'arial_bold': ('Arial đậm', 'arialbd.ttf'),
    'segoe': ('Segoe UI', 'segoeui.ttf'),
    'tahoma': ('Tahoma', 'tahoma.ttf'),
    'times': ('Times New Roman', 'times.ttf'),
}


def font_options():
    options = [dict(id=key, name=value[0]) for key, value in FONTS.items()
               if (Path('C:/Windows/Fonts') / value[1]).is_file()]
    options.append(dict(id='project', name='Font của dự án'))
    return options


def validate(value):
    if not isinstance(value, dict):
        raise ValueError('Thiết lập phụ đề không hợp lệ.')
    font = value.get('font', 'arial_italic')
    size = value.get('size', 36)
    if font not in {item['id'] for item in font_options()}:
        raise ValueError('Font chữ không có trên máy.')
    if isinstance(size, bool) or not isinstance(size, int) or not 16 <= size <= 96:
        raise ValueError('Cỡ chữ phải là số nguyên từ 16 đến 96 px.')
    return dict(font=font, size=size)


def load_font(settings, config):
    value = validate(settings)
    path = ROOT / config.get('font', 'assets/font.ttf') if value['font'] == 'project' else Path('C:/Windows/Fonts') / FONTS[value['font']][1]
    return ImageFont.truetype(str(path), value['size'])
