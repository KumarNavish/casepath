from pathlib import Path
ROOT=Path('/workspace/casepath-smooth-stage-gate-3a02880a-20261013')
OLD=Path('/workspace/casepath-quiet-completion-gate-0d9f9e22-20261013')
for name in ['run_shard.py','verify_prepared_capsules.py']:
    raw=(OLD/'harness'/name).read_text()
    raw=raw.replace(str(OLD),str(ROOT)).replace('0d9f9e225776195f47d335b38b4ca5244d8c555c','3a02880abc3f824e06e5e31a888dc91edf1bcb9d').replace('a91a6ec3d947d82953fa7a07e35e394c6b444ff8901b99ea3084d5f56238302c','ead2ad3ddd10000737985f7db5d704b5e7366da72b54e371624f1a0709ac5c39')
    if name=='run_shard.py':
        raw=raw.replace("Path('/workspace/casepath-release-ae0-shard4') if mode=='collect'", "Path('/workspace/casepath-release-ae0-inventory') if mode=='collect'")
        raw=raw.replace("env={'HOME':str(out/'home')", "temp='/workspace/g3at'+('0' if mode=='collect' else sys.argv[2])\nhome='/workspace/g3ah'+('0' if mode=='collect' else sys.argv[2])\nenv={'HOME':home")
        raw=raw.replace("'TMPDIR':str(out/'tmp')", "'TMPDIR':temp,'TMP':temp,'TEMP':temp")
    (ROOT/'harness'/name).write_text(raw)
print('Adapted normal harness paths and exact identities; observer bytes preserved')
