"""Project background prompts and isolated local image generation."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from scene_backgrounds import normalize

ROOT = Path(__file__).resolve().parent


def make_prompt(record):
    text = normalize(record.get('id','') + ' ' + record.get('description',''))
    rural = any(word in text for word in ('rach','nha la','mien tay','river','mekong'))
    if 'tiem_sua_xe' in text or 'sua xe' in text:
        place = 'small Vietnamese motorcycle repair workshop, corrugated roof, concrete floor, parked motorbike, spare tires, tools hanging on wall, open storefront'
    elif 'nha_la' in text or 'vach la' in text:
        place = 'poor thatched palm leaf stilt house beside a muddy Mekong Delta canal, weathered wooden walls, timber posts, narrow wooden porch, nipa palms'
    elif 'ben_' in text or 'ben van' in text:
        place = 'old narrow wooden jetty on a muddy Mekong Delta canal, small wooden sampan, nipa palms, sparse thatched huts in distance'
    elif rural:
        place = 'poor rural Mekong Delta village along a winding muddy canal, scattered thatched stilt houses, dense nipa palms, quiet riverbank'
    elif 'rung' in text:
        place = 'dense Vietnamese tropical forest, tall old trees, winding dirt path, mist between trees'
    elif 'phong_ngu' in text:
        place = 'modest Vietnamese bedroom, old wooden bed, simple window, worn plaster walls'
    else:
        place = record.get('description','').strip() or record['id'].replace('_',' ')
    light = 'soft daylight'
    if 'dem' in text or 'night' in text:
        light = 'night, dim warm lantern light, deep blue shadows, eerie mist'
    elif 'chieu' in text or 'sunset' in text:
        light = 'late afternoon, muted amber light, long shadows'
    if 'mua' in text or 'rain' in text:
        light += ', rain, wet surfaces'
    prompt = f'Gouache painting, hand drawn 2D animation background, illustrated linework, {place}, {light}, muted gray greens and browns, painted brush textures, wide view, empty scene'
    negative = 'photograph, photorealistic, realistic photo, 3d render, CGI, people, person, face, text, watermark, logo, blurry, oversaturated'
    if rural:
        negative += ', skyscrapers, modern city, apartment blocks, highway'
    return prompt, negative


def ensure_ai_backgrounds(project_dir, bible, scenes, settings, force=False):
    project_dir = Path(project_dir).resolve()
    directory = project_dir / 'backgrounds'
    directory.mkdir(parents=True, exist_ok=True)
    model = Path(os.environ.get('STORY_IMAGE_MODEL', settings.get('model_dir', '../tool/models/ghost-story/openvino-stable-diffusion-v1-5')))
    if not model.is_absolute():
        model = (ROOT / model).resolve()
    if not (model / 'model_index.json').is_file():
        raise RuntimeError('Không tìm thấy model ảnh local: ' + str(model))
    records = {b['id']:b for b in (bible or {}).get('backgrounds', [])}
    images = []
    for bid in sorted({s['background'] for s in scenes}):
        if not re.fullmatch(r'[a-z0-9_]+', bid):
            raise ValueError('ID bối cảnh không hợp lệ.')
        output = directory / (bid + '.ai.png')
        record = records.get(bid, dict(id=bid, description=bid.replace('_',' ')))
        prompt, negative = make_prompt(record)
        signature = hashlib.sha256((prompt+negative+str(model)+str(settings)).encode()).hexdigest()
        provenance = output.with_suffix('.json')
        if output.exists() and provenance.exists() and not force:
            previous = json.loads(provenance.read_text(encoding='utf-8'))
            if previous.get('signature') == signature:
                continue
        images.append(dict(name=record.get('name',bid),prompt=prompt,negative=negative,
            seed=int(signature[:8],16),signature=signature,output=str(output)))
    if not images:
        print('Background AI đã sẵn sàng, dùng lại ảnh trong dự án.',flush=True)
        return
    lock = directory / '.generation.lock'
    lock_file = lock.open('a+b')
    try:
        lock_file.seek(0)
        if os.name == 'nt':
            import msvcrt
            if lock.stat().st_size == 0:
                lock_file.write(b'0')
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        raise RuntimeError('Dự án đang tạo background AI. Chờ hoàn tất rồi xuất video.')
    try:
        with tempfile.TemporaryDirectory(prefix='image_job_',dir=directory) as temp:
            manifest = Path(temp) / 'manifest.json'
            cache = ROOT / 'models' / 'image-cache'
            cache.mkdir(parents=True, exist_ok=True)
            manifest.write_text(json.dumps(dict(model_dir=str(model),cache_dir=str(cache),
                images=images,device=settings.get('device','GPU'),width=settings.get('width',640),
                height=settings.get('height',384),steps=settings.get('steps',20)),ensure_ascii=False),encoding='utf-8')
            command=[sys.executable,'-u','-X','utf8',str(ROOT/'local_image_worker.py'),str(manifest)]
            result=subprocess.run(command,cwd=ROOT,timeout=1800)
            if result.returncode:
                raise RuntimeError(f'Tạo ảnh AI local thất bại (mã {result.returncode}). Xem lỗi OpenVINO phía trên.')
    finally:
        if os.name == 'nt':
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        lock_file.close()


def main():
    folder = Path(sys.argv[1]).resolve()
    data = json.loads((folder/'storyboard.json').read_text(encoding='utf-8'))
    config = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    ensure_ai_backgrounds(folder,data.get('bible'),data['scenes'],config.get('backgrounds',{}), '--force' in sys.argv)


if __name__ == '__main__':
    main()
