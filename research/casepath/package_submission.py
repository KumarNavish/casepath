#!/usr/bin/env python3
"""Package the manuscript and an already verified offline reproduction tree.

No model calls or scientific analyses are run. Inputs must already contain the
completed reports and their exact-replay receipt. All archives are deterministic.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
PAPER = HERE / 'iclr2027-integrated'
IDENTITY = re.compile(rb'kumar0002|KumarNavish|Die Mobiliar|Navish Kumar|sk-or-v1-[A-Za-z0-9]{16,}', re.I)
TEXT = {'.py', '.md', '.json', '.jsonl', '.txt', '.tex', '.bib', '.html', '.sh'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def paper_files():
    pending, found = ['main.tex'], {}
    while pending:
        name = pending.pop()
        if name in found:
            continue
        path = PAPER / name
        found[name] = path.read_bytes()
        for dep in re.findall(r'\\input\{([^}]+)\}', path.read_text()):
            pending.append(dep if dep.endswith('.tex') else dep + '.tex')
        for dep in re.findall(r'\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}', path.read_text()):
            found[dep] = (PAPER / dep).read_bytes()
    for name in ['references.bib', 'iclr2027_conference.sty', 'iclr2027_conference.bst']:
        found[name] = (PAPER / name).read_bytes()
    found['README.md'] = b'# CasePath submission source\n\nCompile main.tex with XeLaTeX and BibTeX, or with Tectonic.\nThe submitted title and abstract are preserved. Measurement provenance,\nfigure generators and offline reproduction are in the companion archive.\n'
    return found


def write_archive(path, files):
    rows = []
    for name, raw in sorted(files.items()):
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('unsafe archive path: ' + name)
        if Path(name).suffix in TEXT and IDENTITY.search(raw):
            raise ValueError('author identity or credential pattern: ' + name)
        if name.endswith('.pdf') and (not raw.startswith(b'%PDF-') or b'%%EOF' not in raw[-64:]):
            raise ValueError('incomplete PDF; finish figure generation before packaging: ' + name)
        if name.endswith('.zip'):
            import io
            with zipfile.ZipFile(io.BytesIO(raw)) as nested:
                for member in nested.namelist():
                    if Path(member).suffix in TEXT and IDENTITY.search(nested.read(member)):
                        raise ValueError('identity in nested archive: ' + name + '/' + member)
        rows.append({'path': name, 'bytes': len(raw), 'sha256': sha(raw)})
    manifest = {'schema': 'casepath.anonymous-release/1', 'files': rows}
    files = dict(files)
    files['ARCHIVE_MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.zip', delete=False) as temp:
        temporary = Path(temp.name)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for name, raw in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(2026, 9, 21, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, raw)
        with zipfile.ZipFile(temporary) as z:
            for row in rows:
                if sha(z.read(row['path'])) != row['sha256']:
                    raise ValueError('archive round-trip mismatch: ' + row['path'])
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return {'files': len(rows), 'bytes': path.stat().st_size, 'sha256': sha(path.read_bytes())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reproduction', type=Path, required=True)
    args = parser.parse_args()
    root = args.reproduction.resolve()
    receipt = json.loads((root / 'REPLAY_VERIFICATION.json').read_text())
    assert receipt['primary']['state'] == 'recorded_native_scores_and_analysis_reproduced'
    assert receipt['request_only']['state'] == 'request_only_diagnostic_reproduced'
    assert receipt['primary']['cells'] == 1050 and receipt['request_only']['observed_request_cells'] == 558
    manifest = json.loads((root / 'recorded-native/REPLAY_MANIFEST.json').read_text())
    for descriptor in [*manifest['expected_reports'].values(), manifest['request_only_diagnostic']['report'], manifest['request_only_diagnostic']['rows']]:
        assert sha((root / 'recorded-native' / descriptor['path']).read_bytes()) == descriptor['sha256']
    dist = PAPER / 'dist'; dist.mkdir(exist_ok=True)
    paper = paper_files()
    result = {'source': write_archive(dist / 'casepath_iclr2027_submission_source.zip', paper)}
    files = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*')
             if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    # Figure regeneration and numerical verification travel with the measurements.
    for p in (PAPER / 'evidence').rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.name not in {'build_native_release.py', 'build_execution_snapshot.py'}:
            files['manuscript/evidence/' + str(p.relative_to(PAPER / 'evidence'))] = p.read_bytes()
    for p in (HERE / 'branch-benchmark').rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            files['branch-benchmark/' + str(p.relative_to(HERE / 'branch-benchmark'))] = p.read_bytes()
    for name, raw in paper.items():
        files['manuscript/' + name] = raw
    files['manuscript/main.pdf'] = (PAPER / 'main.pdf').read_bytes()
    result['reproducibility'] = write_archive(dist / 'casepath_iclr2027_reproducibility.zip', files)
    shutil.copyfile(PAPER / 'main.pdf', dist / 'casepath_iclr2027_submission.pdf')
    result['pdf_sha256'] = sha((PAPER / 'main.pdf').read_bytes())
    result['source_and_archive_roundtrip'] = 'all bytes verified'
    result['scientific_replay'] = 'existing exact-replay receipt, not a new evaluation'
    (dist / 'PACKAGE_VERIFICATION.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
