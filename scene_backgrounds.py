"""Context-aware background plans for offline storyboards."""
import hashlib
import re
import unicodedata


def normalize(text):
    text = unicodedata.normalize('NFKD', text.lower().replace('đ', 'd'))
    return ''.join(c for c in text if not unicodedata.combining(c))


PLACES = {
    'xom_ven_rach': 'Xóm nghèo miền Tây ven con rạch, nước đục phù sa, nhà lá dừa nước thưa thớt, cây dừa nước, nông thôn; không có cao ốc hay đường phố',
    'nha_la_ven_rach': 'Nhà lá nghèo sát mép con rạch miền Tây, vách lá dừa nước cũ, cột tràm trên bùn, hiên nhà và cầu ván gỗ xuống bến, nước phù sa; không có sofa hay nhà cao tầng',
    'ben_van_ven_rach': 'Bến cầu ván gỗ cũ cạnh con rạch miền Tây, dòng nước đục, xuồng nhỏ, cây dừa nước, vài nhà lá xa xa; không có cao ốc',
    'tiem_sua_xe': 'Bên trong tiệm sửa xe máy nhỏ ở Sài Gòn, mái tôn, nền xi măng, xe máy đang sửa, lốp xe và dụng cụ treo trên tường, nhìn ra con phố',
    'duong_sai_gon': 'Đường phố Sài Gòn, nhà phố thấp tầng, cửa hàng, xe máy và vỉa hè',
    'phong_ngu': 'Phòng ngủ, giường và cửa sổ, không có sofa',
    'rung': 'Rừng cây rậm rạp, lối mòn đất và những thân cây cao',
}


def plan_backgrounds(scenes):
    location = 'xom_ven_rach' if any(re.search(r'con rach|mien tay|song nuoc', normalize(s['text'])) for s in scenes) else 'phong_khach'
    period = 'ngay'
    weather = ''
    names = {'xom_ven_rach':'Xóm ven rạch', 'nha_la_ven_rach':'Nhà lá ven rạch', 'ben_van_ven_rach':'Bến ván ven rạch', 'tiem_sua_xe':'Tiệm sửa xe', 'duong_sai_gon':'Đường Sài Gòn', 'phong_khach':'Phòng khách', 'phong_ngu':'Phòng ngủ', 'rung':'Rừng'}
    records = {}
    result = []
    for original in scenes:
        scene = dict(original)
        text = normalize(scene['text'])
        # Dialogue about a remote location does not move the camera there.
        previous_location = location
        if scene.get('speaker') == 'narrator':
            if re.search(r'tiem (?:sua )?xe|tho sua xe|thay bo thang|sua chua xe', text):
                location = 'tiem_sua_xe'
            elif re.search(r'\b(?:truoc|tai|ra|xuong|cho|ngay) ben\b|cheo xuong|cuon troi|\bxac (?:ong|ba|anh|co|chu|em)\b.*\bnoi\b', text):
                location = 'ben_van_ven_rach'
            elif re.search(r'o que chi con', text):
                location = 'nha_la_ven_rach'
            elif re.search(r'troi sai gon|troi thanh pho', text) and any('sua xe' in normalize(s['text']) for s in scenes):
                location = 'tiem_sua_xe'
            elif re.search(r'nha toi|hien nha|vach la|cot tram|nha la', text):
                location = 'nha_la_ven_rach' if any(word in text for word in ('nuoc', 'rach', 'la', 'tram', 'hien')) else 'phong_khach'
            elif re.search(r'vao rung|trong rung|khu rung', text):
                location = 'rung'
            elif re.search(r'phong ngu|len giuong', text):
                location = 'phong_ngu'
            elif re.search(r'duong pho|tren pho|buoc ra duong', text):
                location = 'duong_sai_gon'
            if location != previous_location:
                period = 'ngay'
            if re.search(r'nua dem|dem khuya|ban dem|ba gio sang|toi mit', text):
                period = 'dem'
            elif re.search(r'buoi trua|trua he|sang som|buoi sang|moi som', text):
                period = 'ngay'
            elif re.search(r'buoi chieu|chieu muon|hoang hon', text):
                period = 'chieu'
            if 'nang gat' in text and period == 'dem':
                period = 'ngay'
            if re.search(r'mua tam ta|troi mua|con mua|mua lon', text):
                weather = 'mưa'
            elif re.search(r'nang gat|nang chieu', text):
                weather = ''
        description = PLACES.get(location, 'Bên trong phòng khách giản dị, cửa sổ và bàn gỗ')
        description += {'ngay': '. Ban ngày, ánh sáng tự nhiên', 'dem': '. Ban đêm, ánh sáng đèn vàng yếu, bóng tối ngoài trời', 'chieu': '. Chiều muộn, ánh sáng ấm'}[period]
        if weather:
            description += '. Trời mưa'
        description += '. Phong cách minh họa hoạt hình 2D'
        bid = location + '_' + period + '_' + hashlib.sha256(description.encode()).hexdigest()[:6]
        records[bid] = dict(id=bid, name=names.get(location, location) + ' · ' + {'ngay':'Ngày','dem':'Đêm','chieu':'Chiều'}[period], description=description)
        scene['background'] = bid
        scene['background_description'] = description
        result.append(scene)
    return list(records.values()), result
