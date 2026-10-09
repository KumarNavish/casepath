"""Local-only regression for frozen migration manifests and exact inserts."""
from hashlib import sha256
import json
from pathlib import Path
import runpy
import sqlite3
from types import SimpleNamespace
import pytest

migration = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tools/migrate_hosted.py'))


def test_frozen_manifest_survives_json_roundtrip_without_changing_sources(tmp_path):
    source = tmp_path / 'original'; source.mkdir()
    for index, name in enumerate(migration['DATABASES']):
        with sqlite3.connect(source / name) as db:
            db.executescript(f'CREATE TABLE rows_{index}(id TEXT PRIMARY KEY, content BLOB, cost REAL);')
            db.execute(f'INSERT INTO rows_{index} VALUES(?,?,?)', ('exact', b'\x00\xff', 0.0268581625))
    originals = source / 'autonomous-sources-v1'; originals.mkdir()
    raw = b'Exact original\r\n'; (originals / sha256(raw).hexdigest()).write_bytes(raw)
    args = SimpleNamespace(snapshot=tmp_path / 'frozen', source_root=source, hosting_root=tmp_path / 'checkout')
    before = migration['inventory'](source)
    result = migration['snapshot'](args)
    saved = json.loads((args.snapshot / 'SNAPSHOT.json').read_text())
    assert migration['inventory'](args.snapshot) == saved['snapshot_inventory']
    assert before == migration['inventory'](source)
    assert saved['snapshot_sha256'] == result['snapshot_sha256']
    with pytest.raises(migration['Refused'], match='already exists'):
        migration['snapshot'](args)


def test_migration_insert_skips_identical_immutable_rows_and_refuses_conflict():
    with sqlite3.connect(':memory:') as db:
        db.executescript("CREATE TABLE evidence(id TEXT PRIMARY KEY,value BLOB); "
                         "CREATE TRIGGER immutable BEFORE INSERT ON evidence WHEN EXISTS(SELECT 1 FROM evidence WHERE id=NEW.id) "
                         "BEGIN SELECT RAISE(ABORT,'immutable'); END;")
        command = migration['insert_sql']('evidence', ['id','value'], [('a',b'exact')])
        db.execute(*command); db.execute(*command)
        assert db.execute('SELECT * FROM evidence').fetchall() == [('a',b'exact')]
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(*migration['insert_sql']('evidence',['id','value'], [('a',b'different')]))
        assert db.execute('SELECT * FROM evidence').fetchall() == [('a',b'exact')]
