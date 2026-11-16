import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import unquote

import httpx

from casepath.web.mirror import VolumeMirror
from casepath.web.store import CaseStore

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
        if kind == "files" and request.method == "DELETE":
            return httpx.Response(204) if files.pop(path, None) is not None else httpx.Response(404)
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


    def test_a_deleted_case_is_gone_from_the_volume_too_and_does_not_come_back(self):
        files, transport = fake_volume()
        host = "https://adb.example.azuredatabricks.net"
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second, tempfile.TemporaryDirectory() as third:
            store = CaseStore(first)
            kept = store.create_case("Bleibt", {}, "anna")
            store.add_file(kept["id"], "a.txt", "text/plain", "text", b"bleibt hier", {"text": "bleibt hier"}, "anna")
            gone = store.create_case("Wird geloescht", {}, "anna")
            secret = b"GEHEIMER-INHALT-DES-GELOESCHTEN-FALLS " * 400
            store.add_file(gone["id"], "b.txt", "text/plain", "text", secret, {"text": secret.decode()}, "anna")
            store.append_case_event(gone["id"], {"kind": "note.added", "text": "GEHEIMER-INHALT-DES-GELOESCHTEN-FALLS im Verlauf"})
            mirror = VolumeMirror(first, VOLUME, host, lambda: "t", transport=transport)
            mirror.sync()
            blobs = lambda: sorted(p for p in files if "/files/" in p)
            self.assertEqual(len(blobs()), 2)
            self.assertIn(b"GEHEIMER-INHALT", files[f"{VOLUME}/casepath.db"])
            store.delete_case(gone["id"], "anna")
            self.assertEqual(mirror.sync().get("removed"), 1)  # the file's bytes leave the volume with the case
            self.assertEqual(len(blobs()), 1)
            self.assertNotIn(b"GEHEIMER-INHALT", files[f"{VOLUME}/casepath.db"])  # and its text is not in the copied database
            self.assertEqual((mirror.status()["ok"], bool(mirror.status()["last_copy"])), (True, True))
            store.close()
            # a copy made before the deletion reached the volume (a crash between the two): the orphan comes back with a
            # restore, the store removes what no case refers to, and the next copy removes it from the volume
            orphan = "ab" * 32
            files[f"{VOLUME}/files/{orphan[:2]}/{orphan}"] = b"verwaist"
            fresh = VolumeMirror(second, VOLUME, host, lambda: "t", transport=transport)
            self.assertEqual(fresh.restore(), 2)
            restored = CaseStore(second)
            self.addCleanup(restored.close)
            self.assertEqual(restored.sweep_blobs(), 1)
            self.assertEqual(fresh.sync().get("removed"), 1)
            self.assertEqual(len(blobs()), 1)
            self.assertEqual(restored.file_bytes(restored.list_files(kept["id"])[0]["id"])[0], b"bleibt hier")
            del third


class ImportTests(unittest.TestCase):
    def test_a_dossier_placed_in_the_volume_becomes_a_case(self):
        from fastapi.testclient import TestClient
        from casepath.web.app import create_app
        from casepath.config import load_settings
        from casepath.web.volume import VolumeClient
        files, transport = fake_volume()
        files[f"{VOLUME}/incoming/Fall 1.txt"] = b"Der Vermieter hat nicht geantwortet."
        files[f"{VOLUME}/incoming/schimmel/Fall 2.pdf.part"] = b"x"   # not a case file
        files[f"{VOLUME}/outside.txt"] = b"x"
        with tempfile.TemporaryDirectory() as data:
            settings = load_settings({"CASEPATH_DATA_DIR": data, "CASEPATH_DEV_USER": "anna", "CASEPATH_VOLUME": VOLUME})
            client = TestClient(create_app(settings, model_factory=lambda: None, store=CaseStore(data),  # a given store: no volume copy here
                                           files=VolumeClient("https://adb.example.azuredatabricks.net", lambda: "t", transport=transport)))
            listed = client.get("/api/imports").json()["files"]
            self.assertEqual([(f["name"], f["case"]) for f in listed], [("Fall 1.txt", None)])
            created = client.post("/api/imports", json={"path": listed[0]["path"]}).json()
            self.assertEqual((created["case"]["title"], created["file"]["name"]), ("Fall 1", "Fall 1.txt"))
            self.assertEqual(client.get("/api/imports").json()["files"][0]["case"], created["case"]["id"])
            self.assertEqual(client.post("/api/imports", json={"path": listed[0]["path"]}).status_code, 409)
            self.assertEqual(client.post("/api/imports", json={"path": f"{VOLUME}/outside.txt"}).status_code, 422)
            self.assertTrue(client.get("/api/health").json()["imports"])
            # a prepared case folder imports as one case, with its extraction as prepared
            files[f"{VOLUME}/incoming/Dossier 3/case.json"] = json.dumps({"format": "casepath.prepared-case/1", "title": "Dossier 3", "intake": {},
                "files": [{"name": "Brief.txt", "file": "files/01-Brief.txt", "media_type": "text/plain", "kind": "text",
                           "extraction": {"text": "Die Verwaltung hat nicht reagiert.", "pages": None}, "page_images": {}}]}).encode()
            files[f"{VOLUME}/incoming/Dossier 3/files/01-Brief.txt"] = b"Die Verwaltung hat nicht reagiert."
            listed = {f["name"]: f for f in client.get("/api/imports").json()["files"]}
            self.assertTrue(listed["Dossier 3"]["prepared"])
            self.assertEqual((listed["Dossier 3"]["title"], listed["Dossier 3"]["files"]), ("Dossier 3", 1))  # each dossier is recognisable
            # a folder whose name was made safe for storage lists under the name as uploaded (point 8)
            files[f"{VOLUME}/incoming/Brief_geschw-rzt/case.json"] = json.dumps({"format": "casepath.prepared-case/1", "title": "Brief_geschwärzt",
                "intake": {}, "source_name": "Brief_geschwärzt.txt", "files": []}).encode()
            self.assertIn("Brief_geschwärzt.txt", {f["name"] for f in client.get("/api/imports").json()["files"]})
            prepared = client.post("/api/imports", json={"path": listed["Dossier 3"]["path"]}).json()["case"]
            self.assertEqual(prepared["title"], "Dossier 3")
            self.assertEqual(client.get(f"/api/files/{client.get('/api/cases/' + prepared['id']).json()['files'][0]['id']}/text").json()["text"],
                             "Die Verwaltung hat nicht reagiert.")
            client.app.state.runs.shutdown()
            client.app.state.store.close()


if __name__ == "__main__":
    unittest.main()
