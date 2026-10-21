"""A contact sheet from 24 evenly sampled frames decoded from the actual MP4."""
from pathlib import Path
import json
import sys
from PIL import Image, ImageDraw, ImageFont

out = Path(sys.argv[1])
data = json.loads((out / "contact-frames.json").read_text())
font_path = Path(__file__).resolve().parents[2] / "casepath/assets/fonts/Mulish.ttf"
title = ImageFont.truetype(str(font_path), 32)
label = ImageFont.truetype(str(font_path), 20)
small = ImageFont.truetype(str(font_path), 18)
width, tile_width, tile_height, caption, top = 1920, 480, 300, 42, 120
sheet = Image.new("RGB", (width, top + 6 * (tile_height + caption)), "white")
draw = ImageDraw.Draw(sheet)
draw.text((18, 16), "CasePath · one continuous recorded demonstration", font=title, fill="#141516")
starts = " · ".join(f"{act['id'].title()} {act['start']/1000:.2f}s" for act in data["acts"])
draw.text((18, 66), starts, font=small, fill="#4c4b4d")
frames = sorted((out / "contact").glob("frame-*.png"))
assert len(frames) == len(data["frames"]) == 24
for i, (filename, frame) in enumerate(zip(frames, data["frames"])):
    x, y = (i % 4) * tile_width, top + (i // 4) * (tile_height + caption)
    image = Image.open(filename).convert("RGB")
    assert image.size == (1920, 1200)
    sheet.paste(image.resize((tile_width, tile_height), Image.Resampling.LANCZOS), (x, y))
    seconds = frame["time"]
    text = f"{int(seconds//60):02d}:{seconds%60:06.3f} · {frame['act'].title()} · frame {frame['n']}"
    draw.text((x+12, y+tile_height+8), text, font=label, fill="#4c4b4d")
sheet.save(out / "contact-sheet.png")
