#!/usr/bin/env python3
"""Apply the authored UI iteration in an isolated CI checkout, then seal normally.

This is a reviewable transport recipe, not a second product implementation.
It does not change corpus, predictions, scorers, journal semantics, or credentials.
The workflow retains the resulting readable diff and rendered evidence.
"""
from pathlib import Path
import hashlib
import re

root = Path.cwd()

def edit(relative, old, new, count=1):
    p = root / relative
    source = p.read_text()
    if source.count(old) != count:
        raise SystemExit(f'Unexpected source preimage: {relative}: {old[:100]!r}')
    p.write_text(source.replace(old, new))

tokens = '''/* Shared CasePath visual tokens. White surfaces, source-linked blue, restrained attention.
   Color conveys a named state; labels and icons remain necessary. */
:root {
  --cp-ink: #17263d;
  --cp-muted: #55657a;
  --cp-line: #dde4ed;
  --cp-chrome: #f5f7fa;
  --cp-soft: #f9fafc;
  --cp-accent: #234e82;
  --cp-accent-hover: #183b66;
  --cp-accent-soft: #edf2f9;
  --cp-focus: #315f9d;
  --cp-supported: #285b75;
  --cp-amber: #875c29;
  --cp-attention-soft: #fbf5ec;
  --cp-violet: #605784;
  --cp-font: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  --cp-text-xs: 12px;
  --cp-text-sm: 13px;
  --cp-text-base: 14px;
  --cp-text-lg: 17px;
  --cp-space-1: 4px;
  --cp-space-2: 8px;
  --cp-space-3: 12px;
  --cp-space-4: 16px;
  --cp-space-6: 24px;
  --cp-space-8: 32px;
  --cp-space-12: 48px;
  --cp-radius-sm: 4px;
  --cp-radius: 8px;
  --cp-motion: 140ms;
}
'''
(root/'casepath/assets/product-tokens.css').write_text(tokens)
p=root/'casepath/assets/claims-workspace-v1.css';s=p.read_text()
s=s.replace('--cp-ink:#202125;--cp-muted:#65676f;--cp-line:#e7e7ec;--cp-chrome:#f5f5f7;--cp-soft:#fafafb;--cp-accent:#8f2335;--cp-green:#32664a;--cp-amber:#866027;','--cp-green:var(--cp-supported);')
s=s.replace('color:#202125','color:var(--cp-ink)').replace('font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif','font-family:var(--cp-font)')
s=s.replace('outline:2px solid #8f2335','outline:2px solid var(--cp-focus)').replace('background:#741b2a;border-color:#741b2a','background:var(--cp-accent-hover);border-color:var(--cp-accent-hover)')
p.write_text(s)
color_map={'#8f2335':'var(--cp-accent)','#8F2335':'var(--cp-accent)','#761c2b':'var(--cp-accent-hover)','#741b2a':'var(--cp-accent-hover)','#f6ecef':'var(--cp-accent-soft)','#f8eef1':'var(--cp-accent-soft)','#f7edf0':'var(--cp-accent-soft)','#32664a':'var(--cp-supported)','#32634a':'var(--cp-supported)','#eef6f0':'var(--cp-accent-soft)','#e0efe4':'#e5edf6','#82aa8f':'#7093b5','#866027':'var(--cp-amber)'}
for rel in ['casepath/assets/claims-workspace-presentation-v1.css','casepath/assets/agent-work-v1.css']:
 p=root/rel;s=p.read_text()
 for old,new in color_map.items():s=s.replace(old,new)
 s=s.replace('rgba(143,35,53,','rgba(35,78,130,')
 p.write_text(s)
edit('casepath/assets/claims-workspace-presentation-v1.js','<section id="cwDetail" class="cw-detail" hidden role="region" aria-label="Claim workbench"><article id="cwDetailPanel" class="cw-detail-panel" tabindex="-1"></article></section>','<main id="cwDetail" class="cw-detail" hidden aria-label="Claim workspace"><article id="cwDetailPanel" class="cw-detail-panel" tabindex="-1"></article></main>')
edit('casepath/assets/claims-workspace-presentation-v1.js','<strong>Development workspace</strong><small>Synthetic intake workspace</small>','<strong>Public synthetic data</strong><small>Local claims workspace</small>')
edit('casepath/assets/claims-workspace-presentation-v1.js','<div class="cp-titlebar-actions"><a href="method.html">How it works</a>','<div class="cp-titlebar-actions"><a href="method.html">Method</a><a href="research.html">Evidence</a>')
edit('casepath/assets/claims-workspace-presentation-v1.js','<form id="cwFilters" class="cp-queue-tools" role="search">','<section class="cp-start-here" aria-labelledby="cpStartHereTitle"><div><h2 id="cpStartHereTitle">See why a document is needed.</h2><p>Open a synthetic claim with two conflicting notices, inspect its sources, then follow the next action.</p></div><a class="cw-button cp-example-link" href="#claim=clm_0e538990cc6ba7ef">Explore an example ${icon(\'arrow\')}</a></section>\n<form id="cwFilters" class="cp-queue-tools" role="search">')
edit('casepath/assets/agent-work-v1.js',"work.prepend(section);state.renderKey=null;","const nextAction=work.querySelector('#cwLoopWorkbench');if(nextAction)nextAction.after(section);else work.prepend(section);state.renderKey=null;")
edit('casepath/assets/agent-work-v1.js',"exact source statement${objects.filter(o=>o.kind==='assertion').length===1?'':'s'}","cited statement${objects.filter(o=>o.kind==='assertion').length===1?'':'s'}")
p=root/'casepath/assets/agent-work-v1.js';s=p.read_text();a=s.index('  function compactSummary(summary){');b=s.index('  function roleTrack(summary){',a)
s=s[:a]+'''  function compactSummary(summary){
    if(!summary)return `<header class="aw-console-head"><div><span class="aw-kicker">Agent review</span><h2>${state.busy?'Starting a recorded review…':'Review not started'}</h2><p>Source reads, checked handoffs and outcomes are saved as the work runs.</p></div></header>`;
    const complete=summary.status==='completed',active=summary.current_role;
    const heading=summary.currentness==='historical'?'Earlier review retained':summary.currentness==='unconfirmed'?'Saved review needs checking':complete?'Review recorded':summary.status==='running'?`${h(active?.label||'Review')} in progress`:h(label(summary.status));
    const model=summary.facts_worker==='external_facts'?(modelLabel()||'External model'):'Deterministic worker';
    return `<header class="aw-console-head"><div><span class="aw-kicker">Agent review · ${h(model)}</span><h2>${heading}</h2><p>${complete?'Inspect the sources, handoffs and acceptance checks.':h(summary.last_message||'Waiting for the next saved step.')}</p></div><div class="aw-compact-progress"><span>${summary.completed_roles}/6 stages</span><progress max="6" value="${summary.completed_roles}" aria-label="Completed review stages">${summary.completed_roles} of 6</progress></div></header>`;
  }
''' +s[b:]
old="    host.dataset.status=summary?.status||'ready';";assert old in s
s=s.replace(old,old+"\n    host.hidden=!summary&&hasStart&&!state.busy&&!pendingRequest()&&!state.messages.get(state.claim);")
s=s.replace("start.textContent=summary.recovery?.can_resume?'Resume saved agent review above'","start.textContent=summary.recovery?.can_resume?'Resume the saved review below'")
old='host.innerHTML=`<div class="aw-review-console">${compactSummary(summary)}${roleTrack(summary)}${liveSignal(summary)}${stale}<div class="aw-review-controls">${actions}${worker}${summary?\'<button class="aw-text-button" type="button" data-aw-timeline>Review trace</button>\':\'\'}</div><p class="aw-message" id="awRequestStatus" role="status" aria-live="polite"></p></div>`;'
assert old in s
new='host.innerHTML=`<div class="aw-review-console aw-compact">${compactSummary(summary)}<div class="aw-review-controls">${actions}${worker}${summary?\'<button class="aw-text-button" type="button" data-aw-timeline>Inspect review <span aria-hidden="true">→</span></button>\':\'\'}</div>${stale}<p class="aw-message" id="awRequestStatus" role="status" aria-live="polite"></p></div>`;'
s=s.replace(old,new)
old='host.innerHTML=`<header class="aw-section-heading aw-trace-heading">';assert old in s
s=s.replace(old,'host.innerHTML=`${roleTrack(state.summary)}${liveSignal(state.summary)}<header class="aw-section-heading aw-trace-heading">')
s=s.replace('<span class="aw-kicker">Persisted execution</span><h3>Review trace</h3>','<span class="aw-kicker">Recorded work</span><h3>What the review did</h3>')
old="    const external=all.some(e=>e.worker_kind==='external');";assert old in s
s=s.replace(old,old+"\n    const focused=host.contains(document.activeElement)?document.activeElement:null;const focusedEvent=focused?.dataset.awEvent,focusedRole=focused?.dataset.awRole,focusedToggle=focused?.hasAttribute('data-aw-trace-toggle');")
old="${!events.length?'<p class=\"aw-muted\">No persisted milestones are recorded yet.</p>':''}`;\n  }\n  function renderProcess(){";assert old in s
s=s.replace(old,"${!events.length?'<p class=\"aw-muted\">No persisted milestones are recorded yet.</p>':''}`;\n    const retained=focusedEvent?host.querySelector(`[data-aw-event=\"${CSS.escape(focusedEvent)}\"]`):focusedRole?host.querySelector(`[data-aw-role=\"${CSS.escape(focusedRole)}\"]`):focusedToggle?host.querySelector('[data-aw-trace-toggle]'):null;retained?.focus({preventScroll:true});\n  }\n  function renderProcess(){")
old='    const focusedRole=host.contains(document.activeElement)?document.activeElement?.dataset?.awRole:null;'
new="    const focused=host.contains(document.activeElement)?document.activeElement:null;\n    const focusAttribute=['data-aw-timeline','data-aw-start','data-aw-resume','data-aw-retry'].find(a=>focused?.hasAttribute(a));\n    const focusedWorker=focused?.id==='awFactsWorker';\n    const workerValue=host.querySelector('#awFactsWorker')?.value;";assert old in s;s=s.replace(old,new,1)
old='    if(focusedRole)host.querySelector(`[data-aw-role="${CSS.escape(focusedRole)}"]`)?.focus({preventScroll:true});'
new="    const workerSelect=host.querySelector('#awFactsWorker');if(workerSelect&&workerValue)workerSelect.value=workerValue;\n    const retainedFocus=focusAttribute?host.querySelector(`[${focusAttribute}]`):focusedWorker?workerSelect:null;\n    retainedFocus?.focus({preventScroll:true});";assert old in s;s=s.replace(old,new,1)
p.write_text(s)
edit('casepath/assets/claims-workspace-v1.js',"$('#cwCommandStatus').textContent='Showing the latest saved claim record.';","$('#cwCommandStatus').textContent='';\n    const saved=$('.cp-last-saved');if(saved){saved.title='Showing the latest saved claim record.';saved.setAttribute('aria-label','Showing the latest saved claim record.');}")
p=root/'casepath/assets/method-guide.css';s=p.read_text();s=s.replace('--ink:#202125','--ink:var(--cp-ink)').replace('--muted:#65676f','--muted:var(--cp-muted)').replace('--line:#e7e7ec','--line:var(--cp-line)').replace('--chrome:#f5f5f7','--chrome:var(--cp-chrome)').replace('--accent:#8f2335','--accent:var(--cp-accent)')
s=s.replace('padding:80px 0 72px','padding:44px 0 38px').replace('gap:70px','gap:48px')
s=s.replace('font-size:clamp(42px,5.8vw,70px);line-height:1.04;letter-spacing:-3px','font-size:clamp(32px,3.8vw,44px);line-height:1.12;letter-spacing:-1.4px')
s=s.replace('.intro p{font-size:19px','.intro p{font-size:16px').replace('color:#858792','color:var(--cp-muted)')
s=s.replace('.intro{gap:30px;padding:55px 0}','.intro{gap:30px;padding:36px 0}')
s=s.replace('.intro{display:block;padding:48px 0 38px}','.intro{display:block;padding:30px 0 26px}').replace('.intro p{margin-top:26px;max-width:360px;font-size:17px}','.intro p{margin-top:16px;max-width:360px;font-size:15px}')
s=s.replace('h1{font-size:49px;letter-spacing:-2px}','h1{font-size:34px;letter-spacing:-1px}')
p.write_text(s)
p=root/'casepath/assets/research-evidence.css';s=p.read_text();s=s.replace('padding:76px 0 64px','padding:44px 0 38px').replace('font-size:clamp(40px,5.4vw,65px)','font-size:clamp(32px,3.8vw,44px)').replace('letter-spacing:-2.6px','letter-spacing:-1.4px').replace('.lead{font-size:19px','.lead{font-size:16px').replace('padding-top:58px','padding-top:36px').replace('font-size:42px;letter-spacing:-1.7px','font-size:34px;letter-spacing:-1px');p.write_text(s)
p=root/'casepath/method.html';s=p.read_text();needle='  <link rel="stylesheet" href="assets/method-guide.css">';assert needle in s;s=s.replace(needle,'  <link rel="stylesheet" href="assets/product-tokens.css">\n'+needle).replace('Every request<br>needs a reason.','Every request needs a reason.');p.write_text(s)
for rel in ['casepath/research.html','examples/build_research_evidence.py']:
 p=root/rel;s=p.read_text();needle='<link rel="stylesheet" href="assets/method-guide.css">';assert needle in s;s=s.replace(needle,'<link rel="stylesheet" href="assets/product-tokens.css">'+needle,1);p.write_text(s)
p=root/'casepath/tools/build_static_site.py';s=p.read_text();s=s.replace('PUBLIC_ASSETS = (\n','PUBLIC_ASSETS = (\n    "assets/product-tokens.css",\n',1);s=s.replace('CONTENT_BOUND_ASSETS = (\n','CONTENT_BOUND_ASSETS = (\n    "assets/product-tokens.css",\n',1);p.write_text(s)
p=root/'casepath/assets/agent-work-v1.css';s=p.read_text();changes={
'--aw-ink:#242730':'--aw-ink:var(--cp-ink)','--aw-muted:#636978':'--aw-muted:var(--cp-muted)','--aw-line:#e5e7ed':'--aw-line:var(--cp-line)','--aw-soft:#f7f7fa':'--aw-soft:var(--cp-soft)',
'--aw-agent-soft:#f7f7f9':'--aw-agent-soft:var(--cp-soft)','--aw-agent-soft-2:#f2f3f6':'--aw-agent-soft-2:var(--cp-chrome)',
'--aw-green:#3f7657':'--aw-green:var(--cp-supported)','--aw-green-soft:#edf6f0':'--aw-green-soft:var(--cp-accent-soft)',
'--aw-amber:#8b672f':'--aw-amber:var(--cp-amber)','--aw-amber-soft:#fbf6ec':'--aw-amber-soft:var(--cp-attention-soft)',
'#387052':'var(--cp-supported)','#37704d':'var(--cp-supported)','#38724f':'var(--cp-supported)',
'#edf5ef':'var(--cp-accent-soft)','#d2e4d8':'var(--cp-line)','#d0e3d4':'var(--cp-line)',
'#b998a3':'#a5bad3','#faf5f6':'var(--cp-accent-soft)','#faf8fa':'var(--cp-soft)',
'#f6f4f5':'var(--cp-soft)','#717683':'var(--cp-muted)','#22252c':'var(--cp-ink)',
'#4c6655':'var(--cp-supported)','animation:aw-active-pulse 1.6s ease-in-out infinite;':''}
for a,b in changes.items():s=s.replace(a,b)
s=re.sub(r'@keyframes aw-active-pulse\{0%,100%\{[^}]*\}50%\{[^}]*\}\}','',s)
s+='''
/* Current action comes first; recorded review is a compact, inspectable summary. */
.aw-work-strip{margin:0 0 8px;padding:0;border:0;}
.aw-review-console.aw-compact{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:12px 20px;padding:18px 0;border:0;border-bottom:1px solid var(--cp-line);border-radius:0;box-shadow:none;background:transparent;}
.aw-compact .aw-console-head{margin:0;gap:20px;align-items:center;}
.aw-compact .aw-console-head .aw-kicker{font-size:11px;margin-bottom:4px;color:var(--cp-muted);}
.aw-compact .aw-console-head h2{font-size:15px;line-height:1.4;letter-spacing:-.15px;color:var(--cp-ink);}
.aw-compact .aw-console-head p{font-size:12px;line-height:1.6;color:var(--cp-muted);margin:4px 0 0!important;}
.aw-compact-progress{flex:0 0 94px;display:grid;gap:7px;align-content:center;font-size:11px;color:var(--cp-muted);font-variant-numeric:tabular-nums;}
.aw-compact-progress progress{display:block;appearance:none;width:94px;height:4px;overflow:hidden;border:0;border-radius:2px;background:var(--cp-line);accent-color:var(--cp-accent);}
.aw-compact-progress progress::-webkit-progress-bar{background:var(--cp-line);}
.aw-compact-progress progress::-webkit-progress-value{background:var(--cp-accent);}
.aw-compact-progress progress::-moz-progress-bar{background:var(--cp-accent);}
.aw-compact .aw-review-controls{border:0;margin:0;padding:0;gap:8px 16px;justify-content:flex-end;}
.aw-compact .aw-stale,.aw-compact .aw-message{grid-column:1/-1;margin:0!important;}
#claimsWorkspace .aw-compact .aw-text-button{font-size:12px;min-height:36px;}
.aw-timeline>.aw-agent-flow{margin:0 0 16px;}
.aw-timeline>.aw-live-signal{margin:0 0 28px;}
.aw-agent-copy strong,.aw-team-agent h2{font-size:12px;}
.aw-agent-copy small,.aw-live-signal small,.aw-live-signal p,.aw-trace-actions>span,.aw-trace-list time,.aw-trace-list .aw-event-role,.aw-trace-list .aw-event-state,.aw-team-agent p,.aw-team-agent small{font-size:11px;line-height:1.6;}
.aw-agent-copy em,.aw-trace-list .aw-event-role em{font-size:10px;}
.aw-handoff span{font-size:10px;text-transform:none;letter-spacing:0;}
.aw-handoff{color:var(--cp-muted);}
.aw-trace-list strong,.aw-trace-list blockquote,.aw-live-signal strong{font-size:13px;}
.aw-agent-flow .aw-agent{background:none;padding:10px 4px;}
@media(max-width:900px){
 .aw-review-console.aw-compact{grid-template-columns:1fr;gap:7px;padding:16px 0;}
 .aw-compact .aw-review-controls{justify-content:flex-start;}
 .aw-compact .aw-console-head{gap:12px;}
}
@media(max-width:600px){
 .aw-compact .aw-console-head .aw-kicker{font-size:11px;}
 .aw-compact .aw-console-head h2{font-size:15px;}
 .aw-compact .aw-console-head p{font-size:12px;}
 .aw-compact-progress{flex-basis:70px;font-size:11px;}
 .aw-compact-progress progress{width:70px;}
 .aw-agent-copy strong{font-size:12px;}
 .aw-agent-copy small,.aw-live-signal p{font-size:11px;}
 .aw-agent-copy em{font-size:10px;}
 .aw-live-signal strong{font-size:13px;}
}
''';p.write_text(s)
p=root/'casepath/assets/claims-workspace-presentation-v1.css';s=p.read_text();s+='''
/* A real teaching claim, offered without starting work or changing a journal. */
.cp-start-here{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:20px 0 24px;margin-bottom:4px;border-bottom:1px solid var(--cp-line);}
.cp-start-here h2{margin:0;font-size:17px;font-weight:600;letter-spacing:-.25px;line-height:1.4;color:var(--cp-ink);}
.cp-start-here p{margin:6px 0 0!important;max-width:650px;font-size:13px;line-height:1.6;color:var(--cp-muted);}
#claimsWorkspace .cp-example-link{display:inline-flex;align-items:center;justify-content:center;gap:10px;flex-shrink:0;min-height:40px;padding:9px 13px;border:1px solid var(--cp-accent);border-radius:6px;color:var(--cp-accent);text-decoration:none;font-size:12px;font-weight:550;background:white;}
#claimsWorkspace .cp-example-link:hover{background:var(--cp-accent-soft);}
.cp-example-link .cp-icon{width:15px;height:15px;flex-basis:15px;}
.cp-titlebar-actions a{white-space:nowrap;}
.cp-work-column{scroll-padding-top:55px;}
@media(max-width:700px){
 .cp-start-here{display:block;padding:16px 0 20px;}
 .cp-start-here h2{font-size:16px;}
 .cp-start-here p{font-size:12px;margin-top:5px!important;}
 #claimsWorkspace .cp-example-link{margin-top:12px;min-height:40px;}
 .cp-titlebar-actions{gap:12px;}
 .cp-claim-title h1{font-size:20px;line-height:1.4;}
 .cp-decision h2{font-size:21px;line-height:1.35;}
}
''';p.write_text(s)
p=root/'casepath/index.html';s=p.read_text();needle='  <link rel="stylesheet" href="assets/claims-workspace-v1.css?sha256=';assert needle in s
s=s.replace(needle,'  <link rel="stylesheet" href="assets/product-tokens.css?sha256='+hashlib.sha256(tokens.encode()).hexdigest()+'">\n'+needle,1)
s=re.sub(r'(assets/[^"?]+)\?sha256=[a-f0-9]{64}',lambda m:m[1]+'?sha256='+hashlib.sha256((root/'casepath'/m[1]).read_bytes()).hexdigest(),s);p.write_text(s)
# Root-cause Linux startup fix: preserve the strict single-link runtime policy.
p=root/'bin/casepath';s=p.read_text();assert s.count('"$uv_command" pip sync')==2
s=s.replace('"$uv_command" pip sync --python','"$uv_command" pip sync --link-mode copy --python')
s=s.replace('"$uv_command" pip sync \\\n    --python','"$uv_command" pip sync \\\n    --link-mode copy \\\n    --python')
assert s.count('--link-mode copy')==2;p.write_text(s)
print('Applied the authored UI iteration and private-copy dependency synchronization. Normal source sealing and verification are still required.')
