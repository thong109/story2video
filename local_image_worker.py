"""Isolated OpenVINO inference, released before speech/video rendering."""
import json
import os
from pathlib import Path
import sys
import time


def main():
    manifest = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    cache = Path(manifest['cache_dir'])
    cache.mkdir(parents=True, exist_ok=True)
    os.environ['TMP'] = os.environ['TEMP'] = str(cache)
    os.environ['HF_HOME'] = str(cache / 'huggingface')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    print('Đang nạp Stable Diffusion 1.5 local…', flush=True)
    import logging
    logging.getLogger('optimum.intel.openvino.modeling_base').setLevel(logging.ERROR)
    logging.getLogger('diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion').setLevel(logging.ERROR)
    import torch
    from optimum.intel import OVStableDiffusionPipeline
    device = manifest.get('device', 'GPU')
    pipe = OVStableDiffusionPipeline.from_pretrained(
        manifest['model_dir'], local_files_only=True, device=device, compile=False,
        safety_checker=None, requires_safety_checker=False,
        ov_config={'CACHE_DIR': str(cache / 'compiled'), 'PERFORMANCE_HINT':'LATENCY'})
    pipe.half()
    pipe.reshape(batch_size=1, height=manifest['height'], width=manifest['width'], num_images_per_prompt=1)
    print(f'Đang biên dịch model trên {device} lần đầu; các lần sau dùng cache…', flush=True)
    pipe.compile()
    for i, item in enumerate(manifest['images']):
        print(f"Tạo nền AI {i+1}/{len(manifest['images'])}: {item['name']}", flush=True)
        generator = torch.Generator(device='cpu').manual_seed(item['seed'])
        image = pipe(item['prompt'], negative_prompt=item['negative'],
                     width=manifest['width'], height=manifest['height'],
                     num_inference_steps=manifest['steps'], guidance_scale=7.0, generator=generator).images[0]
        if max(image.convert('RGB').getextrema()[channel][1] for channel in range(3)) <= 2:
            raise RuntimeError('GPU trả về ảnh đen. Thử chuyển background device sang CPU.')
        output = Path(item['output'])
        temporary = output.with_suffix('.part.png')
        from PIL import ImageOps
        ImageOps.fit(image, (1280,720)).save(temporary)
        temporary.replace(output)
        output.with_suffix('.json').write_text(json.dumps(dict(item, model=manifest['model_dir'],
            device=device, steps=manifest['steps'], created=time.time()),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Đã tạo xong background AI local.', flush=True)


if __name__ == '__main__':
    main()
