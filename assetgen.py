"""Tạo asset mặc định (nhân vật + nền) bằng Pillow, phong cách hoạt hình 2D phẳng.

Chạy riêng:  python assetgen.py   -> tạo bộ demo trong assets/
make_video.py tự gọi ensure_assets() cho nhân vật/nền còn thiếu.

Muốn chỉnh ngoại hình một nhân vật: tạo assets/cast.json, ví dụ
{"an": {"gender": "nam", "skin": "#f1c296", "hair": "#1e1e23",
        "shirt": "#4670aa", "pants": "#323c5a", "style": "short"}}
style nam: short | side | bald_top      style nữ: long | bun | bob
Muốn dùng hình tự vẽ: bỏ PNG vào assets/characters/<id>/neutral.png (và <emotion>.png,
<emotion>_talk.png) -> nhân vật đó sẽ không bị tạo tự động.
"""
import json
import math
import random
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

EMOTIONS = ["neutral", "happy", "sad", "angry", "scared", "surprised", "thinking"]
INK = (28, 28, 32, 255)
SK = 4            # siêu lấy mẫu để mịn nét
CW, CH = 400, 700  # toạ độ vẽ
OUT_SCALE = 2     # ảnh xuất 800x1400

SKINS = [(255, 224, 189), (241, 194, 150), (224, 172, 125), (198, 134, 96)]
HAIRS = [(30, 30, 35), (60, 40, 30), (90, 60, 40), (20, 20, 20), (120, 80, 50)]
SHIRTS = [(70, 110, 170), (110, 130, 70), (180, 70, 70), (200, 160, 60), (120, 80, 150), (60, 140, 140), (90, 90, 100)]
PANTS = [(50, 60, 90), (70, 60, 50), (40, 40, 45), (80, 90, 110)]
MOUTH = (120, 35, 40, 255)


def _rgba(c):
    return (*c[:3], 255)


def _hex(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def _is_fem(g):
    return str(g).strip().lower() in ("nữ", "nu", "female", "f", "girl", "woman")


def make_spec(cid, gender="", override=None):
    o = override or {}
    r = random.Random(cid)
    fem = _is_fem(o.get("gender", gender))
    sp = dict(
        fem=fem, skin=r.choice(SKINS), hair=r.choice(HAIRS), shirt=r.choice(SHIRTS), pants=r.choice(PANTS),
        style=r.choice(["long", "bun", "bob", "ponytail", "curly"] if fem else ["short", "side", "bald_top", "curly", "spiky"]),
        glasses=r.random() < 0.28,
        freckles=r.random() < 0.20,
        job=o.get("job", "none"),
        kind=o.get("kind", "human"),
        age=max(1, min(120, int(o.get("age", 25)))),
    )
    for k in ("skin", "hair", "shirt", "pants"):
        if k in o:
            sp[k] = _hex(o[k])
    if "style" in o:
        sp["style"] = o["style"]
    for k in ("glasses", "freckles"):
        if k in o:
            sp[k] = bool(o[k])
    return sp


# ------------------------------------------------------------------ nhân vật
class _C:
    def __init__(self):
        self.im = Image.new("RGBA", (CW * SK, CH * SK), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def _p(self, pts):
        return [(x * SK, y * SK) for x, y in pts]

    def rectangle(self, box, fill, w=0):
        x0, y0, x1, y1 = box
        self.d.rectangle([x0 * SK, y0 * SK, x1 * SK, y1 * SK], fill=fill,
                         outline=INK if w else None, width=int(w * SK))

    def ell(self, cx, cy, rx, ry, fill=None, w=0):
        self.d.ellipse([(cx - rx) * SK, (cy - ry) * SK, (cx + rx) * SK, (cy + ry) * SK],
                       fill=fill, outline=INK if w else None, width=int(w * SK))

    def poly(self, pts, fill, w=0):
        p = self._p(pts)
        self.d.polygon(p, fill=fill)
        if w:
            self.d.line(p + [p[0]], fill=INK, width=int(w * SK), joint="curve")

    def line(self, pts, w, fill=INK):
        p = self._p(pts)
        self.d.line(p, fill=fill, width=int(w * SK), joint="curve")
        r = w * SK / 2
        for x, y in (p[0], p[-1]):
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def limb(self, pts, w, fill):
        self.line(pts, w + 9, INK)
        self.line(pts, w, fill)

    def arc(self, box, a0, a1, w):
        x0, y0, x1, y1 = box
        self.d.arc([x0 * SK, y0 * SK, x1 * SK, y1 * SK], a0, a1, fill=INK, width=int(w * SK))

    def chord(self, box, a0, a1, fill, w):
        x0, y0, x1, y1 = box
        self.d.chord([x0 * SK, y0 * SK, x1 * SK, y1 * SK], a0, a1, fill=fill, outline=INK, width=int(w * SK))


def _mirror(pts):
    return [(400 - x, y) for x, y in pts]


def _arm_poses(emo):
    base = [(140, 300), (112, 390), (118, 470)]
    left, right, front_right = base, _mirror(base), False
    if emo == "happy":
        right = [(260, 300), (315, 290), (335, 215)]
    elif emo == "sad":
        left = [(140, 300), (125, 390), (150, 450)]
        right = _mirror(left)
    elif emo == "angry":
        left = [(140, 300), (92, 375), (140, 425)]
        right = _mirror(left)
    elif emo == "scared":
        left = [(140, 300), (100, 375), (150, 340)]
        right = _mirror(left)
    elif emo == "surprised":
        left = [(140, 300), (82, 325), (62, 255)]
        right = _mirror(left)
    elif emo == "thinking":
        right = [(260, 300), (305, 355), (238, 272)]
        front_right = True
    return left, right, front_right


def _draw_arm(c, pts, sp):
    c.limb(pts, 32, _rgba(sp["shirt"]))
    x, y = pts[-1]
    c.ell(x, y, 20, 20, _rgba(sp["skin"]), 5)


def _hair_front(c, sp):
    hair = _rgba(sp["hair"])
    arc = [(200 + 105 * math.cos(math.radians(a)), 175 + 100 * math.sin(math.radians(a))) for a in range(192, 349, 6)]
    fr = {
        "short": [(285, 120), (262, 128), (235, 110), (205, 128), (172, 112), (140, 128), (115, 118)],
        "side": [(290, 135), (255, 118), (215, 112), (170, 125), (140, 150), (112, 140)],
        "bald_top": [(272, 112), (238, 100), (200, 108), (165, 98), (130, 110)],
        "long": [(285, 125), (250, 115), (205, 132), (160, 115), (118, 125)],
        "bob": [(285, 125), (250, 115), (205, 132), (160, 115), (118, 125)],
        "bun": [(285, 125), (250, 115), (205, 132), (160, 115), (118, 125)],
        "ponytail": [(285, 125), (250, 115), (205, 132), (160, 115), (118, 125)],
        "curly": [(285, 128), (270, 95), (244, 112), (226, 80), (200, 112), (176, 78), (152, 110), (128, 92), (115, 128)],
        "spiky": [(285, 125), (265, 102), (244, 122), (225, 82), (203, 119), (180, 92), (160, 124), (138, 100), (115, 128)],
    }[sp["style"]]
    c.poly(arc + fr, hair, 6)


def _hair_back(c, sp):
    hair = _rgba(sp["hair"])
    st = sp["style"]
    if st == "long":
        c.poly([(88, 150), (312, 150), (325, 340), (75, 340)], hair, 6)
    elif st == "bob":
        c.poly([(92, 160), (308, 160), (302, 262), (98, 262)], hair, 6)
    elif st == "bun":
        c.ell(200, 68, 36, 32, hair, 6)
    elif st == "ponytail":
        c.poly([(286, 145), (320, 155), (350, 255), (318, 285), (300, 220)], hair, 6)
    elif st == "curly":
        for x, y, r in ((112, 145, 28), (140, 105, 30), (174, 88, 30), (210, 92, 31), (246, 103, 29), (278, 137, 30)):
            c.ell(x, y, r, r, hair, 5)


def _face(c, emo, talk, sp):
    fem = sp["fem"]
    L, R = (160, 180), (240, 180)
    white = (255, 255, 255, 255)
    # mắt
    if emo == "happy":
        for cx, cy in (L, R):
            c.arc((cx - 19, cy - 10, cx + 19, cy + 18), 200, 340, 6)
    else:
        r, pr, dx, dy = {
            "neutral": (19, 7, 0, 2), "sad": (18, 7, 0, 6), "angry": (18, 7, 0, 3),
            "scared": (25, 4, 0, 0), "surprised": (26, 5, 0, 0), "thinking": (19, 7, 8, -6),
        }[emo]
        if sp.get("age", 25) < 13:
            r += 3
            pr += 1
        for cx, cy in (L, R):
            c.ell(cx, cy, r, r, white, 4)
            c.ell(cx + dx, cy + dy, pr, pr, INK)
            c.ell(cx + dx - 2, cy + dy - 3, max(2, pr // 3), max(2, pr // 3), white)
    # lông mày
    brows = {
        "neutral": ([(133, 148), (185, 148)], [(215, 148), (267, 148)]),
        "happy": ([(135, 150), (185, 142)], [(215, 142), (265, 150)]),
        "sad": ([(133, 160), (185, 143)], [(215, 143), (267, 160)]),
        "angry": ([(130, 140), (188, 162)], [(212, 162), (270, 140)]),
        "scared": ([(133, 144), (185, 128)], [(215, 128), (267, 144)]),
        "surprised": ([(135, 132), (185, 132)], [(215, 132), (265, 132)]),
        "thinking": ([(133, 150), (185, 150)], [(215, 128), (267, 140)]),
    }[emo]
    for b in brows:
        c.line(b, 7)
    if sp.get("age", 25) >= 60:
        c.line([(142, 207), (176, 207)], 2, (125, 91, 75, 220))
        c.line([(224, 207), (258, 207)], 2, (125, 91, 75, 220))
        c.line([(165, 231), (181, 235)], 2, (125, 91, 75, 220))
        c.line([(219, 235), (235, 231)], 2, (125, 91, 75, 220))
    if sp.get("glasses"):
        for cx in (160, 240):
            c.d.ellipse([(cx - 25) * SK, 155 * SK, (cx + 25) * SK, 205 * SK], outline=INK, width=5 * SK)
        c.line([(185, 178), (215, 178)], 4)
    # mũi
    c.arc((190, 205, 210, 225), 20, 160, 4)
    # má / chi tiết cảm xúc
    if emo == "happy" or (fem and emo == "neutral"):
        c.ell(128, 226, 15, 8, (255, 140, 140, 150))
        c.ell(272, 226, 15, 8, (255, 140, 140, 150))
    if sp.get("freckles"):
        for x, y in ((135, 220), (148, 225), (260, 220), (273, 225)):
            c.ell(x, y, 3, 3, (145, 83, 64, 210))
    if emo == "angry":
        c.ell(128, 226, 15, 9, (235, 80, 70, 170))
        c.ell(272, 226, 15, 9, (235, 80, 70, 170))
        c.line([(285, 98), (308, 122)], 6, (220, 40, 40, 255))
        c.line([(308, 98), (285, 122)], 6, (220, 40, 40, 255))
    if emo == "scared":
        c.poly([(305, 112), (294, 138), (305, 150), (316, 138)], (150, 210, 255, 255), 3)
    if emo == "sad":
        c.ell(138, 214, 6, 10, (150, 210, 255, 255), 2)
    # miệng
    if talk:
        if emo == "happy":
            c.chord((168, 222, 232, 276), 0, 180, MOUTH, 5)
        elif emo == "surprised":
            c.ell(200, 256, 15, 22, MOUTH, 5)
        else:
            c.ell(200, 252, 19, 14, MOUTH, 5)
            c.ell(200, 260, 10, 5, (230, 110, 120, 255))
    else:
        if emo == "neutral":
            c.line([(180, 250), (220, 250)], 6)
        elif emo == "happy":
            c.arc((165, 215, 235, 265), 20, 160, 6)
        elif emo == "sad":
            c.arc((170, 248, 230, 288), 200, 340, 6)
        elif emo == "angry":
            c.arc((172, 250, 228, 280), 200, 340, 6)
        elif emo == "scared":
            c.line([(175, 252), (188, 244), (200, 254), (212, 244), (225, 252)], 5)
        elif emo == "surprised":
            c.ell(200, 254, 13, 17, MOUTH, 5)
        elif emo == "thinking":
            c.line([(185, 252), (222, 246)], 6)


def _profession_details(c, job):
    """Small, readable uniform details that distinguish common story roles."""
    white = (250, 249, 241, 255)
    navy = (35, 58, 90, 255)
    red = (190, 55, 50, 255)
    gold = (238, 190, 65, 255)
    if job == "doctor":
        c.poly([(145, 285), (175, 285), (192, 440), (145, 440)], white, 4)
        c.poly([(255, 285), (225, 285), (208, 440), (255, 440)], white, 4)
        c.line([(200, 300), (200, 350), (218, 370), (218, 402)], 5, navy)
        c.ell(218, 407, 7, 7, navy, 3)
        c.line([(150, 335), (170, 335)], 4, red)
        c.line([(160, 325), (160, 345)], 4, red)
    elif job == "chef":
        c.poly([(160, 320), (240, 320), (254, 440), (146, 440)], white, 4)
        for y in (345, 375, 405):
            c.ell(200, y, 4, 4, navy)
    elif job == "police":
        c.poly([(150, 295), (175, 295), (185, 330), (155, 330)], navy, 3)
        c.poly([(250, 295), (225, 295), (215, 330), (245, 330)], navy, 3)
        c.ell(232, 350, 13, 15, gold, 3)
        c.line([(232, 341), (232, 359)], 3, navy)
    elif job == "artist":
        c.poly([(165, 305), (235, 305), (251, 440), (149, 440)], (190, 125, 85, 255), 4)
        c.ell(180, 350, 6, 6, red)
        c.ell(195, 360, 6, 6, gold)
        c.ell(211, 348, 6, 6, (65, 135, 90, 255))
    elif job == "office":
        c.poly([(145, 285), (175, 285), (195, 440), (145, 440)], navy, 4)
        c.poly([(255, 285), (225, 285), (205, 440), (255, 440)], navy, 4)
        c.poly([(188, 300), (212, 300), (207, 365), (200, 385), (193, 365)], red, 3)
    elif job == "teacher":
        c.poly([(160, 310), (240, 310), (250, 430), (150, 430)], (75, 115, 85, 255), 4)
        c.rectangle((175, 360, 225, 405), (236, 218, 165, 255), 3)
        c.line([(200, 362), (200, 402)], 2, navy)
    elif job == "engineer":
        c.poly([(150, 300), (175, 300), (190, 440), (150, 440)], (230, 125, 45, 255), 4)
        c.poly([(250, 300), (225, 300), (210, 440), (250, 440)], (230, 125, 45, 255), 4)
        c.line([(164, 330), (180, 418)], 7, gold)
        c.line([(236, 330), (220, 418)], 7, gold)
    elif job == "daoist":
        robe = (205, 174, 92, 255)
        c.poly([(145, 285), (185, 285), (202, 440), (130, 465)], robe, 5)
        c.poly([(255, 285), (215, 285), (198, 440), (270, 465)], robe, 5)
        c.line([(160, 340), (240, 340)], 8, red)
        c.rectangle((216, 350, 239, 397), (247, 224, 145, 255), 3)
        c.line([(221, 360), (234, 369), (222, 380), (234, 389)], 2, red)


def _finish_sprite(c):
    out = c.im.resize((CW * OUT_SCALE, CH * OUT_SCALE), Image.LANCZOS)
    alpha = out.getchannel("A")
    glow_mask = alpha.filter(ImageFilter.GaussianBlur(28)).point(lambda value: int(value * 0.16))
    glow = Image.new("RGBA", out.size, (255, 210, 148, 0))
    glow.putalpha(glow_mask)
    glow.alpha_composite(out)
    return glow


def draw_creature(sp, emo="neutral", talk=False):
    c = _C()
    kind = sp.get("kind", "dog")
    fur = _rgba(sp.get("hair", "#8a6547"))
    light = _rgba(sp.get("skin", "#e5c99f"))
    dark = INK
    if kind == "ghost":
        ghost_tint = sp.get("skin", "#f4f3ed")
        ghost_rgb = _hex(ghost_tint) if isinstance(ghost_tint, str) else tuple(ghost_tint[:3])
        cloth = (*ghost_rgb, 225)
        c.ell(200, 230, 105, 110, cloth, 6)
        c.poly([(98, 230), (302, 230), (292, 500), (260, 472), (225, 510), (190, 477), (153, 507), (112, 474)], cloth, 6)
        c.ell(163, 225, 13, 20, dark)
        c.ell(237, 225, 13, 20, dark)
        if talk or emo == "surprised":
            c.ell(200, 278, 16, 21, dark)
        else:
            c.arc((177, 260, 223, 294), 10, 170, 5)
        c.ell(135, 270, 13, 8, (180, 195, 235, 170))
        c.ell(265, 270, 13, 8, (180, 195, 235, 170))
    else:
        # Four-legged body and paws give animals a clearly different silhouette.
        for x in (145, 255):
            c.limb([(x, 420), (x - 8, 555), (x, 610)], 29, fur)
            c.ell(x, 610, 27, 18, fur, 4)
        c.ell(200, 420, 105, 130, fur, 6)
        if kind == "crocodile":
            c.poly([(280, 400), (365, 430), (385, 420), (365, 455), (280, 448)], fur, 5)
            c.ell(205, 260, 105, 80, fur, 6)
            c.ell(275, 295, 115, 42, fur, 5)
            if talk:
                c.ell(275, 307, 80, 20, dark)
            c.ell(366, 289, 13, 9, dark)
            for x in range(205, 333, 20):
                c.poly([(x, 314), (x + 8, 331), (x + 16, 314)], (250, 245, 220, 255), 2)
                c.poly([(x, 278), (x + 8, 261), (x + 16, 278)], (250, 245, 220, 255), 2)
            for x in range(155, 250, 24):
                c.poly([(x, 332), (x + 12, 304), (x + 24, 332)], _mul(fur[:3], 0.82) + (255,), 2)
            c.ell(150, 215, 26, 24, fur, 5)
            c.ell(248, 215, 26, 24, fur, 5)
            c.ell(150, 213, 8, 11, dark)
            c.ell(248, 213, 8, 11, dark)
        else:
            c.ell(200, 255, 88, 87, fur, 6)
            if kind == "cat":
                c.poly([(130, 207), (132, 115), (190, 180)], fur, 6)
                c.poly([(210, 180), (268, 115), (270, 207)], fur, 6)
                c.poly([(145, 190), (141, 142), (174, 181)], _rgba(sp.get("shirt", "#d99aaa")), 2)
                c.poly([(226, 181), (259, 142), (255, 190)], _rgba(sp.get("shirt", "#d99aaa")), 2)
                c.poly([(105, 440), (44, 420), (20, 370), (35, 450), (95, 470)], fur, 5)
            else:
                c.ell(128, 199, 35, 55, fur, 5)
                c.ell(272, 199, 35, 55, fur, 5)
                c.ell(200, 286, 57, 42, light, 4)
                c.ell(200, 268, 13, 10, dark)
                c.arc((170, 277, 200, 305), 5, 90, 3)
                c.arc((200, 277, 230, 305), 90, 175, 3)
            c.ell(168, 245, 10, 15, dark)
            c.ell(232, 245, 10, 15, dark)
            if kind == "cat":
                c.poly([(189, 271), (211, 271), (200, 285)], _rgba(sp.get("shirt", "#d99aaa")))
                if talk:
                    c.ell(200, 296, 9, 12, dark)
                else:
                    c.arc((186, 282, 214, 302), 5, 175, 3)
                for y in (276, 289):
                    c.line([(150, y), (95, y - 9)], 3, dark)
                    c.line([(250, y), (305, y - 9)], 3, dark)
            elif talk:
                c.ell(200, 296, 10, 13, dark)
    return _finish_sprite(c)


def draw_character(sp, emo="neutral", talk=False):
    if sp.get("kind", "human") != "human":
        return draw_creature(sp, emo, talk)
    c = _C()
    gold = (238, 190, 65, 255)
    skin, shirt, pants = _rgba(sp["skin"]), _rgba(sp["shirt"]), _rgba(sp["pants"])
    _hair_back(c, sp)
    # chân
    if sp["fem"]:
        c.limb([(172, 540), (168, 640)], 24, skin)
        c.limb([(228, 540), (232, 640)], 24, skin)
    else:
        c.limb([(172, 470), (168, 640)], 44, pants)
        c.limb([(228, 470), (232, 640)], 44, pants)
        c.poly([(128, 470), (272, 470), (268, 505), (132, 505)], pants, 6)
    c.ell(158, 656, 36, 16, INK)
    c.ell(242, 656, 36, 16, INK)
    # thân
    if sp["fem"]:
        c.poly([(138, 430), (262, 430), (300, 575), (100, 575)], pants, 6)
        c.poly([(145, 280), (255, 280), (262, 445), (138, 445)], shirt, 6)
    else:
        c.poly([(138, 280), (262, 280), (272, 482), (128, 482)], shirt, 6)
    _profession_details(c, sp.get("job", "none"))
    # tay
    left, right, front_right = _arm_poses(emo)
    _draw_arm(c, left, sp)
    if not front_right:
        _draw_arm(c, right, sp)
    # cổ, tai, đầu
    c.poly([(182, 250), (218, 250), (218, 290), (182, 290)], skin)
    c.ell(97, 185, 14, 22, skin, 5)
    c.ell(303, 185, 14, 22, skin, 5)
    c.ell(200, 175, 105, 100, skin, 7)
    _face(c, emo, talk, sp)
    _hair_front(c, sp)
    if sp.get("job") == "chef":
        c.ell(200, 94, 55, 30, (250, 249, 241, 255), 5)
        c.d.rectangle([150 * SK, 93 * SK, 250 * SK, 119 * SK], fill=(250, 249, 241, 255), outline=INK, width=5 * SK)
    elif sp.get("job") == "farmer":
        c.d.ellipse([95 * SK, 100 * SK, 305 * SK, 130 * SK], fill=(190, 145, 60, 255), outline=INK, width=5 * SK)
        c.d.rectangle([150 * SK, 77 * SK, 250 * SK, 112 * SK], fill=(190, 145, 60, 255), outline=INK, width=5 * SK)
    elif sp.get("job") == "engineer":
        c.d.arc([120 * SK, 63 * SK, 280 * SK, 157 * SK], 180, 360, fill=gold, width=10 * SK)
        c.line([(120, 109), (280, 109)], 8, gold)
    elif sp.get("job") == "daoist":
        c.d.rectangle([164 * SK, 58 * SK, 236 * SK, 89 * SK], fill=(35, 45, 58, 255), outline=INK, width=5 * SK)
        c.d.rectangle([178 * SK, 42 * SK, 222 * SK, 63 * SK], fill=(35, 45, 58, 255), outline=INK, width=5 * SK)
    if front_right:
        _draw_arm(c, right, sp)
    return _finish_sprite(c)


def generate_character_set(cid, gender, folder, override=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    sp = make_spec(cid, gender, override)
    for emo in EMOTIONS:
        draw_character(sp, emo, False).save(folder / f"{emo}.png")
        draw_character(sp, emo, True).save(folder / f"{emo}_talk.png")


# ------------------------------------------------------------------ nền
BW, BH = 1280, 720
WALLS = [(226, 214, 190), (200, 220, 214), (232, 206, 200), (210, 214, 232), (214, 200, 172)]
BCOL = [(190, 170, 160), (160, 175, 190), (200, 190, 150), (170, 150, 150), (150, 170, 160)]


def _mul(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _tokens(bid):
    value = str(bid).lower()
    # Recover text accidentally decoded as Windows-1252 before keyword matching.
    try:
        repaired = value.encode("cp1252").decode("utf-8")
        marker_a, marker_b = chr(195), chr(196)
        if repaired.count(marker_a) + repaired.count(marker_b) < value.count(marker_a) + value.count(marker_b):
            value = repaired
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    value = value.replace(chr(273), "d").replace(chr(272), "d")
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    for ch in ".,;:!?/\\-|()[]{}":
        text = text.replace(ch, " ")
    return set(text.split())


def _indoor(d, r, tk):
    wall = r.choice(WALLS)
    floor = _mul(wall, 0.62)
    hz = 500
    for y in range(hz):
        d.line([(0, y), (BW, y)], fill=_lerp(_mul(wall, 1.12), wall, y / hz))
    for y in range(hz, BH):
        d.line([(0, y), (BW, y)], fill=_lerp(floor, _mul(floor, 0.82), (y - hz) / (BH - hz)))
    d.rectangle([0, hz - 14, BW, hz], fill=_mul(wall, 0.8))
    for x in range(-400, BW + 400, 160):
        d.line([(x, hz), ((x - 640) * 1.7 + 640, BH)], fill=_mul(floor, 0.85), width=2)
    special = None
    if tk & {"bep", "kitchen"}:
        special = "kitchen"
    elif tk & {"ngu", "bedroom"}:
        special = "bed"
    elif tk & {"lop", "hoc", "truong", "classroom"}:
        special = "class"
    door_left = r.random() < 0.5
    wx = 880 if door_left else 120
    d.rectangle([wx, 150, wx + 260, 380], fill=(170, 210, 240), outline=(250, 250, 250), width=10)
    d.line([(wx + 130, 150), (wx + 130, 380)], fill=(250, 250, 250), width=8)
    d.line([(wx, 265), (wx + 260, 265)], fill=(250, 250, 250), width=8)
    curtain = r.choice([(154, 91, 99), (67, 105, 111), (174, 130, 82)])
    d.polygon([(wx - 25, 130), (wx + 35, 145), (wx + 28, 395), (wx - 18, 380)], fill=curtain)
    d.polygon([(wx + 285, 130), (wx + 225, 145), (wx + 232, 395), (wx + 278, 380)], fill=curtain)
    d.line([(wx + 8, 150), (wx + 10, 360)], fill=_mul(curtain, 0.78), width=7)
    d.line([(wx + 252, 150), (wx + 250, 360)], fill=_mul(curtain, 0.78), width=7)
    if special == "kitchen":
        d.rectangle([0, 400, BW, hz], fill=(235, 235, 235))
        d.rectangle([0, 392, BW, 410], fill=(120, 100, 85))
        d.rectangle([420, 60, 820, 210], fill=(190, 150, 110), outline=(120, 90, 60), width=6)
    elif special == "bed":
        d.rectangle([640, 380, 1160, hz + 10], fill=(110, 140, 190), outline=(60, 80, 120), width=6)
        d.rectangle([660, 340, 800, 400], fill=(250, 250, 250), outline=(180, 180, 180), width=4)
    elif special == "class":
        d.rectangle([380, 90, 900, 330], fill=(40, 80, 60), outline=(130, 95, 60), width=12)
    else:
        dx = 300 if door_left else 760
        d.rectangle([dx, 120, dx + 200, hz], fill=(140, 100, 70), outline=(90, 60, 40), width=10)
        d.rectangle([dx + 25, 150, dx + 175, 290], outline=(100, 70, 45), width=5)
        d.rectangle([dx + 25, 320, dx + 175, 470], outline=(100, 70, 45), width=5)
        d.ellipse([dx + 160, 310, dx + 182, 332], fill=(230, 200, 90))
        px = 640 if door_left else 500
        d.rectangle([px, 150, px + 130, 250], fill=(235, 225, 200), outline=(110, 80, 50), width=8)
        d.polygon([(px + 15, 235), (px + 55, 185), (px + 85, 215), (px + 105, 195), (px + 118, 235)], fill=(120, 160, 110))
    # Background furniture and set dressing, kept low so characters remain the focus.
    upholstery = r.choice([(72, 111, 117), (143, 91, 88), (130, 111, 80)])
    d.ellipse([290, 434, 990, 515], fill=_mul(floor, 0.72))
    d.rounded_rectangle([350, 366, 930, 482], radius=28, fill=upholstery)
    d.rounded_rectangle([380, 338, 900, 430], radius=24, fill=_mul(upholstery, 1.12))
    d.rounded_rectangle([330, 392, 410, 485], radius=24, fill=_mul(upholstery, 0.88))
    d.rounded_rectangle([870, 392, 950, 485], radius=24, fill=_mul(upholstery, 0.88))
    d.line([(640, 350), (640, 430)], fill=_mul(upholstery, 0.76), width=5)
    d.line([(350, 474), (930, 474)], fill=_mul(upholstery, 0.72), width=8)
    if special != "kitchen":
        d.rectangle([1035, 316, 1055, 465], fill=(102, 76, 55))
        d.ellipse([982, 260, 1112, 352], fill=(68, 125, 83))
        d.ellipse([1010, 230, 1080, 315], fill=(81, 143, 91))
        d.ellipse([1008, 448, 1084, 488], fill=(181, 114, 78), outline=(90, 62, 48), width=5)


def _outdoor(d, r, tk):
    hz = 440
    top, bot = (103, 151, 193), (211, 224, 223)
    for y in range(hz):
        d.line([(0, y), (BW, y)], fill=_lerp(top, bot, y / hz))
    sx = r.randint(900, 1150)
    d.ellipse([sx, 50, sx + 90, 140], fill=(250, 224, 161))
    for _ in range(3):
        cx, cy = r.randint(80, 1100), r.randint(60, 200)
        for k in range(3):
            d.ellipse([cx + k * 50, cy - (k % 2) * 14, cx + k * 50 + 110, cy + 44 - (k % 2) * 14], fill=(238, 239, 231))

    rural = bool(tk & {"que", "nong", "lang", "rural", "countryside", "village", "ruong", "lua"})
    city = not rural and bool(tk & {"thanh", "pho", "city", "downtown", "skyscraper", "street", "road", "duong"})
    if rural:
        # Open countryside horizon, rice fields and low village huts; no urban skyline.
        d.polygon([(0, 350), (230, 250), (420, 355), (700, 235), (930, 350), (1280, 245), (1280, 500), (0, 500)], fill=(108, 139, 119))
        d.rectangle([0, 420, BW, BH], fill=(116, 157, 91))
        d.polygon([(0, 555), (BW, 495), (BW, BH), (0, BH)], fill=(139, 170, 91))
        for x in range(-80, BW + 80, 95):
            d.line([(x, 495), (x + 120, BH)], fill=(170, 186, 112), width=3)
        # Small thatched-roof homes sit well behind the riverbank/dock.
        for x, scale in ((100, 1.0), (1000, .82)):
            y = 335
            w, h = int(155 * scale), int(95 * scale)
            d.rectangle([x, y, x+w, y+h], fill=(191, 161, 115), outline=(102, 82, 61), width=4)
            d.polygon([(x-15, y+8), (x+w//2, y-int(65*scale)), (x+w+18, y+8)], fill=(111, 78, 53))
            d.rectangle([x+int(w*.41), y+int(h*.46), x+int(w*.61), y+h], fill=(93, 66, 48))
        for x, y, rad in ((330, 340, 58), (850, 320, 72), (1170, 350, 62)):
            d.rectangle([x-8, y+35, x+8, 475], fill=(93, 77, 53))
            d.ellipse([x-rad, y-rad, x+rad, y+rad], fill=(59, 111, 73))
            d.ellipse([x-rad*.65, y-rad*1.25, x+rad*.65, y+rad*.25], fill=(72, 127, 79))
    elif city:
        x = -20
        while x < BW:
            w, h = r.randint(130, 220), r.randint(150, 320)
            col = r.choice(BCOL)
            d.rectangle([x, hz-h, x+w, hz], fill=col)
            for wy in range(hz-h+20, hz-25, 46):
                for wx in range(x+15, x+w-20, 40):
                    d.rectangle([wx, wy, wx+19, wy+25], fill=(211, 181, 125))
            x += w + 12
        d.rectangle([0, hz, BW, BH], fill=(83, 83, 90))
        d.rectangle([0, hz, BW, hz+35], fill=(169, 165, 153))
        for x in range(0, BW, 210):
            d.rectangle([x, 610, x+112, 622], fill=(227, 216, 183))
    else:
        # Generic rural park/riverbank: trees and open grass, no row of houses.
        d.polygon([(0, 390), (210, 300), (440, 390), (710, 290), (1000, 390), (1280, 320), (1280, 500), (0, 500)], fill=(112, 145, 120))
        d.rectangle([0, hz, BW, BH], fill=(104, 150, 90))
        for x in (140, 370, 940, 1150):
            d.rectangle([x-10, 300, x+10, 480], fill=(105, 77, 53))
            d.ellipse([x-75, 205, x+75, 365], fill=(62, 121, 76))

    if tk & {"duong", "pho", "street", "road", "duong"} and not rural:
        d.rectangle([0, 560, BW, BH], fill=(72, 75, 82))
        d.polygon([(560, 560), (720, 560), (1080, BH), (160, BH)], fill=(92, 93, 98))
        for y in range(590, BH, 62):
            d.polygon([(620, y), (660, y), (690, y+24), (605, y+24)], fill=(224, 205, 155))


def _forest(d, r, tk):
    hz = 470
    for y in range(hz):
        d.line([(0, y), (BW, y)], fill=_lerp((150, 200, 230), (220, 238, 225), y / hz))
    d.rectangle([0, hz, BW, BH], fill=(80, 140, 80))
    d.rectangle([0, 620, BW, BH], fill=(70, 125, 70))
    trees = sorted([(r.randint(-40, BW + 40), r.randint(160, 300)) for _ in range(16)], key=lambda t: t[1])
    for tx, size in trees:
        base = hz + size // 6
        g = _lerp((40, 110, 60), (30, 85, 50), size / 300)
        d.rectangle([tx - size // 12, base - size // 3, tx + size // 12, base], fill=(100, 70, 50))
        for k in range(3):
            top = base - size - k * 0 - (2 - k) * 0
            w = size * (0.55 - k * 0.12)
            y0 = base - size // 3 - k * size // 3.2
            d.polygon([(tx, y0 - size // 2.2), (tx - w, y0), (tx + w, y0)], fill=g)


def generate_background(bid, path, description="", variant_seed=None):
    tk = _tokens(str(bid) + " " + str(description))
    r = random.Random(variant_seed if variant_seed is not None else bid)
    im = Image.new("RGB", (BW, BH))
    d = ImageDraw.Draw(im)
    if tk & {"rung", "forest", "nui", "doi"}:
        _forest(d, r, tk)
    elif tk & {"duong", "pho", "san", "vuon", "ngoai", "cho", "street", "park", "garden", "road", "bai", "song", "bien", "truoc", "cau", "bridge", "ben", "do", "pier", "wharf", "ferry", "boat", "city", "thanh", "downtown", "skyscraper"}:
        _outdoor(d, r, tk)
    else:
        _indoor(d, r, tk)
    if tk & {"cau", "bridge"}:
        # A broad stone bridge and river make the requested landmark visible at video scale.
        d = ImageDraw.Draw(im)
        d.rectangle([0, 515, BW, BH], fill=(48, 99, 113))
        d.polygon([(0, 485), (BW, 465), (BW, 585), (0, 575)], fill=(107, 104, 97))
        d.polygon([(0, 470), (BW, 450), (BW, 488), (0, 508)], fill=(190, 173, 145))
        for cx in (250, 640, 1030):
            d.ellipse([cx-112, 470, cx+112, 650], fill=(42, 82, 97))
            d.rectangle([cx-116, 470, cx+116, 540], fill=(107, 104, 97))
        for y in range(590, BH, 35):
            d.line([(0, y), (BW, y-18)], fill=(111, 158, 165), width=3)
    if tk & {"ben", "do", "pier", "wharf", "ferry", "boat"}:
        d = ImageDraw.Draw(im)
        d.rectangle([0, 520, BW, BH], fill=(39, 91, 111))
        d.polygon([(570, 438), (710, 438), (875, BH), (435, BH)], fill=(105, 70, 48))
        for x in (585, 630, 675, 710):
            d.line([(x, 445), (x-65, BH)], fill=(67, 47, 39), width=12)
        d.polygon([(80, 580), (260, 580), (330, 640), (20, 640)], fill=(118, 67, 46))
        d.polygon([(20, 580), (160, 520), (300, 580)], fill=(180, 145, 109))
    if tk & {"thanh", "city", "downtown", "skyscraper"}:
        d = ImageDraw.Draw(im)
        for x, top, width in ((60, 125, 150), (250, 55, 180), (465, 155, 145), (760, 35, 190), (990, 115, 180)):
            d.rectangle([x, top, x+width, 442], fill=(53, 65, 82), outline=(91, 105, 118), width=5)
            for wy in range(top+22, 420, 45):
                for wx in range(x+18, x+width-12, 35):
                    d.rectangle([wx, wy, wx+15, wy+22], fill=(218, 177, 112) if (wx+wy) % 3 else (91, 129, 151))
    if tk & {"dem", "night", "khuya", "toi"}:
        im = Image.blend(im, Image.new("RGB", im.size, (18, 28, 58)), 0.36)
        glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse((740, 220, 1120, 600), fill=(255, 174, 88, 80))
        im = Image.alpha_composite(im.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(70))).convert("RGB")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    im.save(path)


# ------------------------------------------------------------------ tự động bổ sung
def ensure_assets(assets, bible, scenes):
    assets = Path(assets)
    cast_path = assets / "cast.json"
    cast = json.loads(cast_path.read_text(encoding="utf-8")) if cast_path.exists() else {}
    genders = {c["id"]: c.get("gender", "") for c in (bible or {}).get("characters", [])}
    chars = {c for s in scenes for c in s.get("characters", [])}
    chars |= {s["speaker"] for s in scenes if s["speaker"] != "narrator"}
    for c in sorted(chars):
        folder = assets / "characters" / c
        if not (folder / "neutral.png").exists():
            print(f"  [asset] tạo nhân vật: {c}")
            generate_character_set(c, genders.get(c, ""), folder, cast.get(c))
    for bg in sorted({s["background"] for s in scenes}):
        p = assets / "backgrounds" / f"{bg}.png"
        if not p.exists():
            print(f"  [asset] tạo nền: {bg}")
            generate_background(bg, p)


if __name__ == "__main__":
    here = Path(__file__).parent / "assets"
    demo_chars = [("an", "nam"), ("binh", "nam"), ("lan", "nữ")]
    for cid, g in demo_chars:
        generate_character_set(cid, g, here / "characters" / cid)
    for b in ("phong_khach", "duong_pho", "phong_ngu_dem", "rung"):
        generate_background(b, here / "backgrounds" / f"{b}.png")
    print("Đã tạo asset demo trong", here)
