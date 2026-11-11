# The one cell of the "casepath deploy" notebook: copy a packaged build from the volume into the app's workspace folder.
# Nothing happens unless the widgets name the build, its file count and its casepath.js hash, and "confirm" repeats
# them as "deploy <build> <files> <hash>". A repeated or stray run (Run all) of an already deployed build changes nothing.
# Afterwards press Deploy on the app's page. Keep this as the notebook's only cell.
import hashlib
import os
import re
import shutil

for name in ("build", "files", "hash", "users", "model", "volume", "confirm"):
    dbutils.widgets.text(name, "")  # noqa: F821  (Databricks provides dbutils)
w = {name: dbutils.widgets.get(name).strip() for name in ("build", "files", "hash", "users", "model", "volume", "confirm")}  # noqa: F821
assert all(w.values()), f"fill every widget: {[k for k, v in w.items() if not v]}"
assert w["confirm"] == f"deploy {w['build']} {w['files']} {w['hash']}", "confirm must read: deploy <build> <files> <hash>"

V = f"{w['volume']}/casepath-app-{w['build']}/casepath-app"
D = f"/Workspace/Users/{w['users'].split(',')[0].strip()}/casepath-app"
N, O = D + "-new", D + "-previous"
listing = lambda root: sorted(os.path.relpath(os.path.join(a, f), root) for a, _, fs in os.walk(root) for f in fs)
js = lambda root: hashlib.sha256(open(root + "/casepath/web/ui/assets/casepath.js", "rb").read()).hexdigest()[:12]

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
