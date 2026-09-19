"""Producer input identity checks using invented files, never target bodies."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from casepath_api.obligation_control.study_v1.inputs import read_release
from casepath_api.obligation_control.study_v1.wire import Invalid
from casepath_api.obligation_control.study_v1 import release_binding
from casepath_api.obligation_control.study_v1.wire import sha


class ReleaseIdentityTests(unittest.TestCase):
    def test_unpinned_release_is_rejected_before_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def put(relative, value):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            rows = []
            for i in range(150):
                dev = i < 60
                zone = 'dev' if dev else 'test'
                row = {'case_id': f'invented_{i}',
                       'split': 'public_dev' if dev else 'hidden_test',
                       'family_id': f'{zone}_{i % (11 if dev else 17)}',
                       'domain': 'invented',
                       'observable_claim_path': f'data/{zone}/claims/{i}.json',
                       'source_registry_path': f'data/{zone}/source-registry/{i}.json'}
                rows.append(row)
                put(row['observable_claim_path'], {
                    'contract': 'invented', 'submission': {}, 'attachments': [],
                    'customer_message': {'body': 'invented message',
                                         'raw_file': {'artifact_id': 'invented'}}})
                put(row['source_registry_path'], {'entries': [{
                    'source_kind': 'case_invariant_rule',
                    'locator': {'artifact_id': 'invented_rule'},
                    'display_value': 'invented rule'}]})
            put('cohort.json', {'cases': rows})
            put('rules/static-rule-templates-v3.json', {
                'case_activation_values_included': False,
                'model_visibility': 'all_three_templates_identical_for_every_case'})
            (root / 'rules/swiss-authority-passages-v3.txt').write_text('invented source')
            with self.assertRaises(Invalid):
                read_release(root, expected_pdf_version='unused-no-pdfs')


class FrozenReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.relative = 'data/dev/claims/invented.json'
        self.path = self.root / self.relative
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b'{"invented":true}')
        self.manifest = {'manifest_sha256': 'a' * 64,
                         'cases': [{'case_id': 'invented'}],
                         'files': [{'relative_path': self.relative,
                                    'file_sha256': sha(self.path.read_bytes()),
                                    'size_bytes': self.path.stat().st_size}]}
        raw = json.dumps(self.manifest).encode()
        (self.root / 'manifest.json').write_bytes(raw)
        (self.root / 'cohort.json').write_text(json.dumps({
            'manifest_sha256': 'a' * 64, 'cases': self.manifest['cases']}))
        for key, value in [('MANIFEST_SHA256', sha(raw)), ('MANIFEST_ID', 'a' * 64)]:
            mocked = patch.object(release_binding, key, value)
            mocked.start()
            self.addCleanup(mocked.stop)

    def test_exact_bytes_and_roster_are_bound(self):
        release = release_binding.FrozenRelease(self.root)
        self.assertEqual(release.load(self.relative), {'invented': True})
        self.assertEqual(release.load('cohort.json')['cases'], self.manifest['cases'])
        self.assertEqual(release.receipt()['verified_input_sha256'][self.relative],
                         sha(self.path.read_bytes()))

    def test_changed_manifest_fails(self):
        with (self.root / 'manifest.json').open('ab') as stream:
            stream.write(b' ')
        with self.assertRaises(Invalid):
            release_binding.FrozenRelease(self.root)

    def test_same_length_changed_input_fails(self):
        release = release_binding.FrozenRelease(self.root)
        self.path.write_bytes(b'{"invented":null}')
        with self.assertRaises(Invalid):
            release.load(self.relative)

    def test_changed_roster_fails(self):
        release = release_binding.FrozenRelease(self.root)
        (self.root / 'cohort.json').write_text(json.dumps({
            'manifest_sha256': 'a' * 64, 'cases': [{'case_id': 'changed'}]}))
        with self.assertRaises(Invalid):
            release.load('cohort.json')

    def test_gold_is_rejected_without_opening(self):
        release = release_binding.FrozenRelease(self.root)
        with patch.object(release_binding, 'regular_bytes') as read:
            with self.assertRaises(Invalid):
                release.read('data/dev/gold/invented.json')
            read.assert_not_called()

    def test_unlisted_input_fails(self):
        release = release_binding.FrozenRelease(self.root)
        extra = self.path.with_name('unlisted.json')
        extra.write_text('{}')
        with self.assertRaises(Invalid):
            release.load('data/dev/claims/unlisted.json')

    def test_symlink_input_fails(self):
        release = release_binding.FrozenRelease(self.root)
        target = self.root / 'same-bytes.json'
        self.path.rename(target)
        self.path.symlink_to(target)
        with self.assertRaises(Invalid):
            release.load(self.relative)
