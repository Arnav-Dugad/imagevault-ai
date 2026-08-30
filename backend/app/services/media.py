import json
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from io import BytesIO
from pathlib import Path

from PIL import ExifTags, Image as PillowImage, ImageOps

from app.core.config import get_settings
from app.models import MediaKind
from app.services.images import MIME_EXTENSIONS, RAW_MIME_TYPES, VIDEO_MIME_TYPES, media_kind_for


@dataclass(frozen=True)
class DecodedMedia:
    frames: list[PillowImage.Image]
    primary: PillowImage.Image
    width: int
    height: int
    frame_count: int
    duration_seconds: float | None
    media_kind: MediaKind
    exif_timestamp: datetime | None = None
    camera_model: str | None = None


def _sample_indices(total: int, limit: int) -> list[int]:
    total = max(1, total)
    count = min(total, max(1, limit))
    if count == 1:
        return [0]
    return sorted({round(index * (total - 1) / (count - 1)) for index in range(count)})


def _photo_metadata(source: PillowImage.Image) -> tuple[datetime | None, str | None]:
    timestamp: datetime | None = None
    camera: str | None = None
    try:
        exif = source.getexif()
        model_value = exif.get(ExifTags.Base.Model.value)
        camera = str(model_value)[:200] if model_value else None
        date_value = exif.get(ExifTags.Base.DateTimeOriginal.value)
        if date_value:
            timestamp = datetime.strptime(str(date_value), "%Y:%m:%d %H:%M:%S").replace(
                tzinfo=UTC
            )
    except (ValueError, TypeError, AttributeError):
        pass
    return timestamp, camera


def _decode_pillow(data: bytes, mime_type: str) -> DecodedMedia:
    if mime_type in {"image/heic", "image/heif"}:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    settings = get_settings()
    with PillowImage.open(BytesIO(data)) as source:
        width, height = source.size
        total = max(1, int(getattr(source, "n_frames", 1)))
        timestamp, camera = _photo_metadata(source)
        frames: list[PillowImage.Image] = []
        duration_ms = 0
        for index in _sample_indices(total, settings.media_sample_frames):
            source.seek(index)
            frame = ImageOps.exif_transpose(source.copy()).convert("RGB")
            frame.thumbnail((1600, 1600), PillowImage.Resampling.LANCZOS)
            frames.append(frame)
            duration_ms += int(source.info.get("duration", 0) or 0)
        primary = frames[0]
        duration = None
        if total > 1:
            sampled_average = duration_ms / max(1, len(frames))
            duration = round(sampled_average * total / 1000.0, 3)
        return DecodedMedia(
            frames=frames,
            primary=primary,
            width=width,
            height=height,
            frame_count=total,
            duration_seconds=duration,
            media_kind=media_kind_for(mime_type, frame_count=total),
            exif_timestamp=timestamp,
            camera_model=camera,
        )


def _decode_raw(data: bytes, mime_type: str) -> DecodedMedia:
    import rawpy

    with rawpy.imread(BytesIO(data)) as raw:
        pixels = raw.postprocess(use_camera_wb=True, output_bps=8, no_auto_bright=False)
        camera = None
        try:
            camera = str(raw.metadata.camera_model or "")[:200] or None
        except AttributeError:
            pass
    image = PillowImage.fromarray(pixels, mode="RGB")
    width, height = image.size
    image.thumbnail((1600, 1600), PillowImage.Resampling.LANCZOS)
    return DecodedMedia(
        frames=[image],
        primary=image,
        width=width,
        height=height,
        frame_count=1,
        duration_seconds=None,
        media_kind=MediaKind.RAW,
        camera_model=camera,
    )


def _safe_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _decode_video(data: bytes, mime_type: str) -> DecodedMedia:
    settings = get_settings()
    suffix = MIME_EXTENSIONS.get(mime_type, ".video")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
            temporary.write(data)
            temporary_path = Path(temporary.name)
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,nb_frames,r_frame_rate,duration:format=duration",
                "-of",
                "json",
                str(temporary_path),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        metadata = json.loads(probe.stdout)
        streams = metadata.get("streams") or []
        if not streams:
            raise ValueError("Video contains no decodable picture stream")
        stream = streams[0]
        width, height = int(stream.get("width") or 0), int(stream.get("height") or 0)
        if width <= 0 or height <= 0:
            raise ValueError("Video dimensions are unavailable")
        duration = _safe_float(stream.get("duration")) or _safe_float(
            (metadata.get("format") or {}).get("duration")
        )
        frame_count = int(stream.get("nb_frames") or 0)
        try:
            frame_rate = float(Fraction(stream.get("r_frame_rate") or "0"))
        except (ValueError, ZeroDivisionError):
            frame_rate = 0.0
        if frame_count <= 0 and duration:
            frame_count = max(1, round(duration * frame_rate)) if frame_rate > 0 else 1
        frame_count = max(1, frame_count)
        sample_count = min(settings.media_sample_frames, frame_count)
        if frame_rate > 0:
            sampled_frames = _sample_indices(frame_count, sample_count)
            seek_margin = min(0.02, 0.25 / frame_rate)
            timestamps = [max(0.0, index / frame_rate - seek_margin) for index in sampled_frames]
        elif duration and duration > 0.1:
            timestamps = [duration * index / sample_count for index in range(sample_count)]
        else:
            timestamps = [0.0]
        frames: list[PillowImage.Image] = []
        for timestamp in timestamps:
            extracted = subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-ss",
                    f"{max(0.0, timestamp):.6f}",
                    "-i",
                    str(temporary_path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=1280:-2:force_original_aspect_ratio=decrease",
                    "-f",
                    "image2pipe",
                    "-vcodec",
                    "png",
                    "pipe:1",
                ],
                check=True,
                capture_output=True,
                timeout=45,
            )
            # Some FFmpeg builds return success but an empty pipe when a seek
            # lands just beyond the final presentation timestamp. Other valid
            # samples are still useful, so skip only that missing frame.
            if not extracted.stdout:
                continue
            try:
                with PillowImage.open(BytesIO(extracted.stdout)) as frame:
                    frames.append(frame.convert("RGB"))
            except OSError:
                continue
        if not frames:
            raise ValueError("No representative video frames could be decoded")
        primary = frames[len(frames) // 2]
        return DecodedMedia(
            frames=frames,
            primary=primary,
            width=width,
            height=height,
            frame_count=frame_count,
            duration_seconds=round(duration, 3) if duration is not None else None,
            media_kind=MediaKind.VIDEO,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        detail = getattr(exc, "stderr", b"")
        message = detail.decode("utf-8", errors="ignore").strip()[-500:]
        raise ValueError(f"Video decoding failed{': ' + message if message else ''}") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def decode_media(data: bytes, mime_type: str) -> DecodedMedia:
    if mime_type in VIDEO_MIME_TYPES:
        return _decode_video(data, mime_type)
    if mime_type in RAW_MIME_TYPES:
        return _decode_raw(data, mime_type)
    return _decode_pillow(data, mime_type)
