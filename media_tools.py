"""Use the bundled stable FFmpeg consistently for audio and video."""
from functools import lru_cache
import os
from pathlib import Path
import shutil


@lru_cache(maxsize=1)
def ffmpeg_executable():
    override = os.environ.get('STORY_FFMPEG')
    if override:
        if not Path(override).is_file():
            raise FileNotFoundError('Không tìm thấy STORY_FFMPEG', override)
        return override
    try:
        import imageio_ffmpeg
        executable = imageio_ffmpeg.get_ffmpeg_exe()
        if Path(executable).is_file():
            return executable
    except ImportError:
        pass
    executable = shutil.which('ffmpeg')
    if executable:
        return executable
    raise FileNotFoundError(2, 'Không tìm thấy FFmpeg', 'ffmpeg')


def ffmpeg_available():
    try:
        ffmpeg_executable()
        return True
    except OSError:
        return False


# Some Windows installs intermittently reject process creation or terminate
# a native decoder during startup. Retry those failures, never format errors.
def popen_ffmpeg(arguments, **kwargs):
    import subprocess
    import time
    for attempt in range(3):
        try:
            return subprocess.Popen([ffmpeg_executable(), *arguments], **kwargs)
        except OSError as exc:
            if getattr(exc, 'winerror', None) not in (5, 8, 1450) or attempt == 2:
                raise
            time.sleep(0.3 * (attempt + 1))


def run_ffmpeg(arguments, **kwargs):
    import subprocess
    import time
    for attempt in range(3):
        try:
            result = subprocess.run([ffmpeg_executable(), *arguments], **kwargs)
        except OSError as exc:
            if getattr(exc, 'winerror', None) not in (5, 8, 1450) or attempt == 2:
                raise
            time.sleep(0.3 * (attempt + 1))
            continue
        if result.returncode not in (3221225477, -1073741819) or attempt == 2:
            return result
        time.sleep(0.3 * (attempt + 1))
