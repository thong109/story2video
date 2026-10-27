"""storyboard.json -> video.mp4  (TTS + nhép miệng + phụ đề + ghép cảnh)

Dùng:  python make_video.py [storyboard.json]
Cần:   pip install edge-tts pillow numpy   và đã cài ffmpeg
"""
import asyncio
import hashlib
import json
import subprocess
import sys
import wave
from functools import lru_cache
from pathlib import Path

import edge_tts
import numpy as np
from assetgen import ensure_assets
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
W, H = CFG["size"]
FPS = CFG["fps"]
PAD = CFG.get("pad_seconds", 0.3)  # khoảng lặng cuối mỗi cảnh
A = ROOT / "assets"
OUT = ROOT / "build"
OUT.mkdir(exist_ok=True)
FONT = ImageFont.truetype(str(ROOT / CFG["font"]), CFG.get("font_size", 40))
def _caption_font(size, *candidates):
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.truetype(str(ROOT / CFG["font"]), size)


CAPTION_FONT = _caption_font(36, Path(r"C:\Windows\Fonts\arialbi.ttf"), Path(r"C:\Windows\Fonts\segoeuii.ttf"))
LABEL_FONT = _caption_font(18, Path(r"C:\Windows\Fonts\arialbd.ttf"), Path(r"C:\Windows\Fonts\segoeuib.ttf"))
CAST = json.loads((A / "cast.json").read_text(encoding="utf-8")) if (A / "cast.json").exists() else {}


# ---------- ảnh ----------
@lru_cache(maxsize=None)
def background(bg_id):
    p = A / "backgrounds" / f"{bg_id}.png"
    if not p.exists():
        p = A / "backgrounds" / "default.png"
    if not p.exists():
        return Image.new("RGBA", (W, H), (200, 200, 200, 255))
    im = Image.open(p).convert("RGBA")
    s = max(W / im.width, H / im.height)  # cover
    im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    l, t = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((l, t, l + W, t + H)).convert("RGB")
    # Subtle warm center light and dark edges add depth to the flat generated sets.
    px = np.asarray(im, dtype=np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    nx = (xx - W * 0.48) / (W * 0.82)
    ny = (yy - H * 0.40) / (H * 0.95)
    radius = np.sqrt(nx * nx + ny * ny)
    glow = np.clip(1.0 - np.sqrt(((xx - W * 0.48) / (W * 0.7)) ** 2 + ((yy - H * 0.28) / (H * 0.8)) ** 2), 0, 1)
    vignette = np.clip((radius - 0.42) * 0.15, 0, 0.13)
    px[:, :, 0] = np.clip(px[:, :, 0] * (1 - vignette) + glow * 7, 0, 255)
    px[:, :, 1] = np.clip(px[:, :, 1] * (1 - vignette) + glow * 4, 0, 255)
    px[:, :, 2] = np.clip(px[:, :, 2] * (1 - vignette) + glow * 2, 0, 255)
    return Image.fromarray(px.astype(np.uint8), "RGB").convert("RGBA")


@lru_cache(maxsize=None)
def sprite(char, emotion, talk):
    base = A / "characters" / char
    names = ([f"{emotion}_talk"] if talk else []) + [emotion, "neutral"]
    for n in names:
        p = base / f"{n}.png"
        if p.exists():
            im = Image.open(p).convert("RGBA")
            h = int(H * CFG.get("char_height", 0.6))
            return im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
    sys.exit(f"Thiếu sprite: {base}/neutral.png")


def draw_subtitle(im, text, speaker="narrator"):
    d = ImageDraw.Draw(im)
    display_text = str(text).strip()
    if speaker != "narrator" and not (display_text.startswith(("“", '"', "‘")) and display_text.endswith(("”", '"', "’"))):
        display_text = f"“{display_text}”"
    lines, cur = [], ""
    for w in display_text.split():
        t = (cur + " " + w).strip()
        if CAPTION_FONT.getlength(t) <= W * 0.90:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    lh = int(CAPTION_FONT.size * 1.20)
    label = CAST.get(speaker, {}).get("name", speaker.replace("_", " ").title()) if speaker != "narrator" else "NGƯỜI KỂ"
    panel_h = 28 + 22 + lh * len(lines) + 18
    y0 = H - panel_h
    # A restrained lower gradient keeps captions readable without a large opaque card.
    shade = Image.new("RGBA", (W, panel_h), (7, 14, 24, 0))
    pixels = shade.load()
    for y in range(panel_h):
        alpha = int(210 * (y / max(1, panel_h - 1)) ** 1.7)
        for x in range(W):
            pixels[x, y] = (7, 14, 24, alpha)
    im.alpha_composite(shade, (0, y0))
    d = ImageDraw.Draw(im)
    label_y = y0 + 15
    d.text(((W - LABEL_FONT.getlength(label.upper())) / 2, label_y), label.upper(),
           font=LABEL_FONT, fill=(255, 211, 112, 255), stroke_width=1, stroke_fill=(20, 18, 13, 220))
    y = label_y + 25
    for ln in lines:
        x = (W - CAPTION_FONT.getlength(ln)) / 2
        d.text((x + 2, y + 3), ln, font=CAPTION_FONT, fill=(0, 0, 0, 220), stroke_width=3, stroke_fill=(0, 0, 0, 190))
        d.text((x, y), ln, font=CAPTION_FONT, fill=(255, 246, 221, 255), stroke_width=2, stroke_fill=(18, 20, 24, 245))
        y += lh


def camera_frame(raw, frame_index, frame_count, scene_index):
    """A restrained animated push-in prevents otherwise static talking-head shots."""
    progress = frame_index / max(1, frame_count - 1)
    scale = 1.0 + 0.022 * progress
    im = Image.frombytes("RGB", (W, H), raw)
    nw, nh = int(W * scale), int(H * scale)
    im = im.resize((nw, nh), Image.Resampling.BICUBIC)
    pan = int((nw - W) * 0.30 * progress) * (-1 if scene_index % 2 else 1)
    left = max(0, min(nw - W, (nw - W) // 2 + pan))
    top = (nh - H) // 2
    return im.crop((left, top, left + W, top + H)).tobytes()


def compose(s, talking):
    im = background(s["background"]).copy()
    sp = s["speaker"]
    chars = list(s.get("characters") or [])
    if sp != "narrator" and sp not in chars:
        chars.append(sp)
    n = len(chars)
    for i, c in enumerate(chars):
        is_sp = c == sp
        spr = sprite(c, s["emotion"] if is_sp else "neutral", talking and is_sp)
        cx = int(W * (i + 1) / (n + 1))
        base_y = int(H * 0.86) - spr.height
        shadow = Image.new("RGBA", (spr.width, 38), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).ellipse((spr.width * 0.2, 5, spr.width * 0.8, 30), fill=(15, 22, 24, 95))
        shadow = shadow.filter(ImageFilter.GaussianBlur(10))
        im.alpha_composite(shadow, (cx - spr.width // 2, int(H * 0.86) - 18))
        im.alpha_composite(spr, (cx - spr.width // 2, base_y))
    draw_subtitle(im, s["text"], sp)
    return im.convert("RGB").tobytes()


# ---------- âm thanh ----------
async def _tts(text, voice, path):
    await edge_tts.Communicate(text, voice, rate=CFG.get("rate", "+0%")).save(str(path))


def ffmpeg(*args):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr)


def mouth_track(wav_path):
    """Trả về mảng bool theo từng frame: True = miệng mở (khi đang nói)."""
    with wave.open(str(wav_path)) as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    spf = max(1, sr // FPS)
    n = max(1, len(data) // spf)
    env = np.array([np.sqrt(np.mean(data[k * spf:(k + 1) * spf] ** 2)) for k in range(n)])
    talk = env > 0.2 * env.max() if env.max() > 0 else np.zeros(n, bool)
    return talk & (np.arange(n) % 2 == 0)  # nháy miệng khi có tiếng


# ---------- render 1 cảnh ----------
def render_scene(i, s):
    voices = CFG["voices"]
    voice = voices.get(s["speaker"], voices["default"])
    key = hashlib.md5((json.dumps(s, sort_keys=True, ensure_ascii=False) + voice).encode()).hexdigest()[:8]
    out = OUT / f"{i:04d}_{key}.mp4"
    if out.exists():
        return out

    mp3, wav = OUT / f"{i:04d}.mp3", OUT / f"{i:04d}.wav"
    asyncio.run(_tts(s["text"], voice, mp3))
    ffmpeg("-i", str(mp3), "-ac", "1", "-ar", "16000", str(wav))
    mouth = mouth_track(wav)

    closed, opened = compose(s, False), compose(s, True)
    tmp = out.with_name(out.stem + ".tmp.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(mp3), "-af", f"apad=pad_dur={PAD}",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100", "-ac", "2",
           "-shortest", str(tmp)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    count = len(mouth) + int(PAD * FPS)
    for k in range(count):
        frame = opened if k < len(mouth) and mouth[k] else closed
        p.stdin.write(camera_frame(frame, k, count, i))
    p.stdin.close()
    if p.wait():
        sys.exit(f"ffmpeg lỗi ở cảnh {i}")
    tmp.rename(out)
    return out


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "storyboard.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    scenes = data["scenes"]
    ensure_assets(A, data.get("bible"), scenes)  # tự vẽ nhân vật/nền còn thiếu
    clips = []
    for i, s in enumerate(scenes):
        print(f"[{i + 1}/{len(scenes)}] {s['speaker']}: {s['text'][:50]}")
        clips.append(render_scene(i, s))

    lst = OUT / "list.txt"
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "video.mp4")
    print("Xong -> video.mp4")


if __name__ == "__main__":
    main()
