"""
playwright_renderer.py
──────────────────────
Uses Playwright (sync API) to load template.html, progressively inject
text chunks into the DOM, and capture a screenshot after each injection.

Returned: list of screenshot paths in order  [frame_000.png, frame_001.png, …]
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import List, Dict

from playwright.sync_api import sync_playwright, Page

# ── Configuration ──────────────────────────────────────────────────────────────

TEMPLATE_PATH = Path(__file__).parent / "template.html"
SCREENSHOT_DIR = Path("output/frames")

# Width of the browser viewport (height is auto)
VIEWPORT_WIDTH = 600
VIEWPORT_HEIGHT = 900   # enough room; card height is content-driven

# How long (ms) to wait after DOM mutation for layout recalculation + CSS transitions
LAYOUT_SETTLE_MS = 450


# ── DOM manipulation helpers ───────────────────────────────────────────────────

_JS_SET_TITLE = """
(title) => {
    document.getElementById('post-title').textContent = title;
}
"""

_JS_ADD_PARAGRAPH = """
(text) => {
    const container = document.getElementById('paragraphs-container');
    const p = document.createElement('p');
    p.className = 'post-paragraph';
    p.textContent = text;
    container.appendChild(p);

    // Force reflow before adding 'visible' so the transition fires
    p.getBoundingClientRect();
    p.classList.add('visible');
}
"""

_JS_GET_CARD_HEIGHT = """
() => {
    const card = document.querySelector('.card');
    return card ? card.getBoundingClientRect().height : 0;
}
"""


# ── Core renderer ──────────────────────────────────────────────────────────────

def render_frames(
    chunks: List[Dict],
    template_path: str | Path = TEMPLATE_PATH,
    screenshot_dir: str | Path = SCREENSHOT_DIR,
    viewport_width: int = VIEWPORT_WIDTH,
) -> List[str]:
    """
    Render a screenshot for every chunk in `chunks`.

    chunks[0] is treated as the **title**.
    chunks[1..] are body paragraphs that appear one at a time.

    Parameters
    ----------
    chunks          : Output of tts_chunker.generate_chunks_with_audio()
    template_path   : Path to template.html
    screenshot_dir  : Directory where frame PNGs will be saved
    viewport_width  : Browser viewport width in pixels

    Returns
    -------
    List of absolute paths to screenshot files, in order.
    """
    template_path = Path(template_path).resolve()
    screenshot_dir = Path(screenshot_dir)
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    if not template_path.exists():
        raise FileNotFoundError(f"template.html not found at {template_path}")

    frame_paths: List[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )

        context = browser.new_context(
            viewport={"width": viewport_width, "height": VIEWPORT_HEIGHT},
            # Transparent background requires a special flag
            # We'll use a CSS transparent body; Playwright screenshots support PNG alpha
        )

        page: Page = context.new_page()

        # Load the template via file:// URL
        page.goto(template_path.as_uri(), wait_until="domcontentloaded")

        # Allow fonts / styles to fully settle
        page.wait_for_timeout(300)

        if not chunks:
            browser.close()
            return frame_paths

        # ── Frame 0: title only ────────────────────────────────────────────────
        title_text = chunks[0]["text"]
        page.evaluate(_JS_SET_TITLE, title_text)
        page.wait_for_timeout(LAYOUT_SETTLE_MS)

        frame_0 = _capture(page, screenshot_dir, 0)
        frame_paths.append(frame_0)
        print(f"[Renderer] frame_000  →  title: '{title_text[:50]}…'")

        # ── Frames 1+: body paragraphs ─────────────────────────────────────────
        for idx, chunk in enumerate(chunks[1:], start=1):
            text = chunk["text"]
            page.evaluate(_JS_ADD_PARAGRAPH, text)

            # Wait for CSS max-height transition to finish
            page.wait_for_timeout(LAYOUT_SETTLE_MS)

            frame_path = _capture(page, screenshot_dir, idx)
            frame_paths.append(frame_path)

            card_h = page.evaluate(_JS_GET_CARD_HEIGHT)
            print(f"[Renderer] frame_{idx:03d}  card_height={card_h:.0f}px  →  '{text[:50]}…'")

        browser.close()

    print(f"[Renderer] Done. {len(frame_paths)} frames saved to '{screenshot_dir}'")
    return frame_paths


# ── Screenshot helper ──────────────────────────────────────────────────────────

def _capture(page: Page, out_dir: Path, index: int) -> str:
    """Take a full-page PNG screenshot and return its path."""
    path = out_dir / f"frame_{index:03d}.png"
    page.screenshot(
        path=str(path),
        full_page=True,
        omit_background=True,   # ← questa riga rimuove lo sfondo bianco
    )
    return str(path)


# ── CLI smoke-test (requires template.html + dummy chunks) ─────────────────────

if __name__ == "__main__":
    dummy_chunks = [
        {"text": "TIFU by accidentally sending my boss a meme instead of the quarterly report",
         "audio_path": "", "duration": 4.0, "is_title": True},
        {"text": "So this happened yesterday and I'm still cringing.",
         "audio_path": "", "duration": 2.5, "is_title": False},
        {"text": "I work as a data analyst at a mid-size insurance company. My boss had been on my case all week about the Q3 report.",
         "audio_path": "", "duration": 5.0, "is_title": False},
        {"text": "I finally finished it at like 11 PM, absolutely exhausted. Then I grabbed my phone…",
         "audio_path": "", "duration": 4.0, "is_title": False},
    ]
    paths = render_frames(dummy_chunks)
    for p in paths:
        print(p)
