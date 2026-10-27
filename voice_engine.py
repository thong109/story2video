"""Windows offline speech and Edge online speech shared by preview/render."""
import asyncio
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import wave
from media_tools import ffmpeg_executable, run_ffmpeg

PIPER_LOCK = threading.Lock()
PIPER_CACHE = {}
MODEL_DIR = Path(os.environ.get("STORY_VOICE_MODELS", str(Path(__file__).resolve().parent.parent / "tool/models/voices")))

def piper_models():
    models = {}
    for directory in (MODEL_DIR, Path(__file__).resolve().parent / 'models/voices'):
        for path in directory.glob('*.onnx'):
            if Path(str(path) + '.json').exists():
                models['piper:' + path.stem] = path
    return models


def piper_voices():
    names = {'ngocngan3701': 'Nguyễn Ngọc Ngạn · Kể chuyện', 'ngochuyennew': 'Ngọc Huyền · Review phim',
             'adam1': 'Adam', 'en_US-ryan-high': 'Ryan · English', 'manhdung': 'Mạnh Dũng',
             'minhquang': 'Minh Quang', 'banmai': 'Ban Mai'}
    return [dict(id=key, name=names.get(path.stem, path.stem),
                 language='en-US' if path.stem.startswith('en_') else 'vi-VN', provider='local')
            for key, path in sorted(piper_models().items())]


def _piper(text, voice, output, rate, profile):
    from piper import PiperVoice, SynthesisConfig
    if voice not in {v["id"] for v in piper_voices()}:
        raise ValueError("Không tìm thấy model giọng local.")
    with PIPER_LOCK:
        model = PIPER_CACHE.get(voice)
        if model is None:
            model = PiperVoice.load(piper_models()[voice])
            PIPER_CACHE[voice] = model
        speed = max(0.5, min(2.0, 1 + float(rate.rstrip("%")) / 100))
        with wave.open(str(output), "wb") as wav:
            model.synthesize_wav(text, wav, syn_config=SynthesisConfig(length_scale=1 / (speed * profile.get("speed", 1)), noise_scale=profile.get("expression", 0.667), noise_w_scale=profile.get("variation", 0.8)))



def _powershell(script, payload=None):
    env = os.environ.copy()
    if payload is not None:
        env['STORY_VOICE_PAYLOAD'] = json.dumps(payload, ensure_ascii=True)
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    result = subprocess.run(
        [str(Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'),
         '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
        env=env, capture_output=True, timeout=120, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('Không chạy được giọng local Windows.')
    return result.stdout.decode('utf-8-sig').strip()


_SETUP = '''$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;
Add-Type -AssemblyName System.Speech;
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;
'''


def local_voices():
    if os.name != 'nt':
        return []
    raw = _powershell(_SETUP + '''try {
@($s.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object {
@{id=('local:' + $_.VoiceInfo.Name); name=$_.VoiceInfo.Name; language=$_.VoiceInfo.Culture.Name; provider='local'}
}) | ConvertTo-Json -Compress
} finally { $s.Dispose() }''')
    result = json.loads(raw or '[]')
    return result if isinstance(result, list) else [result]


def voice_options():
    options = piper_voices() + [
        dict(id='vi-VN-NamMinhNeural', name='Nam Minh · Nam', language='vi-VN', provider='edge'),
        dict(id='vi-VN-HoaiMyNeural', name='Hoài My · Nữ', language='vi-VN', provider='edge')]
    error = ''
    try:
        options += local_voices()
    except Exception as exc:
        error = str(exc)
    return options, error


async def _synthesize_to_file(text, voice, path, rate='+0%', profile=None):
    profile = profile or {}
    if not voice.startswith(('local:', 'piper:')):
        import edge_tts
        await edge_tts.Communicate(text, voice, rate=rate).save(str(path))
        return
    with tempfile.TemporaryDirectory(prefix='story_voice_', dir=Path(path).resolve().parent) as directory:
        wav = Path(directory) / 'speech.wav'
        if voice.startswith('piper:'):
            await asyncio.to_thread(_piper, text, voice, wav, rate, profile)
        else:
            await asyncio.to_thread(_powershell, _SETUP + '''try {
$p = $env:STORY_VOICE_PAYLOAD | ConvertFrom-Json;
$s.SelectVoice($p.voice);
$s.SetOutputToWaveFile($p.path);
$s.Speak($p.text);
} finally { $s.Dispose() }''', dict(voice=voice[6:], text=text, path=str(wav)))
        filters = []
        pitch = max(-4, min(4, float(profile.get('pitch_semitones', 0))))
        if pitch:
            with wave.open(str(wav)) as audio:
                sample_rate = audio.getframerate()
            factor = 2 ** (pitch / 12)
            filters += [f'asetrate={sample_rate * factor}', f'aresample={sample_rate}', f'atempo={1 / factor}']
        if 'loudness_lufs' in profile:
            target = max(-24, min(-14, float(profile['loudness_lufs'])))
            filters.append(f'loudnorm=I={target}:TP=-2:LRA=9')
        command = [ffmpeg_executable(), '-y', '-loglevel', 'error', '-i', str(wav)]
        if filters:
            command += ['-af', ','.join(filters)]
        command += [str(path)]
        result = await asyncio.to_thread(run_ffmpeg, command[1:], capture_output=True)
        if result.returncode:
            raise RuntimeError('Không chuyển được âm thanh local: ' + result.stderr.decode(errors='replace'))


async def synthesize(text, voice, path, rate='+0%', profile=None):
    """Publish only a complete, decodable speech file."""
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not str(text).strip():
        raise ValueError('Cảnh không có nội dung để đọc.')
    last_error = None
    with tempfile.TemporaryDirectory(prefix='audio_', dir=target.parent) as directory:
        temporary = Path(directory) / ('speech' + target.suffix)
        for attempt in range(2):
            try:
                await _synthesize_to_file(text, voice, temporary, rate=rate, profile=profile)
                for validation_attempt in range(2):
                    check = await asyncio.to_thread(run_ffmpeg,
                        [ '-nostdin', '-v', 'error', '-xerror', '-threads', '1', '-i', str(temporary), '-vn', '-f', 'null', '-'],
                        capture_output=True, timeout=120)
                    if check.returncode >= 0:
                        break
                if check.returncode or not temporary.exists() or temporary.stat().st_size < 100:
                    raise RuntimeError(f'Tệp giọng đọc không hợp lệ (mã {check.returncode}): ' + check.stderr.decode(errors='replace').strip())
                temporary.replace(target)
                return
            except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                last_error = exc
                temporary.unlink(missing_ok=True)
        raise RuntimeError(f'Không tạo được âm thanh hợp lệ cho giọng {voice}: {last_error}')
