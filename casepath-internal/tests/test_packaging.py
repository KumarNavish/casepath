"""What an installed copy holds (pyproject.toml, [tool.setuptools.package-data]): every file of the package that is not
Python source must match one of the package-data patterns, or a wheel leaves it out and the installed app misses it (a
form, an area, an options file, the interface). Checked by the patterns alone, without building a wheel, as setuptools
matches them: relative to the package, part by part, a «*» never crossing a «/»."""
from fnmatch import fnmatchcase
from pathlib import Path
import re
import unittest

PROJECT = Path(__file__).resolve().parents[1]
PACKAGE = PROJECT / "casepath"


def package_data():
    """The package-data patterns of the package «casepath»."""
    text = (PROJECT / "pyproject.toml").read_text()
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10: the one table read by hand
        table = re.search(r"^\[tool\.setuptools\.package-data\]\s*\ncasepath\s*=\s*\[(.*?)\]", text, re.M | re.S)
        return re.findall(r'"([^"]+)"', table.group(1))
    return tomllib.loads(text)["tool"]["setuptools"]["package-data"]["casepath"]


def matches(relative, pattern):
    """Whether a path inside the package matches a package-data pattern, as setuptools globs it."""
    parts, wanted = relative.split("/"), pattern.split("/")
    return len(parts) == len(wanted) and all(fnmatchcase(p, w) for p, w in zip(parts, wanted))


class PackageDataTests(unittest.TestCase):
    def test_every_file_that_is_not_python_is_package_data(self):
        patterns = package_data()
        files = [p.relative_to(PACKAGE).as_posix() for p in sorted(PACKAGE.rglob("*"))
                 if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".py", ".pyc", ".pyo"}]
        self.assertTrue(files)
        self.assertEqual([f for f in files if not any(matches(f, p) for p in patterns)], [])

    def test_the_areas_options_files_are_package_data(self):
        patterns = package_data()
        self.assertTrue(any(matches("process/areas/options/mietmangel-handler.json", p) for p in patterns))
        self.assertFalse(any(matches("process/areas/options/notes/old.json", p) for p in patterns))  # one level, as declared


if __name__ == "__main__":
    unittest.main()
