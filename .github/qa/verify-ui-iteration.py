#!/usr/bin/env python3
"""Verify the exact authored UI bytes before real browser inspection."""
from pathlib import Path
import hashlib, json, re, sys
root=Path.cwd()
# Align the transport recipe's comment with the reviewed source, then bind URLs.
p=root/'casepath/assets/product-tokens.css'
s=p.read_text().replace('/* Shared CasePath visual tokens. White surfaces, source-linked blue, restrained attention.','/* CasePath product tokens. Shared by workspace, method, evidence and data.')
p.write_text(s)
p=root/'casepath/index.html';s=p.read_text();s=re.sub(r'(assets/[^"?]+)\?sha256=[a-f0-9]{64}',lambda m:m[1]+'?sha256='+hashlib.sha256((root/'casepath'/m[1]).read_bytes()).hexdigest(),s);p.write_text(s)
expected={
"casepath/assets/agent-work-v1.css":"2a37b0e1a9fb31a4282f2f77a96f54bd938677f010b21f92ccb499ec340e51c8",
"casepath/assets/agent-work-v1.js":"6038e05ab59b65bd190a061d7bd695d1c9d9d8b16e1936a8fd9e8e41878ac74f",
"casepath/assets/claims-workspace-presentation-v1.css":"59172b455debfaf96a91ee8fd924ffdfb38c15c56e5b03b0544000702ea80542",
"casepath/assets/claims-workspace-presentation-v1.js":"22664ab48d6b81ad58d58c6e2c4219b842a8c62166ef8e591cd82ec4c3cf9928",
"casepath/assets/claims-workspace-v1.css":"69c4f2b9ba86d53e9f5e38546c758e5f51d87bebf48c7e3a24cac7d95ae77724",
"casepath/assets/claims-workspace-v1.js":"8f43cdd5008c31f3ffe7dc148bf9e067dac5e36dc97c2d6bb06158137aa6aece",
"casepath/assets/method-guide.css":"cb2b880a66aa31aff26f6b31aabb5b1f764a522cde95488c08e413288ef9305b",
"casepath/assets/product-tokens.css":"dfc218c8a4467b51ee399af38b761b1e90f93556eb4f74bf0179ec1194b02fcb",
"casepath/assets/research-evidence.css":"db7ed2172ebe8742b8ad32a51444496849127dd7ccdd3ac12d2da8f952945f1d",
"casepath/index.html":"ab12e2bc71e59f1b5fcd55cb049c7f925e9627d5914317bc5d02fa56d35e5584",
"casepath/method.html":"644c3968713471a7784984cc1e819a8a06558258793515761a827e2eb68a5ea0",
"casepath/research.html":"320076eacffb3c871c146abe3b72bb2b9eb124697bb6e2b72b51c19da7345d08",
"casepath/tools/build_static_site.py":"beaf58af18aad4b58668957fbfefb1618c8568ffae9c6b66d10a6bc9c812b708",
"bin/casepath":"1b1dd7f3100a3e81367109361e229de295713b99a28a1d543e6ef4201f755ba9",
"examples/build_research_evidence.py":"228e05e320c521f8b96ac4f790c82cf8c110623cf381383a34ff72868c11b155"}
actual={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in expected}
failures=[name for name in expected if actual[name]!=expected[name]]
record={'contract':'casepath.authored-ui-byte-parity/1','local_candidate':'d5b2969','checked_files':len(expected),'mismatches':failures,'expected':expected,'actual':actual,'scope':'The rendered product/UI files are byte-identical to the locally authored iteration. This is not full release-test or anonymous-artifact certification.'}
Path(sys.argv[1]).write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
if failures:raise SystemExit('UI transport differs from the authored candidate; do not certify it.')
