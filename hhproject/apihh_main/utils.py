import os
import tempfile
from pathlib import Path

from moviepy.video.io.VideoFileClip import VideoFileClip

MAX_VIDEO_SIZE_MB = 100
MIN_DURATION = 5
MAX_DURATION = 90


def _build_temp_video_file(uploaded_file):
    suffix = Path(getattr(uploaded_file, 'name', '')).suffix or '.mp4'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        if hasattr(uploaded_file, 'chunks'):
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
        else:
            data = uploaded_file.read()
            if data:
                tmp.write(data)
        temp_path = tmp.name

    if hasattr(uploaded_file, 'seek'):
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

    return temp_path


def _resolve_video_path(file_source):
    if isinstance(file_source, (str, Path)):
        return str(file_source), None

    if hasattr(file_source, 'temporary_file_path'):
        try:
            return file_source.temporary_file_path(), None
        except Exception:
            pass

    temp_path = _build_temp_video_file(file_source)
    return temp_path, temp_path


def validate_video(file_source, file_size=None):
    errors = []
    temp_path_to_delete = None

    try:
        file_path, temp_path_to_delete = _resolve_video_path(file_source)
    except Exception as exc:
        return [f'Ошибка подготовки видео: {str(exc)}']

    if file_size is None and os.path.exists(file_path):
        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            file_size = None

    if file_size is not None and file_size > MAX_VIDEO_SIZE_MB * 1024 * 1024:
        errors.append('Видео слишком большое')

    try:
        with VideoFileClip(file_path) as clip:
            width, height = clip.size
            duration = clip.duration

        # разрешаем 9:16, 1:1, 4:5
        if width > height:
            errors.append('Горизонтальные видео запрещены')

        if duration < MIN_DURATION or duration > MAX_DURATION:
            errors.append('Недопустимая длительность видео')

    except Exception as e:
        errors.append(f'Ошибка обработки видео: {str(e)}')
    finally:
        if temp_path_to_delete and os.path.exists(temp_path_to_delete):
            try:
                os.remove(temp_path_to_delete)
            except OSError:
                pass

    return errors
