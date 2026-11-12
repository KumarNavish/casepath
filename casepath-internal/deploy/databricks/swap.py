# The one cell of the "casepath deploy" notebook: copy a packaged build from the volume into the app's workspace folder.
# It reads one notebook parameter, "confirm" (made with Edit > Add parameter), which must read
# "deploy <build> <files> <tree hash>" for the build uploaded to the volume (package.sh prints the tree hash). Empty or malformed: nothing happens. Already
# deployed: nothing happens, so "Run all" or a repeated run is harmless. Afterwards press Deploy on the app's page.
# Keep this as the notebook's only cell.
import hashlib
import os
import re
import shutil

# The three deployment values are filled in here in the notebook only, never in Git (as in app.yaml).
USERS, MODEL, VOLUME = "FILL-IN: pilot e-mail addresses", "FILL-IN: the gateway model's exact name", "FILL-IN: /Volumes/<catalog>/<schema>/<volume>"
assert not any(v.startswith("FILL-IN") for v in (USERS, MODEL, VOLUME)), "fill in USERS, MODEL and VOLUME in this cell first"
confirm = dbutils.widgets.get("confirm").strip()  # noqa: F821  (Databricks provides dbutils)
match = re.fullmatch(r"deploy ([0-9a-f]{7,40}) (\d+) ([0-9a-f]{12})", confirm)
assert match, "confirm must read: deploy <build> <files> <hash>"
w = {"build": match.group(1), "files": match.group(2), "hash": match.group(3), "users": USERS, "model": MODEL, "volume": VOLUME}

V = f"{w['volume']}/casepath-app-{w['build']}/casepath-app"
D = f"/Workspace/Users/{w['users'].split(',')[0].strip()}/casepath-app"
N, O = D + "-new", D + "-previous"
listing = lambda root: sorted(os.path.relpath(os.path.join(a, f), root) for a, _, fs in os.walk(root) for f in fs)
def js(root):
    """The build's identity: every file's path and bytes, app.yaml excluded (it is filled here); as package.sh prints it."""
    h = hashlib.sha256()
    for rel in listing(root):
        if rel != "app.yaml":
            h.update(rel.encode() + b"\0" + open(os.path.join(root, rel), "rb").read())
    return h.hexdigest()[:12]

if os.path.exists(D + "/casepath/web/ui/assets/casepath.js") and js(D) == w["hash"]:
    print("already deployed:", w["build"], js(D), "- nothing changed")
else:
    assert len(listing(V)) == int(w["files"]) and js(V) == w["hash"], ("the volume copy differs", len(listing(V)), js(V))
    shutil.rmtree(N, ignore_errors=True)
    shutil.copytree(V, N)
    assert listing(N) == listing(V) and js(N) == js(V), "the copy differs"
    values = [w["users"], w["model"], w["volume"]]
    text = re.sub(r'"FILL-IN:[^"]*"', lambda m: '"' + values.pop(0) + '"', open(N + "/app.yaml").read())
    assert not values and "FILL-IN" not in text, "app.yaml has an unexpected number of FILL-IN values"
    open(N + "/app.yaml", "w").write(text)
    shutil.rmtree(O, ignore_errors=True)
    shutil.copytree(D, O)
    shutil.rmtree(D)
    shutil.copytree(N, D)
    if listing(D) == listing(N) and js(D) == w["hash"]:
        print("swap ok:", w["build"], len(listing(D)), "files", js(D), "- now press Deploy on the app's page")
    else:
        shutil.rmtree(D, ignore_errors=True)
        shutil.copytree(O, D)
        raise AssertionError("swap failed; the previous copy is restored")
