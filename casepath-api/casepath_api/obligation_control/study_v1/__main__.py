"""Zero-provider commands only. No command enables inference or target access."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from .wire import save, load
from .schedule import DEFAULT_CONFIG, render_plan
from .inputs import read_release


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    default=sub.add_parser('write-config');default.add_argument('--output',type=Path,required=True)
    render=sub.add_parser('render');render.add_argument('--release-root',type=Path,required=True)
    render.add_argument('--config',type=Path,required=True);render.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='write-config':
        save(args.output,DEFAULT_CONFIG);return
    config=load(args.config)
    sources,cases,projection=read_release(args.release_root,expected_pdf_version=config['pdf_projector_version'])
    args.output.mkdir(parents=True,exist_ok=True)
    save(args.output/'SOURCE_INPUT.json',sources)
    save(args.output/'OBSERVABLE_INPUTS.json',cases)
    save(args.output/'INPUT_PROJECTION.json',projection)
    plan=render_plan(config,sources,cases,args.output)
    print(json.dumps(plan['summary'],indent=2))
    # Nonzero is intentional: a rendered but unaffordable matrix must not be
    # mistaken for dispatch approval by shell chaining.
    if plan['summary']['exceeds_even_unallocated_credit_balance']:
        raise SystemExit(3)

if __name__=='__main__':main()
