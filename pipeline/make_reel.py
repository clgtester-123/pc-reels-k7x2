"""Render a text-and-motion Reel (1080x1920 MP4) from a content row.

No voice, no AI images: branded slides drawn with Pillow, animated with ffmpeg.
"""
import os
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")

# Per-product palette (background, accent). Matches the guides' look.
THEMES = {
    "handstand": {"bg": (14, 18, 26), "accent": (45, 212, 191), "label": "HANDSTAND"},
    "pullup": {"bg": (20, 16, 14), "accent": (251, 146, 60), "label": "PULL-UP"},
}
TEXT = (245, 245, 240)
MUTED = (150, 155, 165)

SLIDE_SECONDS = 3.2
HOOK_SECONDS = 2.8
CTA_SECONDS = 3.0
FPS = 30


def font(weight, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, f"Poppins-{weight}.ttf"), size)


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_block(draw, text, weight, size, color, y_center, max_w=880, spacing=1.25):
    """Draw centred wrapped text, shrinking the font until it fits ~9 lines."""
    while True:
        fnt = font(weight, size)
        lines = wrap(draw, text, fnt, max_w)
        if len(lines) <= 9 or size <= 44:
            break
        size -= 4
    line_h = int(size * spacing)
    total = line_h * len(lines)
    y = y_center - total // 2
    for ln in lines:
        tw = draw.textlength(ln, font=fnt)
        draw.text(((W - tw) / 2, y), ln, font=fnt, fill=color)
        y += line_h


def base(theme, step=None, total=None):
    img = Image.new("RGB", (W, H), theme["bg"])
    d = ImageDraw.Draw(img)
    # top label + brand
    d.text((90, 150), theme["label"], font=font("Bold", 34), fill=theme["accent"])
    brand = "PROGRESSION CLUB"
    bw = d.textlength(brand, font=font("Medium", 30))
    d.text((W - 90 - bw, 154), brand, font=font("Medium", 30), fill=MUTED)
    d.rectangle([90, 210, 90 + 120, 216], fill=theme["accent"])
    # progress dots
    if step is not None and total:
        dot, gap = 16, 18
        span = total * dot + (total - 1) * gap
        x0 = (W - span) // 2
        for i in range(total):
            c = theme["accent"] if i == step else (60, 66, 78)
            d.ellipse([x0 + i * (dot + gap), 1480, x0 + i * (dot + gap) + dot, 1480 + dot], fill=c)
    return img, d


def hook_slide(theme, hook):
    img, d = base(theme)
    draw_block(d, hook, "Bold", 104, TEXT, H // 2 - 40)
    d.text((90, 1480), "Watch to the end.", font=font("Regular", 34), fill=MUTED)
    return img


def tip_slide(theme, text, idx, total):
    img, d = base(theme, step=idx, total=total)
    draw_block(d, text, "Bold", 78, TEXT, H // 2)
    return img


def cta_slide(theme, product):
    img, d = base(theme)
    draw_block(d, "Want the full step-by-step plan?", "Bold", 88, TEXT, H // 2 - 160)
    draw_block(d, "Link in bio", "Bold", 110, theme["accent"], H // 2 + 120)
    disc = "General fitness information. Not medical advice."
    fnt = font("Regular", 30)
    tw = d.textlength(disc, font=fnt)
    d.text(((W - tw) / 2, 1500), disc, font=fnt, fill=MUTED)
    return img


def build(row, out_path):
    theme = THEMES[row["product"]]
    tips = [s.strip() for s in row["slides"].split("|") if s.strip()]
    images = [(hook_slide(theme, row["hook"]), HOOK_SECONDS)]
    for i, t in enumerate(tips):
        images.append((tip_slide(theme, t, i, len(tips)), SLIDE_SECONDS))
    images.append((cta_slide(theme, row["product"]), CTA_SECONDS))

    with tempfile.TemporaryDirectory() as tmp:
        clips = []
        for n, (img, secs) in enumerate(images):
            png = os.path.join(tmp, f"s{n}.png")
            img.save(png)
            clip = os.path.join(tmp, f"c{n}.mp4")
            frames = int(secs * FPS)
            # gentle zoom-in plus fade in/out
            vf = (
                f"scale=2160:3840,zoompan=z='1+0.06*on/{frames}':d={frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},"
                f"fade=t=in:st=0:d=0.25,fade=t=out:st={secs-0.25}:d=0.25,format=yuv420p"
            )
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", png, "-t", str(secs),
                 "-vf", vf, "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", clip],
                check=True,
            )
            clips.append(clip)
        lst = os.path.join(tmp, "list.txt")
        with open(lst, "w") as f:
            for c in clips:
                f.write(f"file '{c}'\n")
        # silent AAC track keeps Instagram happy
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
             "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out_path],
            check=True,
        )
    return out_path


if __name__ == "__main__":
    import csv
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "content", "reels.csv")
    rid = sys.argv[2] if len(sys.argv) > 2 else "001"
    out = sys.argv[3] if len(sys.argv) > 3 else f"/tmp/reel_{rid}.mp4"
    with open(path, newline="", encoding="utf-8") as f:
        row = next(r for r in csv.DictReader(f) if r["id"] == rid)
    print(build(row, out))
