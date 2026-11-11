"""Render one episode (hook + narration lines) into a vertical 1080x1920 Short.

Narration uses a VOICEVOX engine when VOICEVOX_URL is reachable, otherwise
falls back to Open JTalk (pyopenjtalk). Returns which voice was used so the
uploader can credit it.
"""
import colorsys
import hashlib
import os
import re
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SR = 1080, 1920, 30, 48000
CHANNEL = "30秒サイエンス"
OUTRO = "毎日ひとつ、科学の雑学をお届けします。"
GAP = 0.3  # silence after each segment, seconds
MARGIN = 100
NO_LINE_START = "、。，．！？）」』ー・％"

FONT_CANDIDATES = [
    os.environ.get("FONT_PATH", ""),
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
]


def font(size):
    for path in FONT_CANDIDATES:
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size)
    raise RuntimeError("No Japanese font found; set FONT_PATH")


# ---------- speech ----------

def tts_voicevox(text, url, speaker):
    q = requests.post(f"{url}/audio_query", params={"text": text, "speaker": speaker}, timeout=60)
    q.raise_for_status()
    query = q.json()
    query.update(speedScale=1.12, outputSamplingRate=SR, outputStereo=False,
                 prePhonemeLength=0.05, postPhonemeLength=0.05)
    s = requests.post(f"{url}/synthesis", params={"speaker": speaker}, json=query, timeout=300)
    s.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        f.write(s.content)
        f.flush()
        with wave.open(f.name) as w:
            assert w.getframerate() == SR and w.getnchannels() == 1 and w.getsampwidth() == 2
            return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64)


def tts_openjtalk(text):
    import pyopenjtalk
    x, sr = pyopenjtalk.tts(text, speed=1.05)
    assert sr == SR
    return x


def synthesize(texts):
    """Return (list of float arrays, voice credit string)."""
    url = os.environ.get("VOICEVOX_URL", "").rstrip("/")
    speaker = int(os.environ.get("VOICEVOX_SPEAKER", "3"))  # 3 = ずんだもん (ノーマル)
    if url:
        try:
            return [tts_voicevox(t, url, speaker) for t in texts], "VOICEVOX:ずんだもん"
        except Exception as e:  # engine down -> keep the daily upload alive
            print(f"::warning::VOICEVOX failed ({e}); falling back to Open JTalk")
    return [tts_openjtalk(t) for t in texts], "Open JTalk"


# ---------- drawing ----------

def wrap_chars(draw, text, fnt, max_w):
    lines, cur = [], ""
    for ch in text:
        if cur and draw.textlength(cur + ch, font=fnt) > max_w and ch not in NO_LINE_START:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    # avoid a dangling 1-2 character last line
    if len(lines) > 1 and len(lines[-1]) <= 2 and len(lines[-2]) > 4:
        lines[-1] = lines[-2][-2:] + lines[-1]
        lines[-2] = lines[-2][:-2]
    return lines


def wrap(draw, text, fnt, max_w):
    """Break at 、 where possible; fall back to per-character wrapping."""
    lines, cur = [], ""
    for phrase in re.findall(r"[^、]+、?", text):
        if draw.textlength(cur + phrase, font=fnt) <= max_w:
            cur += phrase
            continue
        if cur:
            lines.append(cur)
        if draw.textlength(phrase, font=fnt) <= max_w:
            cur = phrase
        else:
            *full, cur = wrap_chars(draw, phrase, fnt, max_w)
            lines.extend(full)
    if cur:
        lines.append(cur)
    return lines


def background(ep_id):
    hue = int(hashlib.sha256(ep_id.encode()).hexdigest()[:4], 16) / 0xFFFF
    top = np.array(colorsys.hsv_to_rgb(hue, 0.75, 0.16)) * 255
    bottom = np.array(colorsys.hsv_to_rgb((hue + 0.08) % 1, 0.80, 0.42)) * 255
    t = np.linspace(0, 1, H)[:, None, None]
    grad = (top * (1 - t) + bottom * t).astype(np.uint8)
    accent = tuple(int(c * 255) for c in colorsys.hsv_to_rgb((hue + 0.5) % 1, 0.45, 1.0))
    return Image.fromarray(np.broadcast_to(grad, (H, W, 3)).copy()), accent


def draw_block(draw, lines, fnt, y, fill, spacing=1.35):
    lh = int(fnt.size * spacing)
    for i, line in enumerate(lines):
        x = (W - draw.textlength(line, font=fnt)) / 2
        draw.text((x, y + i * lh), line, font=fnt, fill=fill,
                  stroke_width=6, stroke_fill=(0, 0, 0))
    return lh * len(lines)


def card(ep, idx, total, text, kind):
    img, accent = background(ep["id"])
    d = ImageDraw.Draw(img)
    max_w = W - 2 * MARGIN

    # channel badge
    badge = font(44)
    bw = d.textlength(CHANNEL, font=badge)
    d.rounded_rectangle([(W - bw) / 2 - 36, 150, (W + bw) / 2 + 36, 240], radius=45, fill=accent)
    d.text(((W - bw) / 2, 168), CHANNEL, font=badge, fill=(20, 20, 30))

    if kind == "hook":
        f = font(104)
        lines = wrap(d, text, f, max_w)
        draw_block(d, lines, f, (H - int(104 * 1.35) * len(lines)) // 2 - 80, accent)
    else:
        hf = font(56)
        draw_block(d, wrap(d, ep["hook"], hf, max_w), hf, 320, accent)
        f = font(84)
        lines = wrap(d, text, f, max_w)
        draw_block(d, lines, f, (H - int(84 * 1.35) * len(lines)) // 2, (255, 255, 255))

    # progress dots (kept above the Shorts UI overlay at the bottom)
    r, gap = 12, 44
    x0 = (W - (total - 1) * gap) / 2
    for i in range(total):
        d.ellipse([x0 + i * gap - r, 1480 - r, x0 + i * gap + r, 1480 + r],
                  fill=accent if i <= idx else (90, 90, 110))
    return img


# ---------- assembly ----------

def render(ep, out_path):
    """Render episode dict to out_path (mp4). Returns (duration_seconds, voice_credit)."""
    segments = [("hook", ep["hook"])] + [("line", l) for l in ep["lines"]] + [("line", OUTRO)]
    audio, voice = synthesize([t for _, t in segments])
    peak = max(float(np.abs(a).max()) for a in audio) or 1.0
    silence = np.zeros(int(GAP * SR))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        concat, pcm = [], []
        for i, ((kind, text), a) in enumerate(zip(segments, audio)):
            a = np.concatenate([a, silence])
            pcm.append(a)
            png = tmp / f"{i:02d}.png"
            card(ep, i, len(segments), text, kind).save(png)
            concat.append(f"file '{png}'\nduration {len(a) / SR:.4f}\n")
        concat.append(f"file '{png}'\n")  # concat demuxer needs the last frame repeated
        (tmp / "list.txt").write_text("".join(concat))

        samples = np.concatenate(pcm)
        duration = len(samples) / SR
        with wave.open(str(tmp / "audio.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((samples / peak * 0.9 * 32767).astype(np.int16).tobytes())

        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
            "-i", str(tmp / "audio.wav"),
            "-f", "lavfi", "-i", f"color=c=white:s={W}x14:r={FPS}",
            "-filter_complex",
            f"[0:v]fps={FPS},format=yuv420p[bg];"
            f"[bg][2:v]overlay=x='-W+W*t/{duration:.4f}':y=0[v]",
            "-map", "[v]", "-map", "1:a", "-t", f"{duration:.4f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out_path),
        ], check=True)
    return duration, voice
