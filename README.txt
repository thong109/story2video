STORY STUDIO — TRUYỆN THÀNH VIDEO 2D

Cài đặt: python -m pip install -r requirements.txt
Ứng dụng ưu tiên FFmpeg ổn định đi kèm imageio-ffmpeg; cài bằng requirements.txt.
Chạy: python app.py — mở http://127.0.0.1:5000

DỰ ÁN
Mỗi dự án lưu trong projects/<id>/:
  project.json     tên và nội dung truyện
  storyboard.json cảnh và nhân vật
  build/          âm thanh, các cảnh video tạm
  video.mp4       video hoàn chỉnh
Chọn Dự án đã lưu để mở lại; chọn Dự án mới để bắt đầu truyện khác.

GIỌNG ĐỌC
Chọn giọng kể, giọng nhân vật mặc định và voice riêng từng nhân vật.
Piper dùng lại models ở ../tool/models/voices; có thể đổi bằng STORY_VOICE_MODELS.
Giọng kể truyện ma: narrator_profile trong config.json.

STORYBOARD
Không có API: nhận diện lời thoại có tên hoặc câu dẫn rõ người nói.
Có thể sửa người nói và bối cảnh cho mỗi cảnh trước khi xuất video.
Cấu hình AI trong giao diện; API key lưu ở local_settings.json.

PHỤ ĐỀ
Chọn font và cỡ chữ 16–96 px trong Thiết lập video, xem trước rồi Lưu thiết lập phụ đề.
Thiết lập được lưu theo dự án và áp dụng khi xuất video lại.

BỐI CẢNH THEO TRUYỆN
Storyboard offline chọn địa điểm và thời điểm từ nội dung, giữ nền trong các lượt thoại liên tiếp.
Dự án cũ: bấm Khớp bối cảnh theo truyện; xem ảnh nền, sửa mô tả ở từng cảnh rồi xuất video lại.
Ảnh nền riêng lưu trong projects/<id>/backgrounds.

BACKGROUND AI LOCAL
Đã bật Stable Diffusion 1.5/OpenVINO trong config.json (backgrounds.provider=local_ai).
Bấm Tạo nền AI local để xem trước; xuất video tự tạo các nền còn thiếu.
Ảnh AI lưu tại projects/<id>/backgrounds/*.ai.png; dùng lại khi mô tả không đổi.
Bản model tương thích models/sd15-openvino dùng chung trọng số với model có sẵn, không sửa model gốc.
Cache tạo ảnh nằm trên ổ dự án trong models/image-cache.

NHÂN VẬT MA VÀ TƯ THẾ NẰM
Tab Nhân vật: chọn Ma hoặc Thi thể, chọn tư thế đứng/nằm đầu trái/nằm đầu phải.
Storyboard: mở Nhân vật xuất hiện để chọn nhân vật trong cảnh và đổi tư thế riêng cho cảnh.
Thi thể giữ mắt nhắm và không nhép miệng.

NHẬN DIỆN NHÂN VẬT XUẤT HIỆN
Bấm Nhận diện nhân vật theo câu văn để gợi ý người có mặt trong từng cảnh.
Phân biệt người được nhắc đến với người xuất hiện; giọng ở đầu dây có thể để ngoài khung hình.
Có thể sửa checkbox Nhân vật xuất hiện và Hiện người nói; đại từ mơ hồ cần kiểm tra thủ công.

TỶ LỆ TRẺ EM
Nhân vật dưới 12 tuổi có thân/tay/chân ngắn hơn và thấp hơn người lớn trong video.
Chiều cao theo tuổi: 1–3: 50%, 4–6: 60%, 7–9: 68%, 10–11: 76%, từ 12: 100%.
Giữ cùng mặt đất; áp dụng cả cho ma, thi thể và tư thế nằm.
