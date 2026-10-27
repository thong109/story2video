"""Conservative dialogue attribution for stories without an AI connection."""
import re
import unicodedata

NAME = r"[A-ZĐÀ-Ỹ][a-zđà-ỹ]*(?:[ \t]+[A-ZĐÀ-Ỹ][a-zđà-ỹ]*){0,3}"
VERB = r"(?:nói|hỏi|đáp|trả lời|thì thầm|kêu|hét|bảo|gọi|cười nói|nói khẽ|nói lớn)"
TAG = re.compile(r"(?P<name>" + NAME + r")[ \t]+(?:khẽ |liền |bỗng |vội )?" + VERB + r"[^.!?\n:“”\"]{0,35}:?[ \t]*$", re.UNICODE)
PREFIX = re.compile(r"^(?P<name>" + NAME + r")[ \t]*:[ \t]*(?P<text>.+)$")
QUOTE = re.compile(r'“([^”]+)”|"([^"\n]+)"|«([^»]+)»')


def split_story(story, background, cast=None):
    characters = {}
    known = {v.get('name', key.replace('_', ' ')): (key, v) for key, v in (cast or {}).items()}
    def register(name):
        name = name.strip()
        if name in known:
            cid, spec = known[name]
        else:
            plain = unicodedata.normalize('NFKD', name.replace('Đ', 'D').replace('đ', 'd'))
            cid = re.sub(r'[^a-z0-9]+', '_', ''.join(c for c in plain if not unicodedata.combining(c)).lower()).strip('_')
            if not cid or cid == 'narrator':
                cid = 'nhan_vat_' + str(len(characters) + 1)
            spec = {}
        characters[cid] = dict(id=cid, name=name, gender=spec.get('gender', ''), look=spec.get('description', ''))
        return cid

    def cue(text):
        # Role names may be lowercase and may be separated from speech by narration.
        voice = re.search(r'\b[Gg]iọng\s+(má|mẹ|ba|bố|tôi|anh|chị|cô|chú|ông|bà)\b', text)
        if voice:
            return register(voice[1].capitalize())
        tag = TAG.search(text)
        return register(tag['name']) if tag else None

    # Recognize explicitly introduced people, without treating every capitalized word as a name.
    for match in re.finditer(r'\b(?:ông|bà|chú|cô|anh|chị|út|tên là)\s+(' + NAME + r')', story):
        register(match[1])

    scenes = []
    def emit(text, speaker='narrator'):
        # Cut at sentence endings only; commas and the 25-word target do not break scenes.
        for sentence in re.split(r'(?<=[.!?…])(?<!\.\.)\s+|\n+', text.strip()):
            sentence = sentence.strip()
            if sentence:
                scenes.append(dict(speaker=speaker, text=sentence, emotion='neutral', background=background, characters=[] if speaker=='narrator' else [speaker]))

    pending = None
    for line in story.splitlines():
        line = line.strip()
        if not line:
            continue
        direct = PREFIX.fullmatch(line)
        if direct and len(direct['name'].split()) <= 4:
            emit(direct['text'].strip('“”"'), register(direct['name']))
            pending = None
            continue
        if line.startswith(('-', '–', '—')):
            dialogue = line.lstrip('-–— ').strip()
            # A dash followed by a narration clause ends the spoken turn.
            attribution = re.search(r'\s+[—–-]\s+(?P<name>Tôi|tôi|Má|má|Mẹ|mẹ|' + NAME + r')\b', dialogue)
            if attribution:
                emit(dialogue[:attribution.start()], register(attribution['name'].capitalize() if attribution['name'].lower() in ('tôi', 'má', 'mẹ') else attribution['name']))
                emit(dialogue[attribution.start():].lstrip('—–- '))
            else:
                emit(dialogue, pending or 'narrator')
            pending = None
            continue
        matches = list(QUOTE.finditer(line))
        if not matches:
            tag = TAG.search(line)
            pending = cue(line)
            emit(line)
            continue
        cursor = 0
        for match in matches:
            before = line[cursor:match.start()]
            tag = TAG.search(before)
            following = line[match.end():]
            after = re.match(r'[\s,;—–-]*(' + NAME + r')\s+' + VERB, following)
            speaker = register(tag['name']) if tag else register(after[1]) if after else pending
            if speaker:
                emit(before)
                emit(next(g for g in match.groups() if g is not None), speaker)
            else:
                # Quoted terms such as chữ \"S\" are not dialogue.
                continue
            cursor = match.end()
            pending = None
        emit(line[cursor:])
    # Show identified characters where their names occur in narration as well.
    for scene in scenes:
        for cid, character in characters.items():
            if re.search(r'(?<!\w)' + re.escape(character['name']) + r'(?!\w)', scene['text']) and cid not in scene['characters']:
                scene['characters'].append(cid)
    return list(characters.values()), scenes
