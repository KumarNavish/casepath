import json, os, time
from pathlib import Path
import pytest
ROOT=Path(os.environ['CASEPATH_QA_REPOSITORY']).resolve()
OUT=Path(os.environ['CASEPATH_QA_ARTIFACTS'])
def identity(item):
    return item.path.resolve().relative_to(ROOT).as_posix()+'::'+item.nodeid.split('::',1)[1]
def pytest_collection_finish(session):
    rows=[{'id':identity(item),'pytest_nodeid':item.nodeid,'file':item.path.resolve().relative_to(ROOT).as_posix()} for item in session.items]
    (OUT/'collected.json').write_text(json.dumps(rows,indent=2))
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item,call):
    result=yield
    report=result.get_result()
    row={'id':identity(item),'when':report.when,'outcome':report.outcome,'duration':report.duration,'utc_epoch':time.time()}
    if report.skipped: row['skip_reason']=str(report.longrepr)
    if report.failed: row['failure']=str(report.longrepr)
    with (OUT/'reports.jsonl').open('a') as handle: handle.write(json.dumps(row)+'\n')
