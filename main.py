"""
main.py
───────
Orchestrates the full Reddit Shorts pipeline:
  1. TTS & chunking      (tts_chunker.py)
  2. Playwright frames   (playwright_renderer.py)
  3. Video compositing   (video_compositor.py)

Usage:
    python main.py
    python main.py --bg path/to/gameplay.mp4
    python main.py --voice en-GB-RyanNeural --bg gameplay.mp4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tts_chunker import generate_chunks_with_audio
from playwright_renderer import render_frames
from video_compositor import composite_video

# ── Sample content (replace or wire up to user input / CLI) ───────────────────

SAMPLE_TITLE = "TIFU by accidentally sending my boss a meme instead of the quarterly report"

SAMPLE_BODY = """
So this happened yesterday and I'm still cringing about it.

I work as a data analyst at a mid-size insurance company. My boss had been on my case all week about the Q3 report — deadlines, you know how it is.

I finally finished it at around 11 PM, absolutely exhausted. I'd been texting my friend all evening, sending dumb memes back and forth to decompress.

Here's where I messed up. When I opened my email to send the report, I had my phone in the other hand. Without even looking, I attached the last file I'd shared — which was a gif of a cat violently slapping things off a table — and hit send.

I only realized what happened when my boss replied two minutes later: "Is this your quarterly report?" followed by a laughing emoji.

I wanted to dissolve into the floor right then and there. Sent the actual report immediately with a very long apology. He said it made his night.

TL;DR: Sent my exhausted boss a cat-slapping meme instead of Q3 financials. He found it hilarious. I did not.
"""


# ── Pipeline ───────────────────────────────────────────────────────────────────

def run(
    title: str,
    body: str,
    bg_video: str | None,
    voice: str = "en-US-ChristopherNeural",
    output: str = "output/final_short.mp4",
) -> None:
    print("=" * 60)
    print("  Reddit Shorts Generator  —  Full Pipeline")
    print("=" * 60)

    # ── Step 1: TTS ───────────────────────────────────────────────────────────
    print("\n[Step 1/3]  TTS & Chunking")
    chunks = generate_chunks_with_audio(
        title=title,
        body_text=body,
        voice=voice,
    )

    # ── Step 2: Playwright frames ─────────────────────────────────────────────
    print("\n[Step 2/3]  Playwright Rendering")
    frame_paths = render_frames(chunks)

    # ── Step 3: Video compositing ─────────────────────────────────────────────
    if bg_video:
        print("\n[Step 3/3]  Video Compositing")
        out = composite_video(
            chunks=chunks,
            frame_paths=frame_paths,
            bg_video_path=bg_video,
            output_path=output,
        )
        print(f"\n✅  Short exported to: {out}")
    else:
        print("\n[Step 3/3]  Skipped  (no --bg video provided)")
        print("           Frames saved to: output/frames/")
        print("           Audio saved to:  output/audio/")
        print("\n  To finish, run with:  --bg path/to/gameplay.mp4")

    print("\n" + "=" * 60)


# ── Entry point ────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate a Reddit-style YouTube Short from text."
    )
    p.add_argument("--title",   default=SAMPLE_TITLE,  help="Post title string")
    p.add_argument("--body",    default=SAMPLE_BODY,   help="Post body text")
    p.add_argument("--bg",      default=None,          help="Path to background gameplay video")
    p.add_argument("--voice",   default="en-US-ChristopherNeural",
                   help="edge-tts voice name (default: en-US-ChristopherNeural)")
    p.add_argument("--output",  default="output/final_short.mp4",
                   help="Output video path")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(
        title=args.title,
        body=args.body,
        bg_video=args.bg,
        voice=args.voice,
        output=args.output,
    )
