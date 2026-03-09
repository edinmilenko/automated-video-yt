"""
video_compositor.py
───────────────────
Composites the Reddit card screenshots over a background gameplay video
and combines all TTS audio chunks into the final 9:16 YouTube Short.

Output: output/final_short.mp4
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict

from moviepy.editor import (
    VideoFileClip,
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_audioclips,
    concatenate_videoclips,
    ColorClip,
)
from moviepy.video.fx.all import crop

# ── Configuration ──────────────────────────────────────────────────────────────

SHORT_WIDTH  = 1080
SHORT_HEIGHT = 1920

OUTPUT_PATH = Path("output/final_short.mp4")

# Card occupies this fraction of frame width
CARD_WIDTH_RATIO = 0.88

# Distance from the top of the frame where the card starts (in pixels)
CARD_TOP_MARGIN = 180

# Dimming overlay on the background
BG_DIM_OPACITY = 0.45

# Export quality
EXPORT_FPS         = 60
EXPORT_CODEC       = "libx264"
EXPORT_AUDIO_CODEC = "aac"
EXPORT_PRESET      = "fast"
EXPORT_THREADS     = 4
EXPORT_BITRATE     = "8000k"


# ── Background processing ──────────────────────────────────────────────────────

def _prepare_background(bg_path: str | Path, total_duration: float) -> VideoFileClip:
    """Load background video, crop to 9:16, loop if needed, trim to duration."""
    bg = VideoFileClip(str(bg_path), audio=False)

    target_ratio = SHORT_WIDTH / SHORT_HEIGHT
    src_ratio    = bg.w / bg.h

    if src_ratio > target_ratio:
        new_w = int(bg.h * target_ratio)
        x1    = (bg.w - new_w) // 2
        bg    = crop(bg, x1=x1, width=new_w)
    elif src_ratio < target_ratio:
        new_h = int(bg.w / target_ratio)
        y1    = (bg.h - new_h) // 2
        bg    = crop(bg, y1=y1, height=new_h)

    bg = bg.resize((SHORT_WIDTH, SHORT_HEIGHT))

    if bg.duration < total_duration:
        loops = int(total_duration / bg.duration) + 1
        bg    = concatenate_videoclips([bg] * loops)

    return bg.subclip(0, total_duration)


# ── Card overlay ───────────────────────────────────────────────────────────────

def _build_card_clips(
    frame_paths: List[str],
    durations: List[float],
) -> List[ImageClip]:
    """
    Turn screenshots into ImageClips positioned at a fixed top-left anchor.
    Each frame is sized to card_pixel_width; height is auto-proportional.
    The card is placed at a fixed X and fixed TOP Y — it only grows downward.
    """
    card_pixel_width = int(SHORT_WIDTH * CARD_WIDTH_RATIO)
    x_pos = (SHORT_WIDTH - card_pixel_width) // 2   # horizontally centered
    y_pos = CARD_TOP_MARGIN                          # fixed top anchor

    clips = []
    for path, dur in zip(frame_paths, durations):
        clip = (
            ImageClip(path)
            .set_duration(dur)
            .resize(width=card_pixel_width)
            .set_position((x_pos, y_pos))   # top-left corner fixed
        )
        clips.append(clip)

    return clips


# ── Audio assembly ─────────────────────────────────────────────────────────────

def _build_audio_track(chunks: List[Dict]) -> AudioFileClip:
    """Concatenate all per-chunk MP3s into a single audio track."""
    audio_clips = [AudioFileClip(c["audio_path"]) for c in chunks]
    return concatenate_audioclips(audio_clips)


# ── Public API ─────────────────────────────────────────────────────────────────

def composite_video(
    chunks: List[Dict],
    frame_paths: List[str],
    bg_video_path: str | Path,
    output_path: str | Path = OUTPUT_PATH,
) -> str:
    """
    Composite everything into the final Short.

    Because each frame screenshot already has the full cumulative card state
    (title + all paragraphs so far), we place each ImageClip at the SAME
    fixed top position. The card visually grows downward as new frames appear.
    """
    if len(chunks) != len(frame_paths):
        raise ValueError(
            f"Mismatch: {len(chunks)} audio chunks but {len(frame_paths)} frames."
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    durations      = [c["duration"] for c in chunks]
    total_duration = sum(durations)

    print(f"[Compositor] Total duration: {total_duration:.2f}s  ({len(chunks)} chunks)")

    # 1. Background
    print("[Compositor] Preparing background …")
    bg = _prepare_background(bg_video_path, total_duration)

    # 2. Dim overlay
    dim = ColorClip(
        size=(SHORT_WIDTH, SHORT_HEIGHT),
        color=(0, 0, 0),
        duration=total_duration,
    ).set_opacity(BG_DIM_OPACITY)

    # 3. Card clips — each at fixed top position, duration = its chunk audio
    print("[Compositor] Building card overlay …")
    card_clips = _build_card_clips(frame_paths, durations)

    # 4. Audio
    print("[Compositor] Assembling audio …")
    final_audio = _build_audio_track(chunks)

    # 5. Composite: bg + dim + all card clips (each with its own start time)
    print("[Compositor] Compositing layers …")

    # Set start times so clips play sequentially
    t = 0.0
    timed_clips = []
    for clip, dur in zip(card_clips, durations):
        timed_clips.append(clip.set_start(t))
        t += dur

    final_video = CompositeVideoClip(
        [bg, dim] + timed_clips,
        size=(SHORT_WIDTH, SHORT_HEIGHT),
    ).set_audio(final_audio)

    # 6. Export
    print(f"[Compositor] Exporting → {output_path}")
    final_video.write_videofile(
        str(output_path),
        fps=EXPORT_FPS,
        codec=EXPORT_CODEC,
        audio_codec=EXPORT_AUDIO_CODEC,
        preset=EXPORT_PRESET,
        threads=EXPORT_THREADS,
        bitrate=EXPORT_BITRATE,
        logger="bar",
    )

    final_video.close()
    bg.close()
    final_audio.close()

    print(f"[Compositor] Done → {output_path.resolve()}")
    return str(output_path.resolve())


if __name__ == "__main__":
    print("Run main.py to execute the full pipeline.")
