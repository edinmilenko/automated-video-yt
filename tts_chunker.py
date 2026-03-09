"""
tts_chunker.py
──────────────
Splits body text into chunks, generates a per-chunk TTS .mp3 with edge-tts,
and returns a list of dicts: [{"text": str, "audio_path": str, "duration": float}]
"""

from __future__ import annotations

import asyncio
import os
import re
import textwrap
from pathlib import Path
from typing import List, Dict

import edge_tts
from mutagen.mp3 import MP3

# ── Configuration ──────────────────────────────────────────────────────────────

DEFAULT_VOICE = "en-US-ChristopherNeural"   # Deep, Reddit-story-friendly voice
AUDIO_OUTPUT_DIR = Path("output/audio")
MAX_CHUNK_CHARS = 500                        # Soft cap for a single paragraph chunk


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_mp3_duration(path: str | Path) -> float:
    """Return duration of an MP3 file in seconds using mutagen."""
    try:
        audio = MP3(str(path))
        return audio.info.length
    except Exception:
        # Fallback: estimate ~150 wpm
        word_count = len(Path(path).stem.split("_"))
        return word_count / 150 * 60


def _split_into_chunks(body_text: str) -> List[str]:
    """
    Split body_text into meaningful chunks.

    Strategy (in priority order):
      1. Split on double-newlines (explicit paragraphs).
      2. If a resulting segment is still very long, split further by sentence.
      3. Strip empty / whitespace-only chunks.
    """
    # First pass: paragraph breaks
    raw_paragraphs = re.split(r"\n{2,}", body_text.strip())

    chunks: List[str] = []
    for para in raw_paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(para) <= MAX_CHUNK_CHARS:
            chunks.append(para)
        else:
            # Split long paragraph by sentence boundary
            sentences = re.split(r"(?<=[.!?])\s+", para)
            current = ""
            for sent in sentences:
                if len(current) + len(sent) + 1 <= MAX_CHUNK_CHARS:
                    current = (current + " " + sent).strip()
                else:
                    if current:
                        chunks.append(current)
                    current = sent
            if current:
                chunks.append(current)

    return chunks


async def _generate_single_tts(text: str, path: Path, voice: str) -> None:
    """Generate a single TTS audio file asynchronously."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(path))


async def _generate_all_tts(
    items: List[Dict],
    voice: str,
) -> None:
    """Generate all TTS files concurrently (but edge-tts is usually rate-limited, so sequential)."""
    for item in items:
        await _generate_single_tts(item["text"], Path(item["audio_path"]), voice)


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_chunks_with_audio(
    title: str,
    body_text: str,
    output_dir: str | Path = AUDIO_OUTPUT_DIR,
    voice: str = DEFAULT_VOICE,
) -> List[Dict]:
    """
    Main entry point.

    Parameters
    ----------
    title       : Reddit post title string.
    body_text   : Full body text of the post.
    output_dir  : Directory where .mp3 files will be saved.
    voice       : edge-tts voice name.

    Returns
    -------
    List of dicts:
        [
          {"text": "...", "audio_path": "/path/to/chunk_0.mp3", "duration": 3.21},
          ...
        ]
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build ordered list: title first, then body chunks
    body_chunks = _split_into_chunks(body_text)
    all_texts = [title] + body_chunks

    # Pre-build metadata list
    items: List[Dict] = []
    for idx, text in enumerate(all_texts):
        audio_path = output_dir / f"chunk_{idx:03d}.mp3"
        items.append(
            {
                "text": text,
                "audio_path": str(audio_path),
                "duration": 0.0,  # filled in after generation
                "is_title": idx == 0,
            }
        )

    # Generate TTS (synchronous wrapper around async calls)
    print(f"[TTS] Generating {len(items)} audio chunks with voice '{voice}' …")
    asyncio.run(_generate_all_tts(items, voice))

    # Measure durations
    for item in items:
        item["duration"] = _get_mp3_duration(item["audio_path"])
        print(f"  chunk_{items.index(item):03d}  {item['duration']:.2f}s  →  {item['text'][:60]}…")

    print(f"[TTS] Done. Total audio: {sum(i['duration'] for i in items):.2f}s")
    return items


# ── CLI smoke-test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample_title = "TIFU by accidentally sending my boss a meme instead of the quarterly report"
    sample_body = """
So this happened yesterday and I'm still cringing.

I work as a data analyst at a mid-size insurance company.
My boss had been on my case all week about the Q3 report.
I finally finished it at like 11 PM, absolutely exhausted.

Here's where I messed up. I'd been texting my friend all evening,
sending dumb memes back and forth to decompress. When I opened
my email to send the report, I had my phone in my other hand.

Without even looking, I attached the last file I'd shared — which was
a gif of a cat violently slapping things off a table — and hit send.

I only realized what happened when my boss replied two minutes later:
"Is this your quarterly report?" with a laughing emoji.

I wanted to dissolve into the floor. Lesson learned: never multitask
when you're running on three hours of sleep.

TL;DR: Sent my exhausted boss a cat-slapping meme instead of Q3 financials.
He found it funny. I did not.
"""

    result = generate_chunks_with_audio(sample_title, sample_body)
    for r in result:
        print(r)
