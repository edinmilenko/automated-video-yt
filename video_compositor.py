"""
video_compositor.py
───────────────────
Composites the Reddit card screenshots over a background gameplay video
and combines all TTS audio chunks into the final 9:16 YouTube Short.

Output: output/final_short.mp4
"""

from __future__ import annotations

import os
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
from moviepy.video.fx.all import crop, resize

# ── Configuration ──────────────────────────────────────────────────────────────

# Final Short dimensions (9:16 portrait)
SHORT_WIDTH  = 2160
SHORT_HEIGHT = 3840

OUTPUT_PATH = Path("output/final_short.mp4")

# Visual style for the card overlay
CARD_WIDTH_RATIO = 0.88          # card occupies 88% of frame width
CARD_VERTICAL_CENTER = 0.42      # vertical center point (0=top, 1=bottom)

# Dimming overlay on the background (0.0 = none, 1.0 = black)
BG_DIM_OPACITY = 0.45

# Export quality
EXPORT_FPS       = 60
EXPORT_CODEC     = "libx264"
EXPORT_AUDIO_CODEC = "aac"
EXPORT_PRESET    = "fast"
EXPORT_THREADS   = 4
EXPORT_BITRATE   = "8000k"


# ── Background processing ──────────────────────────────────────────────────────

def _prepare_background(bg_path: str | Path, total_duration: float) -> VideoFileClip:
    """
    Load background video, crop to 9:16, loop if shorter than needed,
    and trim to total_duration.
    """
    bg = VideoFileClip(str(bg_path), audio=False)

    # ── Crop to 9:16 ──────────────────────────────────────────────────────────
    target_ratio = SHORT_WIDTH / SHORT_HEIGHT
    src_ratio    = bg.w / bg.h

    if src_ratio > target_ratio:
        # Wider than 9:16 → crop horizontally
        new_w = int(bg.h * target_ratio)
        x1    = (bg.w - new_w) // 2
        bg    = crop(bg, x1=x1, width=new_w)
    elif src_ratio < target_ratio:
        # Taller than 9:16 → crop vertically
        new_h = int(bg.w / target_ratio)
        y1    = (bg.h - new_h) // 2
        bg    = crop(bg, y1=y1, height=new_h)

    bg = bg.resize((SHORT_WIDTH, SHORT_HEIGHT))

    # ── Loop if background is shorter than needed ──────────────────────────────
    if bg.duration < total_duration:
        loops = int(total_duration / bg.duration) + 1
        bg    = concatenate_videoclips([bg] * loops)

    bg = bg.subclip(0, total_duration)
    return bg


# ── Card overlay ───────────────────────────────────────────────────────────────

def _build_card_overlay(
    frame_paths: List[str],
    durations: List[float],
) -> CompositeVideoClip:
    """
    Turn screenshots into ImageClips, resize to fit the frame width,
    and concatenate them so each holds for its audio chunk's duration.
    """
    clips = []
    card_pixel_width = int(SHORT_WIDTH * CARD_WIDTH_RATIO)

    for path, dur in zip(frame_paths, durations):
        clip = (
            ImageClip(path)
            .set_duration(dur)
            .resize(width=card_pixel_width)   # height is auto-proportional
        )
        clips.append(clip)

    # Stack sequentially (each card state holds until next chunk starts)
    overlay = concatenate_videoclips(clips, method="compose")

    # Center horizontally, anchor vertically
    x_pos = (SHORT_WIDTH  - card_pixel_width) // 2
    y_pos = int(SHORT_HEIGHT * CARD_VERTICAL_CENTER - overlay.h / 2)
    y_pos = max(80, y_pos)  # never clip off the top

    overlay = overlay.set_position((x_pos, y_pos))
    return overlay


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

    Parameters
    ----------
    chunks          : Output of tts_chunker.generate_chunks_with_audio()
    frame_paths     : Output of playwright_renderer.render_frames()
    bg_video_path   : Path to background gameplay video.
    output_path     : Where to write the final .mp4

    Returns
    -------
    Path to the exported video as a string.
    """
    if len(chunks) != len(frame_paths):
        raise ValueError(
            f"Mismatch: {len(chunks)} audio chunks but {len(frame_paths)} frames. "
            "Every chunk must have a corresponding frame."
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    durations     = [c["duration"] for c in chunks]
    total_duration = sum(durations)

    print(f"[Compositor] Total duration: {total_duration:.2f}s  ({len(chunks)} chunks)")

    # ── 1. Background ──────────────────────────────────────────────────────────
    print("[Compositor] Preparing background …")
    bg = _prepare_background(bg_video_path, total_duration)

    # ── 2. Dim overlay ─────────────────────────────────────────────────────────
    dim = ColorClip(
        size=(SHORT_WIDTH, SHORT_HEIGHT),
        color=(0, 0, 0),
        duration=total_duration,
    ).set_opacity(BG_DIM_OPACITY)

    # ── 3. Card overlay ────────────────────────────────────────────────────────
    print("[Compositor] Building card overlay …")
    card_overlay = _build_card_overlay(frame_paths, durations)

    # ── 4. Audio ───────────────────────────────────────────────────────────────
    print("[Compositor] Assembling audio …")
    final_audio = _build_audio_track(chunks)

    # ── 5. Composite ───────────────────────────────────────────────────────────
    print("[Compositor] Compositing layers …")
    final_video = CompositeVideoClip(
        [bg, dim, card_overlay],
        size=(SHORT_WIDTH, SHORT_HEIGHT),
    ).set_audio(final_audio)

    # ── 6. Export ──────────────────────────────────────────────────────────────
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

    # Clean up open file handles
    final_video.close()
    bg.close()
    final_audio.close()

    print(f"[Compositor] Done → {output_path.resolve()}")
    return str(output_path.resolve())


# ── CLI smoke-test (no bg video needed, skips compositor) ─────────────────────

if __name__ == "__main__":
    print("Run main.py to execute the full pipeline.")
