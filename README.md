# Reddit Shorts Generator

Fully automated pipeline that turns a Reddit-style post (title + body text) into a
YouTube Short (1080×1920, 9:16). No Reddit API or scraping required.

```
reddit_shorts/
├── template.html          ← Reddit dark-mode UI (Playwright renders this)
├── tts_chunker.py         ← Splits text, generates per-chunk TTS MP3s
├── playwright_renderer.py ← Screenshots of progressive DOM expansion
├── video_compositor.py    ← MoviePy compositing into final Short
├── main.py                ← Orchestrator / CLI entry point
└── requirements.txt
```

---

## Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

---

## Usage

### Minimal (no background video — frames + audio only)
```bash
python main.py
```

### Full pipeline with background gameplay
```bash
python main.py --bg path/to/gameplay.mp4
```

### Custom content + voice
```bash
python main.py \
  --title "TIFU by accidentally emailing my CEO" \
  --body  "So this happened last Tuesday..." \
  --bg    subway_surfers.mp4 \
  --voice en-US-JennyNeural \
  --output output/my_short.mp4
```

### Available edge-tts voices (recommended)
| Voice                    | Style       |
|--------------------------|-------------|
| en-US-ChristopherNeural  | Deep, calm  |
| en-US-JennyNeural        | Friendly    |
| en-GB-RyanNeural         | British     |
| en-AU-WilliamNeural      | Australian  |

List all voices: `edge-tts --list-voices`

---

## Output structure
```
output/
├── audio/
│   ├── chunk_000.mp3   ← Title TTS
│   ├── chunk_001.mp3   ← Paragraph 1
│   └── ...
├── frames/
│   ├── frame_000.png   ← Title only
│   ├── frame_001.png   ← Title + paragraph 1
│   └── ...
└── final_short.mp4     ← Composited 9:16 video
```

---

## How it works

1. **TTS & Chunking** (`tts_chunker.py`)
   - Splits body text on double-newlines; further splits long paragraphs at sentence boundaries.
   - Generates a separate `.mp3` per chunk using `edge-tts`.
   - Measures each MP3's exact duration with `mutagen`.

2. **Playwright Rendering** (`playwright_renderer.py`)
   - Loads `template.html` in a headless Chromium instance.
   - Injects the title into `#post-title`.
   - For each body chunk: appends a `<p class="post-paragraph">` then adds the `visible` class, triggering the CSS `max-height` transition.
   - Waits 450 ms for the transition to complete, then screenshots.
   - Returns a list of `frame_NNN.png` paths.

3. **MoviePy Compositing** (`video_compositor.py`)
   - Crops/resizes background video to 1080×1920.
   - Adds a semi-transparent dim overlay for contrast.
   - Each `frame_NNN.png` becomes an `ImageClip` whose duration = corresponding MP3 duration.
   - `concatenate_videoclips` stitches frames; `concatenate_audioclips` stitches MP3s.
   - `CompositeVideoClip` layers: background → dim → card overlay.
   - Exports with H.264/AAC at 8 Mbps.

---

## Customisation tips

| What to change              | Where                        |
|-----------------------------|------------------------------|
| Subreddit name / username   | `template.html` `.card-header` |
| Card width on screen        | `video_compositor.py` `CARD_WIDTH_RATIO` |
| Card vertical position      | `video_compositor.py` `CARD_VERTICAL_CENTER` |
| Background dim amount       | `video_compositor.py` `BG_DIM_OPACITY` |
| Text chunk max length       | `tts_chunker.py` `MAX_CHUNK_CHARS` |
| CSS expand transition speed | `template.html` `.post-paragraph` transition |
