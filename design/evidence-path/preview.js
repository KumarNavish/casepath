/* Read-only visual exploration. Every object is projected from a saved fictional claim. */
(() => {
  'use strict';
  const BASE='/api/claim-loops/v1/autonomous', core=window.CasePathAutonomous;
  const $=s=>document.querySelector(s), all=s=>[...document.querySelectorAll(s)];
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list=v=>Array.isArray(v)?v:[], words=v=>String(v??'').replace(/[_.:-]+/g,' ').replace(/^./,c=>c.toUpperCase());
  const shortTitle=v=>String(v||'Untitled claim').replace(/^Fictional claim\s*[·—-]\s*/i,'');
  const label=v=>({true:'Applies',false:'Does not apply',unresolved:'Unresolved',established:'Established',insufficient:'Insufficient',missing:'Missing',needed_later:'Needed later',needed_now:'Needed now',not_needed:'Not required',held_behind_question:'Depends on an unresolved question',held_not_reviewed:'Acquired · not established',completed:'Completed',ready:'Ready in the process',blocked:'Waiting for prerequisites',inactive:'Does not apply',deferred:'Awaiting evidence or authority',resolved:'Resolved',running:'Working',acquired:'Acquired',satisfied:'Satisfied'})[v]||words(v)||'Not recorded';
  const compact={'Capture issuer, receipt and end date':'Notice details','Preserve challenge or extension deadline':'Preserve deadline','Check form and service':'Form & service','Classify termination type':'Termination type','Check arrears cure preconditions':'Arrears conditions','Check separate family-home service':'Separate service','Screen stated reason and good-faith concerns':'Grounds & good faith','Assess extension evidence':'Extension evidence','Collect type-specific evidence':'Required evidence','Prepare challenge, extension or settlement':'Prepare resolution','Record termination outcome':'Record outcome'};
  const nodeName=n=>compact[n?.label]||n?.label||'Process step';
  const documentIcon='<svg viewBox="0 0 16 19" aria-hidden="true"><path d="M3 1h7l4 4v13H3zM10 1v5h4M6 10h5m-5 3h5"/></svg>';
  const proofIcon='<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 2l6 3v5c0 4-6 8-6 8s-6-4-6-8V5zM7 10l2 2 4-4"/></svg>';
  const state={claims:[],knowledge:null,cache:new Map(),claim:null,projection:null,events:[],selected:null,fact:null,doc:null,mode:'path',route:'claim',version:2};
  let epoch=0, sourceRequest=0, refs=[], returnFocus=null;
  const get=async path=>{const r=await fetch(BASE+path);if(!r.ok)throw new Error('The saved preview could not be loaded.');return r.json();};
  const citeRef=c=>{refs.push(c);return refs.length-1;};
  const descriptor=id=>state.claim.source_descriptors.find(s=>s.artifact_id===id);
  const friendlyFile=name=>String(name||'Original source').replace(/\.(txt|eml|pdf|md)$/i,'').replace(/[-_]/g,' ').replace(/^./,c=>c.toUpperCase());
  function quoteMarkup(c){
    const f=state.claim?relationships().fact:null,phrase=f?.fact_id.startsWith('condition:')?f.label:null;
    const index=phrase?c.quote.toLowerCase().indexOf(phrase.toLowerCase()):-1;
    return index<0?esc(c.quote):`${esc(c.quote.slice(0,index))}<mark>${esc(c.quote.slice(index,index+phrase.length))}</mark>${esc(c.quote.slice(index+phrase.length))}`;
  }
  const sourceCard=(c,i=0)=>`<button class="source-card" data-source="${esc(c.artifact_id)}" data-cite="${citeRef(c)}" data-wire="source-${i}" aria-label="Open ${esc(descriptor(c.artifact_id)?.file_name||'original source')} at cited passage"><span class="file-label">${documentIcon}<span class="file-name">${esc(friendlyFile(descriptor(c.artifact_id)?.file_name))}</span><span class="arrow" aria-hidden="true">↗</span></span><q>${quoteMarkup(c)}</q></button>`;
  const relates=(item,id)=>item.node_id===id||item.decision_node_id===id||list(item.node_ids).includes(id)||list(item.required_at_node_ids).includes(id);
  function relationships(){
    const s=state.claim,n=s.graph.nodes.find(n=>n.node_id===state.selected)||s.graph.nodes[0];
    if(!n)return{node:null,facts:[],docs:[],evaluation:{},layout:core.layoutGraph(s.graph)};
    const incoming=s.graph.edges.filter(e=>e.target_node_id===n.node_id),obs=s.obligations.filter(o=>relates(o,n.node_id));
    const flags=[...new Set([...core.conditionFlags(n.condition),...incoming.flatMap(e=>core.conditionFlags(e.condition))])];
    const ids=new Set([...flags.map(f=>'condition:'+f),...obs.flatMap(o=>list(o.required_fact_ids))]);
    const facts=s.facts.filter(f=>ids.has(f.fact_id)||relates(f,n.node_id)).sort((a,b)=>Number(!a.fact_id.startsWith('condition:'))-Number(!b.fact_id.startsWith('condition:')));
    const docs=obs.map(o=>({...o,...s.evaluation.documents.find(d=>d.document_type===o.document_type)}));
    const fact=facts.find(f=>f.fact_id===state.fact)||facts[0],doc=docs.find(d=>d.document_type===state.doc)||docs[0];
    return{node:n,facts,docs,fact,doc,incoming,evaluation:s.evaluation.nodes.find(e=>e.node_id===n.node_id)||{},layout:core.layoutGraph(s.graph)};
  }
  function header(){
    const s=state.claim;
    return `<div class="claim-header"><div><p class="eyebrow"><a href="#work">Work</a> &nbsp; / &nbsp; Fictional claim</p><h1>${esc(shortTitle(s.title))}</h1><p class="subtitle">${esc(s.graph.title||s.graph.label||'Source-grounded investigation')}</p></div><div class="claim-status"><span class="status-label"><span class="status-dot"></span>${esc(label(s.status))}</span><button data-sheet="constraint">What is holding this claim? ↗</button></div></div>`;
  }
  function pathMarkup(){
    const r=relationships();if(!r.node)return'<p class="no-object">No process has been recorded for this claim.</p>';
    const {node,fact,doc,facts,docs,evaluation,layout}=r,citations=list(fact?.citations);
    const sources=citations.slice(0,2), stepIndex=layout.nodes.findIndex(n=>n.node_id===node.node_id)+1;
    const prerequisites=list(evaluation.blocked_by).map(id=>layout.byId.get(id)).filter(Boolean);
    return `<h2 class="sr-only">Evidence for ${esc(node.label)}</h2>
      <div class="lens-grid" id="evidence-lens"><svg class="links" aria-hidden="true"></svg>
        <div class="column"><span class="column-label">01 · Source passages</span><div class="source-stack">${sources.map(sourceCard).join('')||'<p class="no-object">No supporting passage is recorded for this fact.</p>'}</div>${citations.length>2?`<p class="source-count"><button data-sheet="fact">View all ${citations.length} passages ↗</button></p>`:''}</div>
        <div class="column"><span class="column-label">02 · ${fact?.fact_id.startsWith('condition:')?'Branch condition':'Required fact'}</span>${fact?`<button class="object fact-object" data-trace-fact aria-expanded="false" data-wire="fact"><span class="object-icon" aria-hidden="true">${['true','established'].includes(fact.status)?'✓':fact.status==='false'?'−':'?'}</span><strong class="object-title">${esc(words(fact.label))}</strong><span class="object-state">${esc(label(fact.status))}</span></button><div class="fact-inline" id="fact-inline" hidden><p>${list(fact.citations).length} supporting passage${list(fact.citations).length===1?'':'s'}</p><button data-sheet="fact">Open fact record ↗</button></div>`:'<p class="no-object">No fact is attached to this step.</p>'}${facts.length>1?`<div class="extra-options"><button data-sheet="facts">${facts.length-1} related fact${facts.length>2?'s':''} ↗</button></div>`:''}</div>
        <div class="column"><span class="column-label">03 · Process step</span><button class="object step-object" data-sheet="step" data-wire="step"><span class="object-icon" aria-hidden="true">${String(stepIndex).padStart(2,'0')}</span><strong class="object-title">${esc(nodeName(node))}</strong><span class="object-state">${esc(evaluation.execution_state==='blocked'?'Not reached':label(evaluation.execution_state))}</span></button></div>
        <div class="column"><span class="column-label">04 · Derived requirement</span>${doc?`<button class="object doc-object" data-route="${esc(doc.route_state)}" data-sheet="document" data-wire="doc"><span class="object-icon" aria-hidden="true">${doc.review_state==='satisfied'?'✓':'·'}</span><strong class="object-title">${esc(doc.label)}</strong><span class="object-state">${esc(label(doc.review_state))}</span><span class="doc-timing">${esc(doc.route_state==='needed_later'?'Needed when this step is reached':label(doc.route_state))}</span></button>${docs.length>1?`<div class="extra-options" aria-label="Requirements for this step">${docs.map(d=>`<button data-doc="${esc(d.document_type)}" aria-pressed="${d===doc}">${esc(d.label)}</button>`).join('')}</div>`:''}`:'<p class="no-object">No document requirement is attached to this step.</p>'}</div>
      </div>
      <div class="branch-note"><span class="note-rule"></span>${prerequisites.length?`<span>This step waits for</span>${prerequisites.map(n=>`<button data-node="${esc(n.node_id)}">${esc(nodeName(n))} ↗</button>`).join(' <span>and</span> ')}`:evaluation.activation==='false'?'<span>This route does not apply to the recorded facts.</span>':evaluation.activation==='unresolved'?'<span>Branch relevance remains unresolved.</span>':'<span>No unfinished prerequisite is recorded for this step.</span>'}<span class="note-rule"></span></div>`;
  }
  function graphMarkup(compactView=false){
    const s=state.claim,layout=core.layoutGraph(s.graph);let number=0;
    return `<div class="graph-help"><span>Every saved branch · ${layout.nodes.length} steps / ${layout.edges.length} connections</span><span>Scroll horizontally to explore →</span></div><div class="graph-scroll${compactView?' compact-scroll':''}" tabindex="0" aria-label="Complete process graph; scroll horizontally"><div class="graph-board${compactView?' compact-board':''}" id="graph-board"><svg class="links" aria-hidden="true"></svg>${layout.rows.map(row=>`<div class="graph-rank">${row.map(n=>{const ev=s.evaluation.nodes.find(e=>e.node_id===n.node_id)||{};const ordinal=++number;return `<button class="graph-node" data-node="${esc(n.node_id)}" data-graph-node="${esc(n.node_id)}" data-state="${esc(ev.execution_state)}" aria-pressed="${n.node_id===state.selected}" aria-label="${esc(n.label)}; ${esc(label(ev.execution_state))}"><span class="graph-number" data-junction="${esc(n.node_id)}">${ev.execution_state==='completed'?'✓':String(ordinal).padStart(2,'0')}</span><strong>${esc(nodeName(n))}</strong><small>${esc(label(ev.execution_state))}</small></button>`;}).join('')}</div>`).join('')}</div></div><p class="graph-count">Select a step to open its source → fact → requirement path. Dashed routes do not apply.</p>`;
  }
  function documentsMarkup(){return `<div class="lens-heading"><strong>Requirements follow the process</strong><span class="hint">A held file is not automatically sufficient evidence</span></div><div class="documents-list">${state.claim.evaluation.documents.map(d=>`<article class="document-row"><span class="doc-symbol" aria-hidden="true">${d.review_state==='satisfied'?'✓':'·'}</span><div><h3>${esc(d.label)}</h3><span class="document-state">${esc(label(d.review_state))} · ${esc(label(d.route_state))}</span><p>From ${list(d.required_at_node_ids).map(id=>`<button data-node="${esc(id)}" data-select-doc="${esc(d.document_type)}">${esc(nodeName(state.claim.graph.nodes.find(n=>n.node_id===id)))}</button>`).join(', ')||'the saved process'}</p></div><button data-document="${esc(d.document_type)}" aria-label="Inspect ${esc(d.label)}">↗</button></article>`).join('')}</div>`;}
  function branches(){
    return state.claim.graph.nodes.filter(n=>state.claim.graph.edges.some(e=>e.target_node_id===n.node_id&&core.conditionFlags(e.condition).length)).map(n=>{
      const ev=state.claim.evaluation.nodes.find(e=>e.node_id===n.node_id);return `<button class="path-chip" data-node="${esc(n.node_id)}" data-status="${esc(ev?.activation)}" aria-pressed="${state.selected===n.node_id}"><span class="chip-dot"></span>${esc(nodeName(n))}</button>`;
    }).join('');
  }
  function renderClaim(){
    const c=state.claim,used=list(c.knowledge_uses).length;
    $('#main').innerHTML=`${header()}<section class="canvas-frame" aria-label="Investigation canvas"><div class="canvas-toolbar"><nav class="view-tabs" aria-label="Investigation views">${[['path','Evidence path'],['process','Whole process'],['documents','Documents']].map(([id,name])=>`<button data-mode="${id}" aria-pressed="${state.mode===id}">${name}</button>`).join('')}</nav><div class="toolbar-actions"><button data-sheet="sources"><b>${c.source_descriptors.length}</b> originals ↗</button><button class="activity-link" data-sheet="activity">Activity ↗</button></div></div><div class="stage" id="stage"><svg id="focus-tether" aria-hidden="true"><path/></svg>${state.mode==='path'?`<div class="process-strip">${graphMarkup(true)}</div><div id="lens-panel">${pathMarkup()}</div>`:state.mode==='process'?graphMarkup():documentsMarkup()}</div><div class="case-footer"><span class="understanding"><span>Fictional sources · original context available</span></span><button data-sheet="reuse">${used?`${used} knowledge version reused`:'Knowledge record'} ↗</button></div></section><div class="more-paths"><span class="eyebrow">Follow another branch</span>${branches()}</div>`;
    requestAnimationFrame(()=>{draw();centerSelection();});navActive('work');
  }
  function centerSelection(){
    const scroll=$('.compact-scroll'),selected=$('.compact-board [aria-pressed="true"]');
    if(!scroll||!selected||scroll.scrollWidth<=scroll.clientWidth)return;
    const a=scroll.getBoundingClientRect(),b=selected.getBoundingClientRect();
    if(b.left<a.left+8||b.right>a.right-8)scroll.scrollLeft+=b.left-a.left-(scroll.clientWidth-b.width)/2;
  }
  function navActive(name){all('[data-nav]').forEach(a=>a.toggleAttribute('aria-current',a.dataset.nav===name));}
  function renderWork(query=''){
    navActive('work');
    const filtered=state.claims.filter(c=>[c.title,c.status,c.phase_summary,c.outcome?.summary].filter(Boolean).join(' ').toLowerCase().includes(query.toLowerCase()));
    const rows=filtered.map(c=>`<a class="claim-row" href="#claim/${encodeURIComponent(c.claim_id)}"><div><div class="claim-name">${esc(shortTitle(c.title))}</div><p class="claim-context">Fictional claim · ${esc(c.phase?words(c.phase):'Saved work')}</p></div><p class="claim-summary">${esc(c.outcome?.issues?.[0]||c.outcome?.reason||c.outcome?.summary||c.phase_summary||'Open the saved investigation.')}</p><span class="row-state">${esc(label(c.status))}</span><span class="row-arrow" aria-hidden="true">↗</span></a>`).join('')||'<p class="loading">No matching claims.</p>';
    if($('#claim-rows')){$('#claim-rows').innerHTML=rows;return;}
    $('#main').innerHTML=`<section class="collection"><header class="collection-header"><div><p class="eyebrow">The workspace</p><h1>Work in context.</h1><p>Open a claim. Follow the evidence. See what comes next.</p></div><span class="number" aria-label="${state.claims.length} saved claims">${String(state.claims.length).padStart(2,'0')}</span></header><div class="search-row"><label for="search">Saved claims</label><input id="search" type="search" placeholder="Find a claim…" autocomplete="off" aria-label="Find a claim"><span>↗</span></div><div id="claim-rows">${rows}</div></section>`;
  }
  function claimLink(id){return `<a class="knowledge-claim" href="#claim/${encodeURIComponent(id)}"><span>${esc(shortTitle(state.claims.find(c=>c.claim_id===id)?.title)||id)}</span><span>↗</span></a>`;}
  function renderKnowledge(){
    navActive('knowledge');
    const versions=state.knowledge.versions,v=versions.find(v=>v.version===state.version)||versions.at(-1),uses=state.knowledge.uses.filter(u=>u.knowledge_id===v.knowledge_id&&(u.knowledge_sha256?u.knowledge_sha256===v.knowledge_sha256:String(u.version)===String(v.version)));
    state.version=v.version;
    const receiving=[...new Set(uses.map(u=>u.claim_id).filter(Boolean))];
    $('#main').innerHTML=`<section class="collection"><header class="knowledge-header"><p class="eyebrow">A memory with a source</p><h1>Each case leaves<br>something useful.</h1><p>Qualified process definitions carry their origin and checks into the next investigation. Case values and source files stay with their claim.</p></header><div class="knowledge-path" id="knowledge-path"><svg class="links" aria-hidden="true"></svg><div class="column" data-wire="origin"><span class="column-label">01 · Learned from</span>${claimLink(v.source_claim_id)}<p class="subtitle" style="margin-top:14px">${esc(v.added_document_types?.length?'Added '+v.added_document_types.map(words).join(' and ')+'.':v.change_reason||'Recorded source claim')}</p></div><div class="column" data-wire="version"><span class="column-label">02 · Qualified process</span><button class="version-object" data-sheet="version"><span class="version-number">VERSION ${v.version} · ${esc(label(v.qualification.status))}</span><h2>${esc(v.title)}</h2><p>${v.qualification.evidence_recipe_count} evidence recipes · ${v.graph.nodes.length} process steps</p><span class="version-foot"><span>${v.qualification.regression_cases} branch assignments checked</span><span>↗</span></span></button></div><div class="column" data-wire="reuse"><span class="column-label">03 · Reused in ${receiving.length} claims</span>${receiving.map(claimLink).join('')||'<p class="subtitle">No reuse is recorded for this version.</p>'}</div></div><div class="version-switch"><span>Follow the versions</span>${versions.map(version=>`<button data-version="${version.version}" aria-pressed="${v===version}">Version ${version.version}</button>`).join('')}<button data-sheet="quarantine">${state.knowledge.quarantined.length} quarantined candidates ↗</button></div><div class="knowledge-detail"><h3>What can be reused</h3><div class="recipe-list">${v.evidence_recipes.map((r,i)=>`<button class="recipe" data-recipe="${i}">${esc(words(r.document_type))}<span>${list(r.required_fields).length} required evidence fields ↗</span></button>`).join('')}</div></div></section>`;
    requestAnimationFrame(draw);
  }
  function renderIntake(){navActive('work');$('#main').innerHTML=`<section class="intake"><p class="eyebrow">New investigation</p><h1>Start with the source.</h1><p>A message and the original files are the starting point. The process and its document requirements follow from the evidence.</p><form id="intake-form"><label for="claim-title">Claim title</label><input id="claim-title" name="title" placeholder="A short name for this claim" required maxlength="300"><label for="claim-message">What happened?</label><textarea id="claim-message" name="message" placeholder="Paste the original message or describe the claim…" required></textarea><div class="file-zone"><label for="packet-files">Original source files</label><input id="packet-files" name="files" type="file" multiple><div id="packet-list" class="packet-list"></div></div><p class="intake-note">This design preview keeps the packet in this tab. It does not save a claim or run an agent.</p><button type="submit" class="primary" style="margin-top:20px">Review source packet ↗</button></form></section>`;}
  function wire(container,pairs){
    const svg=container?.querySelector('.links');if(!svg)return;
    const parent=container.getBoundingClientRect();svg.setAttribute('viewBox',`0 0 ${container.scrollWidth} ${container.scrollHeight}`);svg.setAttribute('width',container.scrollWidth);svg.setAttribute('height',container.scrollHeight);
    container.querySelectorAll('.connector-label').forEach(el=>el.remove());
    svg.innerHTML=pairs.map(([from,to,text,muted=false])=>{
      const a=container.querySelector(`[data-wire="${CSS.escape(from)}"]`),b=container.querySelector(`[data-wire="${CSS.escape(to)}"]`);if(!a||!b)return'';
      const ar=a.getBoundingClientRect(),br=b.getBoundingClientRect(),x=ar.right-parent.left,y=ar.top-parent.top+ar.height/2,tx=br.left-parent.left,ty=br.top-parent.top+br.height/2;
      const gap=Math.max(15,(tx-x)/2);
      if(text){const l=document.createElement('span');l.className='connector-label';l.style.left=`${(x+tx)/2}px`;l.style.top=`${(y+ty)/2-16}px`;l.textContent=text;container.append(l);}
      return `<path class="${muted?'muted-edge':'emphasis'}" d="M${x} ${y} C${x+gap} ${y},${tx-gap} ${ty},${tx} ${ty}"/><circle cx="${tx}" cy="${ty}" r="2.5"/>`;
    }).join('');
  }
  function draw(){
    const lens=$('#evidence-lens');if(lens){const r=relationships(),src=list(r.fact?.citations).slice(0,2);wire(lens,[...src.map((_,i)=>[`source-${i}`,'fact',i===0?'supports':'']),['fact','step',r.fact?.fact_id.startsWith('condition:')?'relevance':'informs'],['step','doc','requires',r.evaluation.activation==='false']]);}
    const graph=$('#graph-board');if(graph){
      const p=graph.getBoundingClientRect(),svg=graph.querySelector('svg');svg.setAttribute('viewBox',`0 0 ${graph.scrollWidth} ${graph.scrollHeight}`);
      svg.innerHTML=state.claim.graph.edges.map(e=>{
        const a=graph.querySelector(`${graph.classList.contains('compact-board')?'[data-junction':'[data-graph-node'}="${CSS.escape(e.source_node_id)}"]`).getBoundingClientRect(),b=graph.querySelector(`${graph.classList.contains('compact-board')?'[data-junction':'[data-graph-node'}="${CSS.escape(e.target_node_id)}"]`).getBoundingClientRect();
        const x=a.right-p.left,y=a.top-p.top+a.height/2,tx=b.left-p.left,ty=b.top-p.top+b.height/2;
        const ev=state.claim.evaluation.edges.find(row=>row.edge_id===e.edge_id),rank=core.layoutGraph(state.claim.graph).rows;const fromRank=rank.findIndex(row=>row.some(n=>n.node_id===e.source_node_id)),toRank=rank.findIndex(row=>row.some(n=>n.node_id===e.target_node_id));const skip=toRank-fromRank>1,low=graph.classList.contains('compact-board')?169:290;
        const d=skip?`M${x} ${y} C${x+20} ${y},${x+20} ${low},${x+38} ${low} L${tx-25} ${low} Q${tx-12} ${low} ${tx-12} ${ty+18} Q${tx-12} ${ty} ${tx} ${ty}`:`M${x} ${y} C${x+22} ${y},${tx-22} ${ty},${tx} ${ty}`;
        return `<path data-edge="${esc(e.edge_id)}" class="${ev?.activation==='false'?'muted-edge':''}" d="${d}"><title>${esc(e.label)}</title></path>`;
      }).join('');
    }
    const tether=$('#focus-tether'),selected=$('.compact-board [aria-pressed="true"] .graph-number'),junction=$('[data-sheet="step"] .object-icon');
    if(tether&&selected&&junction&&innerWidth>850){
      const frame=$('#stage').getBoundingClientRect(),a=selected.getBoundingClientRect(),b=junction.getBoundingClientRect(),mid=$('.process-strip').getBoundingClientRect().bottom-frame.top+14;
      tether.setAttribute('viewBox',`0 0 ${frame.width} ${frame.height}`);
      const x=a.left-frame.left+a.width/2,y=a.bottom-frame.top,tx=b.left-frame.left+b.width/2,ty=b.top-frame.top;
      const path=tether.querySelector('path'),d=`M${x} ${y} C${x} ${mid},${tx} ${mid},${tx} ${ty}`,old=path.getAttribute('d');
      path.setAttribute('d',d);
      if(old&&path.dataset.selected!==state.selected&&!matchMedia('(prefers-reduced-motion: reduce)').matches){
        path.getAnimations().forEach(a=>a.cancel());path.animate([{d:`path("${old}")`},{d:`path("${d}")`}],{duration:320,easing:'cubic-bezier(.22,.75,.18,1)'});
      }
      path.dataset.selected=state.selected;
    }
    wire($('#knowledge-path'),[['origin','version','qualifies'],['version','reuse','reuses']]);
  }
  function openSheet(title,eyebrow,body){
    const sheet=$('#sheet'),wasOpen=sheet.open;if(!wasOpen)returnFocus=document.activeElement;
    $('#sheet-content').innerHTML=`<header class="sheet-header"><div><p class="eyebrow">${esc(eyebrow)}</p><h2 id="sheet-title">${esc(title)}</h2></div><button class="close-sheet" data-close aria-label="Close detail">×</button></header><div class="sheet-body">${body}</div>`;
    if(!wasOpen){sheet.showModal();if(!matchMedia('(prefers-reduced-motion: reduce)').matches)sheet.animate([{transform:'translateX(50px)',opacity:.4},{transform:'translateX(0)',opacity:1}],{duration:330,easing:'cubic-bezier(.22,.75,.18,1)'});}
    sheet.scrollTop=0;
  }
  function factDetail(){const r=relationships(),f=r.fact;if(!f)return;openSheet(words(f.label),'Recorded fact',`<span class="status-label">${esc(label(f.status))}</span><p>${esc(f.summary)}</p><h3>Supporting passages</h3>${list(f.citations).map(sourceCard).join('')||'<p class="muted">No source passage supports this fact yet.</p>'}<h3>Connected step</h3><button class="linked-button" data-node="${esc(r.node.node_id)}">${esc(r.node.label)}<span>↗</span></button><div class="sheet-meta">Fact identity · ${esc(f.fact_id)}</div>`);}
  function documentDetail(type){const s=state.claim,d=s.evaluation.documents.find(d=>d.document_type===type),obs=s.obligations.filter(o=>o.document_type===type);if(!d)return;const facts=s.facts.filter(f=>obs.some(o=>list(o.required_fact_ids).includes(f.fact_id)));openSheet(d.label,'Derived document requirement',`<span class="status-label">${esc(label(d.review_state))} · ${esc(label(d.route_state))}</span><p>${esc(d.reason)}</p><h3>What the evidence must establish</h3>${facts.map(f=>`<p>${esc(f.label)}.</p><p class="muted">${esc(f.summary)}</p>`).join('')||'<p>No additional fact definition is recorded.</p>'}<h3>Required by</h3>${list(d.required_at_node_ids).map(id=>`<button class="linked-button" data-node="${esc(id)}">${esc(state.claim.graph.nodes.find(n=>n.node_id===id)?.label)}<span>↗</span></button>`).join('')}<details><summary>Requirement source</summary><p style="margin-top:16px">${esc(d.authority?.title)}</p><p>${esc(d.authority?.quote)}</p></details>`);}
  function sheetFor(kind){
    const s=state.claim,r=s?relationships():null;
    if(kind==='fact')return factDetail();
    if(kind==='facts')return openSheet('Facts connected to this step','Recorded evidence',r.facts.map(f=>`<button class="linked-button" data-fact="${esc(f.fact_id)}">${esc(words(f.label))}<span>${esc(label(f.status))} ↗</span></button>`).join(''));
    if(kind==='document')return r.doc&&documentDetail(r.doc.document_type);
    if(kind==='sources')return openSheet('Original sources','Saved source packet',s.source_descriptors.map(d=>`<button class="source-card" data-source="${esc(d.artifact_id)}"><span class="file-label">${documentIcon}<span class="file-name">${esc(d.file_name)}</span><span>↗</span></span><span class="subtitle">${d.size_bytes.toLocaleString()} bytes · Original source</span></button>`).join(''));
    if(kind==='constraint')return openSheet('What holds this claim','Recorded outcome',`<span class="status-label">${esc(label(s.status))}</span><p>${esc(s.deferral?.reason||s.outcome?.summary||'No outcome has been recorded.')}</p>${list(s.outcome?.issues).map(i=>`<p>${esc(i)}</p>`).join('')}<h3>Authority limits</h3>${list(s.outcome?.authority_limits).map(i=>`<p>${esc(i)}</p>`).join('')||'<p>No additional limit is recorded.</p>'}<p class="muted">${esc(s.outcome?.next_action||'')}</p>`);
    if(kind==='step')return openSheet(r.node.label,'Saved process step',`<span class="status-label">${esc(label(r.evaluation.execution_state))}</span><p>Branch relevance: ${esc(label(r.evaluation.activation))}.</p>${list(r.evaluation.blocked_by).length?`<h3>Waiting for</h3>${r.evaluation.blocked_by.map(id=>`<button class="linked-button" data-node="${esc(id)}">${esc(nodeName(r.layout.byId.get(id)))}<span>↗</span></button>`).join('')}`:''}<h3>Process authority</h3><p>${esc(r.node.authority?.title||'No authority title recorded.')}</p><p>${esc(r.node.authority?.quote||'')}</p><details><summary>Capability and execution record</summary><pre>${esc(JSON.stringify({evaluation:r.evaluation,capability:state.projection.node_capabilities?.[r.node.node_id]},null,2))}</pre></details>`);
    if(kind==='activity')return openSheet('Recorded work','Saved event journal',`<p class="muted">These are completed journal entries, not a live animation.</p><ol>${state.events.map(e=>`<li style="margin-bottom:12px;font-size:12px"><strong>${esc(words(e.kind))}</strong>${e.payload?.phase?` · ${esc(words(e.payload.phase))}`:''}</li>`).join('')}</ol><div class="sheet-meta">Revision ${s.revision} · ${esc(s.state_sha256)}</div>`);
    if(kind==='reuse')return openSheet('Knowledge used here','Exact recorded reuse',list(s.knowledge_uses).map(u=>`<h3>Version ${esc(u.version)}</h3><p>${esc(u.reason||'Qualified process definition reused.')}</p><a class="linked-button" href="#knowledge">Inspect knowledge <span>↗</span></a><details><summary>Public reuse record</summary><pre>${esc(JSON.stringify(u,null,2))}</pre></details>`).join('')||'<p>No knowledge use is recorded for this claim.</p>');
    const v=state.knowledge.versions.find(v=>v.version===state.version);
    if(kind==='version')return openSheet(`Version ${v.version}`,v.title,`<span class="status-label done">${esc(label(v.qualification.status))}</span><p>${esc(v.change_reason||'Qualified reusable process definition.')}</p><h3>Qualification checks</h3><ul>${v.qualification.checks.map(c=>`<li>${esc(words(c))}</li>`).join('')}</ul><p>${v.qualification.regression_cases} branch assignments checked.</p><h3>Source claim</h3>${claimLink(v.source_claim_id)}<details><summary>Version identity</summary><pre>${esc(JSON.stringify({knowledge_id:v.knowledge_id,version:v.version,knowledge_sha256:v.knowledge_sha256,parent_knowledge_sha256:v.parent_knowledge_sha256,source_state_sha256:v.source_state_sha256},null,2))}</pre></details>`);
    if(kind==='quarantine')return openSheet('Quarantined candidates','Excluded from qualified knowledge',state.knowledge.quarantined.map(q=>`<h3>${esc(q.title||q.knowledge_id||'Candidate')}</h3><p>${esc(q.qualification?.reason||q.reason||'Qualification was not admitted.')}</p><details><summary>Candidate record</summary><pre>${esc(JSON.stringify(q,null,2))}</pre></details>`).join(''));
  }
  async function openSource(id,citation){
    const captured=state.claim,desc=descriptor(id);openSheet(desc?.file_name||'Original source','Original context','<p>Checking the original text and cited passage…</p>');
    const token=epoch,request=++sourceRequest;
    try{const response=await get(`/sources/${encodeURIComponent(captured.claim_id)}/${encodeURIComponent(id)}/text`),checked=await core.checkedSource(captured,desc,response,citation);if(epoch!==token||request!==sourceRequest||!$('#sheet').open)return;
      openSheet(desc.file_name,'Original context',`<div class="verified">${proofIcon}<span>Source text verified${checked.span?' · exact cited span verified':''}</span></div><div class="source-text">${checked.span?`${esc(checked.span.before)}<mark id="cited-span">${esc(checked.span.quote)}</mark>${esc(checked.span.after)}`:esc(checked.source.text)}</div><details class="sheet-meta"><summary>Source identity</summary><p>${esc(id)}</p><p>SHA-256 ${esc(checked.source.sha256)}</p></details>`);
    }catch(e){if(epoch===token&&request===sourceRequest&&$('#sheet').open)openSheet(desc?.file_name||'Source','Verification failed',`<p class="error">${esc(e.message)}</p>`);}
  }
  function selectNode(id,doc=null){
    state.selected=id;state.fact=null;state.doc=doc;
    if($('#sheet').open)$('#sheet').close();
    const panel=$('#lens-panel'),old=$('[data-sheet="step"]')?.getBoundingClientRect();
    if(state.mode==='path'&&panel){
      panel.innerHTML=pathMarkup();
      all('[data-graph-node]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.graphNode===id)));
      const paths=$('.more-paths');if(paths)paths.innerHTML=`<span class="eyebrow">Follow another branch</span>${branches()}`;
      requestAnimationFrame(draw);
    }else{state.mode='path';renderClaim();}
    const target=$(`[data-graph-node="${CSS.escape(id)}"]`);
    target?.focus({preventScroll:true});centerSelection();
    if(!matchMedia('(prefers-reduced-motion: reduce)').matches){
      const ring=target?.querySelector('.graph-number');ring?.animate([{boxShadow:'0 0 0 8px #274eb51a'},{boxShadow:'0 0 0 0 #274eb500'}],{duration:360,easing:'ease-out'});
      const next=$('[data-sheet="step"]');
      if(next&&old){const bounds=next.getBoundingClientRect();next.animate([{transform:`translate(${old.left-bounds.left}px,${old.top-bounds.top}px)`},{transform:'translate(0,0)'}],{duration:360,easing:'cubic-bezier(.22,.75,.18,1)'});}
      for(const el of all('#lens-panel .source-card, #lens-panel .fact-object, #lens-panel .doc-object'))el.animate([{opacity:.4,transform:'translateY(7px)'},{opacity:1,transform:'translateY(0)'}],{duration:320,easing:'cubic-bezier(.22,.75,.18,1)'});
    }
  }
  async function route(){
    const token=++epoch;refs=[];if($('#sheet').open)$('#sheet').close();const [view,id,node]=location.hash.slice(1).split('/');state.route=view||'claim';
    try{
      if(view==='work'){renderWork();return;}
      if(view==='knowledge'){renderKnowledge();return;}
      if(view==='intake'){renderIntake();return;}
      const cid=id||'auto_764f712d3833988ce6ff6cfd';let entry=state.cache.get(cid);
      if(!entry){const [response,events]=await Promise.all([get(`/claims/${encodeURIComponent(cid)}`),get(`/claims/${encodeURIComponent(cid)}/events?after=0`)]);entry={...core.readState(response,cid),events};core.acceptEvents(null,events,entry.state);state.cache.set(cid,entry);}
      if(token!==epoch)return;state.claim=entry.state;state.projection=entry.projection;state.events=entry.events.events;state.selected=node||(cid==='auto_764f712d3833988ce6ff6cfd'?'lt_family':entry.state.evaluation.focus_node_id)||entry.state.graph.nodes[0]?.node_id;state.fact=null;state.doc=null;state.mode='path';renderClaim();
    }catch(e){if(token===epoch)$('#main').innerHTML=`<p class="error">${esc(e.message)}</p>`;}
  }
  document.addEventListener('click',e=>{
    const b=e.target.closest('button,a');if(!b)return;
    if(b.hasAttribute('data-trace-fact')){
      const panel=$('#fact-inline'),columns=all('#evidence-lens .column'),before=columns.map(el=>el.getBoundingClientRect());
      panel.hidden=!panel.hidden;b.setAttribute('aria-expanded',String(!panel.hidden));$('#evidence-lens').classList.toggle('trace-fact',!panel.hidden);
      if(!matchMedia('(prefers-reduced-motion: reduce)').matches){
        columns.forEach((el,i)=>{const after=el.getBoundingClientRect(),dy=before[i].top-after.top;el.animate([{transform:`translateY(${dy}px)`},{transform:'translateY(0)'}],{duration:350,easing:'cubic-bezier(.22,.75,.18,1)'});});
        const until=performance.now()+360;const follow=()=>{draw();if(performance.now()<until&&panel.isConnected)requestAnimationFrame(follow);};requestAnimationFrame(follow);
      }else draw();return;
    }
    if(b.hasAttribute('data-close')){$('#sheet').close();return;}
    if(b.dataset.source){openSource(b.dataset.source,b.hasAttribute('data-cite')?refs[Number(b.dataset.cite)]:null);return;}
    if(b.dataset.node){selectNode(b.dataset.node,b.dataset.selectDoc);return;}
    if(b.dataset.mode){state.mode=b.dataset.mode;renderClaim();$(`[data-mode="${CSS.escape(state.mode)}"]`)?.focus({preventScroll:true});return;}
    if(b.dataset.fact){state.fact=b.dataset.fact;if($('#sheet').open)$('#sheet').close();renderClaim();$(`[data-fact="${CSS.escape(state.fact)}"]`)?.focus({preventScroll:true});return;}
    if(b.dataset.doc){state.doc=b.dataset.doc;renderClaim();$(`[data-doc="${CSS.escape(state.doc)}"]`)?.focus({preventScroll:true});return;}
    if(b.dataset.document){documentDetail(b.dataset.document);return;}
    if(b.dataset.sheet){sheetFor(b.dataset.sheet);return;}
    if(b.dataset.version){state.version=Number(b.dataset.version);renderKnowledge();$(`[data-version="${state.version}"]`)?.focus({preventScroll:true});return;}
    if(b.hasAttribute('data-recipe')){const v=state.knowledge.versions.find(v=>v.version===state.version),r=v.evidence_recipes[Number(b.dataset.recipe)];openSheet(words(r.document_type),'Qualified evidence recipe',`<p>${esc(r.summary)}</p><h3>Required evidence fields</h3><ul>${r.required_fields.map(f=>`<li>${esc(words(typeof f==='string'?f:f.name||f.field))}</li>`).join('')}</ul><details><summary>Recipe record</summary><pre>${esc(JSON.stringify(r,null,2))}</pre></details>`);}
  });
  document.addEventListener('input',e=>{if(e.target.id==='search')renderWork(e.target.value);});
  document.addEventListener('change',e=>{if(e.target.id==='packet-files')$('#packet-list').innerHTML=[...e.target.files].map(f=>`<div>${esc(f.name)} · ${f.size.toLocaleString()} bytes</div>`).join('');});
  document.addEventListener('submit',e=>{if(e.target.id!=='intake-form')return;e.preventDefault();const form=e.target,files=[...form.elements.files.files];openSheet(form.elements.title.value,'Local source packet preview',`<p>${esc(form.elements.message.value)}</p><h3>${files.length} original files selected</h3><ul>${files.map(f=>`<li>${esc(f.name)} · ${f.size.toLocaleString()} bytes</li>`).join('')}</ul><p class="muted">This is a local preview. No claim was saved and no interpretation was run.</p>`);});
  $('#sheet').addEventListener('close',()=>{sourceRequest++;if(returnFocus?.isConnected)returnFocus.focus({preventScroll:true});});
  window.addEventListener('hashchange',()=>{window.scrollTo(0,0);route();});
  window.addEventListener('resize',()=>requestAnimationFrame(()=>{draw();centerSelection();}));
  Promise.all([get('/claims'),get('/knowledge')]).then(([claims,knowledge])=>{state.claims=claims.claims;state.knowledge=knowledge;return route();}).catch(e=>{$('#main').innerHTML=`<p class="error">${esc(e.message)}</p>`;});
  window.CasePathPreview={inspect:()=>({claim_id:state.claim?.claim_id,revision:state.claim?.revision,selected:state.selected,mode:state.mode,route:state.route})};
})();
