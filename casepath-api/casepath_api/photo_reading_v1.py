"""Deterministic photo reading: when a photo was taken and where it is discoloured.

Pure pixel measurement with Pillow. No model, network, randomness or clock. The
reading states what the pixels show -- dark spotting or brown staining on an
otherwise light surface -- where that area is and how much of the photo it
covers. It does not name a cause, a material or a legal consequence; a person
or a later step decides what the marked area means.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections import deque
from datetime import datetime

from PIL import ExifTags, Image, ImageFilter, ImageOps

CONTRACT = 'casepath.photo-reading/1.0.0'
METHOD = 'local-luminance-and-tint-deviation/1'
WORK_EDGE = 480          # long edge, in pixels, of the measured copy
MIN_SHARE = 0.003        # smaller areas are noise, not a reading
MAX_SEGMENTS = 400       # measured marks returned per area
KIND_LABEL = {'dark_spotting': 'Dark spotting', 'brown_staining': 'Brown staining'}


class PhotoReadingError(ValueError):
    pass


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _captured_at(image: Image.Image):
    exif = image.getexif()
    tags = {ExifTags.TAGS.get(key, key): value for key, value in exif.items()}
    tags.update({ExifTags.TAGS.get(key, key): value for key, value in exif.get_ifd(ExifTags.IFD.Exif).items()})
    for name in ('DateTimeOriginal', 'DateTimeDigitized', 'DateTime'):
        value = tags.get(name)
        if isinstance(value, str):
            try:
                return datetime.strptime(value.strip(), '%Y:%m:%d %H:%M:%S').isoformat(), f'exif:{name}'
            except ValueError:
                continue
    return None, None


def _components(mask: list[list[bool]], width: int, height: int):
    seen = [[False] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            if not mask[y][x] or seen[y][x]:
                continue
            queue, pixels = deque([(x, y)]), []
            seen[y][x] = True
            while queue:
                cx, cy = queue.popleft()
                pixels.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < width and 0 <= ny < height and mask[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        queue.append((nx, ny))
            yield pixels


def _position(cx: float, cy: float) -> str:
    row = 'upper' if cy < 1 / 3 else 'lower' if cy > 2 / 3 else 'middle'
    column = 'left' if cx < 1 / 3 else 'right' if cx > 2 / 3 else 'centre'
    return 'centre' if (row, column) == ('middle', 'centre') else f'{row} {column}'


def _mask_image(flags, w, h):
    image = Image.new('L', (w, h))
    image.putdata([255 if f else 0 for f in flags])
    return image


def _specks(flags, w, h, longest):
    """Keep only small blob-like marks; lines, edges and objects are longer."""
    keep, boxes = [False] * (w * h), []
    rows = [flags[y * w:(y + 1) * w] for y in range(h)]
    for pixels in _components(rows, w, h):
        xs, ys = [p[0] for p in pixels], [p[1] for p in pixels]
        if len(pixels) >= 2 and max(max(xs) - min(xs), max(ys) - min(ys)) + 1 <= longest:
            boxes.append((min(xs), min(ys), max(xs) + 1, max(ys) + 1))
            for x, y in pixels:
                keep[y * w + x] = True
    return keep, boxes


def _cells(flags, w, h, size=6, cover=0.3):
    """A coarse grid of the flagged area, for patches without separate marks."""
    boxes = []
    for y0 in range(0, h, size):
        for x0 in range(0, w, size):
            x1, y1 = min(w, x0 + size), min(h, y0 + size)
            hits = sum(1 for y in range(y0, y1) for x in range(x0, x1) if flags[y * w + x])
            if hits >= cover * (x1 - x0) * (y1 - y0):
                boxes.append((x0, y0, x1, y1))
    return boxes


def _regions(kind, flags, evidence, pieces, w, h, scale, width, height, window, threshold, min_fill):
    density = _mask_image(flags, w, h).filter(ImageFilter.BoxBlur(window // 2))
    dense = density.point(lambda v: 255 if v >= threshold else 0).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(3))
    values = list(dense.get_flattened_data())
    rows = [[values[y * w + x] > 0 for x in range(w)] for y in range(h)]
    found = []
    for pixels in _components(rows, w, h):
        covered = sum(1 for x, y in pixels if evidence[y * w + x])
        share = covered / (w * h)
        xs, ys = [p[0] for p in pixels], [p[1] for p in pixels]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs) + 1, max(ys) + 1
        if share < MIN_SHARE or covered / ((x1 - x0) * (y1 - y0)) < min_fill:
            continue
        # The measured marks inside the area, in original pixels, top to bottom.
        segments = sorted((bx0, by0, bx1, by1) for bx0, by0, bx1, by1 in pieces
                          if x0 <= (bx0 + bx1) / 2 < x1 and y0 <= (by0 + by1) / 2 < y1)
        segments.sort(key=lambda box: (box[1], box[0]))
        found.append({
            'kind': kind, 'label': KIND_LABEL[kind],
            'x': round(x0 / scale), 'y': round(y0 / scale),
            'width': min(width, round((x1 - x0) / scale)), 'height': min(height, round((y1 - y0) / scale)),
            'share': round(share, 4),
            'position': _position((x0 + x1) / 2 / w, (y0 + y1) / 2 / h),
            'segments': [[round(bx0 / scale), round(by0 / scale), max(1, round((bx1 - bx0) / scale)), max(1, round((by1 - by0) / scale))]
                         for bx0, by0, bx1, by1 in segments[:MAX_SEGMENTS]],
        })
    return found


def read_photo(raw: bytes) -> dict:
    """Return the deterministic reading of one photo's bytes."""
    if not isinstance(raw, (bytes, bytearray)) or not raw:
        raise PhotoReadingError('A photo reading needs the original image bytes.')
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as error:  # Pillow raises several decoder errors
        raise PhotoReadingError('The file could not be decoded as an image.') from error
    captured_at, captured_source = _captured_at(image)
    image = ImageOps.exif_transpose(image).convert('RGB')
    width, height = image.size
    scale = WORK_EDGE / max(width, height)
    work = image.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.Resampling.BILINEAR)
    w, h = work.size
    longest = max(w, h)
    luma = work.convert('L')
    # The surrounding surface: a wide blur after a median that removes small marks.
    surface = luma.filter(ImageFilter.MedianFilter(11)).filter(ImageFilter.GaussianBlur(max(4, round(longest * 0.06))))
    hsv = work.convert('HSV')
    tint = hsv.getchannel('S').filter(ImageFilter.MedianFilter(11)).filter(ImageFilter.GaussianBlur(max(6, round(longest * 0.15))))
    L, S = list(luma.get_flattened_data()), list(surface.get_flattened_data())
    H, Sat, V, T = (list(band.get_flattened_data()) for band in (hsv.getchannel('H'), hsv.getchannel('S'), hsv.getchannel('V'), tint))
    # A neutral surface (wall, ceiling): light enough and of low colour.
    neutral = [S[i] >= 80 and T[i] <= 70 for i in range(w * h)]
    dark = [neutral[i] and S[i] - L[i] >= max(14, 0.13 * S[i]) for i in range(w * h)]
    specks, speck_boxes = _specks(dark, w, h, max(3, round(longest * 0.045)))
    # A stain is a light, softly tinted patch: wood, copper and fabric are darker or more saturated.
    stain = [S[i] >= 120 and T[i] <= 70 and 15 <= H[i] * 360 / 255 <= 55 and 20 <= Sat[i] <= 105 and Sat[i] >= T[i] + 14 and V[i] >= 140 for i in range(w * h)]
    window = max(5, round(longest * 0.05)) | 1
    readings = []
    if len(speck_boxes) >= 12:
        readings += _regions('dark_spotting', specks, specks, speck_boxes, w, h, scale, width, height, window, 12, 0.015)
    readings += _regions('brown_staining', stain, stain, _cells(stain, w, h), w, h, scale, width, height, window, 110, 0.2)
    readings.sort(key=lambda row: (-row['share'], row['kind'], row['y'], row['x']))
    result = {
        'contract': CONTRACT, 'method': METHOD,
        'image_sha256': hashlib.sha256(bytes(raw)).hexdigest(),
        'width': width, 'height': height,
        'captured_at': captured_at, 'captured_at_source': captured_source,
        'regions': readings[:3],
        'limits': ['Pixel measurement only: the reading does not name a cause or a material.',
                   'The share is of the photo, not of the wall or room.'],
    }
    return {**result, 'reading_sha256': _digest(result)}
