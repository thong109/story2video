"""Conservative on-screen character suggestions from Vietnamese scene text."""
import re
import unicodedata

NAME = r'[A-ZĐÀ-Ỹ][a-zđà-ỹ]*(?:[ \t]+[A-ZĐÀ-Ỹ][a-zđà-ỹ]*){0,2}'


def slug(name):
    plain = unicodedata.normalize('NFKD', name.lower().replace('đ', 'd'))
    return re.sub(r'[^a-z0-9]+', '_', ''.join(c for c in plain if not unicodedata.combining(c))).strip('_')


def age_near_name(text, name):
    numbers = {'một':1, 'hai':2, 'ba':3, 'bốn':4, 'năm':5, 'sáu':6, 'bảy':7, 'tám':8, 'chín':9, 'mười':10, 'mười một':11, 'mười hai':12}
    for match in re.finditer(r'(?<!\w)' + re.escape(name) + r'(?!\w)', text, re.I):
        tail = text[match.end():match.end()+100]
        age = re.search(r'(?:mới(?: tròn)?|tròn|năm nay|lúc đó(?: mới(?: tròn)?)?)\s+([\d]+|mười một|mười hai|mười|một|hai|ba|bốn|năm|sáu|bảy|tám|chín)\s+tuổi', tail, re.I)
        if age:
            between = tail[:age.start()]
            if re.search(r'\bvà\b|[.!?\n]', between, re.I) or any(word[:1].isupper() for word in between.split()):
                continue
            value = int(age[1]) if age[1].isdigit() else numbers.get(age[1].casefold())
            if value and 1 <= value <= 120:
                return value
    return None


def suggest_characters(scenes, characters=None, cast=None):
    cast = cast or {}
    people, aliases, remap = {}, {}, {}
    text_all = '\n'.join(str(s.get('text', '')) for s in scenes)

    def contains(text, alias):
        return re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', text, re.I)

    def add(name, cid=None, spec=None):
        name = name.strip()
        key = name.casefold()
        if key in aliases:
            return aliases[key]
        spec = dict(spec or {})
        candidate = cid or slug(name) or 'nhan_vat'
        if candidate in cast and cast[candidate].get('name', candidate).casefold() != key:
            candidate += '_truyen'
        while candidate in people and people[candidate]['name'].casefold() != key:
            candidate += '_2'
        people[candidate] = dict(spec, id=candidate, name=name)
        aliases[key] = candidate
        return candidate

    stop_names = {'Con','Nó','Họ','Chúng Tôi','Chúng Ta','Sao','Ai','Vì','Đâu','Khi','Nếu','Bỗng','Có','Không','Về','Là','Năm','Cái','Giọng','Trời','Người'}
    for person in characters or []:
        explicit_cast = person['id'] in cast and cast[person['id']].get('name', '').casefold() == person['name'].casefold()
        if not explicit_cast and (person['name'] in stop_names or not person['name'][:1].isupper()):
            continue
        cid = add(person['name'], person['id'], person)
        if cid != person['id']:
            remap[person['id']] = cid
    for cid, person in cast.items():
        name = person.get('name', cid.replace('_', ' '))
        if contains(text_all, name):
            add(name, cid, person)

    title_roles = {}
    # Explicit introductions and names performing actions; avoid arbitrary capitals.
    for match in re.finditer(r'(?P<title>(?i:ông|bà|chú|cô|anh|chị|thằng út|con bé|út|tên là))\s+(?P<name>' + NAME + r')', text_all):
        name = match['name']
        if not all(word[:1].isupper() for word in name.split()) or name in stop_names:
            continue
        cid = aliases.get(name.casefold()) or add(name)
        aliases[(match['title'] + ' ' + name).casefold()] = cid
        title = match['title'].casefold()
        if not people[cid].get('gender'):
            if title in ('ông','chú','anh','thằng út','út'):
                people[cid]['gender'] = 'nam'
            elif title in ('bà','cô','chị','con bé'):
                people[cid]['gender'] = 'nữ'
        if title in ('ông','bà','anh','chị','cô','chú'):
            title_roles.setdefault(title + ' ấy', set()).add(cid)
        if match['title'].casefold() in ('út', 'thằng út'):
            for alias in ('thằng út', 'em trai', 'đứa em trai'):
                aliases.setdefault(alias, cid)
    action = r'(?:đang|vừa|bước|chạy|đứng|ngồi|nằm|mở|đi|nhìn|nói|hỏi|đáp|khóc|cười|xuất hiện|bị)\b'
    for match in re.finditer(r'(?<!\w)(?P<name>' + NAME + r')\s+' + action, text_all):
        if not all(word[:1].isupper() for word in match['name'].split()) or match['name'] in stop_names:
            continue
        if match['name'] not in ('Tôi', 'Má', 'Mẹ', 'Trời', 'Người', 'Nhưng', 'Họ', 'Nó', 'Con', 'Chúng', 'Cô', 'Anh', 'Ông', 'Bà'):
            add(match['name'])
    if contains(text_all, 'tôi'):
        add('Tôi')
    for role in ('má', 'mẹ'):
        role_text = re.sub(r'như tấm lòng người mẹ|tấm lòng người mẹ|mẹ thiên nhiên', '', text_all, flags=re.I)
        if contains(role_text, role):
            cid = add(role.capitalize())
            if not people[cid].get('gender'):
                people[cid]['gender'] = 'nữ'
    for alias in ('con ma', 'bóng ma', 'hồn ma'):
        if contains(text_all, alias):
            cid = aliases.get(alias) or add('Ma', spec={'kind':'ghost'})
            aliases[alias] = cid

    for person in people.values():
        if not person.get('age'):
            age = age_near_name(text_all, person['name'])
            if age is not None:
                person['age'] = age

    # Link pronouns only when a unique, explicitly introduced character is known.
    male = [cid for cid, person in people.items() if person.get('gender') == 'nam' and person['name'] != 'Tôi']
    female = [cid for cid, person in people.items() if person.get('gender') in ('nữ','nu')]
    if len(male) == 1:
        aliases.setdefault('anh ấy', male[0])
    if len(female) == 1:
        aliases.setdefault('cô ấy', female[0])

    for alias, candidates in title_roles.items():
        if len(candidates) == 1:
            aliases[alias] = next(iter(candidates))

    active, remote = [], set()
    previous_place = None
    result = []
    for original in scenes:
        scene = dict(original)
        speaker = remap.get(scene.get('speaker'), scene.get('speaker', 'narrator'))
        scene['speaker'] = speaker
        if scene.get('character_poses'):
            scene['character_poses'] = {remap.get(k,k):v for k,v in scene['character_poses'].items()}
        text = scene.get('text', '')
        low = text.casefold()
        # Ignore changes of lighting, but reset at a different physical set.
        place = re.sub(r'_(?:ngay|dem|chieu)_[a-f0-9]+$', '', scene.get('background', ''))
        if place != previous_place or re.search(r'\b(?:nhiều năm sau|năm tôi|hôm sau|sáng hôm sau|từ đó|trở về quê)\b', low):
            active = []
            remote = set()
        previous_place = place
        hits = []
        for alias, cid in sorted(aliases.items(), key=lambda item: -len(item[0])):
            match = contains(text, alias)
            if people[cid]['name'] == 'Tôi':
                for candidate in re.finditer(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', text, re.I):
                    if re.match(r'\s*(?:đang|vừa|bước|chạy|đứng|ngồi|nằm|mở|đi|nhìn|cầm|kẹp|quệt|cặm|thay|phải khăn gói|lên)\b', low[candidate.end():]):
                        match = candidate
                        break
            if match and cid not in [item[0] for item in hits]:
                hits.append((cid, match))
        phone = bool(re.search(r'điện thoại|đầu dây|gọi về|gọi cho|alo', low))
        if phone and re.search(r'giọng|đầu dây', low):
            remote.update(cid for cid, _ in hits if people[cid]['name'] != 'Tôi')
            active = [cid for cid in active if cid not in remote]

        visible = []
        if speaker == 'narrator':
            for cid, match in hits:
                before = low[max(0,match.start()-55):match.start()]
                after = low[match.end():match.end()+55]
                if cid in remote:
                    continue
                if re.search(r'như (?:tấm lòng )?(?:người )?$', before):
                    continue
                if re.search(r'(?:nhớ về|nhớ đến|nhớ|nghĩ về|nghĩ đến|kể về|nhắc đến|hỏi thăm|thương yêu|gọi cho)\s*(?:người |thằng |con )?$', before):
                    continue
                if re.match(r'\s*(?:không có ở đây|vắng mặt|chưa đến|đã rời|đã đi khỏi)', after) or re.search(r'không (?:có|thấy)\s*$', before):
                    active = [person for person in active if person != cid]
                    continue
                if people[cid]['name'] == 'Tôi':
                    if not re.match(r'\s*(?:đang|vừa|bước|chạy|đứng|ngồi|nằm|mở|đi|nhìn|cầm|kẹp|quệt|cặm|thay|phải khăn gói|lên)\b', after):
                        continue
                if phone and people[cid]['name'] != 'Tôi':
                    continue
                visible.append(cid)
            if visible:
                active = visible
        else:
            # A person mentioned in dialogue is not automatically in the frame.
            if speaker in people and speaker not in remote:
                active = list(dict.fromkeys(active + [speaker]))
        scene['speaker_visible'] = speaker == 'narrator' or speaker not in remote
        scene['characters'] = list(dict.fromkeys(cid for cid in active if cid in people and cid not in remote))
        result.append(scene)
    # Keep introduced people available for manual adjustment, even if off-screen.
    return list(people.values()), result
