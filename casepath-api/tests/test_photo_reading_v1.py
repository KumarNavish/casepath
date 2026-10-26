"""Photo reading measures pixels of the exact original and admits nothing."""
import io
import random
from hashlib import sha256

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from casepath_api.autonomous_api_v1 import create_autonomous_router
from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_store_v1 import AutonomousStore
from casepath_api.photo_reading_v1 import PhotoReadingError, read_photo

PREFIX = '/api/claim-loops/v1/autonomous'
PHOTO_CLAIM, PHOTO_SOURCE = 'clm_731b214dde882f89', 'src_8291405543acf1003fa5b7c1824e8551'


def jpeg(image, exif=None):
    out = io.BytesIO()
    image.save(out, 'JPEG', quality=92, **({'exif': exif} if exif is not None else {}))
    return out.getvalue()


def wall(size=(640, 480), colour=(214, 212, 206)):
    return Image.new('RGB', size, colour)


def spotted_wall():
    image, rng = wall(), random.Random(7)
    draw = ImageDraw.Draw(image)
    for _ in range(160):  # small dark specks clustered in one patch
        x, y, r = rng.randint(380, 560), rng.randint(120, 330), rng.randint(2, 5)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(48, 50, 44))
    draw.line((0, 440, 640, 440), fill=(60, 55, 50), width=4)  # a skirting edge is not spotting
    return image


def inside(region, box, slack=25):
    x0, y0, x1, y1 = box
    return (region['x'] >= x0 - slack and region['y'] >= y0 - slack and
            region['x'] + region['width'] <= x1 + slack and region['y'] + region['height'] <= y1 + slack)


def test_dark_spotting_is_located_and_edges_are_not():
    reading = read_photo(jpeg(spotted_wall()))
    regions = [row for row in reading['regions'] if row['kind'] == 'dark_spotting']
    assert len(regions) == 1 and inside(regions[0], (380, 120, 560, 330))
    assert regions[0]['label'] == 'Dark spotting' and regions[0]['position'] == 'middle right'
    assert 0 < regions[0]['share'] < 0.2


def test_brown_staining_is_located_on_a_light_ceiling():
    image = wall(colour=(226, 224, 220))
    ImageDraw.Draw(image).ellipse((120, 140, 360, 320), fill=(205, 178, 128))
    regions = [row for row in read_photo(jpeg(image))['regions'] if row['kind'] == 'brown_staining']
    assert len(regions) == 1 and inside(regions[0], (120, 140, 360, 320))


def test_a_clean_wall_has_no_reading_and_the_result_is_deterministic():
    raw = jpeg(wall())
    first, second = read_photo(raw), read_photo(raw)
    assert first['regions'] == [] and first == second
    assert first['image_sha256'] == sha256(raw).hexdigest() and len(first['reading_sha256']) == 64


def test_capture_date_comes_only_from_recorded_metadata():
    exif = Image.Exif()
    exif.get_ifd(0x8769)[36867] = '2025:03:14 08:15:00'  # DateTimeOriginal
    dated = read_photo(jpeg(wall(), exif=exif))
    assert dated['captured_at'] == '2025-03-14T08:15:00' and dated['captured_at_source'] == 'exif:DateTimeOriginal'
    undated = read_photo(jpeg(wall()))
    assert undated['captured_at'] is None and undated['captured_at_source'] is None


def test_unreadable_bytes_fail_closed():
    for raw in (b'', b'not an image'):
        with pytest.raises(PhotoReadingError):
            read_photo(raw)


@pytest.fixture
def api(tmp_path):
    corpus = CanonicalCorpus()
    store = AutonomousStore(tmp_path / 'canonical.sqlite3')
    service = AutonomousController(store, corpus._corpus.static_policy(), enforce_intake_gate=True)
    service.submit = lambda claim_id: pytest.fail('a photo reading must not start work')
    app = FastAPI()
    app.include_router(create_autonomous_router(lambda: service, corpus_getter=lambda: corpus))
    with TestClient(app) as client:
        yield client, store, corpus
    service.shutdown()


def test_customer_photo_reading_is_bound_to_the_original_and_admits_nothing(api):
    client, store, corpus = api
    before = corpus.preview_state(PHOTO_CLAIM)
    path = f'{PREFIX}/sources/{PHOTO_CLAIM}/{PHOTO_SOURCE}'
    original = client.get(path)
    reading = client.get(path + '/photo-reading')
    assert reading.status_code == 200
    body = reading.json()
    assert body['image_sha256'] == sha256(original.content).hexdigest() == original.headers['x-content-sha256']
    assert body['artifact_id'] == PHOTO_SOURCE and body['evidence_admitted'] is False
    assert body['captured_at'] == '2025-03-14T12:00:00' and body['captured_at_source'] == 'exif:DateTimeOriginal'
    spots = [row for row in body['regions'] if row['kind'] == 'dark_spotting']
    assert spots and spots[0]['position'] == 'centre'
    message = next(row['artifact_id'] for row in before['source_descriptors'] if row['media_type'] == 'message/rfc822')
    assert client.get(f'{PREFIX}/sources/{PHOTO_CLAIM}/{message}/photo-reading').status_code == 415
    assert store.list() == [] and corpus.preview_state(PHOTO_CLAIM) == before
