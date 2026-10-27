"""Truyện -> storyboard.json (danh sách cảnh) + kiểm tra bám nguyên văn.

Dùng:  python storyboard.py truyen.txt
Cần:   pip install anthropic   và biến môi trường ANTHROPIC_API_KEY
"""
import json
import os
import re
import json as json_lib
import urllib.error
import urllib.request
import sys
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-5-5"
client = None
PROVIDER = "anthropic"
OLLAMA_BASE_URL = "http://localhost:11434"
HF_TOKEN = ""
CHUNK_CHARS = 3000
EMOTIONS = "neutral|happy|sad|angry|scared|surprised|thinking"


def configure_client(provider=None, api_key=None, model=None, base_url=None):
    """Configure the Anthropic-compatible client for Anthropic or Meta Muse."""
    global client, MODEL, PROVIDER, OLLAMA_BASE_URL, HF_TOKEN
    provider = provider or ("muse" if (os.environ.get("MODEL_API_KEY") or os.environ.get("MUSE_API_KEY")) else "anthropic")
    PROVIDER = provider
    if provider == "huggingface":
        MODEL = model or "Qwen/Qwen2.5-7B-Instruct-1M:fastest"
        HF_TOKEN = api_key or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN", "")
        client = None
        return None
    if provider == "ollama":
        MODEL = model or "qwen2.5:7b"
        OLLAMA_BASE_URL = (base_url or "http://localhost:11434").rstrip("/")
        client = None
        return None
    api_key = api_key or (os.environ.get("MODEL_API_KEY") or os.environ.get("MUSE_API_KEY") if provider == "muse" else os.environ.get("ANTHROPIC_API_KEY"))
    if provider == "muse":
        MODEL = model or os.environ.get("MUSE_MODEL", "muse-spark-1.3")
        client = anthropic.Anthropic(auth_token=api_key, base_url="https://api.meta.ai") if api_key else None
    else:
        MODEL = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
        client = anthropic.Anthropic(api_key=api_key) if api_key else None
    return client

BIBLE_SYS = """Bạn đọc một truyện và lập "story bible" cho video hoạt hình 2D đơn giản.
Trả về DUY NHẤT một JSON (không markdown) dạng:
{"characters":[{"id":"snake_case_ascii","name":"tên gốc","gender":"nam|nữ","look":"mô tả ngoại hình ngắn"}],
 "backgrounds":[{"id":"snake_case_ascii","description":"mô tả ngắn"}]}
Chỉ liệt kê nhân vật có thoại hoặc xuất hiện rõ, và các bối cảnh chính (tối đa ~10)."""

SCENE_SYS = f"""Bạn là biên tập storyboard cho video hoạt hình 2D đơn giản (nhân vật đứng yên, đổi biểu cảm, có lồng tiếng và phụ đề).
Chia đoạn truyện thành các cảnh theo đúng thứ tự. Trả về DUY NHẤT một mảng JSON (không markdown), mỗi phần tử:
{{"speaker":"narrator hoặc id nhân vật","text":"...","emotion":"{EMOTIONS}","background":"id bối cảnh","characters":["id nhân vật đang có mặt"]}}

Quy tắc bắt buộc:
- "text" phải CHÉP NGUYÊN VĂN từ truyện: không thêm, không bớt, không diễn đạt lại, không đổi tình tiết.
- Mỗi cảnh tối đa khoảng 25 từ, cắt ở ranh giới câu.
- Lời thoại: bỏ dấu ngoặc kép/gạch đầu dòng, speaker là nhân vật nói. Phần dẫn như "anh ta nói" thì tách thành cảnh narrator.
- Văn miêu tả/dẫn truyện: speaker = "narrator".
- Chỉ dùng id có trong story bible. "emotion" là cảm xúc của người nói.
"""


def ask_json(system, user, max_tokens=8000):
    if PROVIDER == "huggingface":
        payload = json_lib.dumps({
            "model": MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": 0.1,
        }).encode("utf-8")
        req = urllib.request.Request("https://router.huggingface.co/v1/chat/completions", data=payload,
                                    headers={"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=600) as response:
                result = json_lib.loads(response.read().decode("utf-8"))
            t = result["choices"][0]["message"]["content"].strip()
            t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
            return json.loads(t)
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Hugging Face Inference Providers không truy cập được: {exc}") from exc
    if PROVIDER == "ollama":
        payload = json_lib.dumps({
            "model": MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "format": "json",
            "options": {"num_predict": max_tokens},
        }).encode("utf-8")
        req = urllib.request.Request(OLLAMA_BASE_URL + "/api/chat", data=payload,
                                    headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=600) as response:
                result = json_lib.loads(response.read().decode("utf-8"))
            return json_lib.loads(result["message"]["content"])
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Không kết nối được Ollama tại {OLLAMA_BASE_URL}: {exc}") from exc
    if client is None:
        configure_client()
    if client is None:
        raise RuntimeError("Chưa cấu hình API key cho Anthropic hoặc Meta Muse.")
    r = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    t = "".join(b.text for b in r.content if b.type == "text").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    return json.loads(t)


def chunk_story(story):
    chunks, cur = [], ""
    for para in re.split(r"\n\s*\n|\n", story):
        para = para.strip()
        if not para:
            continue
        if cur and len(cur) + len(para) > CHUNK_CHARS:
            chunks.append(cur)
            cur = ""
        cur += para + "\n"
    if cur:
        chunks.append(cur)
    return chunks


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def check_fidelity(story, scenes):
    """Đánh dấu câu trong truyện gốc mà các cảnh không còn chứa (so khớp trigram từ)."""
    words = norm(" ".join(s["text"] for s in scenes)).split()
    grams = {tuple(words[i:i + 3]) for i in range(len(words) - 2)}
    missing = []
    for sent in re.split(r"(?<=[.!?…])\s+|\n+", story):
        w = norm(sent).split()
        if len(w) < 3:
            continue
        g = [tuple(w[i:i + 3]) for i in range(len(w) - 2)]
        cover = sum(x in grams for x in g) / len(g)
        if cover < 0.6:
            missing.append(sent.strip())
    return missing


def print_needed_assets(scenes):
    chars, bgs = {}, set()
    for s in scenes:
        bgs.add(s["background"])
        for c in s.get("characters", []):
            chars.setdefault(c, set()).add("neutral")
        if s["speaker"] != "narrator":
            chars.setdefault(s["speaker"], set()).add(s["emotion"])
    print("\n== Asset sẽ dùng (thiếu thì make_video.py tự vẽ; muốn dùng hình riêng thì bỏ PNG vào đúng đường dẫn) ==")
    for c, emos in sorted(chars.items()):
        print(f"assets/characters/{c}/  ->  " + ", ".join(f"{e}.png (+ {e}_talk.png)" for e in sorted(emos)))
    for b in sorted(bgs):
        print(f"assets/backgrounds/{b}.png")


def main():
    if len(sys.argv) < 2:
        sys.exit("Dùng: python storyboard.py truyen.txt")
    story = Path(sys.argv[1]).read_text(encoding="utf-8")

    print("1/2 Lập story bible...")
    bible = ask_json(BIBLE_SYS, story[:60000], max_tokens=3000)
    ids_c = [c["id"] for c in bible["characters"]]
    ids_b = [b["id"] for b in bible["backgrounds"]]

    print("2/2 Chia cảnh...")
    scenes = []
    for n, chunk in enumerate(chunk_story(story), 1):
        context = json.dumps(scenes[-2:], ensure_ascii=False)
        user = (
            f"STORY BIBLE:\n{json.dumps(bible, ensure_ascii=False)}\n\n"
            f"HAI CẢNH CUỐI CỦA ĐOẠN TRƯỚC (để giữ liền mạch bối cảnh):\n{context}\n\n"
            f"ĐOẠN TRUYỆN CẦN CHIA:\n{chunk}"
        )
        part = ask_json(SCENE_SYS, user)
        for s in part:
            if s["speaker"] != "narrator" and s["speaker"] not in ids_c:
                s["speaker"] = "narrator"
            s["characters"] = [c for c in s.get("characters", []) if c in ids_c]
            if s["background"] not in ids_b:
                s["background"] = ids_b[0]
            if s.get("emotion") not in EMOTIONS.split("|"):
                s["emotion"] = "neutral"
        scenes += part
        print(f"   đoạn {n}: +{len(part)} cảnh")

    out = Path("storyboard.json")
    out.write_text(json.dumps({"bible": bible, "scenes": scenes}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nĐã ghi {out} ({len(scenes)} cảnh)")

    missing = check_fidelity(story, scenes)
    if missing:
        print(f"\n!! {len(missing)} câu có thể bị bỏ sót/sửa. Kiểm tra lại:")
        for m in missing[:20]:
            print("  -", m)
    else:
        print("Kiểm tra bám cốt truyện: OK (mọi câu đều có trong các cảnh).")

    print_needed_assets(scenes)
    print("\nMở storyboard.json xem/sửa tay, rồi chạy: python make_video.py")


if __name__ == "__main__":
    main()
