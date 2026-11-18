"""The house profile (casepath/house, docs/HOUSE.md): what belongs to one insurer is named in one file and can be replaced.

- With nothing configured the house is Protekta, and a representative synthetic case renders exactly as it did before
  the profile existed (tests/fixtures/house/protekta_three_phases.json, taken on the commit before it).
- With another profile (tests/fixtures/house/beispiel.json, an invented insurer) the same case names that house in the
  account, the letters and the screen, and the whole case view no longer names Protekta; a house that brings folders of
  its own instead of borrowing the shipped ones is read from them.
- A profile that misses a required field is refused, naming the field, before anything starts.
- The page learns the house from its first call and writes no insurer's name of its own.

The house is read once per process, so the cases are rendered by tests/house_probe.py in a process of its own."""
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from casepath import house
from casepath.config import SettingsError, load_settings

PROJECT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "house"
EXAMPLE = FIXTURES / "beispiel.json"
SCRIPT = (PROJECT / "casepath" / "web" / "ui" / "assets" / "casepath.js").read_text(encoding="utf-8")
FIRST_REQUEST, AFTER_IT = "2025-02-05", "2025-02-15"  # the two cuts of the case: before the first request and after it


def started(arguments, house_file=None):
    """A command of this project in a process of its own, for the built-in house or for a profile file."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop(house.VARIABLE, None)
    if house_file:
        env[house.VARIABLE] = str(house_file)
    return subprocess.run([sys.executable, *arguments], cwd=PROJECT, env=env, capture_output=True, encoding="utf-8", timeout=600)


def probe(house_file=None, *arguments):
    done = started(["-m", "tests.house_probe", *arguments], house_file)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


def words(value):
    return json.dumps(value, ensure_ascii=False)


class BuiltInHouseTests(unittest.TestCase):
    def test_the_built_in_profile_holds_the_values_the_code_had(self):
        own, package = house.built_in(), PROJECT / "casepath"
        self.assertEqual((own.id, own.name, own.legal_name), ("protekta", "Protekta", "Protekta Rechtsschutz-Versicherung AG"))
        self.assertEqual((own.recognised_by, own.claim_number), (("protekta", "rechtsschutz"), r"\d{4}\.\d{4}\.\d{4}"))
        self.assertEqual((own.conditions.short, own.conditions.name, own.conditions.name_inflected),
                         ("AVB", "Allgemeine Bedingungen", "Allgemeinen Bedingungen"))
        self.assertEqual(own.writing.case_work, "in the language of the case files, usually German, with Swiss spelling (ss, not ß)")
        self.assertEqual(own.writing.photos, "in German with Swiss\nspelling (ss, not ß)")
        self.assertEqual((own.letters.greeting, own.letters.greeting_ms, own.letters.greeting_mr, own.letters.greeting_by_name, own.letters.closing),
                         ("Sehr geehrte Damen und Herren", "Sehr geehrte Frau {name}", "Sehr geehrter Herr {name}", "Guten Tag {name}", "Freundliche Grüsse"))
        self.assertEqual([p.resolve() for p in (own.catalogue, own.knowledge_seed, own.conditions.cover, own.conditions.texts)],
                         [package / "process" / "areas", package / "process" / "knowledge_seed", package / "process" / "areas" / "cover.json",
                          PROJECT / "docs" / "sources" / "protekta"])
        self.assertEqual(own.named_in("versicher"), "protekta|rechtsschutz|versicher")

    @unittest.skipIf(os.environ.get(house.VARIABLE, "") not in ("", house.BUILT_IN), "this run is for another house")
    def test_with_nothing_configured_the_modules_read_the_built_in_house(self):
        from casepath.process import area, cover, knowledge

        own = house.active()
        self.assertIs(own, house.built_in())
        self.assertEqual((area.AREAS, cover.PATH, cover.TEXTS, knowledge.SEED_DIR),
                         (own.catalogue, own.conditions.cover, own.conditions.texts, own.knowledge_seed))
        self.assertEqual(load_settings({}).reference_pattern, own.claim_number)
        self.assertEqual(load_settings({"CASEPATH_REFERENCE_PATTERN": r"S-\d+"}).reference_pattern, r"S-\d+")  # a setting still wins
        shipped = {"note": "Protekta verlangt ihn", "insurer": ["protekta", "rechtsschutz"]}
        self.assertIs(house.in_own_name(shipped), shipped)  # the built-in house's data is handed back untouched

    def test_the_representative_case_renders_as_before_the_profile(self):
        expected = json.loads((FIXTURES / "protekta_three_phases.json").read_text(encoding="utf-8"))["cuts"]
        out = probe()
        self.assertEqual(sorted(out["cuts"]), [FIRST_REQUEST, AFTER_IT])
        for day, cut in out["cuts"].items():
            for part in ("account", "letters", "screen", "file_note", "status", "follow_up"):
                self.assertEqual(cut["shown"][part], expected[day][part], f"{day}: {part}")
        self.assertEqual(out["house"], {"id": "protekta", "name": "Protekta", "legal_name": "Protekta Rechtsschutz-Versicherung AG",
                                        "conditions": {"short": "AVB", "name_inflected": "Allgemeinen Bedingungen"}})


class AnotherHouseTests(unittest.TestCase):
    """The same case in the file of an invented insurer, «Beispiel Rechtsschutz AG»: its documents name it and carry its
    claim number."""

    @classmethod
    def setUpClass(cls):
        cls.out = probe(EXAMPLE, "--insurer-in-file", "Beispiel", "--claim-number", "B-250303")
        cls.first, cls.later = cls.out["cuts"][FIRST_REQUEST]["shown"], cls.out["cuts"][AFTER_IT]["shown"]

    def test_the_account_names_the_house_as_a_party(self):
        self.assertEqual([row["who"] for row in self.first["account"]], ["Kundschaft → Beispiel"])
        self.assertIn("Beispiel → Kundschaft", [row["who"] for row in self.later["account"]])

    def test_the_letters_follow_the_houses_lines_and_claim_number(self):
        letter = self.first["letters"]["draft"]["text"]
        self.assertTrue(letter.startswith("Unsere Referenz: B-250303\n\nGrüezi Lea Brunner\n"), letter[:80])
        self.assertIn("unter der Referenz B-250303 provisorisch registriert", letter)
        template = self.first["letters"]["for_the_customer"][0]  # the customer's own letter is marked as not the house's
        self.assertIn("in Ihrem eigenen Namen zu senden; kein Schreiben von Beispiel)", template.splitlines()[0])
        self.assertIn("\n\nGuten Tag\n\n", template)
        self.assertIn("\n\nBeste Grüsse\n\n", template)

    def test_the_screen_names_the_house_in_its_cover_points(self):
        points = self.first["screen"]["cover_points"]
        self.assertIn("Hat die Kundschaft unverzüglich gemeldet und keinen Anwalt beauftragt oder Schritte eingeleitet, bevor Beispiel sie genehmigt hat?",
                      [p["label"]["de"] for p in points])

    def test_nothing_the_case_view_returns_names_protekta(self):
        default = json.loads((FIXTURES / "protekta_three_phases.json").read_text(encoding="utf-8"))["cuts"]
        for day, cut in self.out["cuts"].items():
            for part in ("account", "letters", "screen", "file_note"):
                self.assertNotIn("Protekta", words(cut["shown"][part]), f"{day}: {part}")
                # wherever the built-in house was named, this house is
                self.assertEqual(words(cut["shown"][part]).count("Beispiel"), words(default[day][part]).count("Protekta"), f"{day}: {part}")
            whole = cut["whole_view"]  # the facts, the process, the stored run and everything else the page loads
            self.assertEqual(whole["names_protekta"], 0, day)
            self.assertGreater(whole["names_insurer_in_file"], 100, day)

    def test_the_page_is_told_the_house(self):
        self.assertEqual(self.out["house"], {"id": "beispiel", "name": "Beispiel", "legal_name": "Beispiel Rechtsschutz AG",
                                             "conditions": {"short": "ARB", "name_inflected": "Allgemeinen Rechtsschutzbedingungen"}})

    def test_a_house_with_folders_of_its_own_is_read_from_them(self):
        """The example profile borrows the shipped catalogue, cover points and seeded knowledge. Here the house brings
        copies in which its own name is written, in another place: the case comes out the same, digest included."""
        package, example = PROJECT / "casepath" / "process", json.loads(EXAMPLE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as folder:
            own = Path(folder)
            shutil.copytree(package / "areas", own / "catalogue")
            shutil.copytree(package / "knowledge_seed", own / "seed")
            for file in [*(own / "catalogue").glob("*.json"), *(own / "seed").glob("*.json")]:
                file.write_text(file.read_text(encoding="utf-8").replace("Protekta", "Beispiel"), encoding="utf-8")
            profile = {**example, "catalogue": "catalogue", "knowledge_seed": "seed",
                       "conditions": {**example["conditions"], "cover": "catalogue/cover.json", "texts": "texts"}}
            (own / "house.json").write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
            out = probe(own / "house.json", "--insurer-in-file", "Beispiel", "--claim-number", "B-250303")
        self.assertEqual(out, self.out)


class RefusedProfileTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.complete = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        for key in ("catalogue", "knowledge_seed"):  # the paths of a profile are relative to it: here they are given whole
            self.complete[key] = str((EXAMPLE.parent / self.complete[key]).resolve())
        for key in ("cover", "texts"):
            self.complete["conditions"][key] = str((EXAMPLE.parent / self.complete["conditions"][key]).resolve())

    def written(self, profile):
        path = Path(self.folder.name) / "house.json"
        path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        return path

    def without(self, *keys):
        profile = json.loads(json.dumps(self.complete))
        inner = profile
        for key in keys[:-1]:
            inner = inner[key]
        del inner[keys[-1]]
        return self.written(profile)

    def test_the_complete_profile_loads(self):
        own = house.load(self.written(self.complete))
        self.assertEqual((own.name, own.legal_name, own.conditions.short), ("Beispiel", "Beispiel Rechtsschutz AG", "ARB"))

    def test_every_missing_field_is_named(self):
        fields = [(k,) for k in house.FIELDS if not isinstance(house.FIELDS[k], dict)]
        fields += [(k, inner) for k, kind in house.FIELDS.items() if isinstance(kind, dict) for inner in kind]
        self.assertIn(("legal_name",), fields)
        self.assertIn(("conditions", "cover"), fields)
        for keys in fields:
            with self.assertRaises(house.HouseError) as refused:
                house.load(self.without(*keys))
            self.assertIn(f"house.json: the required field «{'.'.join(keys)}» is missing", str(refused.exception))

    def test_a_field_this_build_does_not_know_a_bad_number_pattern_and_a_missing_place_are_refused(self):
        for change, message in (({"motto": "x"}, "unknown field «motto»"), ({"claim_number": "B-(\\d"}, "«claim_number» is not a regular expression"),
                                ({"recognised_by": ["Beispiel"]}, "«recognised_by» holds lower-case words"), ({"name": ""}, "«name» must be a non-empty text"),
                                ({"catalogue": "nowhere"}, "«catalogue» points to"),
                                ({"letters": {**self.complete["letters"], "greeting_ms": "Guten Tag"}}, "«letters.greeting_ms» must hold {name}")):
            with self.assertRaises(house.HouseError) as refused:
                house.load(self.written({**self.complete, **change}))
            self.assertIn(message, str(refused.exception))
        with self.assertRaises(house.HouseError) as refused:
            house.load("no-such-house")
        self.assertIn("no such file", str(refused.exception))

    def test_an_incomplete_profile_stops_the_start_with_the_field_it_misses(self):
        broken = self.without("legal_name")
        done = started(["-m", "casepath", "contract"], broken)  # any command: the house is read before it starts
        self.assertEqual(done.returncode, 1)
        self.assertEqual(done.stdout, "")
        self.assertEqual(done.stderr.strip(), f"house invalid: house profile {broken}: the required field «legal_name» is missing")

    def test_the_settings_refuse_an_incomplete_profile(self):
        broken = self.without("claim_number")
        try:
            with mock.patch.dict(os.environ, {house.VARIABLE: str(broken)}):
                house.active.cache_clear()  # as a process that starts with this profile
                with self.assertRaises(SettingsError) as refused:
                    load_settings({})
            self.assertIn("the required field «claim_number» is missing", str(refused.exception))
        finally:
            house.active.cache_clear()


class OneNameTests(unittest.TestCase):
    def test_the_page_takes_the_house_from_its_first_call_and_keeps_one_default(self):
        self.assertIn('const HOUSE = { name: "Protekta", conditions: { short: "AVB", name_inflected: "Allgemeinen Bedingungen" } };', SCRIPT)
        self.assertIn("if ((health.house || {}).name) { Object.assign(HOUSE, health.house); PARTY_DE.versicherer = HOUSE.name; }", SCRIPT)
        self.assertEqual(SCRIPT.count("Protekta"), 1)  # the default, until the answer is here

    def test_no_text_in_the_code_names_the_insurer(self):
        """The insurer's name stands in its profile. In the package's Python it may stand in a comment or a docstring
        that explains where something came from, never in a text the code uses."""
        found = []
        for path in sorted((PROJECT / "casepath").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                          if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body
                          and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)}
            found += [f"{path.relative_to(PROJECT)}:{node.lineno}" for node in ast.walk(tree)
                      if isinstance(node, ast.Constant) and isinstance(node.value, str) and "Protekta" in node.value and id(node) not in docstrings]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
