"""Verify only producer-visible bytes against the frozen public manifest."""
from pathlib import Path
from .wire import Invalid, decode, digest, regular_bytes, safe_member, sha

MANIFEST_SHA256 = '638630886a1d291dfe9009839eb0519130e56700bb4d454277ce2e45c6044f4c'
MANIFEST_ID = 'ff5aec73ae3c7de03b1caa23e476701653539c0c0ec45f0b2427348b25c6af47'
_FIXED = {'cohort.json', 'rules/static-rule-templates-v3.json',
          'rules/swiss-authority-passages-v3.txt'}
_PREFIXES = ('data/dev/claims/', 'data/test/claims/',
             'data/dev/source-registry/', 'data/test/source-registry/')


class FrozenRelease:
    def __init__(self, root: Path):
        self.root = Path(root)
        try:
            raw = regular_bytes(safe_member(self.root, 'manifest.json', ('manifest.json',)),
                                16 * 1024 * 1024)
        except OSError as exc:
            raise Invalid('frozen public release manifest is unavailable') from exc
        if sha(raw) != MANIFEST_SHA256:
            raise Invalid('public release manifest differs from the frozen identity')
        self.manifest = decode(raw)
        if self.manifest.get('manifest_sha256') != MANIFEST_ID:
            raise Invalid('public release declared identity differs')
        self.files = {row['relative_path']: row for row in self.manifest['files']}
        if len(self.files) != len(self.manifest['files']):
            raise Invalid('duplicate manifest file path')
        self.verified = {}

    def read(self, relative: str, limit: int = 16 * 1024 * 1024) -> bytes:
        if relative not in _FIXED and not relative.startswith(_PREFIXES):
            raise Invalid('release binding may read only producer-visible inputs')
        path = safe_member(self.root, relative, tuple(_FIXED) + _PREFIXES)
        raw = regular_bytes(path, limit)
        if relative == 'cohort.json':
            cohort = decode(raw)
            if (cohort.get('manifest_sha256') != MANIFEST_ID or
                    cohort.get('cases') != self.manifest['cases']):
                raise Invalid('cohort differs from the frozen manifest roster')
        else:
            row = self.files.get(relative)
            if (row is None or len(raw) != row['size_bytes'] or
                    sha(raw) != row['file_sha256']):
                raise Invalid('observable/source input differs from frozen manifest: ' + relative)
        self.verified[relative] = sha(raw)
        return raw

    def load(self, relative: str):
        return decode(self.read(relative))

    def receipt(self):
        return {'manifest_raw_sha256': MANIFEST_SHA256,
                'manifest_declared_id': MANIFEST_ID,
                'verified_input_sha256': dict(sorted(self.verified.items())),
                'verified_input_set_sha256': digest(self.verified),
                'target_bodies_read': False}
