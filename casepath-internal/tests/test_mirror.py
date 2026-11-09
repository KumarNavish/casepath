import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import unquote

import httpx

from casepath_internal.mirror import VolumeMirror
from casepath_internal.store import CaseStore

VOLUME = "/Volumes/team/casepath/pilot"


def fake_volume():
    """The Files API over a dict: PUT and GET files, list directories."""
    files = {}

    def handler(request):
        kind, path = request.url.path.split("/api/2.0/fs/")[1].split("/", 1)
        path = "/" + unquote(path)
        if kind == "files" and request.method == "PUT":
            files[path] = request.content
            return httpx.Response(204)
        if kind == "files":
            return httpx.Response(200, content=files[path]) if path in files else httpx.Response(404)
        children = {p[len(path) + 1:].split("/")[0] for p in files if p.startswith(path + "/")}
        if not children:
            return httpx.Response(404)
        return httpx.Response(200, json={"contents": [{"path": f"{path}/{c}", "is_directory": f"{path}/{c}" not in files} for c in sorted(children)]})
    return files, httpx.MockTransport(handler)


class MirrorTests(unittest.TestCase):
    def test_a_restarted_app_gets_its_cases_back_from_the_volume(self):
        files, transport = fake_volume()
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            store = CaseStore(first)
            case = store.create_case("Schimmel", {}, "anna")
            store.add_file(case["id"], "brief.txt", "text/plain", "text", b"Mietzins", {"text": "Mietzins"}, "anna")
            mirror = VolumeMirror(first, VOLUME, "https://adb.example.azuredatabricks.net", lambda: "t", transport=transport)
            self.assertEqual(mirror.sync(), {"files": 1, "database": True})
            self.assertEqual(mirror.sync(), {"files": 0, "database": False})  # nothing new, nothing written
            store.close()
            fresh = VolumeMirror(second, VOLUME, "https://adb.example.azuredatabricks.net", lambda: "t", transport=transport)
            self.assertEqual(fresh.restore(), 1)
            restored = CaseStore(second)
            self.addCleanup(restored.close)
            self.assertEqual([c["title"] for c in restored.list_cases()], ["Schimmel"])
            self.assertEqual(restored.file_bytes(restored.list_files(case["id"])[0]["id"])[0], b"Mietzins")
            self.assertEqual(fresh.restore(), 0)  # a store that is already there is never overwritten


if __name__ == "__main__":
    unittest.main()
