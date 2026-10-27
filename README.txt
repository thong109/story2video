story2video - Truyen -> video hoat hinh 2D (nhan vat, nen, giong doc, phu de: tu dong het)

CAI DAT
  pip install -r requirements.txt     (can ffmpeg + bien moi truong ANTHROPIC_API_KEY cho buoc 1)

THU NGAY (khong can API key)
  python make_video.py demo_storyboard.json   -> video.mp4 (can Internet de edge-tts doc giong)

  Truyen mau: truyen_mau.txt + storyboard_truyen_mau.json (18 canh)
  python make_video.py storyboard_truyen_mau.json

DUNG VOI TRUYEN CUA BAN
  1. Dat truyen vao truyen.txt
  2. python storyboard.py truyen.txt   -> storyboard.json (+ bao cac cau co the bi sot/sua)
  3. Mo storyboard.json xem/sua tay neu can
  4. Dien ten nhan vat -> giong trong config.json (mac dinh: narrator = nam, con lai = nu)
  5. python make_video.py              -> video.mp4
     Nhan vat/nen chua co se duoc TU VE (7 bieu cam x mieng dong/mo).

TUY CHINH
  - assets/cast.json : doi ngoai hinh (mau da/toc/ao/quan, kieu toc, gioi tinh) cho tung nhan vat
  - Dung hinh rieng : bo PNG nen trong suot vao assets/characters/<id>/neutral.png (+ <emotion>.png, <emotion>_talk.png)
                      va assets/backgrounds/<id>.png -> se duoc uu tien thay cho hinh tu ve
  - Xoa assets/characters/<id>/ de ve lai nhan vat do
  - config.json : kich thuoc, fps, font, toc do doc (rate), giong doc
  - Giong doc tieng Viet (edge-tts): vi-VN-HoaiMyNeural (nu), vi-VN-NamMinhNeural (nam)

STORYBOARD AI (tuy chon)
  Anthropic: dat ANTHROPIC_API_KEY nhu truoc.
  Meta Muse: PowerShell -> $env:MODEL_API_KEY = "API_KEY_CUA_BAN"
             sau do chay python app.py; mac dinh dung muse-spark-1.3.
  Hoac dung MUSE_API_KEY thay cho MODEL_API_KEY. Khong ghi key truc tiep vao ma nguon.

CAI DAT API TRONG GIAO DIEN
  Mo tab Cai dat AI, chon Meta Muse hoac Anthropic, dan API key roi bam Luu API key.
  Bam Kiem tra ket noi de xac nhan. Key duoc luu trong local_settings.json (da them vao .gitignore).


Ollama (local, khong can API key): tai Ollama, chay `ollama pull qwen2.5:7b`, mo tab Cai dat AI, chon Ollama va nhap ten model da cai.
Hugging Face: tab Cai dat AI, chon Hugging Face Inference, dan HF token co quyen Inference Providers; model mac dinh Qwen/Qwen2.5-7B-Instruct-1M:fastest. Credit Free hang thang co gioi han.
