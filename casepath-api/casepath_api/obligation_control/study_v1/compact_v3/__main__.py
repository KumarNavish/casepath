"""Zero-provider renderer. No run/score/authorize subcommand exists."""
from __future__ import annotations
import argparse
import importlib.util
import json
import time
from pathlib import Path
from ..inputs import read_release
from ..adapters import NativeBoundary
from ..wire import sha,load,save,Invalid
from .schedule import configuration,render_plan


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native-binding',type=Path,required=True,help='Existing native schema/parser hash binding; not a new evaluator')
    p.add_argument('--config',type=Path)
    args=p.parse_args();started=time.perf_counter();cpu=time.process_time()
    # Refuse deployment on the old vulnerable ingestion code. The mechanical
    # release_binding and inputs fixes remain untouched by this delta.
    if importlib.util.find_spec('casepath_api.obligation_control.study_v1.release_binding') is None:
        raise Invalid('current independently fixed release_binding module is required')
    config=load(args.config) if args.config else configuration()
    sources,cases,input_receipt=read_release(args.release,expected_pdf_version=config['pdf_projector_version'])
    native=NativeBoundary(args.release,load(args.native_binding))
    plan=render_plan(config,sources,cases,native,args.output)
    save(args.output/'RENDER_EXECUTION.json',{'wall_seconds':time.perf_counter()-started,'cpu_seconds':time.process_time()-cpu,
      'input_projection_receipt':input_receipt,'provider_calls':0,'target_scoring':False,
      'dependencies':{'inputs_py_sha256':sha(Path(__import__('casepath_api.obligation_control.study_v1.inputs',fromlist=['x']).__file__).read_bytes())}})
    print(json.dumps(plan['summary'],indent=2))
    return 0 if plan['summary']['fits_observed_upper_bound'] else 3

if __name__=='__main__':raise SystemExit(main())
