/* Autonomous work is rendered from persisted state and its matching event cursor. */
(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CasePathAutonomous = api;
})(typeof globalThis === 'object' ? globalThis : this, function (root) {
  'use strict';
  const BASE = '/api/claim-loops/v1/autonomous';
  const DOMAINS = Object.freeze([
    {id:'defect_mold_heating',label:'Defects & repairs'},
    {id:'lease_termination_dispute',label:'Lease termination'},
    {id:'rent_increase_dispute',label:'Rent changes'}
  ]);
  // Mac's source-inspected selection, commit 80939f0. Presentation metadata only.
  // These IDs never create packets or contribute facts to an investigation.
  const DEMO_CASES = Object.freeze([
    {claim_id:'clm_e262801f9368bc12',domain:'defect_mold_heating',label:'Recurring leak and a received image'},
    {claim_id:'clm_521c20913f4e0f9b',domain:'defect_mold_heating',label:'Cold home and an unconfirmed repair plan'},
    {claim_id:'clm_ee29ac770b1bf7b9',domain:'defect_mold_heating',label:'Dampness with disputed contractor access'},
    {claim_id:'clm_f69b1747447bc221',domain:'lease_termination_dispute',label:'Different tenant and spouse notice dates'},
    {claim_id:'clm_0c5e7c7723a3c694',domain:'lease_termination_dispute',label:'Competing notices and an alleged correction'},
    {claim_id:'clm_2a9c260c26afaa34',domain:'lease_termination_dispute',label:'Mixed debt demand and unknown payment allocation'},
    {claim_id:'clm_c44ddc0914ba9298',domain:'rent_increase_dispute',label:'Net rent and ancillary-charge reclassification'},
    {claim_id:'clm_7dbd7c7d1c4ddf90',domain:'rent_increase_dispute',label:'A supplied form with an unfilled reason field'},
    {claim_id:'clm_9a179a4481767d43',domain:'rent_increase_dispute',label:'Reference-rate date conflict without supplied forms'}
  ].map(Object.freeze));
  const mounts = new WeakMap();
  let activeMount = null;
  const h = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const list = value => Array.isArray(value) ? value : [];
  const words = value => String(value ?? '').replace(/[_.-]+/g, ' ').replace(/^./, c => c.toUpperCase());
  const text = value => typeof value === 'string' ? value : '';
  const name = item => item?.label || item?.title || item?.name || words(item?.node_id || item?.document_type || item?.fact_id || item?.type || item?.action_id || item?.kind);
  const dateLabel = value => { const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value || '') : new Intl.DateTimeFormat('en', {dateStyle:'medium',timeStyle:'short'}).format(date); };
  const key = value => encodeURIComponent(String(value));
  const button = (label, attr, primary = false) => `<button type="button" class="${primary ? 'au-primary' : 'au-secondary'}" ${attr}>${h(label)}</button>`;
  const complete = status => ['completed','complete','resolved'].includes(status);
  const statusFilter = status => complete(status) ? 'investigation_complete' : status;
  const active = status => ['received', 'queued', 'running', 'working', 'investigating'].includes(status);
  const tone = status => ['completed', 'complete', 'resolved', 'established', 'satisfied', 'qualified'].includes(status) ? 'done' : ['deferred', 'blocked', 'failed', 'unresolved', 'unknown', 'quarantined'].includes(status) ? 'blocked' : active(status) || status === 'ready' ? 'active' : 'neutral';
  const statusLabel = status => ({not_started:'Not started',not_run:'Not run',received:'Received', queued:'Queued', running:'Working', working:'Working', completed:'Completed', complete:'Completed', resolved:'Completed', investigation_complete:'Investigation complete', deferred:'Deferred', failed:'Stopped', ready:'Ready', true:'Applies', false:'Does not apply', insufficient:'Insufficient evidence', prepared_not_sent:'Prepared · not sent', not_reached:'Not reached', inactive:'Does not apply', unresolved:'Evidence needed', blocked:'Waiting for prerequisites', established:'Established', satisfied:'Satisfied', needed_now:'Needed now', needed_later:'Needed later', held_behind_question:'Depends on unresolved evidence', held_not_reviewed:'Acquired · not established', not_needed:'Not required', optional:'Optional'})[status] || words(status) || 'Not recorded';
  const claimStatusLabel = status => complete(status) ? 'Investigation complete' : statusLabel(status);
  const isHash = value => /^[a-f0-9]{64}$/i.test(value || '');
  const originalText = state => state.message || state.original_binding?.intake?.customer_message?.body || (typeof state.source_preview === 'string' ? state.source_preview : state.source_preview?.text) || '';
  const domainOf = claim => claim.browse_metadata?.domain || '';

  function readState(response, claimId) {
    const state = response?.state && typeof response.state === 'object' ? response.state : response;
    if (!state || typeof state.claim_id !== 'string' || !Number.isSafeInteger(state.revision) || state.revision < 0 || !isHash(state.state_sha256)) throw new Error('The saved claim identity is incomplete.');
    if (state.revision === 0 && (state.mode !== 'unprocessed' || state.status !== 'not_started' || state.phase !== 'not_run' || state.graph !== null || state.evaluation !== null || state.outcome || state.deferral || ['facts','obligations','actions','acquired_sources'].some(field => list(state[field]).length))) throw new Error('The unprocessed claim identity contains unaccepted work.');
    if (claimId && state.claim_id !== claimId) throw new Error('The response belongs to another claim.');
    if (state.graph?.claim_id && state.graph.claim_id !== state.claim_id) throw new Error('The process belongs to another claim.');
    const projection = response.projection || {};
    // Older envelopes omitted projection identity; present bindings must match.
    for (const field of ['claim_id','revision','state_sha256']) if (Object.prototype.hasOwnProperty.call(projection, field) && projection[field] !== state[field]) throw new Error('The capability projection belongs to a different saved claim revision.');
    if (Object.prototype.hasOwnProperty.call(projection, 'parent_revision') && projection.parent_revision !== state.revision) throw new Error('The capability projection belongs to a different saved claim revision.');
    if (Object.prototype.hasOwnProperty.call(projection, 'parent_state_sha256') && projection.parent_state_sha256 !== state.state_sha256) throw new Error('The capability projection belongs to a different saved claim revision.');
    return {state, projection};
  }
  function readSnapshot(response, claimId, previous, reconnect = false) {
    const incoming = readState(response,claimId), state = incoming.state;
    if (response.current_revision !== state.revision || response.current_state_sha256 !== state.state_sha256) {
      const error = new Error('The atomic snapshot does not match its saved revision.'); error.transientAdvance = true; throw error;
    }
    if (incoming.projection.revision !== state.revision || incoming.projection.state_sha256 !== state.state_sha256) throw new Error('The snapshot capability projection has no matching identity.');
    const zero = state.revision === 0;
    if (zero ? response.cursor_sha256 !== null : !isHash(response.cursor_sha256)) throw new Error('The snapshot journal cursor identity is incomplete.');
    if (state.last_event_sha256 !== undefined && response.cursor_sha256 !== state.last_event_sha256) throw new Error('The snapshot cursor differs from the saved journal identity.');
    const accepted = acceptEvents(previous,response,state,reconnect);
    if (!accepted.ready) throw new Error('The snapshot event cursor does not match its saved revision.');
    const last = accepted.events.at(-1);
    if (last?.event_sha256 && last.event_sha256 !== response.cursor_sha256) throw new Error('The snapshot final event differs from the journal cursor.');
    return {...incoming,accepted,cursor_sha256:response.cursor_sha256};
  }

  function layoutGraph(graph) {
    const nodes = list(graph?.nodes), edges = list(graph?.edges);
    const byId = new Map(), parents = new Map(), children = new Map(), ranks = new Map();
    for (const node of nodes) {
      if (!node.node_id || byId.has(node.node_id)) throw new Error('The saved process has duplicate or missing step identities.');
      byId.set(node.node_id, node); parents.set(node.node_id, []); children.set(node.node_id, []); ranks.set(node.node_id, 0);
    }
    for (const edge of edges) {
      const from = edge.source_node_id, to = edge.target_node_id;
      if (!byId.has(from) || !byId.has(to)) throw new Error('A saved process connection has no step.');
      parents.get(to).push(from); children.get(from).push(to);
    }
    const pending = new Map([...parents].map(([id, entries]) => [id, entries.length]));
    const queue = nodes.filter(node => !pending.get(node.node_id)).map(node => node.node_id), ordered = [];
    for (let i = 0; i < queue.length; i++) {
      const id = queue[i]; ordered.push(byId.get(id));
      for (const next of children.get(id)) {
        ranks.set(next, Math.max(ranks.get(next), ranks.get(id) + 1));
        pending.set(next, pending.get(next) - 1);
        if (!pending.get(next)) queue.push(next);
      }
    }
    if (ordered.length !== nodes.length) throw new Error('The saved process contains a cycle and cannot be displayed as an executable path.');
    const rows = [];
    for (const node of ordered) (rows[ranks.get(node.node_id)] ||= []).push(node);
    return {rows, nodes:ordered, edges, parents, children, byId};
  }

  function eventIdentity(event) {
    const after = event.after || event.payload?.after || {};
    return {revision:after.revision ?? event.revision ?? event.after_revision, state_sha256:after.state_sha256 ?? event.state_sha256 ?? event.after_state_sha256, graph_sha256:after.graph_sha256};
  }
  function acceptEvents(previous, batch, state, reconnect = false) {
    if (!batch || !Array.isArray(batch.events) || !Number.isSafeInteger(batch.current_revision)) throw new Error('The saved event cursor is incomplete.');
    if (batch.current_revision !== state.revision) return {ready:false, cursor:previous, events:[], animate:[]};
    if (batch.current_state_sha256 && batch.current_state_sha256 !== state.state_sha256) throw new Error('The event response differs from the saved claim identity.');
    const rows = [...batch.events].sort((a,b) => a.seq - b.seq);
    let cursor = previous ?? 0;
    for (const event of rows) {
      if (!Number.isSafeInteger(event.seq) || event.seq < 1 || (event.claim_id && event.claim_id !== state.claim_id)) throw new Error('An event has an invalid claim or sequence.');
      if (event.seq !== cursor + 1 || eventIdentity(event).revision !== event.seq) throw new Error('The saved event sequence has a gap or duplicate.');
      cursor = event.seq;
    }
    if (cursor !== state.revision) throw new Error('The event cursor does not reach the saved claim revision.');
    if (rows.length && eventIdentity(rows.at(-1)).state_sha256 !== state.state_sha256) throw new Error('The latest event does not match the saved claim identity.');
    const animate = previous == null || reconnect ? [] : rows.filter(event => {
      const after = eventIdentity(event);
      return event.seq > previous && after.revision === state.revision && after.state_sha256 === state.state_sha256 && (!after.graph_sha256 || after.graph_sha256 === state.graph?.graph_sha256);
    });
    return {ready:true, cursor, events:rows, animate};
  }

  function conditionFlags(expression) {
    if (!expression || typeof expression !== 'object') return [];
    return [...new Set([...(expression.flag ? [expression.flag] : []), ...conditionFlags(expression.not), ...list(expression.all || expression.any).flatMap(conditionFlags)])];
  }
  function changedTargets(before, after) {
    const nodeValue = (state, id) => JSON.stringify([list(state?.graph?.nodes).find(row => row.node_id === id), list(state?.evaluation?.nodes).find(row => row.node_id === id)]);
    const docValue = (state, id) => JSON.stringify([list(state?.obligations).filter(row => row.document_type === id), list(state?.evaluation?.documents).find(row => row.document_type === id)]);
    return {nodes:list(after.graph?.nodes).filter(node => nodeValue(before,node.node_id) !== nodeValue(after,node.node_id)).map(node => node.node_id), documents:[...new Set(list(after.obligations).map(row => row.document_type))].filter(id => docValue(before,id) !== docValue(after,id))};
  }

  function progressModel(state, history = []) {
    state ||= {};
    let start = state.run_id ? history.length : 0;
    for (let i=history.length-1;i>=0;i--) if (history[i].kind === 'work.started' && (!state.run_id || history[i].payload?.run_id === state.run_id)) { start=i; break; }
    const events=history.slice(start), phases=new Set(events.filter(event=>event.kind==='work.phase').map(event=>event.payload?.phase));
    if (state.status==='running') phases.add(state.phase);
    const has=kind=>events.some(event=>event.kind===kind);
    const accepted=[...events].reverse().find(event=>event.kind==='interpretation.accepted');
    const checks=list(accepted?.payload?.receipt?.checks);
    const sources=list(state.acquired_sources).length,total=list(state.source_descriptors).length;
    const publications=list(state.knowledge_published),published=publications.filter(item=>item.qualification?.status==='qualified').length,quarantined=publications.filter(item=>item.qualification?.status==='quarantined').length,uses=list(state.knowledge_uses).length;
    const phaseStage={acquiring:'sources',interpreting:'interpretation',verifying:'verification',progressing:'process'};
    const working=state.status==='running' ? phaseStage[state.phase] : null;
    const lastPhase=[...events].reverse().find(event=>event.kind==='work.phase')?.payload?.phase;
    const stopped=!active(state.status) ? phaseStage[lastPhase] : null;
    const definitions=[
      {id:'sources',label:'Sources',complete:total>0&&sources===total,detail:`${sources} / ${total} acquired`},
      {id:'interpretation',label:'Interpretation',complete:phases.has('verifying')||Boolean(accepted),detail:phases.has('verifying')||accepted?'Proposal recorded':phases.has('interpreting')?(working==='interpretation'?'Reading the evidence':'Interpretation not accepted'):'Not yet recorded'},
      {id:'verification',label:'Independent verification',complete:Boolean(accepted),detail:checks.length?`${checks.length} checks recorded`:accepted?'Interpretation admitted':phases.has('verifying')?(working==='verification'?'Checking source support':'Verification not accepted'):'Not yet recorded'},
      {id:'process',label:'Process & actions',complete:has('outcome.recorded'),detail:`${list(state.actions).length} action${list(state.actions).length===1?'':'s'} recorded in this claim · ${list(state.obligations).length} obligations`},
      {id:'knowledge',label:'Knowledge',complete:events.some(event=>event.kind==='knowledge.published'&&event.payload?.knowledge?.qualification?.status==='qualified'),detail:`${published} published · ${uses} reused${quarantined?` · ${quarantined} quarantined`:''}`}
    ];
    const stages=definitions.map(stage=>({...stage,state:working===stage.id?'active':stage.complete?'complete':stopped===stage.id?'blocked':stage.id==='knowledge'&&has('knowledge.published')?'blocked':stage.id==='knowledge'&&has('knowledge.used')?'recorded':'pending'}));
    const explanation=state.status==='running' ? (working ? state.phase_summary || 'Autonomous work has started.' : 'Autonomous work has started.') : state.deferral?.reason || state.outcome?.summary || 'Showing recorded work.';
    return {stages,explanation};
  }
  function progressMarkup(state,history) {
    const progress=progressModel(state,history);
    return `<section class="au-work-progress" aria-label="Recorded autonomous work"><ol class="au-progress-track">${progress.stages.map((stage,index)=>`<li data-au-stage="${stage.id}" data-state="${stage.state}"${stage.state==='active'?' aria-current="step"':''}><span class="au-progress-marker" aria-hidden="true">${stage.state==='complete'?'✓':stage.state==='recorded'?'↺':index+1}</span><div><strong>${h(stage.label)}</strong><span>${stage.state==='recorded'?'Reuse recorded · ':''}${h(stage.detail)}</span></div></li>`).join('')}</ol><p class="au-progress-explanation${active(state.status) ? '' : ' au-sr-only'}" role="status" aria-live="polite">${h(progress.explanation)}</p></section>`;
  }
  function transitionPlan(before,after,accepted,history=[]) {
    if (!before || before.claim_id!==after.claim_id || after.revision<=before.revision || !accepted?.ready || !accepted.animate?.length) return null;
    const newest=accepted.animate.at(-1),identity=eventIdentity(newest);
    if (identity.revision!==after.revision || identity.state_sha256!==after.state_sha256 || newest.seq!==accepted.cursor) return null;
    const changes=changedTargets(before,after), layout=layoutGraph(after.graph), ranks=new Map(layout.rows.flatMap((row,rank)=>row.map(node=>[node.node_id,rank])));
    const changedFacts=list(after.facts).filter(fact=>JSON.stringify(list(before.facts).find(row=>row.fact_id===fact.fact_id))!==JSON.stringify(fact));
    const sourceValue=(state,id)=>JSON.stringify([list(state.source_descriptors).find(row=>row.artifact_id===id),list(state.acquired_sources).find(row=>row.artifact_id===id)]);
    const sourceIds=new Set(list(after.source_descriptors).filter(source=>sourceValue(before,source.artifact_id)!==sourceValue(after,source.artifact_id)).map(source=>source.artifact_id));
    for (const fact of changedFacts) for (const citation of citationRows(fact)) sourceIds.add(citation.artifact_id);
    const edgeValue=(state,id)=>JSON.stringify([list(state.graph?.edges).find(row=>row.edge_id===id),list(state.evaluation?.edges).find(row=>row.edge_id===id)]);
    const edges=list(after.graph?.edges).filter(edge=>edgeValue(before,edge.edge_id)!==edgeValue(after,edge.edge_id)).map(edge=>({id:edge.edge_id,delay:260,duration:140}));
    const minimum=changes.nodes.length ? Math.min(...changes.nodes.map(id=>ranks.get(id)||0)) : 0;
    const nodes=changes.nodes.map(id=>({id,delay:400+Math.min(40,((ranks.get(id)||0)-minimum)*10),duration:180}));
    const facts=changedFacts.map(fact=>({id:fact.fact_id,delay:120,duration:140}));
    const sources=[...sourceIds].filter(Boolean).map(id=>({id,delay:0,duration:120}));
    const documents=changes.documents.map(id=>({id,delay:620,duration:160}));
    return {sources,facts,edges,nodes,documents,stages:[],duration:780};
  }
  function animateTransition(host,plan,environment={}) {
    const animations=new Set(),overlays=new Set();
    const cancel=()=>{for(const animation of animations)animation.cancel();animations.clear();for(const overlay of overlays)overlay.remove();overlays.clear();};
    if (!plan || environment.reducedMotion || environment.hidden || environment.dialogOpen || environment.keyboard) return {cancel,count:0};
    const run=(element,frames,timing,cleanup=()=>{})=>{
      if (!element?.animate || (element.closest?.('[hidden]') || element.closest?.('details:not([open])')) || element===environment.activeElement || element.contains?.(environment.activeElement)) { cleanup(); return; }
      const animation=element.animate(frames,{...timing,easing:'cubic-bezier(.2,.65,.3,1)',fill:'none'});animations.add(animation);
      animation.finished?.then(()=>{animations.delete(animation);cleanup();},()=>{animations.delete(animation);cleanup();});
    };
    for(const edge of host.querySelectorAll('[data-au-edge]')) {
      const timing=(plan.edges || []).find(row=>row.id===edge.dataset.auEdge);if(!timing)continue;
      const length=edge.getTotalLength?.();if(!Number.isFinite(length)||length<=0)continue;
      const overlay=edge.cloneNode(false);overlay.setAttribute('class','au-live-edge');overlay.removeAttribute?.('data-au-edge');edge.parentNode.appendChild(overlay);overlays.add(overlay);overlay.removeAttribute?.('data-state');overlay.removeAttribute?.('data-selected');
      run(overlay,[{strokeDasharray:`${length} ${length}`,strokeDashoffset:String(length),opacity:1},{strokeDasharray:`${length} ${length}`,strokeDashoffset:'0',opacity:1}],timing,()=>{overlay.remove();overlays.delete(overlay);});
    }
    for(const [selector,field,rows]of [['[data-au-source]','auSource',plan.sources || []],['[data-au-node]','auNode',plan.nodes || []],['[data-au-fact]','auFact',plan.facts || []],['[data-au-document]','auDocument',plan.documents || []]]) {
      for(const element of host.querySelectorAll(selector)) {
        const timing=rows.find(row=>row.id===element.dataset[field]);if(!timing)continue;
        run(element,[{opacity:.58},{opacity:1}],timing);
      }
    }
    return {cancel,count:animations.size};
  }

  const citationRows = item => list(item?.citations || item?.sources || item?.source_spans);
  const sourceLabel = (state, id) => name(list(state.source_descriptors).find(source => source.artifact_id === id)) || list(state.source_descriptors).find(source => source.artifact_id === id)?.file_name || 'Original source';
  function sourceButtons(state, item, origin = `record:${item?.fact_id || item?.obligation_id || item?.document_type || item?.action_id || item?.kind || 'claim'}`) {
    return citationRows(item).map(citation => `<button type="button" class="au-source-link" data-au-source="${h(citation.artifact_id)}" data-au-source-origin="${h(origin)}" data-au-citation="${h(JSON.stringify(citation))}">${h(sourceLabel(state, citation.artifact_id))}${citation.quote ? `<q>${h(citation.quote)}</q>` : ''}</button>`).join('');
  }
  function preferredNode(state, remembered = null) {
    const nodes = list(state.graph?.nodes), has = id => nodes.some(node => node.node_id === id);
    return has(remembered) ? remembered : has(state.evaluation?.focus_node_id) ? state.evaluation.focus_node_id : list(state.evaluation?.nodes).find(node => node.execution_state === 'ready' && has(node.node_id))?.node_id || nodes[0]?.node_id || null;
  }
  function edgeState(state, id) {
    const evaluation = list(state.evaluation?.edges).find(edge => edge.edge_id === id);
    return evaluation?.activation || evaluation?.condition_verdict || 'unresolved';
  }
  function graphMarkup(state, selected, projection = {}) {
    const graph = state.graph;
    if (!graph) return '<p class="au-empty">The packet is saved. No process has been committed yet.</p>';
    const layout = layoutGraph(graph), evaluation = new Map(list(state.evaluation?.nodes).map(node => [node.node_id, node]));
    const inspectionIndex = layout.nodes.findIndex(node => node.node_id === selected);
    const inspection = `<nav class="au-mobile-inspection" data-au-node-inspection aria-label="Inspect recorded process steps"><button type="button" class="au-secondary" data-au-node-previous aria-label="Inspect previous recorded step"${inspectionIndex <= 0 ? ' disabled' : ''}>Previous</button><div><strong data-au-inspection-position>${inspectionIndex >= 0 ? `Step ${inspectionIndex+1} of ${layout.nodes.length}` : `${layout.nodes.length} recorded steps`}</strong><span>Inspection position</span></div><button type="button" class="au-secondary" data-au-node-next aria-label="Inspect next recorded step"${inspectionIndex === layout.nodes.length-1 || !layout.nodes.length ? ' disabled' : ''}>Next</button></nav>`;
    return `${inspection}<div class="au-evidence-graph-help"><span>Complete recorded process · ${layout.nodes.length} steps · ${layout.edges.length} connections</span><span>Dashed routes do not apply. Scroll to follow every branch.</span></div><div class="au-graph-viewport au-evidence-graph-scroll" data-au-graph-pan tabindex="0" role="region" aria-label="Complete process graph; scroll horizontally"><div class="au-graph au-evidence-graph" data-au-graph data-orientation="horizontal" style="--au-ranks:${Math.max(1,layout.rows.length)}"><svg class="au-graph-lines" aria-hidden="true">${layout.edges.map(edge => `<path data-au-edge="${h(edge.edge_id)}" data-state="${h(edgeState(state,edge.edge_id))}" data-selected="${edge.source_node_id === selected || edge.target_node_id === selected}"><title>${h(edge.label || 'Recorded process connection')} · ${h(statusLabel(edgeState(state,edge.edge_id)))}</title></path>`).join('')}</svg>${layout.rows.map((row, rank) => `<div class="au-graph-rank" data-rank="${rank}">${row.map(node => {
      const evaluated = evaluation.get(node.node_id) || {}, status = evaluated.execution_state || evaluated.state || 'pending';
      const statusText = statusLabel(status) + (status === 'ready' && projection.node_capabilities?.[node.node_id]?.authorized === false ? ' · execution unavailable' : '');
      const parents = layout.parents.get(node.node_id).map(id => name(layout.byId.get(id))), fullName = name(node);
      return `<button type="button" class="au-node au-evidence-node" data-au-node="${h(node.node_id)}" data-status="${h(status)}" data-activation="${h(evaluated.activation || 'unresolved')}" aria-pressed="${selected === node.node_id}" aria-label="${h(fullName)}. ${h(statusText)}${parents.length ? `. After ${h(parents.join(' + '))}` : ''}"><span class="au-node-index au-evidence-junction" data-au-junction="${h(node.node_id)}">${status === 'completed' ? '✓' : String(layout.nodes.indexOf(node) + 1).padStart(2, '0')}</span><span class="au-node-copy"><strong class="au-node-title">${h(fullName)}</strong><span class="au-node-state">${h(statusText)}</span><span class="au-node-deps au-sr-only">${parents.length ? `After ${h(parents.join(' + '))}` : 'Starting point'}</span></span></button>`;
    }).join('')}</div>`).join('')}</div></div>`;
  }
  function obligationMarkup(state, selected, suppliedRows) {
    const documents = new Map(list(state.evaluation?.documents).map(doc => [doc.document_type, doc]));
    const rows = suppliedRows || list(state.obligations).concat(list(state.evaluation?.documents).filter(doc => !list(state.obligations).some(item => item.document_type === doc.document_type)));
    if (!rows.length) return '<p class="au-empty">No document obligations have been accepted yet.</p>';
    return `<ul class="au-obligations">${rows.map(obligation => {
      const doc = documents.get(obligation.document_type) || {}, nodes = [...new Set([obligation.node_id,obligation.decision_node_id,...list(obligation.required_at_node_ids),...list(obligation.node_ids)].filter(Boolean))];
      const status = doc.route_state || obligation.status || 'pending';
      const requiredFacts = list(obligation.required_fact_ids).map(id => list(state.facts).find(fact => fact.fact_id === id)?.label).filter(Boolean);
      return `<li class="au-obligation" data-au-obligation="${h(obligation.obligation_id || obligation.document_type)}" data-au-document="${h(obligation.document_type)}" data-status="${h(status)}"${nodes.includes(selected) ? ' data-selected="true"' : ''}><div><strong>${h(name(obligation) || name(doc))}</strong><span class="au-obligation-state">${h(statusLabel(status))}${doc.review_state && doc.review_state !== 'unreviewed' ? ` · ${h(words(doc.review_state))}` : ''}</span>${requiredFacts.length && !suppliedRows ? `<p>${h(requiredFacts.join('; '))}</p>` : ''}${obligation.reason ? `<details data-au-disclosure="obligation:${h(obligation.obligation_id || obligation.document_type)}"><summary>Why required</summary><p>${h(obligation.reason)}</p></details>` : ''}<div class="au-related">${nodes.filter(id => !suppliedRows || id !== selected).map(id => button(name(list(state.graph?.nodes).find(node => node.node_id === id)) || words(id), `data-au-select="${h(id)}"`)).join('')}</div>${['needed_now','unresolved','pending','held_behind_question'].includes(status) ? button('Add supporting files','data-au-add-files') : ''}</div>${sourceButtons(state, obligation)}</li>`;
    }).join('')}</ul>`;
  }
  function actionInstanceIdentity(action, receipt = {}, index = 0, entry = {}) {
    const logical = action.action_id || name(action) || 'recorded-action';
    const binding = receipt.receipt_sha256 ? `receipt:${receipt.receipt_sha256}` : `record:${JSON.stringify([receipt.parent_revision ?? null,receipt.parent_state_sha256 ?? null,receipt.workflow_id || entry.workflow_id || action.workflow_id || null,receipt.run_id || entry.run_id || action.run_id || null,index])}`;
    return `${logical}:${binding}`;
  }
  function actionRows(state, events = []) {
    let start = null;
    const runId = typeof state.run_id === 'string' && state.run_id.trim() ? state.run_id : null;
    if (runId) for (const event of events) if (event.kind === 'work.started' && event.payload?.run_id === runId) start = event.seq;
    return list(state.actions).map((entry,index) => {
      const result = entry.result || entry, receipt = entry.receipt || {};
      const revision = receipt.parent_revision;
      const scope = Number.isSafeInteger(start) && Number.isSafeInteger(revision) ? revision >= start ? 'current' : 'historical' : 'unassociated';
      return {result, receipt, scope,instanceId:actionInstanceIdentity(result,receipt,index,entry)};
    });
  }
  function actionMarkup(state, rows) {
    return rows.map(({result:action,receipt,scope,instanceId},index) => `<article class="au-action" data-au-action-scope="${scope}"><div class="au-action-heading"><strong>${h(name(action))}</strong><span>${h(statusLabel(action.status))}</span></div><p class="au-meta">${scope === 'current' ? 'Recorded in this run' : scope === 'historical' ? 'Recorded in an earlier run' : 'Recorded action · run association not recorded'}</p><p>${h(action.summary || action.reason || '')}</p>${sourceButtons(state,action,`action:${instanceId || actionInstanceIdentity(action,receipt,index)}`)}${Object.keys(receipt).length ? `<details class="au-receipt" data-au-disclosure="action:${h(instanceId || actionInstanceIdentity(action,receipt,index))}"><summary>Action receipt</summary>${Number.isSafeInteger(receipt.parent_revision) ? `<p>Recorded after revision ${h(receipt.parent_revision)}.</p>` : ''}${receipt.operation ? `<p>${h(words(receipt.operation))}</p>` : ''}<pre class="au-record-body">${h(JSON.stringify(receipt,null,2))}</pre></details>` : ''}<details class="au-technical-record" data-au-disclosure="action-record:${h(instanceId || actionInstanceIdentity(action,receipt,index))}"><summary>Full public action record</summary><pre class="au-record-body">${h(JSON.stringify({result:action,receipt,scope},null,2))}</pre></details></article>`).join('') || '<p class="au-empty">No action result recorded for this step.</p>';
  }
  function routeMarkup(state, selected) {
    const nodes = new Map(list(state.graph?.nodes).map(node => [node.node_id,node]));
    const edges = list(state.graph?.edges).filter(edge => edge.target_node_id === selected || edge.source_node_id === selected);
    const evaluation = new Map(list(state.evaluation?.edges).map(edge => [edge.edge_id,edge]));
    const currentNode = list(state.evaluation?.nodes).find(node => node.node_id === selected);
    const expression = nodes.get(selected)?.condition;
    const condition = value => {
      if (!value || typeof value !== 'object') return '';
      if (Object.prototype.hasOwnProperty.call(value,'const')) return h(statusLabel(value.const));
      if (value.flag) { const fact = list(state.facts).find(item => item.fact_id === `condition:${value.flag}` || item.flag === value.flag); return `${h(name(fact) || words(value.flag))}: ${h(statusLabel(fact?.verdict || fact?.status))}`; }
      if (value.not) return `Not (${condition(value.not)})`;
      if (value.all) return list(value.all).map(condition).join(' and ');
      if (value.any) return list(value.any).map(condition).join(' or ');
      return '';
    };
    return `<details class="au-step-route" data-au-disclosure="route:${h(selected)}"><summary>Branch and prerequisites <span>${edges.length} connections</span></summary>${expression ? `<p class="au-branch-condition">Recorded condition: ${condition(expression) || 'No condition detail recorded'}.</p>` : ''}${currentNode?.activation ? `<p>Recorded applicability: ${h(statusLabel(currentNode.activation))}.</p>` : ''}<ul class="au-step-relations">${edges.map(edge => {
      const incoming = edge.target_node_id === selected, other = incoming ? edge.source_node_id : edge.target_node_id, view = evaluation.get(edge.edge_id);
      const relation = edge.relation ? words(edge.relation) : incoming ? 'Follows' : 'Leads to';
      return `<li data-au-relation="${h(edge.relation || 'recorded_connection')}" data-au-edge-status="${h(view?.activation || view?.condition_verdict || 'unknown')}"><span>${h(incoming ? 'From' : 'To')} ${h(name(nodes.get(other)) || words(other))} · ${h(relation)}${view?.activation || view?.condition_verdict ? ` · ${h(statusLabel(view.activation || view.condition_verdict))}` : ''}</span>${edge.condition ? `<p>${condition(edge.condition)}</p>` : ''}${button('Inspect connected step',`data-au-select="${h(other)}"`)}</li>`;
    }).join('') || '<li>No process connection recorded for this step.</li>'}</ul></details>`;
  }
  function evidenceRelationships(state, selected, context = {}) {
    const node = list(state.graph?.nodes).find(item => item.node_id === selected);
    const relates = item => item.node_id === selected || item.decision_node_id === selected || list(item.node_ids).includes(selected) || list(item.required_at_node_ids).includes(selected);
    const obligations = list(state.obligations).filter(relates), incoming = list(state.graph?.edges).filter(edge => edge.target_node_id === selected);
    const ids = new Set(obligations.flatMap(item => list(item.required_fact_ids)));
    for (const flag of conditionFlags(node?.condition).concat(incoming.flatMap(edge => conditionFlags(edge.condition)))) ids.add(`condition:${flag}`);
    const facts = list(state.facts).filter(item => ids.has(item.fact_id) || relates(item)).sort((a,b) => Number(b.fact_id?.startsWith('condition:')) - Number(a.fact_id?.startsWith('condition:')));
    const evaluated = list(state.evaluation?.documents).filter(relates);
    const types = [...new Set([...obligations,...evaluated].map(item => item.document_type))];
    const documents = types.map(type => ({...obligations.find(item => item.document_type === type),...list(state.evaluation?.documents).find(item => item.document_type === type)}));
    return {node,obligations,incoming,facts,documents,fact:facts.find(item => item.fact_id === context.fact) || facts[0],document:documents.find(item => item.document_type === context.document) || documents[0],evaluation:list(state.evaluation?.nodes).find(item => item.node_id === selected) || {}};
  }
  function factRecordMarkup(state, fact) {
    return `<article class="au-fact" data-au-fact="${h(fact.fact_id)}"><strong>${h(name(fact) || words(fact.flag))}</strong><span>${h(statusLabel(fact.verdict || fact.status))}</span>${fact.summary || fact.reason ? `<p>${h(fact.summary || fact.reason)}</p>` : ''}${sourceButtons(state,fact)}${['unresolved','unknown','insufficient'].includes(fact.verdict || fact.status) ? button('Add evidence','data-au-add-files') : ''}<details class="au-technical-record" data-au-disclosure="fact-record:${h(fact.fact_id)}"><summary>Full fact record</summary><pre class="au-record-body">${h(JSON.stringify(fact,null,2))}</pre></details></article>`;
  }
  function evidencePathMarkup(state, selected, projection = {}, context = {}) {
    const r = evidenceRelationships(state,selected,context), {node,fact,document:requirement,evaluation} = r;
    if (!node) return '<p class="au-empty">No process step has been recorded yet.</p>';
    const citations = citationRows(fact), capability = projection.node_capabilities?.[selected], execution = evaluation.execution_state || evaluation.state;
    const stepStatus = execution === 'ready' ? `Process ready${capability?.authorized === false ? ' · execution unavailable' : ''}` : statusLabel(execution);
    const blocked = list(evaluation.blocked_by || evaluation.unresolved_dependencies);
    const sources = citations.slice(0,2).map((citation,index) => `<button type="button" class="au-source-link au-evidence-source" data-au-source="${h(citation.artifact_id)}" data-au-citation="${h(JSON.stringify(citation))}" data-au-source-origin="path:${h(selected)}:${h(fact.fact_id)}" data-au-wire="source-${index}"><span class="au-evidence-source-label">${h(sourceLabel(state,citation.artifact_id))}<span aria-hidden="true">↗</span></span>${citation.quote ? `<q>${context.trace ? `<mark>${h(citation.quote)}</mark>` : h(citation.quote)}</q>` : '<span>No passage text recorded.</span>'}</button>`).join('');
    const route = requirement?.route_state || 'pending', review = requirement?.review_state || 'unreviewed';
    const timing = {needed_later:'Needed when a requiring step is reached',needed_now:'Needed now in the recorded process',held_behind_question:'Held until the recorded question is resolved',held_not_reviewed:'Acquired; its evidence has not been established',not_needed:'Not required on the recorded route'}[route] || statusLabel(route);
    return `<div class="au-evidence-path${context.trace ? ' au-evidence-trace' : ''}" data-au-evidence-path><svg class="au-evidence-lines" aria-hidden="true"></svg><section class="au-evidence-column au-evidence-column--sources"><h4 class="au-evidence-column-label">01 · Original passages</h4><div class="au-evidence-source-stack">${sources || '<p class="au-empty">No supporting source passage is recorded for this fact.</p>'}</div>${citations.length > 2 ? `<details data-au-disclosure="passages:${h(fact.fact_id)}"><summary>All ${citations.length} supporting passages</summary>${sourceButtons(state,fact,`passages:${selected}:${fact.fact_id}`)}</details>` : ''}</section><section class="au-evidence-column au-evidence-column--facts"><h4 class="au-evidence-column-label">02 · ${fact?.fact_id?.startsWith('condition:') ? 'Branch condition' : 'Recorded fact'}</h4>${fact ? `<article class="au-fact au-evidence-fact" data-au-fact="${h(fact.fact_id)}" data-au-wire="fact"><button type="button" class="au-evidence-fact-select" data-au-fact-select="${h(fact.fact_id)}" aria-pressed="${Boolean(context.trace)}"><span class="au-evidence-object-symbol" aria-hidden="true">${['true','established'].includes(fact.verdict || fact.status) ? '✓' : (fact.verdict || fact.status) === 'false' ? '−' : '?'}</span><strong>${h(name(fact))}</strong><span>${h(statusLabel(fact.verdict || fact.status))}</span></button><details data-au-disclosure="focused-fact:${h(fact.fact_id)}"><summary>Inspect fact record</summary>${fact.summary || fact.reason ? `<p>${h(fact.summary || fact.reason)}</p>` : ''}<pre class="au-record-body">${h(JSON.stringify(fact,null,2))}</pre></details></article>` : '<p class="au-empty">No fact dependency is attached to this step.</p>'}${r.facts.length > 1 ? `<div class="au-evidence-options" aria-label="Related facts">${r.facts.filter(item => item !== fact).map(item => `<button type="button" data-au-fact-select="${h(item.fact_id)}" aria-pressed="false">${h(name(item))} · ${h(statusLabel(item.verdict || item.status))}</button>`).join('')}</div>` : ''}</section><section class="au-evidence-column au-evidence-column--step"><h4 class="au-evidence-column-label">03 · Selected process step</h4><header class="au-step-heading au-evidence-step" data-au-wire="step"><span class="au-evidence-step-junction" data-au-expanded-junction="${h(selected)}" aria-hidden="true">${String(layoutGraph(state.graph).nodes.findIndex(item => item.node_id === selected)+1).padStart(2,'0')}</span><h3 tabindex="-1" data-au-inspector-heading="${h(selected)}">${h(name(node))}</h3><p class="au-step-status">${h(stepStatus)}</p>${blocked.length ? `<p class="au-evidence-wait">Waiting for ${h(blocked.map(id => name(list(state.graph?.nodes).find(item => item.node_id === id)) || words(id)).join(', '))}.</p>` : evaluation.activation === 'false' ? '<p class="au-evidence-wait">This route does not apply to the recorded facts.</p>' : evaluation.activation === 'unresolved' ? '<p class="au-evidence-wait">Applicability remains unresolved.</p>' : ''}</header>${capability?.authorized === false ? `<p class="au-evidence-limit">${h(capability.reason || 'Execution is unavailable for this step.')}</p>` : ''}<button type="button" class="au-link au-back-process" data-au-back-process="${h(selected)}">Return focus to process ↗</button></section><section class="au-evidence-column au-evidence-column--requirements"><h4 class="au-evidence-column-label">04 · Derived requirement</h4>${requirement ? `<article class="au-evidence-requirement" data-au-document="${h(requirement.document_type)}" data-route="${h(route)}" data-au-wire="requirement"><span class="au-evidence-object-symbol" aria-hidden="true">${review === 'satisfied' ? '✓' : '·'}</span><h3>${h(name(requirement))}</h3><p class="au-evidence-review">${h(statusLabel(review))}</p><p class="au-evidence-timing">${h(timing)}</p><details data-au-disclosure="focused-document:${h(requirement.document_type)}"><summary>Inspect requirement</summary>${requirement.reason ? `<p>${h(requirement.reason)}</p>` : ''}${sourceButtons(state,requirement)}<pre class="au-record-body">${h(JSON.stringify({evaluation:list(state.evaluation?.documents).find(item => item.document_type === requirement.document_type),obligations:list(state.obligations).filter(item => item.document_type === requirement.document_type)},null,2))}</pre></details></article>` : '<p class="au-empty">No document requirement is attached to this step.</p>'}${r.documents.length > 1 ? `<div class="au-evidence-options" aria-label="Requirements for this step">${r.documents.map(item => `<button type="button" data-au-document-select="${h(item.document_type)}" aria-pressed="${item.document_type === requirement.document_type}">${h(name(item))} · ${h(statusLabel(item.route_state))}</button>`).join('')}</div>` : ''}</section></div>`;
  }
  function inspectorMarkup(state, selected, projection = {}, events = [], context = {}) {
    const r = evidenceRelationships(state,selected,context), {node,facts,obligations,evaluation} = r;
    if (!node) return '<div class="au-empty">Select a process step to inspect its evidence and consequences.</div>';
    const relates = item => item.node_id === selected || item.decision_node_id === selected || list(item.node_ids).includes(selected) || list(item.required_at_node_ids).includes(selected);
    const actions = actionRows(state,events).filter(({result:item}) => relates(item) || obligations.some(obligation => item.obligation_id === obligation.obligation_id));
    const capability = projection.node_capabilities?.[selected], executionState = evaluation.execution_state || evaluation.state;
    const execution = capability ? `<section class="au-capability" data-authorized="${capability.authorized === true}"><strong>${capability.authorized === true ? ['ready','completed'].includes(executionState) ? 'Available capability' : 'Available after prerequisites' : 'Execution limit'}</strong><p>${h(capability.reason || words(capability.id))}</p><p class="au-meta">Process readiness does not record execution or external authorization.</p></section>` : '';
    return `<div class="au-inspector au-evidence-inspector" data-au-selected-step="${h(selected)}">${evidencePathMarkup(state,selected,projection,context)}<details class="au-evidence-inspection" data-au-disclosure="inspection:${h(selected)}"><summary>Step evidence, actions and authority <span>${facts.length} facts · ${obligations.length} obligations · ${actions.length} recorded actions</span></summary>${execution}<div class="au-step-evidence"><section class="au-step-facts"><h4>Facts this step requires</h4>${facts.map(fact => factRecordMarkup(state,fact)).join('') || '<p class="au-empty">No fact dependencies recorded for this step.</p>'}</section><section class="au-step-documents"><h4>Required documents</h4>${obligationMarkup(state,selected,obligations)}${obligations.length ? `<details class="au-document-rules" data-au-disclosure="document-rules:${h(selected)}"><summary>Document rules and acquisition</summary>` : ''}${obligations.map(item => `<p class="au-meta">${list(item.rule_refs).length ? `Rule ${h(list(item.rule_refs).map(ref => typeof ref === 'string' ? ref : ref.rule_id || ref.title || ref.authority_id).join(' · '))} · ` : ''}${item.capability_id ? `Acquisition: ${h(words(item.capability_id))}` : 'No acquisition capability recorded'}</p>`).join('')}${obligations.length ? '</details>' : ''}</section><section class="au-step-actions"><h4>Recorded actions</h4>${actionMarkup(state,actions)}</section></div>${routeMarkup(state,selected)}<details class="au-rule-trace" data-au-disclosure="rules:${h(selected)}"><summary>Admitted rules</summary>${node.authority?.title ? `<strong>${h(node.authority.title)}</strong>` : ''}${node.authority?.quote ? `<blockquote>${h(node.authority.quote)}</blockquote>` : ''}${node.meaning && node.meaning !== node.authority?.quote ? `<p>${h(node.meaning)}</p>` : ''}${list(node.provenance?.rule_refs).map(ref => `<p>${h(typeof ref === 'string' ? ref : ref.title || ref.rule_id || ref.authority_id)}</p>`).join('')}${node.authority?.source_id ? `<p class="au-meta">${h(node.authority.source_id)}</p>` : ''}</details><details class="au-technical-record" data-au-disclosure="step-record:${h(selected)}"><summary>Complete step and capability record</summary><pre class="au-record-body">${h(JSON.stringify({node,evaluation,capability},null,2))}</pre></details></details></div>`;
  }
  function eventLabel(event) {
    if (event.kind === 'knowledge.published') return event.payload?.knowledge?.qualification?.status === 'qualified' ? 'Qualified knowledge version published' : 'Knowledge candidate withheld';
    return event.payload?.summary || event.payload?.reason || ({'intake':'Incoming packet saved', 'intake.received':'Incoming packet saved', 'work.started':'Autonomous investigation started', 'sources.acquired':'Original sources acquired', 'interpretation.accepted':'Source-grounded process accepted', 'graph.advanced':'Process advanced', 'action.completed':'Action result saved', 'outcome.recorded':'Operational outcome saved', 'work.completed':'Operational outcome saved', 'work.deferred':'Work deferred', 'knowledge.published':'Qualified knowledge version published', 'knowledge.used':'Qualified knowledge reused', 'knowledge.reused':'Qualified knowledge reused'})[event.kind] || words(event.kind);
  }
  function outcomeMarkup(state, outcome) {
    if (!outcome) return '';
    const gaps = list(outcome.missing_evidence).length, limits = list(outcome.authority_limits).length;
    const summary = [claimStatusLabel(state.status), gaps ? `${gaps} evidence gap${gaps === 1 ? '' : 's'}` : '', limits ? `${limits} execution limit${limits === 1 ? '' : 's'}` : ''].filter(Boolean).join(' · ');
    const reason = outcome.reason || outcome.authority_limits?.[0] || outcome.summary || outcome.title;
    return `<details class="au-outcome" data-status="${h(state.status)}" data-au-disclosure="outcome"><summary><strong>${h(summary)}</strong><span>${h(reason)}</span></summary><div class="au-outcome-body"><p class="au-eyebrow">${state.status === 'deferred' ? 'Why work stopped' : 'Recorded outcome'}</p><h2>${h(outcome.title || words(outcome.status) || claimStatusLabel(state.status))}</h2><p>${h(outcome.summary || outcome.reason || '')}</p>${list(outcome.authority_limits).map(reason => `<p>${h(reason)}</p>`).join('')}${gaps ? `<p><strong>Evidence still needed:</strong> ${h(outcome.missing_evidence.map(item => item.label || words(item.document_type)).join('; '))}.</p>${button('Add supporting files','data-au-add-files')}` : ''}${list(outcome.unresolved_facts).length ? `<p><strong>Unresolved:</strong> ${h(outcome.unresolved_facts.map(item => item.summary || words(item.fact_id)).join('; '))}.</p>` : ''}${outcome.next_action ? `<p>${h(outcome.next_action)}</p>` : ''}${sourceButtons(state,outcome)}${outcome.request_draft ? `<details data-au-disclosure="request-draft"><summary>Evidence request · ${h(statusLabel(outcome.request_draft.status))}</summary><p><strong>${h(outcome.request_draft.subject)}</strong></p><pre class="au-draft-body">${h(outcome.request_draft.body)}</pre></details>` : ''}<details class="au-technical-record" data-au-disclosure="outcome-record"><summary>Full public ${state.outcome ? 'outcome' : state.deferral ? 'deferral' : 'outcome'} record</summary><pre class="au-record-body">${h(JSON.stringify(state.outcome || state.deferral || outcome,null,2))}</pre></details></div></details>`;
  }
  function sourcesMarkup(state, readOnly = false) {
    return `<section class="au-supporting"><div class="au-section-heading"><h2>Original sources</h2><span>${list(state.acquired_sources).length} of ${list(state.source_descriptors).length} acquired</span></div><ul class="au-source-list">${list(state.source_descriptors).map(source => {const acquired = list(state.acquired_sources).find(row => row.artifact_id === source.artifact_id);return `<li>${button(source.file_name || name(source) || 'Original source', `data-au-source="${h(source.artifact_id)}" data-au-source-origin="originals:${h(source.artifact_id)}"`)}<span>${!acquired ? 'Received' : acquired.extraction === 'unsupported_metadata' ? 'Received · interpretation unsupported' : acquired.complete ? 'Extracted · sufficiency not established' : 'Partially extracted'}</span></li>`;}).join('') || '<li>No original source recorded.</li>'}</ul>${state.revision > 0 && !readOnly ? '<form data-au-arrival class="au-arrival"><label for="auAdditionalFiles">Add supporting files</label><input id="auAdditionalFiles" name="files" type="file" multiple required><button class="au-secondary" type="submit">Add files</button><p class="au-form-status" role="status"></p></form>' : ''}</section>`;
  }
  function activityMarkup(state, events, projection = {}) {
    return `<section class="au-activity"><h2>Activity</h2><p class="au-meta">The saved journal records work in sequence.</p><details class="au-history" data-au-disclosure="history"><summary>Recorded work <span>${events.length} events</span></summary><ol class="au-event-list">${events.slice().reverse().map(event => `<li><span class="au-event-seq">${h(event.seq)}</span><div><strong>${h(eventLabel(event))}</strong><time datetime="${h(event.timestamp || '')}">${h(dateLabel(event.timestamp))}</time><details class="au-technical-record" data-au-disclosure="event:${h(event.seq)}"><summary>Journal entry</summary><pre class="au-record-body">${h(JSON.stringify(event,null,2))}</pre></details></div></li>`).join('') || '<li>No events loaded.</li>'}</ol></details><section class="au-recorded-actions"><h3>Action record</h3>${actionMarkup(state,actionRows(state,events))}</section>${list(state.knowledge_uses).length ? `<section class="au-reuse"><h3>Knowledge used here</h3>${list(state.knowledge_uses).map(use => `<article><strong>${h(use.name || use.knowledge_id || use.version_id)} · version ${h(use.version || use.version_id)}</strong>${reuseDetails(use)}${knowledgeLink(use)}</article>`).join('')}${button('Inspect knowledge','data-au-nav="knowledge"')}</section>` : '<p class="au-empty">No knowledge reuse recorded for this claim.</p>'}<details class="au-technical-record" data-au-disclosure="claim-record"><summary>Complete saved claim and capability record</summary><pre class="au-record-body">${h(JSON.stringify({state,projection},null,2))}</pre></details></section>`;
  }
  function workMarkup(state, projection, selected, events, detail = 'step', context = {}, presentation = {}) {
    const mode = presentation.mode === 'replay' ? 'Verified replay' : presentation.mode === 'live' ? 'Live execution' : 'Saved state';
    const presentationControls = presentation.playing ? button('Pause presentation','data-au-demo-stop') : '';
    const itinerary = presentation.playing && DEMO_CASES[presentation.position]?.claim_id === state.claim_id ? `<details class="au-demo-itinerary" data-au-disclosure="demo-itinerary"><summary><span class="au-demo-position">Presentation ${String(presentation.position+1).padStart(2,'0')} of 09</span> · independent case order</summary>${demoItineraryMarkup(presentation.claims || [],presentation.position,state)}</details>` : '';
    if (state.revision === 0) return `<header class="au-work-head au-original-head"><div><p class="au-eyebrow"><button type="button" class="au-back-work" data-au-nav="work">Cases</button> / Original intake</p><h1 class="au-page-heading au-original-subject" id="auClaimTitle" data-au-claim-title tabindex="-1">${h(state.title)}</h1><p class="au-meta" data-au-presentation-mode>${h(mode)}</p></div><div class="au-work-controls"><span class="au-status">Not started</span>${presentation.mode !== 'replay' ? `<button type="button" class="au-primary" data-au-start${presentation.availability?.ready ? '' : ' disabled'}>Start investigation</button>` : ''}${presentationControls}</div></header>${itinerary}<section class="au-original-intake" aria-labelledby="auOriginalMessage"><div class="au-original-layout"><aside class="au-original-source-rail" aria-label="Original sources">${sourcesMarkup(state)}</aside><div class="au-original-message-column"><p class="au-eyebrow">Original customer message</p><h2 id="auOriginalMessage" class="au-sr-only">Original message</h2><pre class="au-original-message">${h(originalText(state))}</pre></div></div><p class="au-meta" data-au-start-availability>${h(presentation.mode === 'replay' ? 'No investigation had started at this point in the recorded history.' : presentation.availability?.reason || 'Checking live execution availability…')}</p></section>${presentation.replay ? replayIdentityMarkup(presentation.replay) : ''}`;
    const outcome = state.outcome || (state.deferral ? {title:words(state.deferral.code),reason:state.deferral.reason,status:'deferred',details:state.deferral.details} : null);
    const panels = [['step','Evidence path',inspectorMarkup(state,selected,projection,events,context)],['documents','Documents',`<section aria-labelledby="auDocumentsTitle" class="au-documents"><div class="au-section-heading"><h2 id="auDocumentsTitle">All document requirements</h2><span>${new Set([...list(state.obligations),...list(state.evaluation?.documents)].map(item => item.document_type)).size} documents</span></div><p class="au-meta">Requirements follow the recorded route. Acquiring a file does not establish its facts.</p>${obligationMarkup(state,selected)}</section>`],['sources','Original sources',sourcesMarkup(state,presentation.mode === 'replay')],['activity','Recorded work',activityMarkup(state,events,projection)]];
    return `<header class="au-work-head au-identity-claim-head"><div><p class="au-eyebrow"><button type="button" class="au-back-work" data-au-nav="work">Cases</button><span aria-hidden="true"> / </span>Claim · revision ${h(state.revision)}</p><h1 class="au-page-heading" id="auClaimTitle" data-au-claim-title tabindex="-1">${h(state.title)}</h1><p class="au-meta"><span data-au-presentation-mode>${h(mode)}</span> · ${h(state.graph?.title || state.graph?.label || 'Source-grounded investigation')}${state.phase ? ` · Recorded phase: ${h(words(state.phase))}` : ''}</p></div><div class="au-work-controls"><span class="au-status" data-tone="${tone(state.status)}">${h(claimStatusLabel(state.status))}</span>${presentation.mode !== 'replay' ? state.status === 'running' ? button('Pause work','data-au-pause') : state.deferral?.code === 'paused' ? button('Resume work','data-au-resume') : '' : ''}${presentation.pendingStart && presentation.mode !== 'replay' ? button('Retry start','data-au-start') : ''}${presentationControls}</div></header>${itinerary}${active(state.status) ? `<p class="au-evidence-working" role="status" aria-live="polite">${h(state.phase_summary || progressModel(state,events).explanation)}</p>` : ''}${outcomeMarkup(state,outcome)}<section class="au-evidence-canvas" data-au-canvas aria-label="Connected claim evidence"><div class="au-evidence-toolbar"><nav class="au-context-nav" aria-label="Claim details">${panels.map(([id,label]) => `<button type="button" data-au-detail="${id}" aria-pressed="${detail === id}" aria-controls="auPanel-${id}">${h(label)}</button>`).join('')}</nav><span class="au-evidence-packet-count">${list(state.source_descriptors).length} originals</span></div><div class="au-evidence-stage" data-au-evidence-stage><svg class="au-evidence-tether" data-au-tether aria-hidden="true"><path/></svg><section class="au-process-hero au-evidence-process" aria-labelledby="auProcessTitle"${detail === 'step' ? '' : ' hidden'}><h2 id="auProcessTitle" class="au-sr-only">Complete process</h2>${graphMarkup(state,selected,projection)}</section><div class="au-context-body" data-au-context="${h(detail)}">${panels.map(([id,label,body]) => `<section class="au-context-view" id="auPanel-${id}" data-au-panel="${id}" aria-label="${h(label)}"${detail === id ? '' : ' hidden'}>${body}</section>`).join('')}</div></div></section>${presentation.replay ? replayIdentityMarkup(presentation.replay) : ''}`;
  }
  function replayIdentityMarkup(record) {
    return `<details class="au-technical-record au-replay-identity"><summary>Verified replay · revision ${h(record.through_seq)} of ${h(record.current_revision)}</summary><dl class="au-chain"><div><dt>Recorded prefix · state</dt><dd class="au-hash">${h(record.state?.state_sha256)}</dd></div><div><dt>Current saved head</dt><dd class="au-hash">${h(record.current_state_sha256)}</dd></div></dl><pre class="au-record-body">${h(JSON.stringify(record.provenance,null,2))}</pre></details>`;
  }
  function knowledgeLink(use) {
    const id = use.knowledge_id || use.version_id, version = use.version || use.version_id;
    return id && version ? button('Inspect reused version',`data-au-knowledge="${h(id)}" data-au-version="${h(version)}" data-au-knowledge-sha="${h(use.knowledge_sha256 || '')}"`) : '';
  }
  function reuseDetails(use) {
    const applicability = typeof use.applicability === 'string' ? words(use.applicability) : use.applicability?.summary;
    const observed = [];
    if (Number.isSafeInteger(use.avoided_rule_compilations) && use.avoided_rule_compilations >= 0) observed.push(`${use.avoided_rule_compilations} rule compilation${use.avoided_rule_compilations === 1 ? '' : 's'} avoided`);
    if (Number.isSafeInteger(use.avoided_qualification_cases) && use.avoided_qualification_cases >= 0) observed.push(`${use.avoided_qualification_cases} qualification cases reused`);
    return `${use.reason || applicability ? `<p>${h(use.reason || applicability)}</p>` : ''}${observed.length ? `<p class="au-meta">${h(observed.join(' · '))}</p>` : ''}<details class="au-technical-record au-reuse-record" data-au-disclosure="reuse:${h(use.knowledge_id || use.version_id || '')}:${h(use.version || use.version_id || '')}:${h(use.workflow_id || use.claim_id || '')}"><summary>Public reuse record</summary><pre class="au-record-body">${h(JSON.stringify(use,null,2))}</pre></details>`;
  }
  function definitionMarkup(version) {
    const graph = version.graph || {nodes:[],edges:[]}, layout = layoutGraph(graph);
    const facts = new Map(list(version.facts).map(fact => [fact.fact_id,fact]));
    const rules = refs => list(refs).map(ref => typeof ref === 'string' ? ref : ref.title || ref.rule_id || ref.authority_id).filter(Boolean).join(' · ');
    return `<details class="au-definition" data-au-disclosure="definition:${h(version.knowledge_id || version.version_id || name(version))}:${h(version.version || version.version_id || '')}"><summary>Reusable definition</summary><h3>Process</h3><ol class="au-definition-steps">${layout.nodes.map(node => `<li><strong>${h(name(node))}</strong>${node.meaning ? `<p>${h(node.meaning)}</p>` : ''}${layout.parents.get(node.node_id).length ? `<p class="au-meta">After ${h(layout.parents.get(node.node_id).map(id => name(layout.byId.get(id))).join(' + '))}</p>` : ''}</li>`).join('') || '<li>No process definition recorded.</li>'}</ol><h3>Required facts</h3><ul class="au-definition-list">${[...facts.values()].map(fact => `<li>${h(name(fact))}</li>`).join('') || '<li>No fact definition recorded.</li>'}</ul><h3>Document obligations</h3><ul class="au-definition-list">${list(version.obligations).map(item => `<li><strong>${h(name(item))}</strong><p>${h(name(layout.byId.get(item.decision_node_id || item.node_id)) || words(item.node_id))} → ${h(list(item.required_fact_ids).map(id => name(facts.get(id)) || words(id)).join('; '))}</p>${item.reason ? `<p>${h(item.reason)}</p>` : ''}${list(item.rule_refs).length ? `<p class="au-meta">Rule ${h(rules(item.rule_refs))}</p>` : ''}</li>`).join('') || '<li>No obligation definition recorded.</li>'}</ul>${list(version.evidence_recipes).length ? `<h3>Qualified evidence recipes</h3><ul class="au-definition-list">${version.evidence_recipes.map(recipe => `<li><strong>${h(words(recipe.document_type))}</strong><p>${h(recipe.summary)}</p><ul>${list(recipe.required_fields).map(field => `<li>${h(field)}</li>`).join('')}</ul><p class="au-meta">Rule ${h(rules(recipe.rule_refs))}</p></li>`).join('')}</ul>` : ''}</details>`;
  }
  function lineageMarkup(version, versions = []) {
    const parent = versions.find(item => item.knowledge_sha256 && item.knowledge_sha256 === version.parent_knowledge_sha256);
    return `<div class="au-lineage-summary">${version.change_reason ? `<p>${h(version.change_reason)}</p>` : ''}${version.parent_knowledge_sha256 ? `<p class="au-meta">${parent ? `Derived from version ${h(parent.version || parent.version_id)}` : 'Parent version is not in this record'}${parent?.source_claim_id ? ` · ${button('Open parent source claim',`data-au-claim="${h(parent.source_claim_id)}"`)}` : ''}</p>` : '<p class="au-meta">First recorded version</p>'}</div>`;
  }
  function knowledgeUses(version, uses = []) {
    return list(uses).filter(use => {
      if ((use.knowledge_id || use.version_id) !== (version.knowledge_id || version.version_id) || String(use.version ?? use.version_id) !== String(version.version ?? version.version_id)) return false;
      if (Object.prototype.hasOwnProperty.call(use,'knowledge_sha256') && use.knowledge_sha256 != null) return Boolean(use.knowledge_sha256) && use.knowledge_sha256 === version.knowledge_sha256;
      return true;
    });
  }
  function knowledgeMarkup(data, claims = []) {
    const claimLabel = (id, fallback) => list(claims).find(claim => claim.claim_id === id)?.title || `${fallback} · ${String(id).slice(-8)}`;
    const claimLink = (id, fallback) => button(claimLabel(id,fallback),`data-au-claim="${h(id)}"`);
    const versions = list(data?.versions), uses = list(data?.uses), quarantined = list(data?.quarantined), groups = new Map();
    for (const version of versions) { const id = version.knowledge_id || version.version_id; if (!groups.has(id)) groups.set(id,[]); groups.get(id).push(version); }
    const versionMarkup = (version,history,latest) => {
      const receiving = knowledgeUses(version,uses), receivingIds = [...new Set(receiving.map(use => use.claim_id).filter(Boolean))];
      const identity = `${version.knowledge_id || version.version_id || name(version)}:${version.version || version.version_id || ''}`;
      const qualification = version.qualification || {}, status = qualification.status || version.validation?.status || version.status;
      return `<li class="au-knowledge-version au-version-row au-identity-knowledge-version" data-au-version="${h(version.version || version.version_id)}" data-au-knowledge-identity="${h(identity)}" data-current="${latest}"><div class="au-version-heading"><strong>Version ${h(version.version || version.version_id)}</strong><span>${latest ? 'Latest recorded version' : 'Earlier recorded version'}</span>${version.created_at ? `<time datetime="${h(version.created_at)}" title="${h(version.created_at)}">${h(dateLabel(version.created_at))}</time>` : ''}</div><div class="au-evidence-knowledge-path" data-au-knowledge-path><svg class="au-evidence-lines" aria-hidden="true"></svg><section class="au-evidence-knowledge-origin" data-au-wire="origin"><h4 class="au-evidence-column-label">01 · Learned from</h4>${version.source_claim_id ? claimLink(version.source_claim_id,'Open source claim') : '<p class="au-meta">Source claim not recorded</p>'}${lineageMarkup(version,history)}</section><section class="au-evidence-knowledge-definition" data-au-wire="version"><h4 class="au-evidence-column-label">02 · Qualified process version</h4><div class="au-evidence-version-object"><span class="au-knowledge-status">${h(statusLabel(status))} · version ${h(version.version || version.version_id)}</span><h3>${h(name(version))}</h3><p>${list(version.graph?.nodes).length} process steps · ${list(version.evidence_recipes).length} evidence recipes</p>${qualification.regression_cases ? `<p>${h(qualification.regression_cases)} branch assignments checked</p>` : ''}${qualification.summary ? `<p>${h(qualification.summary)}</p>` : ''}</div></section><section class="au-evidence-knowledge-receiving" data-au-wire="reuse"><h4 class="au-evidence-column-label">03 · Reused in ${receivingIds.length} claims</h4>${receivingIds.map(id => claimLink(id,'Open receiving claim')).join('') || '<p class="au-meta">No receiving claim recorded yet</p>'}<p class="au-meta">Reuse carries a process definition. Each claim must establish its own facts from its original sources.</p></section></div><details class="au-evidence-inspection" data-au-disclosure="knowledge-inspection:${h(identity)}"><summary>Version definition, qualification and lineage</summary>${definitionMarkup(version)}<details class="au-qualification" data-au-disclosure="qualification:${h(identity)}"><summary>Qualification checks</summary><p>${h(qualification.summary || statusLabel(status))}</p>${qualification.regression_cases ? `<p>${h(qualification.regression_cases)} branch assignments checked</p>` : ''}<ul>${list(qualification.checks).map(check => `<li>${h(typeof check === 'string' ? words(check) : check.summary || check.name || check.check || check.status)}</li>`).join('') || '<li>No qualification checks recorded.</li>'}</ul></details>${receiving.length ? `<details data-au-disclosure="version-uses:${h(identity)}"><summary>Exact receiving-claim reuse records</summary>${receiving.map(use => `<article>${use.claim_id ? claimLink(use.claim_id,'Open receiving claim') : ''}${reuseDetails(use)}</article>`).join('')}</details>` : ''}<details class="au-provenance" data-au-disclosure="provenance:${h(identity)}"><summary>Provenance and receipts</summary><dl class="au-chain">${['source_claim_id','parent_knowledge_sha256','parent_definition_sha256','knowledge_sha256','rule_pack_sha256','source_state_sha256','proposer_receipt_sha256','verifier_receipt_sha256','regression_receipt_sha256'].filter(field => version[field]).map(field => `<div><dt>${h(words(field.replace('_sha256','')))}</dt><dd class="${field.endsWith('sha256') ? 'au-hash' : ''}">${h(version[field])}</dd></div>`).join('')}</dl><details class="au-technical-record"><summary>Full public version record</summary><pre class="au-record-body">${h(JSON.stringify(version,null,2))}</pre></details></details></details></li>`;
    };
    const cards = [...groups.values()].map(history => {
      history.sort((a,b) => Number(b.version) - Number(a.version));
      const version = history[0], identity = version.knowledge_id || version.version_id || name(version);
      return `<article class="au-knowledge-card au-identity-knowledge-card"><p class="au-eyebrow">${h(words(version.category || version.family || 'Process knowledge'))}</p><h2>${h(name(version) || version.knowledge_id || version.version_id)}</h2>${version.summary || version.description ? `<p>${h(version.summary || version.description)}</p>` : ''}<ol class="au-version-lineage">${versionMarkup(version,history,true)}</ol><details class="au-version-disclosure" data-au-disclosure="versions:${h(identity)}"><summary>Version history <span>${history.length}</span></summary><ol class="au-version-history">${history.slice(1).map(item => versionMarkup(item,history,false)).join('') || '<li>No earlier recorded version.</li>'}</ol></details></article>`;
    }).join('');
    return `<header class="au-work-head au-identity-knowledge-head"><div><p class="au-eyebrow">A memory with a source</p><h1 class="au-page-heading" tabindex="-1">Knowledge in context.</h1></div></header><p class="au-lead">Qualified process definitions carry their origin, checks and applicability into the next investigation. Case values and original files stay with their claim.</p><div class="au-knowledge-summary"><span><strong>${versions.length}</strong> recorded versions</span><span><strong>${uses.length}</strong> recorded uses</span><span><strong>${quarantined.length}</strong> quarantined candidates</span></div><div class="au-knowledge-grid">${cards || '<p class="au-empty">No qualified knowledge version has been published.</p>'}</div>${uses.length ? `<details class="au-knowledge-reuse au-evidence-inspection" data-au-disclosure="all-knowledge-uses"><summary>All recorded reuse <span>${uses.length}</span></summary><ul class="au-event-list">${uses.map(use => `<li><div><strong>${h(use.name || use.knowledge_id || use.version_id)} · version ${h(use.version || use.version_id)}</strong>${reuseDetails(use)}${knowledgeLink(use)}${use.claim_id ? claimLink(use.claim_id,'Open receiving claim') : ''}</div></li>`).join('')}</ul></details>` : ''}<details class="au-history au-quarantine" data-au-disclosure="quarantine"><summary>Quarantined candidates <span>${quarantined.length}</span></summary><ul class="au-event-list">${quarantined.map(item => `<li><div><strong>${h(name(item) || item.candidate_id || item.knowledge_id || 'Quarantined candidate')}</strong><p>${h(item.qualification?.reason || item.reason || item.summary || 'No qualification recorded')}</p>${item.source_claim_id ? claimLink(item.source_claim_id,'Open source claim') : ''}<details class="au-technical-record"><summary>Public quarantine record</summary><pre class="au-record-body">${h(JSON.stringify(item,null,2))}</pre></details></div></li>`).join('') || '<li>No quarantined candidates.</li>'}</ul></details>`;
  }
  function collectionRows(claims, scope = 'all') {
    return list(claims).filter(claim => scope === 'all' || (scope === 'originals' ? claim.origin === 'canonical_original' : claim.origin !== 'canonical_original'));
  }
  function collectionFilters(rows) {
    return [...new Set(['all','not_started','working','deferred','investigation_complete',...rows.map(claim => statusFilter(claim.status)).filter(status => status && !active(status))])];
  }
  function collectionCounts(rows, scope) {
    return [[scope === 'added' ? 'Added cases' : 'Original cases',rows.length],['In progress',rows.filter(claim => active(claim.status)).length],['Deferred',rows.filter(claim => claim.status === 'deferred').length],['Investigation complete',rows.filter(claim => complete(claim.status)).length]];
  }
  function matchingClaims(claims, {search = '', filter = 'all', domain = 'all', scope = 'all'} = {}) {
    const terms = search.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    return collectionRows(claims,scope).filter(claim => (domain === 'all' || domainOf(claim) === domain) && (filter === 'all' || filter === 'working' && active(claim.status) || statusFilter(claim.status) === statusFilter(filter)) && terms.every(term => [claim.claim_id,claim.title,originalText(claim),claim.language,claim.channel,claimStatusLabel(claim.status),claim.phase,claim.phase_summary,claim.outcome?.summary,claim.outcome?.reason,claimConstraint(claim),claim.browse_metadata?.family_id].filter(Boolean).join(' ').toLocaleLowerCase().includes(term)));
  }
  function claimConstraint(claim) {
    const outcome = claim.outcome;
    const missing = list(outcome?.missing_evidence).map(item => item.label || words(item.document_type)).filter(Boolean);
    return outcome?.reason || (missing.length ? `Evidence needed: ${missing.join('; ')}` : '') || list(outcome?.authority_limits)[0] || outcome?.next_action || '';
  }
  function claimsMarkup(claims, options = {}) {
    return matchingClaims(claims,options).map(claim => {
      const unprocessed = claim.mode === 'unprocessed' || claim.status === 'not_started';
      const constraint = originalText(claim).slice(0,240) || claimConstraint(claim) || claim.outcome?.summary || (active(claim.status) ? claim.phase_summary : 'Open original sources and recorded work.');
      const native = [claim.language === 'de-CH' ? 'Deutsch' : claim.language === 'en' ? 'English' : claim.language,claim.channel,Number.isSafeInteger(claim.attachment_count) ? `${claim.attachment_count} attachment${claim.attachment_count === 1 ? '' : 's'}` : ''].filter(Boolean);
      return `<article class="au-claim-row au-identity-claim-row" data-au-claim-row="${h(claim.claim_id)}"><button type="button" class="au-claim-open" data-au-claim="${h(claim.claim_id)}"><strong>${h(claim.title || 'Untitled claim')}</strong>${constraint ? `<span class="au-claim-constraint">${h(constraint)}</span>` : ''}<span class="au-claim-phase">${claim.origin !== 'canonical_original' ? `${claim.origin === 'native_intake' ? 'Added intake' : 'Origin not recorded'} · ` : ''}${h(native.join(' · '))}${native.length ? ' · ' : ''}${unprocessed ? 'Original intake' : claim.phase ? `Recorded phase: ${h(words(claim.phase))}` : 'Saved work'}${Number.isSafeInteger(claim.revision) && !unprocessed ? ` · revision ${h(claim.revision)}` : ''}</span></button><span class="au-status" data-tone="${tone(claim.status)}">${h(claimStatusLabel(claim.status))}</span></article>`;
    }).join('') || `<p class="au-empty">${list(claims).length ? 'No cases match this search.' : 'No cases are available.'}</p>`;
  }
  function domainMarkup(claims, domain = 'all') {
    return `<nav class="au-domain-browse" aria-label="Browse case domains"><button type="button" data-au-domain="all" aria-pressed="${domain === 'all'}"><span>All cases</span><strong>${claims.length}</strong></button>${DOMAINS.map(item => `<button type="button" data-au-domain="${item.id}" aria-pressed="${domain === item.id}"${claims.some(claim => domainOf(claim) === item.id) ? '' : ' disabled'}><span>${h(item.label)}</span><strong>${claims.filter(claim => domainOf(claim) === item.id).length}</strong></button>`).join('')}</nav>`;
  }
  function collectionMarkup(claims, options = {}) {
    const {search = '', domain = 'all', scope = 'originals'} = options, filter = statusFilter(options.filter || 'all');
    const rows = collectionRows(claims,scope), filters = collectionFilters(rows), counts = collectionCounts(rows,scope), matching = {...options,scope,filter};
    return `<section class="au-collection au-identity-collection"><header class="au-collection-head"><div><p class="au-eyebrow">${scope === 'added' ? 'Added cases' : 'Original case collection'}</p><h1 class="au-page-heading" tabindex="-1">Every case has a source.</h1><p class="au-lead">${scope === 'added' ? 'Additional intakes retain their own sources and recorded history.' : 'Explore the 150 original intakes, then follow the work that actually exists.'}</p></div>${button('New claim','data-au-nav="intake"',true)}</header><nav class="au-collection-scope" aria-label="Case collection"><button type="button" data-au-collection-scope="originals" aria-pressed="${scope === 'originals'}">Original cases <span>${collectionRows(claims,'originals').length}</span></button><button type="button" data-au-collection-scope="added" aria-pressed="${scope === 'added'}">Added cases <span>${collectionRows(claims,'added').length}</span></button></nav>${scope === 'originals' ? domainMarkup(rows,domain) : ''}<div class="au-collection-summary">${counts.map(([label,count]) => `<span><strong>${count}</strong> ${h(label)}</span>`).join('')}</div><div class="au-collection-tools"><label for="auClaimSearch">Search cases<input id="auClaimSearch" type="search" data-au-claim-search value="${h(search)}" placeholder="Original message, title or case ID" autocomplete="off"></label><label for="auClaimFilter">Status<select id="auClaimFilter" data-au-claim-filter>${filters.map(value => `<option value="${h(value)}"${filter === value ? ' selected' : ''}>${h(value === 'all' ? 'All statuses' : value === 'working' ? 'In progress' : statusLabel(value))}</option>`).join('')}</select></label><button type="button" class="au-link" data-au-refresh-claims>Refresh</button></div><div class="au-section-heading"><h2>${scope === 'added' ? 'Added cases' : 'Cases'}</h2><span data-au-collection-count>${matchingClaims(rows,matching).length} of ${rows.length}</span></div><div class="au-claim-list" data-au-claims>${claimsMarkup(rows,matching)}</div></section>`;
  }
  function liveAvailability(status) {
    if (!status) return {ready:false,reason:'Checking live execution availability…'};
    if (!status.enabled) return {ready:false,reason:'Live execution is disabled.'};
    if (!status.provider_ready) return {ready:false,reason:'Live inference is unavailable.'};
    if (status.limits?.autonomous_can_start === false) return {ready:false,reason:status.limits.autonomous_reason === 'call_limit_reached' ? 'The recorded call allowance is exhausted.' : status.limits.autonomous_reason === 'cost_limit_reached' ? 'The recorded cost allowance is exhausted.' : 'The recorded allowance does not permit new work.'};
    return {ready:true,reason:'One worker handles the live queue in sequence.'};
  }
  function demoItineraryMarkup(claims, position = null, current = null) {
    return `<div class="au-demo-selection" aria-label="Presentation order of independent cases">${DOMAINS.map(domain => `<section data-au-demo-domain="${domain.id}"><div class="au-section-heading"><h2>${h(domain.label)}</h2><span>3 original cases</span></div><ol start="${DEMO_CASES.findIndex(row => row.domain === domain.id)+1}">${DEMO_CASES.filter(row => row.domain === domain.id).map(row => {
      const index = DEMO_CASES.indexOf(row), claim = current?.claim_id === row.claim_id ? current : claims.find(claim => claim.claim_id === row.claim_id), here = index === position;
      return `<li data-au-demo-case="${row.claim_id}"${here ? ' aria-current="step"' : ''}><span class="au-demo-order" aria-hidden="true">${String(index+1).padStart(2,'0')}</span><button type="button" data-au-claim="${row.claim_id}" title="${h(claim?.title || 'Original record')}" aria-label="${h(`Presentation case ${String(index+1).padStart(2,'0')}. ${row.label}. ${claim?.title || 'Original record'}`)}"><strong>${h(row.label)}</strong><span>${h(claim?.title || 'Original record')}</span></button><span class="au-status" data-tone="${tone(claim?.status)}">${h(claim ? claimStatusLabel(claim.status) : 'Status not loaded')}</span></li>`;
    }).join('')}</ol></section>`).join('')}</div>`;
  }
  function demonstrationMarkup(claims, status, mode = 'replay') {
    const availability = liveAvailability(status);
    return `<section class="au-demonstration"><header class="au-collection-head"><div><p class="au-eyebrow">Nine original cases · three domains</p><h1 class="au-page-heading" tabindex="-1">Follow the evidence.</h1><p class="au-lead">A selected route through the same cases, sources and accepted histories.</p></div></header><div class="au-demo-controls"><div class="au-mode-choice" role="group" aria-label="Demonstration mode"><button type="button" data-au-demo-mode="replay" aria-pressed="${mode === 'replay'}">Verified replay</button><button type="button" data-au-demo-mode="live" aria-pressed="${mode === 'live'}">Live execution</button></div>${button(mode === 'replay' ? 'Play recorded work' : 'Start live presentation','data-au-demo-play',true)}<p class="au-meta" data-au-demo-availability>${h(mode === 'live' ? availability.reason : 'Recorded executions only. A case without accepted history remains not started.')}</p></div><p class="au-meta au-demo-order-note">01–09 · Presentation order across independent original cases.</p>${demoItineraryMarkup(claims)}</section>`;
  }
  function mediaType(file) {
    if (text(file.type).trim()) return file.type;
    const extension = String(file.name || '').match(/\.([^.]+)$/)?.[1].toLowerCase();
    return ({eml:'message/rfc822',txt:'text/plain',md:'text/markdown',csv:'text/csv',json:'application/json'})[extension] || 'application/octet-stream';
  }
  async function digest(value) {
    if (!root.crypto?.subtle) throw new Error('Source identity cannot be checked in this browser.');
    const bytes = typeof value === 'string' ? new TextEncoder().encode(value) : value;
    return [...new Uint8Array(await root.crypto.subtle.digest('SHA-256', bytes))].map(byte => byte.toString(16).padStart(2,'0')).join('');
  }
  function canonicalJSON(value) {
    if (Array.isArray(value)) return '[' + value.map(canonicalJSON).join(',') + ']';
    if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonicalJSON(value[key])).join(',') + '}';
    return JSON.stringify(value);
  }
  async function checkedPreview(state, descriptor, response) {
    if (!response || response.preview_only !== true || response.evidence_admitted !== false || Object.prototype.hasOwnProperty.call(response,'receipt_sha256')) throw new Error('The source preview is not a read-only preview.');
    if (response.claim_id !== state.claim_id || response.artifact_id !== descriptor.artifact_id || response.sha256 !== descriptor.sha256 || response.file_name !== descriptor.file_name || response.media_type !== descriptor.media_type) throw new Error('The preview source identity differs from the original packet.');
    const material = {...response}; delete material.preview_sha256;
    if (!isHash(response.preview_sha256) || await digest(canonicalJSON(material)) !== response.preview_sha256) throw new Error('The source preview failed its identity check.');
    if (typeof response.text !== 'string' || !isHash(response.text_sha256) || await digest(response.text) !== response.text_sha256) throw new Error('The preview text failed its identity check.');
    const originalSource = list(state.original_binding?.source_map).some(source => source.artifact_id === descriptor.artifact_id);
    if (originalSource && response.original_binding_sha256 !== state.original_binding.original_binding_sha256) throw new Error('The source preview belongs to another original binding.');
    return response;
  }
  function readReplay(response, claimId, through) {
    const incoming = readState(response,claimId), state = incoming.state;
    if (response.mode !== 'replay' || response.replay_only !== true || response.through_seq !== through || state.revision !== through || !Number.isSafeInteger(response.current_revision) || response.current_revision < through || !isHash(response.current_state_sha256) || !response.provenance || typeof response.provenance !== 'object') throw new Error('The verified replay identity or provenance is incomplete.');
    if (response.current_revision === 0 ? response.current_event_sha256 !== null : !isHash(response.current_event_sha256)) throw new Error('The replay current head event identity is incomplete.');
    if (response.current_revision === through && (response.current_state_sha256 !== state.state_sha256 || response.current_event_sha256 !== state.last_event_sha256)) throw new Error('The replay prefix differs from the same saved head revision.');
    const provenance = response.provenance;
    for (const [field,stateField] of [['source_roster_sha256','source_roster_sha256'],['policy_id','policy_id'],['run_id','run_id'],['event_sha256','last_event_sha256']]) {
      if (state[stateField] !== undefined && (!Object.prototype.hasOwnProperty.call(provenance,field) || provenance[field] !== state[stateField])) throw new Error('The replay provenance differs from its recorded prefix.');
    }
    const binding = state.original_binding || {};
    for (const field of ['original_binding_sha256','claim_binding_sha256','corpus_manifest_sha256','static_template_sha256']) {
      if ((field === 'original_binding_sha256' && binding[field] !== undefined || Object.prototype.hasOwnProperty.call(provenance,field)) && provenance[field] !== (binding[field] ?? null)) throw new Error('The replay original binding provenance differs from its prefix.');
    }
    if (provenance.sources) {
      const sources = list(state.source_descriptors), recorded = list(provenance.sources);
      if (sources.length !== recorded.length || new Set(recorded.map(source => source.artifact_id)).size !== recorded.length || recorded.some((source,index) => { const original = sources[index]; return original.artifact_id !== source.artifact_id || original.sha256 !== source.sha256 || Object.keys(source).some(field => canonicalJSON(source[field]) !== canonicalJSON(original[field])); })) throw new Error('The replay source provenance differs from the prefix packet.');
    }
    if (provenance.source_map && canonicalJSON(provenance.source_map) !== canonicalJSON(binding.source_map || [])) throw new Error('The replay source map differs from its original binding.');
    if (provenance.rule_pack_sha256) {
      const packs = [...new Set(list(state.receipts).map(row => row.receipt?.rule_pack_sha256).filter(Boolean))].sort();
      if (canonicalJSON(provenance.rule_pack_sha256) !== canonicalJSON(packs)) throw new Error('The replay rule provenance differs from its recorded receipts.');
    }
    if (response.current_head && (response.current_head.revision !== response.current_revision || response.current_head.state_sha256 !== response.current_state_sha256 || response.current_head.event_sha256 !== response.current_event_sha256)) throw new Error('The replay current head identity differs from its envelope.');
    // Prefix state and events bind to their own revision, separately from the live head.
    const prefix = {...response,current_revision:state.revision,current_state_sha256:state.state_sha256};
    return {...readSnapshot(prefix,claimId,null,true),replay:response};
  }
  function demoAssetURL(value, location) {
    const url = new URL(value, location.href);
    if (url.origin !== location.origin || url.username || url.password || !/^[a-f0-9]{64}$/i.test(url.searchParams.get('sha256') || '')) throw new Error('The fictional packet asset has no local content identity.');
    return url;
  }
  async function checkedExamples(bytes, expectedHash) {
    if (await digest(bytes) !== expectedHash.toLowerCase()) throw new Error('The fictional packet asset failed its identity check.');
    const value = JSON.parse(new TextDecoder().decode(bytes));
    if (!Array.isArray(value.packets) || value.packets.length > 20) throw new Error('The fictional packet list is invalid.');
    for (const packet of value.packets) {
      if (typeof packet.title !== 'string' || !packet.title || packet.title.length > 300 || typeof packet.message !== 'string' || !packet.message || packet.message.length > 100000 || !Array.isArray(packet.files) || packet.files.length > 20) throw new Error('A fictional packet is incomplete.');
      for (const file of packet.files) if (typeof file.file_name !== 'string' || !file.file_name || typeof file.media_type !== 'string' || typeof file.content_base64 !== 'string' || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(file.content_base64)) throw new Error('A fictional source file is invalid.');
    }
    return value.packets;
  }
  function prefillExample(form, packet) {
    if (!root.DataTransfer || !root.File) throw new Error('This browser cannot prefill supporting files.');
    const transfer = new root.DataTransfer();
    for (const file of packet.files) {
      const bytes = Uint8Array.from(root.atob(file.content_base64), char => char.charCodeAt(0));
      transfer.items.add(new root.File([bytes], file.file_name, {type:file.media_type}));
    }
    form.elements.files.files = transfer.files;
    form.elements.title.value = packet.title;
    form.elements.message.value = packet.message;
  }
  async function checkedSource(state, descriptor, response, citation) {
    const source = response.source || response;
    if (source.claim_id && source.claim_id !== state.claim_id) throw new Error('The source belongs to another claim.');
    if (source.artifact_id !== descriptor.artifact_id || source.sha256 !== descriptor.sha256 || typeof source.text !== 'string') throw new Error('The source identity differs from the saved packet.');
    const hash = await digest(source.text);
    if (!source.text_sha256 || source.text_sha256 !== hash) throw new Error('The source text failed its identity check.');
    let span = null;
    if (citation) {
      if (citation.artifact_id !== source.artifact_id || (citation.sha256 && citation.sha256 !== source.sha256) || (citation.text_sha256 && citation.text_sha256 !== hash)) throw new Error('The cited passage belongs to a different source version.');
      const chars = Array.from(source.text), start = citation.start_char, end = citation.end_char;
      if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || end <= start || end > chars.length || chars.slice(start,end).join('') !== citation.quote) throw new Error('The exact cited passage could not be located in this source.');
      span = {before:chars.slice(0,start).join(''), quote:chars.slice(start,end).join(''), after:chars.slice(end).join('')};
    }
    return {source, span};
  }

  function mount(container, options = {}) {
    if (!container?.addEventListener) throw new Error('An autonomous workspace container is required.');
    destroy(container);
    const doc = container.ownerDocument, fetcher = options.fetch || root.fetch?.bind(root), base = options.apiBase || BASE;
    const mainTag = container.tagName === 'MAIN' ? 'div' : 'main';
    if (!fetcher) throw new Error('The autonomous API is unavailable.');
    let disposed = false, epoch = 0, timer = null, selected = null, current = null, projection = {}, cursor = null, history = [], detail = 'step', view = 'work', disconnected = false, connectionFailed = false, busy = false, status = null, pendingIntake = null, pendingArrival = null, pendingControl = null, dialogReturn = null, sourceEpoch = 0, polling = null, claimRead = 0;
    let openingId = null, openingPreferences = {}, snapshotAvailable = null, presentationMode = 'saved', replayRecord = null, demoMode = 'replay', demoSession = null, demoTimer = null, pendingStart = null, nativeSourceURL = null;
    let evidenceContext = {}, selectionMotion = null, tetherGeometry = null, graphViewportWidth = null;
    const controllers = new Set();
    const reduced = root.matchMedia?.('(prefers-reduced-motion: reduce)');
    let motion = null, keyboard = false, examples = null, routedFragment = null, intakeForm = null, claims = [], claimsLoaded = false, claimsRead = 0;
    const claimViews = new Map(), arrivalForms = new Map(), arrivals = new Map(), controls = new Map(), starts = new Map();
    const collection = {search:'',filter:'all',domain:'all',scope:'originals'};
    container.classList.add('au-workspace');
    container.innerHTML = `<div class="au-shell au-identity-shell"><header class="au-identity-header"><a class="au-brand" href="#autonomous/cases">CasePath<span>Evidence into action</span></a><button type="button" class="au-header-new" data-au-nav="intake">New claim <span aria-hidden="true">↗</span></button><nav class="au-nav" aria-label="CasePath"><button type="button" data-au-nav="work" aria-current="page">Cases</button><button type="button" data-au-nav="demonstration">Demonstration</button><button type="button" data-au-nav="knowledge">Knowledge</button></nav></header><${mainTag} class="au-main"><div class="au-global-status" role="status" aria-live="polite"></div><div class="au-body" data-au-view data-au-view-state="work"></div></${mainTag}></div><dialog class="au-source-dialog" aria-labelledby="auSourceTitle"><header class="au-dialog-header"><div><p class="au-eyebrow">Original source</p><h2 id="auSourceTitle">Source</h2></div><button type="button" class="au-secondary" data-au-close>Close source</button></header><div data-au-source-content></div></dialog>`;
    const host = container.querySelector('[data-au-view]'), globalStatus = container.querySelector('.au-global-status'), dialog = container.querySelector('dialog');
    function notice(message, error = false) { globalStatus.textContent = message; globalStatus.classList.toggle('au-error', error); }
    function route(fragment, writeHistory = true) {
      if (writeHistory && root.location && root.location.hash !== fragment && root.history?.pushState) root.history.pushState(null,'',root.location.pathname + root.location.search + fragment);
      routedFragment = writeHistory ? fragment : root.location?.hash || fragment;
      if (dialog.open) { dialogReturn = null; sourceEpoch++; dialog.close(); }
    }
    function pendingRoute() { return Boolean(root.location && root.location.hash !== routedFragment); }
    function routeChanged() {
      if (disposed || busy || (!root.location && routedFragment !== null)) return;
      const fragment = root.location?.hash || '';
      if (fragment === routedFragment) return;
      if (fragment === '#autonomous/knowledge') showKnowledge(false);
      else if (fragment.startsWith('#autonomous/knowledge?')) { const params = new URLSearchParams(fragment.slice(fragment.indexOf('?')+1)); showKnowledge(false,{knowledge_id:params.get('knowledge'),version:params.get('version'),knowledge_sha256:params.get('sha256')}); }
      else if (fragment.startsWith('#autonomous/claim/')) {
        try { const [encoded,query = ''] = fragment.slice('#autonomous/claim/'.length).split('?'), params = new URLSearchParams(query), id = decodeURIComponent(encoded); id ? openClaim(id,false,{mode:params.get('mode') === 'replay' ? 'replay' : 'saved',through:Number(params.get('through') || 0),detail:params.get('detail')}) : showWork(false); }
        catch (_) { showWork(false); }
      } else if (fragment.startsWith('#autonomous/demonstration')) { const params = new URLSearchParams(fragment.split('?')[1] || ''); demoMode = params.get('mode') === 'live' ? 'live' : 'replay'; showDemonstration(false); }
      else if (fragment.startsWith('#autonomous/cases?') || fragment.startsWith('#autonomous/work?')) {
        const params = new URLSearchParams(fragment.split('?')[1]); collection.search = params.get('q') || ''; collection.filter = statusFilter(params.get('status') || 'all'); collection.domain = params.get('domain') || 'all'; collection.scope = params.get('scope') === 'added' ? 'added' : 'originals'; showWork(false);
      } else if (['#autonomous/new','#autonomous/intake'].includes(fragment)) showIntake(false);
      else { collection.search = ''; collection.filter = 'all'; collection.domain = 'all'; collection.scope = 'originals'; showWork(false); }
    }
    async function request(path, init = {}) {
      const controller = new AbortController(); controllers.add(controller);
      const timeout = root.setTimeout(() => controller.abort(), 15000);
      try {
        const response = await fetcher(base + path, {...init, signal:controller.signal, headers:{Accept:'application/json', ...(init.body ? {'Content-Type':'application/json','X-CasePath-Agent-Work':'1'} : {}), ...init.headers}, cache:'no-store'});
        const data = await response.json();
        if (!response.ok) { const error = new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || data.message || `Request refused (${response.status}).`); error.status = response.status; throw error; }
        return data;
      } finally { root.clearTimeout(timeout); controllers.delete(controller); }
    }
    function cancelPoll() { if (timer) root.clearTimeout(timer); timer = null; }
    function clearNativeSource() { if (nativeSourceURL) root.URL?.revokeObjectURL(nativeSourceURL); nativeSourceURL = null; }
    async function nativeSource(path, descriptor, token, sourceToken) {
      const controller = new AbortController(); controllers.add(controller);
      const timeout = root.setTimeout(() => controller.abort(),15000);
      try {
        const response = await fetcher(base + path,{signal:controller.signal,headers:{Accept:descriptor.media_type || 'application/octet-stream'},cache:'no-store',credentials:'same-origin',redirect:'error'});
        if (!response.ok) throw new Error('Native preview unavailable. Download the original file.');
        const bytes = await response.arrayBuffer();
        if (await digest(bytes) !== descriptor.sha256 || Number.isSafeInteger(descriptor.size_bytes) && descriptor.size_bytes !== bytes.byteLength) throw new Error('The original file failed its byte identity check.');
        if (disposed || token !== epoch || sourceToken !== sourceEpoch || !dialog.open) return null;
        clearNativeSource(); nativeSourceURL = root.URL.createObjectURL(new root.Blob([bytes],{type:descriptor.media_type})); return nativeSourceURL;
      } finally { root.clearTimeout(timeout); controllers.delete(controller); }
    }
    function schedule() { cancelPoll(); if (!disposed && view === 'claim' && openingId && presentationMode !== 'replay') timer = root.setTimeout(current ? poll : () => loadOpenedClaim(openingId,epoch), current && !active(current.status) ? 6000 : 1600); }
    function focusTitle() { host.querySelector('h1')?.focus({preventScroll:true}); }
    function focusPanel(element) {
      const panel = element?.closest?.('[data-au-panel]');
      return panel?.dataset?.auPanel ? panel : null;
    }
    function focusEligible(element, token) {
      const panel = focusPanel(element);
      return (!panel || !panel.hidden) && (!token?.panel || panel?.dataset.auPanel === token.panel);
    }
    function focusToken(element) {
      if (!element || !host.contains(element)) return null;
      const panel = focusPanel(element)?.dataset.auPanel || null;
      for (const attr of ['data-au-start','data-au-node-previous','data-au-node-next','data-au-node','data-au-select','data-au-fact-select','data-au-document-select','data-au-source','data-au-nav','data-au-pause','data-au-resume','data-au-graph-pan','data-au-claim-title','data-au-inspector-heading','data-au-back-process','data-au-detail','data-au-add-files']) if (element.hasAttribute(attr)) return {attr,value:element.getAttribute(attr),citation:element.getAttribute('data-au-citation'),origin:element.getAttribute('data-au-source-origin'),panel};
      const details = element.matches('summary') ? element.parentElement : null;
      return details?.hasAttribute('data-au-disclosure') ? {disclosure:details.dataset.auDisclosure,panel} : null;
    }
    function focusTarget(token) {
      if (!token) return null;
      if (token.disclosure) return [...host.querySelectorAll('[data-au-disclosure]')].find(el => el.dataset.auDisclosure === token.disclosure && focusEligible(el.querySelector('summary'),token))?.querySelector('summary');
      return [...host.querySelectorAll(`[${token.attr}]`)].find(el => el.getAttribute(token.attr) === token.value && el.getAttribute('data-au-citation') === token.citation && el.getAttribute('data-au-source-origin') === token.origin && focusEligible(el,token));
    }
    function nav(name) { container.querySelectorAll('.au-identity-header [data-au-nav]').forEach(item => { if (item.dataset.auNav === name) item.setAttribute('aria-current','page'); else item.removeAttribute('aria-current'); }); }
    function connectionGeometry(surface, pairs) {
      const svg = surface?.querySelector?.('.au-evidence-lines'), frame = surface?.getBoundingClientRect?.();
      if (!svg || !frame?.width || !frame.height || surface.closest?.('[hidden],details:not([open])')) return null;
      const ports = new Map([...surface.querySelectorAll('[data-au-wire]')].map(element => [element.dataset.auWire,element.getBoundingClientRect()]));
      const paths = pairs.map(([from,to,muted=false]) => {
        const a = ports.get(from), b = ports.get(to); if (!a || !b) return '';
        const horizontal = b.left >= a.right, x1 = horizontal ? a.right-frame.left : a.left+a.width/2-frame.left, y1 = horizontal ? a.top+a.height/2-frame.top : a.bottom-frame.top, x2 = horizontal ? b.left-frame.left : b.left+b.width/2-frame.left, y2 = horizontal ? b.top+b.height/2-frame.top : b.top-frame.top;
        const path = horizontal ? `M${x1} ${y1} C${(x1+x2)/2} ${y1},${(x1+x2)/2} ${y2},${x2} ${y2}` : `M${x1} ${y1} C${x1} ${(y1+y2)/2},${x2} ${(y1+y2)/2},${x2} ${y2}`;
        return `<path d="${path}" data-state="${muted ? 'false' : 'true'}"/><circle cx="${x2}" cy="${y2}" r="2"/>`;
      }).join('');
      return {svg,width:frame.width,height:frame.height,paths};
    }
    function drawEdges(navigation = false) {
      if (disposed) return;
      // Read every relevant rectangle before writing SVG geometry.
      const graph = host.querySelector('[data-au-graph]'), graphSvg = graph?.querySelector('svg'), frame = graph?.getBoundingClientRect?.();
      let graphPaths = null;
      if (graphSvg && frame?.width && frame.height && current?.graph) {
        const nodes = new Map([...graph.querySelectorAll('[data-au-node]')].map(element => {
          const junction = element.querySelector?.('[data-au-junction]') || element;
          return [element.dataset.auNode,{bounds:junction.getBoundingClientRect(),rank:Number(element.parentElement.dataset.rank)}];
        }));
        graphPaths = list(current.graph.edges).map((edge,index) => {
          const from = nodes.get(edge.source_node_id), to = nodes.get(edge.target_node_id); if (!from || !to) return '';
          const x1=from.bounds.right-frame.left,y1=from.bounds.top+from.bounds.height/2-frame.top,x2=to.bounds.left-frame.left,y2=to.bounds.top+to.bounds.height/2-frame.top,lane=frame.height-14-(index%3)*9;
          const path=to.rank-from.rank>1 ? `M${x1} ${y1} C${x1+18} ${y1},${x1+18} ${lane},${x1+34} ${lane} L${x2-34} ${lane} C${x2-18} ${lane},${x2-18} ${y2},${x2} ${y2}` : `M${x1} ${y1} C${(x1+x2)/2} ${y1},${(x1+x2)/2} ${y2},${x2} ${y2}`;
          return `<path d="${path}" data-au-edge="${h(edge.edge_id)}" data-state="${h(edgeState(current,edge.edge_id))}" data-selected="${edge.source_node_id === selected || edge.target_node_id === selected}"><title>${h(edge.label || 'Recorded process connection')} · ${h(statusLabel(edgeState(current,edge.edge_id)))}</title></path>`;
        }).join('');
      }
      const lens = host.querySelector('[data-au-evidence-path]'), relations = current ? evidenceRelationships(current,selected,evidenceContext) : null;
      const wires = [connectionGeometry(lens,[...citationRows(relations?.fact).slice(0,2).map((_,index) => [`source-${index}`,'fact']),['fact','step'],['step','requirement',relations?.evaluation.activation === 'false']]), ...[...host.querySelectorAll('[data-au-knowledge-path]')].map(surface => connectionGeometry(surface,[['origin','version'],['version','reuse']]))].filter(Boolean);
      const stage=host.querySelector('.au-evidence-stage'), tether=host.querySelector('[data-au-tether]'), path=tether?.querySelector('path'), junction=[...host.querySelectorAll('[data-au-junction]')].find(element => element.dataset.auJunction === selected), expanded=host.querySelector('[data-au-expanded-junction]'), viewport=host.querySelector('.au-graph-viewport');
      const a=junction?.getBoundingClientRect?.(), b=expanded?.getBoundingClientRect?.(), area=viewport?.getBoundingClientRect?.(), bounds=stage?.getBoundingClientRect?.();
      let nextTether=null;
      if (detail === 'step' && current && path && bounds?.width && bounds.height && a && b && area && a.left >= area.left && a.right <= area.right && !expanded.closest?.('[hidden]')) {
        const x=a.left+a.width/2-bounds.left,y=a.bottom-bounds.top,mid=area.bottom-bounds.top+18;
        const narrow = root.matchMedia?.('(max-width: 1000px)')?.matches || bounds.width < 650;
        const tx=narrow ? b.left-bounds.left : b.left+b.width/2-bounds.left,ty=narrow ? b.top+b.height/2-bounds.top : b.top-bounds.top;
        let geometry;
        if (narrow) {
          const lane=2,bend=mid+20,end=Math.max(bend,ty-18);
          geometry=`M${x} ${y} C${x} ${mid},${lane} ${mid},${lane} ${bend} L${lane} ${end} C${lane} ${ty},${tx} ${ty},${tx} ${ty}`;
        } else {
          // Split the measured desktop cubic without changing its shape; both
          // responsive routes retain M/C/L/C commands for one cancellable morph.
          const mx=(x+tx)/2,my=(y+6*mid+ty)/8;
          geometry=`M${x} ${y} C${x} ${(y+mid)/2},${(3*x+tx)/4} ${(y+3*mid)/4},${mx} ${my} L${mx} ${my} C${(x+3*tx)/4} ${(3*mid+ty)/4},${tx} ${(mid+ty)/2},${tx} ${ty}`;
        }
        nextTether={claim:current.claim_id,node:selected,width:bounds.width,height:bounds.height,d:geometry};
      }
      if (!navigation && selectionMotion && tetherGeometry?.d !== nextTether?.d) selectionMotion.cancel();
      if (graphPaths !== null) { graphSvg.setAttribute('viewBox',`0 0 ${frame.width} ${frame.height}`); graphSvg.innerHTML=graphPaths; }
      for (const wire of wires) { wire.svg.setAttribute('viewBox',`0 0 ${wire.width} ${wire.height}`); wire.svg.innerHTML=wire.paths; }
      if (path) {
        if (nextTether) {
          tether.setAttribute('viewBox',`0 0 ${nextTether.width} ${nextTether.height}`); path.setAttribute('d',nextTether.d); path.setAttribute('data-au-selected-junction',selected);
          if (navigation && tetherGeometry?.claim === nextTether.claim && tetherGeometry.node !== nextTether.node && tetherGeometry.width === nextTether.width && !doc.hidden && !dialog.open && !reduced?.matches && !keyboard && path.animate) {
            selectionMotion?.cancel(); selectionMotion=path.animate([{d:`path("${tetherGeometry.d}")`},{d:`path("${nextTether.d}")`}],{duration:320,easing:'cubic-bezier(.22,.75,.18,1)',fill:'none'});
          }
        } else path.removeAttribute('d');
      }
      tetherGeometry=nextTether; graphViewportWidth=area?.width ?? null;
    }
    function preserveClaimView() {
      if (view !== 'claim' || !current) return;
      const viewport = host.querySelector('.au-graph-viewport');
      claimViews.set(current.claim_id,{selected,detail,evidenceContext:{...evidenceContext},scrollLeft:viewport?.scrollLeft || 0,scrollTop:viewport?.scrollTop || 0,open:new Set([...host.querySelectorAll('details[open][data-au-disclosure]')].map(el => el.dataset.auDisclosure))});
      const arrival = host.querySelector('[data-au-arrival]');
      if (arrival) { arrivalForms.set(current.claim_id,arrival); arrival.remove?.(); }
      if (pendingArrival) arrivals.set(current.claim_id,pendingArrival); else arrivals.delete(current.claim_id);
      if (pendingControl) controls.set(current.claim_id,pendingControl); else controls.delete(current.claim_id);
    }
    function leaveView() {
      motion?.cancel(); selectionMotion?.cancel(); tetherGeometry = null;
      if (view === 'intake') { intakeForm = host.querySelector('[data-au-intake]') || intakeForm; intakeForm?.remove?.(); }
      if (view === 'work') { const main = container.querySelector('.au-main'); collection.scrollTop = host.scrollTop || 0; collection.mainTop = main?.scrollTop || 0; collection.mainLeft = main?.scrollLeft || 0; collection.scrollX = root.scrollX || 0; collection.scrollY = root.scrollY || 0; }
      preserveClaimView();
    }
    function setView(name) { view = name; host.setAttribute?.('data-au-view-state',name); }
    function revealGraphNode(node, center = false) {
      const viewport = host.querySelector('.au-graph-viewport');
      const area = viewport?.getBoundingClientRect?.(), bounds = node?.getBoundingClientRect?.();
      if (!area || !bounds) return;
      if (center || bounds.left < area.left+8 || bounds.right > area.right-8) viewport.scrollLeft += bounds.left-area.left-(area.width-bounds.width)/2;
      if (center || bounds.top < area.top+8 || bounds.bottom > area.bottom-8) viewport.scrollTop += bounds.top-area.top-(area.height-bounds.height)/2;
    }
    function renderClaim(changes = null, navigation = false) {
      if (!current || view !== 'claim') return;
      motion?.cancel(); selectionMotion?.cancel();
      const focused = doc.activeElement, focusKey = focusToken(focused);
      const previous = claimViews.get(current.claim_id);
      const open = new Set([...host.querySelectorAll('details[open][data-au-disclosure]')].map(el => el.dataset.auDisclosure));
      if (!host.querySelector('[data-au-claim-title]') && previous) for (const id of previous.open) open.add(id);
      const priorViewport = host.querySelector('.au-graph-viewport');
      const scrollLeft = priorViewport?.scrollLeft ?? previous?.scrollLeft ?? 0, scrollTop = priorViewport?.scrollTop ?? previous?.scrollTop ?? 0;
      const arrival = host.querySelector('[data-au-arrival]') || arrivalForms.get(current.claim_id), focusInArrival = arrival?.contains?.(focused);
      // Moving the original node keeps native FileList, entered text and retry state.
      arrival?.remove?.();
      host.innerHTML = workMarkup(current,projection,selected,history,detail,evidenceContext,{mode:presentationMode,replay:replayRecord,pendingStart:Boolean(pendingStart),playing:Boolean(demoSession),position:demoSession?.index,claims,availability:pendingStart ? {ready:true,reason:'The start response is unconfirmed. Retry uses the same request.'} : liveAvailability(status)});
      if (arrival) host.querySelector('[data-au-arrival]')?.replaceWith(arrival);
      const presentArrival = host.querySelector('[data-au-arrival]');
      if (presentArrival) arrivalForms.set(current.claim_id,presentArrival);
      if (pendingArrival && presentArrival) { lockForm(presentArrival,true,true); presentArrival.querySelector('.au-form-status').textContent ||= 'The prior response was not confirmed. Retry sends the same saved supporting-file request.'; }
      if (focusInArrival) focused?.focus?.({preventScroll:true});
      const viewport = host.querySelector('.au-graph-viewport'); if (viewport) { viewport.scrollLeft = scrollLeft; viewport.scrollTop = scrollTop; }
      for (const disclosure of host.querySelectorAll('[data-au-disclosure]')) disclosure.open = open.has(disclosure.dataset.auDisclosure);
      focusTarget(focusKey)?.focus({preventScroll:true});
      if (navigation || !priorViewport) revealGraphNode([...host.querySelectorAll('[data-au-node]')].find(element => element.dataset.auNode === selected));
      if (pendingStart?.claimId === current.claim_id) { const start = host.querySelector('[data-au-start]'); if (start) { start.textContent = busy ? 'Starting…' : 'Retry start'; start.disabled = busy; } }
      if (pendingControl?.claimId === current.claim_id) { const control = host.querySelector(`[data-au-${pendingControl.action}]`); if (control) { control.textContent = busy ? `${pendingControl.action === 'pause' ? 'Pausing' : 'Resuming'}…` : `Retry ${pendingControl.action}`; control.disabled = busy; } }
      drawEdges(navigation);
      motion = animateTransition(host,changes,{hidden:doc.hidden,dialogOpen:dialog.open,reducedMotion:reduced?.matches,keyboard,activeElement:doc.activeElement});
    }
    function setDetail(value, focusFiles = false) {
      if (view !== 'claim' || !['step','documents','sources','activity'].includes(value)) return;
      motion?.cancel(); selectionMotion?.cancel(); detail = value;
      host.querySelector('[data-au-context]')?.setAttribute('data-au-context',value);
      const process = host.querySelector('.au-evidence-process'); if (process) process.hidden = value !== 'step';
      for (const panel of host.querySelectorAll('[data-au-panel]')) panel.hidden = panel.dataset.auPanel !== value;
      for (const control of host.querySelectorAll('.au-context-nav [data-au-detail]')) control.setAttribute('aria-pressed',String(control.dataset.auDetail === value));
      drawEdges();
      if (root.history?.replaceState && current) { const fragment = claimFragment(current.claim_id,{mode:presentationMode,through:replayRecord?.through_seq,detail}); root.history.replaceState(null,'',root.location.pathname + root.location.search + fragment); routedFragment = fragment; }
      if (focusFiles) host.querySelector('#auAdditionalFiles')?.focus({preventScroll:true});
    }
    async function consistentRead(id, after, reconnect = false, token = epoch) {
      let missingSnapshot = false;
      if (snapshotAvailable !== false) {
        try {
          const response = await request(`/claims/${key(id)}/snapshot?after=${after ?? 0}`);
          if (disposed || token !== epoch) throw new Error('The claim view changed while reading its snapshot.');
          const result = readSnapshot(response,id,after,reconnect);
          snapshotAvailable = true;
          return result;
        } catch (error) {
          if (![404,405,501].includes(error.status)) throw error;
          if (error.status === 404) missingSnapshot = true; else snapshotAvailable = false;
        }
      }
      const incoming = readState(await request(`/claims/${key(id)}`),id);
      if (disposed || token !== epoch) throw new Error('The claim view changed while reading its saved state.');
      const batch = await request(`/claims/${key(id)}/events?after=${after ?? 0}`);
      const accepted = acceptEvents(after,batch,incoming.state,reconnect);
      if (missingSnapshot) snapshotAvailable = false;
      return {...incoming,accepted};
    }
    function verifiedAdvance(incoming) {
      if (current && incoming.state.revision < current.revision) throw new Error('A stale claim revision was returned.');
      if (current && incoming.state.revision === current.revision && incoming.state.state_sha256 !== current.state_sha256) throw new Error('A saved revision changed identity.');
    }
    async function poll() {
      const token = epoch, id = current?.claim_id;
      if (!id || disposed || view !== 'claim' || presentationMode === 'replay' || polling === token) return;
      polling = token; const read = ++claimRead;
      try {
        const incoming = await consistentRead(id,cursor,disconnected);
        if (disposed || token !== epoch || pendingRoute() || view !== 'claim' || read !== claimRead) return;
        const accepted = incoming.accepted;
        if (!accepted.ready) return;
        verifiedAdvance(incoming);
        const changed = disconnected || !current || current.state_sha256 !== incoming.state.state_sha256 || cursor !== accepted.cursor || JSON.stringify(projection) !== JSON.stringify(incoming.projection);
        const changes = transitionPlan(current,incoming.state,accepted,history);
        current = incoming.state; projection = incoming.projection; cursor = accepted.cursor;
        const existing = new Map(history.map(event => [event.seq,event])); for (const event of accepted.events) existing.set(event.seq,event);
        history = [...existing.values()].sort((a,b) => a.seq-b.seq);
        selected = preferredNode(current,selected);
        if (changed) { renderClaim(changes); rememberClaim(current); }
        if (connectionFailed) notice('Connection restored. Showing saved work.'); else notice('');
        disconnected = false; connectionFailed = false;
        advanceLivePresentation();
      } catch (error) { if (!disposed && token === epoch && !pendingRoute() && read === claimRead) { disconnected = true; connectionFailed = true; notice(`Updates paused: ${error.message} Saved work remains visible.`, true); } }
      finally { if (polling === token) polling = null; if (!disposed && token === epoch && !pendingRoute() && view === 'claim') schedule(); }
    }
    async function loadOpenedClaim(id, token, preferences = openingPreferences) {
      const read = ++claimRead;
      try {
        let incoming;
        // Old servers still need paired reads. Three attempts stay bounded;
        // transient writer advances then recover on the normal timer.
        for (let attempt = 0; attempt < 3; attempt++) {
          try { incoming = await consistentRead(id,null,true,token); }
          catch (error) { if (!error.transientAdvance) throw error; incoming = null; }
          if (disposed || token !== epoch || pendingRoute() || view !== 'claim' || id !== openingId || read !== claimRead) return;
          if (incoming?.accepted.ready) break;
        }
        if (!incoming?.accepted.ready) {
          const error = new Error('The writer advanced while the claim was opening. Checking again automatically.'); error.transientAdvance = true; throw error;
        }
        verifiedAdvance(incoming);
        const initial = !current, changed = initial || current.state_sha256 !== incoming.state.state_sha256 || JSON.stringify(projection) !== JSON.stringify(incoming.projection);
        current = incoming.state; projection = incoming.projection; cursor = incoming.accepted.cursor; history = incoming.accepted.events;
        const previous = initial ? claimViews.get(id) : {selected,evidenceContext,detail};
        selected = preferredNode(current,previous?.selected); evidenceContext = previous?.evidenceContext || {};
        detail = preferences.detail || previous?.detail || (current.revision === 0 ? 'sources' : 'step');
        if (changed) renderClaim(); rememberClaim(current); notice(''); if (initial) focusTitle(); schedule();
        resumeLivePresentation();
        if (!claimsLoaded) loadClaims(token).catch(() => {});
        serviceStatus(token).catch(() => {});
        return current;
      } catch (error) {
        if (!disposed && token === epoch && !pendingRoute() && view === 'claim' && read === claimRead) {
          notice(error.message,true);
          if (!current) host.innerHTML = button('Retry opening claim',`data-au-claim="${h(id)}"`);
          if (error.transientAdvance || !error.status || error.status >= 500) schedule();
        }
      }
    }
    function claimFragment(id, preferences = {}) {
      const params = new URLSearchParams();
      if (preferences.mode === 'replay') { params.set('mode','replay'); params.set('through',String(preferences.through || 0)); }
      if (preferences.detail && preferences.detail !== 'step') params.set('detail',preferences.detail);
      return `#autonomous/claim/${key(id)}${params.size ? '?' + params : ''}`;
    }
    async function openClaim(id, writeHistory = true, preferences = {}) {
      if (!preferences.demo) stopPresentation();
      leaveView(); route(claimFragment(id,preferences),writeHistory);
      epoch++; const token = epoch; if (preferences.demo && demoSession) demoSession.epoch = token; cancelPoll(); motion?.cancel(); setView('claim'); current = null; openingId = id; openingPreferences = preferences; selected = null; cursor = null; history = []; disconnected = false; connectionFailed = false; pendingArrival = arrivals.get(id) || null; pendingControl = controls.get(id) || null; pendingStart = starts.get(id) || null; presentationMode = preferences.mode || 'saved'; replayRecord = null; nav(preferences.demo ? 'demonstration' : 'work'); notice(presentationMode === 'replay' ? 'Verifying recorded history…' : 'Opening saved claim…');
      host.innerHTML = '<p class="au-empty">Loading the saved claim.</p>';
      if (presentationMode !== 'replay') return loadOpenedClaim(id,token,preferences);
      try {
        const through = preferences.through ?? 0;
        const incoming = readReplay(await request(`/claims/${key(id)}/replay?through_seq=${through}`),id,through);
        if (disposed || token !== epoch || pendingRoute() || view !== 'claim') return;
        current = incoming.state; projection = incoming.projection; cursor = incoming.accepted.cursor; history = incoming.accepted.events; replayRecord = incoming.replay;
        const previous = claimViews.get(id); selected = preferredNode(current,previous?.selected); evidenceContext = previous?.evidenceContext || {}; detail = preferences.detail || previous?.detail || (current.revision === 0 ? 'sources' : 'step');
        renderClaim(); notice(''); focusTitle();
        return current;
      } catch (error) { if (!disposed && token === epoch) { notice(`Verified replay unavailable: ${error.message}`,true); host.innerHTML = button('Return to demonstration','data-au-nav="demonstration"'); stopPresentation(); } }
    }
    function railClaims() {
      const queue = container.querySelector('[data-au-recent-claims]');
      if (!queue) return;
      queue.innerHTML = claims.slice(0,6).map(claim => `<button type="button" class="au-recent-claim" data-au-claim="${h(claim.claim_id)}"${current?.claim_id === claim.claim_id && view === 'claim' ? ' aria-current="page"' : ''}><strong>${h(claim.title || 'Untitled claim')}</strong><span data-tone="${tone(claim.status)}">${h(claimStatusLabel(claim.status))}</span></button>`).join('') || '<p class="au-empty">No saved claims yet.</p>';
    }
    function rememberClaim(state, origin) {
      const index = claims.findIndex(row => row.claim_id === state.claim_id);
      const summary = {...(index >= 0 ? claims[index] : {}),...(origin ? {origin} : {}),claim_id:state.claim_id,title:state.title,status:state.status,phase:state.phase,phase_summary:state.phase_summary,revision:state.revision,state_sha256:state.state_sha256,updated_at:state.updated_at,outcome:state.outcome,mode:state.revision === 0 ? 'unprocessed' : 'saved'};
      if (index >= 0) {
        if (!Number.isSafeInteger(claims[index].revision) || claims[index].revision <= summary.revision) claims[index] = summary;
      } else claims.unshift(summary);
      railClaims();
    }
    function refreshCollection() {
      if (view !== 'work') return;
      const output = host.querySelector('[data-au-claims]'); if (output) output.innerHTML = claimsMarkup(claims,collection);
      const scoped = collectionRows(claims,collection.scope);
      const count = host.querySelector('[data-au-collection-count]'); if (count) count.textContent = `${matchingClaims(scoped,collection).length} of ${scoped.length}`;
      const summary = host.querySelector('.au-collection-summary');
      if (summary) summary.innerHTML = collectionCounts(scoped,collection.scope).map(([label,count]) => `<span><strong>${count}</strong> ${h(label)}</span>`).join('');
      for (const control of host.querySelectorAll('[data-au-collection-scope]')) {
        control.setAttribute('aria-pressed',String(collection.scope === control.dataset.auCollectionScope));
        const number = control.querySelector('span'); if (number) number.textContent = String(collectionRows(claims,control.dataset.auCollectionScope).length);
      }
      for (const control of host.querySelectorAll('[data-au-domain]')) {
        const id = control.dataset.auDomain, count = id === 'all' ? scoped.length : scoped.filter(claim => domainOf(claim) === id).length;
        control.setAttribute('aria-pressed',String(collection.domain === id)); control.disabled = id !== 'all' && !count;
        const number = control.querySelector('strong'); if (number) number.textContent = String(count);
      }
      const filter = host.querySelector('[data-au-claim-filter]');
      if (filter) filter.innerHTML = collectionFilters(scoped).map(value => `<option value="${h(value)}"${collection.filter === value ? ' selected' : ''}>${h(value === 'all' ? 'All statuses' : value === 'working' ? 'In progress' : statusLabel(value))}</option>`).join('');
    }
    async function loadClaims(token = epoch) {
      const read = ++claimsRead;
      const data = await request('/claims');
      if (disposed || token !== epoch || read !== claimsRead) return;
      const rows = [...list(data.claims)];
      if (Number.isSafeInteger(data.total) && data.total > rows.length) {
        let offset = rows.length;
        while (offset < data.total) {
          const page = await request(`/claims?limit=200&offset=${offset}`);
          if (disposed || token !== epoch || read !== claimsRead) return;
          if (page.total !== data.total || page.offset !== offset || !list(page.claims).length || (data.collection_sha256 && page.collection_sha256 !== data.collection_sha256)) throw new Error('The case collection changed while loading. Refresh to read one collection identity.');
          rows.push(...page.claims); offset += page.claims.length;
        }
      }
      if (new Set(rows.map(row => row.claim_id)).size !== rows.length) throw new Error('The case collection contains duplicate canonical identities.');
      const remembered = new Map(claims.map(row => [row.claim_id,row]));
      claims = rows.map(row => {
        const known = remembered.get(row.claim_id);
        if (!known || !Number.isSafeInteger(known.revision)) return row;
        const verified = current?.claim_id === row.claim_id && current.revision === row.revision && known.revision === current.revision && known.state_sha256 === current.state_sha256;
        return !Number.isSafeInteger(row.revision) || known.revision > row.revision || verified ? {...row,...known} : row;
      });
      if (current && !claims.some(row => row.claim_id === current.claim_id) && remembered.has(current.claim_id)) claims.unshift(remembered.get(current.claim_id));
      claimsLoaded = true; railClaims(); refreshCollection(); refreshDemonstration();
    }
    async function serviceStatus(token) {
      const data = await request('/status');
      if (disposed || token !== epoch) return;
      status = data;
      if (view === 'claim') {
        const start = host.querySelector('[data-au-start]'); if (start) start.disabled = busy || !liveAvailability(status).ready && !pendingStart;
        const availability = host.querySelector('[data-au-start-availability]'); if (availability) availability.textContent = liveAvailability(status).reason;
      }
      if (view === 'demonstration') refreshDemonstration();
      resumeLivePresentation();
      const service = host.querySelector('[data-au-service]');
      const allowanceMessage = status.limits?.autonomous_can_start === false ? new Map([
        ['call_limit_reached','The recorded call allowance does not permit more autonomous work.'],
        ['cost_limit_reached','The recorded cost allowance does not permit more autonomous work.'],
        ['provider_outcome_pending','A provider outcome is pending, so new autonomous work cannot start yet.'],
        ['provider_cost_bound_exceeded','A recorded provider cost exceeded its bound, so new autonomous work cannot start.']
      ]).get(status.limits.autonomous_reason) || 'Autonomous inference is unavailable for new work.' : '';
      if (service) service.textContent = !status.enabled ? 'Autonomous work is disabled.' : !status.provider_ready ? 'Inference is unavailable. New packets are saved with a named deferral.' : allowanceMessage ? `${allowanceMessage} You can still save a new claim; autonomous work will have a named deferral.` : 'Local evidence acquisition and document preparation are available. External dispatch is not configured.';
      if (view === 'intake' && !busy && !pendingIntake) idleIntakeSubmit(host.querySelector('[data-au-intake]'));
      if (view === 'intake' && !status.enabled && !pendingIntake) { const submit = host.querySelector('button[type="submit"]'); if (submit) submit.disabled = true; }
    }
    function collectionFragment() {
      const params = new URLSearchParams();
      if (collection.scope === 'added') params.set('scope','added');
      if (collection.search) params.set('q',collection.search);
      if (collection.filter !== 'all') params.set('status',collection.filter);
      if (collection.domain !== 'all') params.set('domain',collection.domain);
      return '#autonomous/cases' + (params.size ? '?' + params : '');
    }
    function rememberCollectionRoute() {
      if (!root.location || !root.history?.replaceState) return;
      const fragment = collectionFragment(); root.history.replaceState(null,'',root.location.pathname + root.location.search + fragment); routedFragment = fragment;
    }
    function refreshDemonstration() {
      if (view !== 'demonstration') return;
      const selection = host.querySelector('.au-demo-selection');
      if (selection) { const wrapper = doc.createElement?.('div'); if (wrapper) { wrapper.innerHTML = demonstrationMarkup(claims,status,demoMode); selection.innerHTML = wrapper.querySelector('.au-demo-selection').innerHTML; } }
      for (const choice of host.querySelectorAll('[data-au-demo-mode]')) choice.setAttribute('aria-pressed',String(choice.dataset.auDemoMode === demoMode));
      const play = host.querySelector('[data-au-demo-play]'); if (play) { play.textContent = demoMode === 'replay' ? 'Play recorded work' : 'Start live presentation'; play.disabled = demoMode === 'live' && !liveAvailability(status).ready; }
      const availability = host.querySelector('[data-au-demo-availability]'); if (availability) availability.textContent = demoMode === 'live' ? liveAvailability(status).reason : 'Recorded executions only. A case without accepted history remains not started.';
    }
    async function showDemonstration(writeHistory = true) {
      stopPresentation(); leaveView(); route(`#autonomous/demonstration?mode=${demoMode}`,writeHistory);
      epoch++; const token = epoch; cancelPoll(); current = null; setView('demonstration'); nav('demonstration'); notice('');
      host.innerHTML = demonstrationMarkup(claims,status,demoMode); refreshDemonstration(); focusTitle();
      const results = await Promise.allSettled([serviceStatus(token),loadClaims(token)]);
      if (!disposed && token === epoch) { refreshDemonstration(); for (const result of results) if (result.status === 'rejected') notice(result.reason.message,true); }
    }
    function stopPresentation() {
      if (demoTimer) root.clearTimeout(demoTimer); demoTimer = null; demoSession = null;
    }
    async function beginPresentation() {
      if (busy || view !== 'demonstration') return;
      if (demoMode === 'live' && !liveAvailability(status).ready) { notice(liveAvailability(status).reason,true); return; }
      demoSession = {mode:demoMode,index:0};
      await openPresentationCase(demoSession);
    }
    async function openPresentationCase(session) {
      if (demoSession !== session || disposed || pendingRoute()) return;
      if (session.index >= DEMO_CASES.length) { stopPresentation(); notice('The selected recorded histories have been inspected.'); renderClaim(); return; }
      const id = DEMO_CASES[session.index].claim_id; session.claimId = id; session.startAttempted = false;
      await openClaim(id,true,{mode:session.mode,through:0,demo:true});
      if (demoSession !== session || !current || disposed || pendingRoute()) return;
      if (session.mode === 'replay') {
        if (!replayRecord.current_revision) { stopPresentation(); renderClaim(); notice('This original case has no accepted execution to replay. Its original sources remain available.'); return; }
        demoTimer = root.setTimeout(() => replayTick(session,epoch),1400);
      } else { resumeLivePresentation(); advanceLivePresentation(); }
    }
    async function replayTick(session, token) {
      demoTimer = null;
      if (demoSession !== session || disposed || token !== epoch || pendingRoute() || presentationMode !== 'replay' || !current || !replayRecord) return;
      if (doc.hidden || dialog.open) { demoTimer = root.setTimeout(() => replayTick(session,token),1400); return; }
      if (replayRecord.through_seq >= replayRecord.current_revision) { session.index++; await openPresentationCase(session); return; }
      const id = current.claim_id, through = replayRecord.through_seq + 1;
      try {
        const incoming = readReplay(await request(`/claims/${key(id)}/replay?through_seq=${through}`),id,through);
        if (demoSession !== session || disposed || token !== epoch || pendingRoute() || view !== 'claim') return;
        const accepted = acceptEvents(cursor,{...incoming.replay,current_revision:incoming.state.revision,current_state_sha256:incoming.state.state_sha256,events:incoming.accepted.events.filter(event => event.seq > cursor)},incoming.state);
        const changes = transitionPlan(current,incoming.state,accepted,history);
        current = incoming.state; projection = incoming.projection; cursor = incoming.accepted.cursor; history = incoming.accepted.events; replayRecord = incoming.replay; selected = preferredNode(current,selected);
        const fragment = claimFragment(id,{mode:'replay',through,detail});
        if (root.history?.replaceState) { root.history.replaceState(null,'',root.location.pathname + root.location.search + fragment); routedFragment = fragment; }
        renderClaim(changes);
        demoTimer = root.setTimeout(() => replayTick(session,token),through >= replayRecord.current_revision ? 3200 : 1400);
      } catch (error) { if (!disposed && token === epoch) { stopPresentation(); renderClaim(); notice(`Verified replay stopped: ${error.message}`,true); } }
    }
    function resumeLivePresentation() {
      const session = demoSession;
      if (!session || session.mode !== 'live' || session.epoch !== epoch || disposed || pendingRoute() || doc.hidden || dialog.open || view !== 'claim' || presentationMode !== 'live' || !openingPreferences.demo || !current || current.claim_id !== session.claimId || DEMO_CASES[session.index]?.claim_id !== session.claimId || current.revision !== 0 || busy || pendingStart || session.startAttempted || !liveAvailability(status).ready) return;
      // Play authorizes one original Start after a verified opening. An uncertain
      // admission retains its exact request for explicit operator recovery.
      session.startAttempted = true;
      startOriginal(host.querySelector('[data-au-start]'));
    }
    function advanceLivePresentation() {
      const session = demoSession;
      if (!session || session.mode !== 'live' || !current || busy || pendingStart || active(current.status) || current.revision === 0 || demoTimer) return;
      if (['model_unavailable','call_limit_reached','cost_limit_reached'].includes(current.deferral?.code)) { stopPresentation(); renderClaim(); notice(current.deferral.reason || 'Live execution is unavailable.',true); return; }
      const token = epoch, id = current.claim_id;
      demoTimer = root.setTimeout(() => livePresentationTick(session,token,id),3200);
    }
    function livePresentationTick(session, token, id) {
      demoTimer = null;
      if (demoSession !== session || disposed || token !== epoch || pendingRoute() || session.epoch !== token || view !== 'claim' || presentationMode !== 'live' || current?.claim_id !== id || session.claimId !== id || DEMO_CASES[session.index]?.claim_id !== id || busy || pendingStart || active(current.status)) return;
      if (doc.hidden || dialog.open) { demoTimer = root.setTimeout(() => livePresentationTick(session,token,id),1600); return; }
      session.index++; openPresentationCase(session);
    }
    async function startOriginal(target) {
      if (busy || pendingRoute() || !current || current.revision !== 0 && !pendingStart || presentationMode === 'replay' || !liveAvailability(status).ready && !pendingStart) return;
      const token = epoch, id = current.claim_id;
      pendingStart ||= {claimId:id,body:{expected_revision:current.revision,expected_state_sha256:current.state_sha256,idempotency_key:`browser.${root.crypto.randomUUID()}`}};
      starts.set(id,pendingStart); busy = true; if (target) { target.disabled = true; target.textContent = 'Starting…'; }
      try {
        readState(await request(`/claims/${key(id)}/start`,{method:'POST',body:JSON.stringify(pendingStart.body)}),id);
        starts.delete(id); pendingStart = null;
        if (!disposed && token === epoch && !pendingRoute()) { presentationMode = 'live'; await loadOpenedClaim(id,token); }
      } catch (error) {
        if (error.status && error.status < 500) { starts.delete(id); pendingStart = null; }
        if (!disposed && token === epoch) notice(`${error.message}${pendingStart ? ' Response unconfirmed; retry uses the same request.' : ''}`,true);
      } finally { busy = false; routeChanged(); if (target?.isConnected) { target.disabled = !pendingStart && !liveAvailability(status).ready; target.textContent = pendingStart ? 'Retry start' : 'Start investigation'; } }
    }
    async function showWork(writeHistory = true) {
      stopPresentation(); leaveView(); route(collectionFragment(),writeHistory);
      epoch++; const token = epoch; cancelPoll(); setView('work'); nav('work'); current = null; notice('');
      host.innerHTML = collectionMarkup(claims,collection);
      if (collection.scrollTop !== undefined) { host.scrollTop = collection.scrollTop; const main = container.querySelector('.au-main'); if (main) { main.scrollTop = collection.mainTop; main.scrollLeft = collection.mainLeft; } root.scrollTo?.({left:collection.scrollX,top:collection.scrollY,behavior:'instant'}); }
      if (!claimsLoaded) { const output = host.querySelector('[data-au-claims]'); if (output) output.innerHTML = '<p class="au-empty">Loading original cases and saved work.</p>'; }
      const results = await Promise.allSettled([serviceStatus(token),loadClaims(token)]);
      if (!disposed && token === epoch) for (const result of results) if (result.status === 'rejected') notice(result.reason.message,true);
    }
    async function showIntake(writeHistory = true) {
      if (view === 'intake' && host.querySelector('[data-au-intake]')) { route('#autonomous/new',writeHistory); return; }
      stopPresentation(); leaveView(); route('#autonomous/new',writeHistory);
      epoch++; const token = epoch; cancelPoll(); setView('intake'); nav('intake'); current = null; notice('');
      host.innerHTML = `<div class="au-intake-layout au-identity-intake"><section><p class="au-eyebrow">New claim</p><h1 class="au-page-heading" tabindex="-1">Start with the source.</h1><p class="au-lead">Add the original message and files. Evidence establishes the facts, process and document requirements.</p><p class="au-meta" data-au-service>Checking service availability…</p><form class="au-intake" data-au-intake><div class="au-examples" data-au-examples hidden><label for="auExample">Try a fictional claim</label><select id="auExample" data-au-example><option value="">Choose a fictional example</option></select></div><label for="auTitle">Claim title</label><input id="auTitle" name="title" required maxlength="300" autocomplete="off" placeholder="A short name for this claim"><label for="auMessage">Incoming message</label><textarea id="auMessage" name="message" required maxlength="100000" rows="7" placeholder="Paste the original message"></textarea><label class="au-upload" for="auFiles">Supporting files <span>Optional · original files stay available for inspection</span></label><input id="auFiles" name="files" type="file" multiple><div class="au-intake-controls"><button class="au-primary" type="submit">Start autonomous work <span aria-hidden="true">↗</span></button><button type="button" class="au-secondary" data-au-nav="work">Cancel</button></div><p class="au-form-status" role="status"></p></form></section></div>`;
      if (intakeForm) host.querySelector('[data-au-intake]')?.replaceWith?.(intakeForm);
      else intakeForm = host.querySelector('[data-au-intake]');
      if (pendingIntake && intakeForm) {
        intakeForm.elements.title.value = pendingIntake.body.title; intakeForm.elements.message.value = pendingIntake.body.message;
        lockForm(intakeForm,true,true); intakeForm.querySelector('.au-form-status').textContent = 'The prior response was not confirmed. Retry sends the same saved intake request.';
      } else if (!busy) idleIntakeSubmit(intakeForm);
      loadExamples(token); focusTitle();
      try { await serviceStatus(token); } catch (error) { if (!disposed && token === epoch) notice(error.message,true); }
    }
    async function loadExamples(token) {
      const meta = doc.querySelector?.('meta[name="casepath-autonomous-demo-packets"]')?.content;
      if (!meta || !root.location) return;
      const controller = new AbortController(); controllers.add(controller);
      const timeout = root.setTimeout(() => controller.abort(), 15000);
      try {
        if (!examples) {
          const url = demoAssetURL(meta, root.location);
          const response = await fetcher(url.href, {signal:controller.signal,cache:'no-store',credentials:'same-origin',redirect:'error'});
          if (!response.ok) throw new Error('The fictional packets could not be loaded.');
          examples = await checkedExamples(await response.arrayBuffer(), url.searchParams.get('sha256'));
        }
        if (disposed || token !== epoch || view !== 'intake') return;
        const wrapper = host.querySelector('[data-au-examples]'), select = host.querySelector('[data-au-example]');
        if (!wrapper || !select) return;
        const chosen = select.value;
        select.innerHTML = '<option value="">Choose a fictional example</option>' + examples.map((packet,index)=>`<option value="${index}">${h(packet.title)}</option>`).join('');
        if (/^\d+$/.test(chosen) && examples[Number(chosen)]) select.value = chosen;
        select.disabled = busy || Boolean(pendingIntake); wrapper.hidden = false;
      } catch (error) { if (!disposed && token === epoch) notice(`Fictional examples unavailable: ${error.message}`,true); }
      finally { root.clearTimeout(timeout); controllers.delete(controller); }
    }
    function change(event) {
      const select = event.target;
      if (select.matches?.('[data-au-claim-filter]') && view === 'work') { collection.filter = select.value; refreshCollection(); rememberCollectionRoute(); return; }
      if (!select.matches?.('[data-au-example]') || view !== 'intake' || busy || pendingIntake || select.disabled || !/^\d+$/.test(select.value)) return;
      const packet = examples?.[Number(select.value)], form = host.querySelector('[data-au-intake]');
      if (!packet || !form) return;
      try { prefillExample(form,packet); form.querySelector('.au-form-status').textContent = 'Fictional example loaded. Start autonomous work when ready.'; }
      catch (error) { form.querySelector('.au-form-status').textContent = error.message; }
    }
    async function showKnowledge(writeHistory = true, pin = null) {
      stopPresentation(); leaveView();
      const fragment = pin ? `#autonomous/knowledge?knowledge=${key(pin.knowledge_id)}&version=${key(pin.version)}&sha256=${key(pin.knowledge_sha256 || '')}` : '#autonomous/knowledge';
      route(fragment,writeHistory);
      epoch++; const token = epoch; cancelPoll(); setView('knowledge'); nav('knowledge'); current = null; notice('Loading recorded knowledge…'); host.innerHTML = '';
      try {
        const results = await Promise.allSettled([request('/knowledge'),claimsLoaded ? Promise.resolve() : loadClaims(token)]);
        if (disposed || token !== epoch) return;
        if (results[0].status === 'rejected') throw results[0].reason;
        const data = results[0].value;
        host.innerHTML = knowledgeMarkup(data,claims); drawEdges(); notice(''); focusTitle();
        if (pin) {
          const version = list(data.versions).find(item => String(item.knowledge_id || item.version_id) === String(pin.knowledge_id) && String(item.version || item.version_id) === String(pin.version) && (!pin.knowledge_sha256 || item.knowledge_sha256 === pin.knowledge_sha256));
          if (!version) { notice('The exact reused knowledge version is not available in this record.',true); return; }
          const row = [...host.querySelectorAll('[data-au-knowledge-identity]')].find(element => element.dataset.auKnowledgeIdentity === `${pin.knowledge_id}:${pin.version}`);
          if (row) { let parent = row.parentElement; while (parent && parent !== host) { if (parent.tagName === 'DETAILS') parent.open = true; parent = parent.parentElement; } row.setAttribute('data-pinned','true'); row.setAttribute('tabindex','-1'); row.focus({preventScroll:true}); row.scrollIntoView?.({block:'nearest',behavior:'instant'}); drawEdges(); }
        }
      } catch (error) { if (!disposed && token === epoch) notice(error.message,true); }
    }
    function idleIntakeSubmit(form) {
      const submit = form?.querySelector('button[type="submit"]');
      if (!submit) return;
      submit.textContent = status?.enabled === true && (status.provider_ready === false || status.limits?.autonomous_can_start === false) ? 'Save claim' : 'Start autonomous work ↗';
      if (status) submit.disabled = !status.enabled;
    }
    function lockForm(form, lock, retry = false) {
      for (const control of form.querySelectorAll('input,textarea,select,button[type="submit"]')) control.disabled = lock;
      const submit = form.querySelector('button[type="submit"]');
      if (retry) { submit.disabled = false; submit.textContent = 'Retry same request'; }
      else if (!lock && form.matches('[data-au-intake]')) idleIntakeSubmit(form);
      else submit.textContent = lock ? 'Saving…' : 'Add files';
    }
    async function filesFrom(input) {
      const files = [...input.files], output = [];
      if (files.length > 20) throw new Error('Add at most 20 supporting files at once.');
      for (const file of files) {
        if (status?.limits?.max_file_bytes && file.size > status.limits.max_file_bytes) throw new Error(`${file.name} exceeds the file size limit.`);
        const bytes = new Uint8Array(await file.arrayBuffer()); let binary = '';
        for (let offset=0; offset<bytes.length; offset+=8192) binary += String.fromCharCode(...bytes.subarray(offset,offset+8192));
        output.push({file_name:file.name, media_type:mediaType(file), content_base64:root.btoa(binary)});
      }
      return output;
    }
    async function submit(event) {
      const form = event.target;
      if (!form.matches('[data-au-intake],[data-au-arrival]')) return;
      event.preventDefault(); if (busy) return;
      const intake = form.matches('[data-au-intake]'), token = epoch, saved = current;
      if (!intake && (!saved || presentationMode === 'replay')) return;
      let submitted = false;
      busy = true; lockForm(form,true); const message = form.querySelector('.au-form-status'); message.textContent = '';
      try {
        let operation = intake ? pendingIntake : pendingArrival;
        if (!operation) {
          const files = await filesFrom(form.elements.files), idempotency_key = `browser.${root.crypto.randomUUID()}`;
          operation = {body:intake ? {title:form.elements.title.value.trim(), message:form.elements.message.value, files, idempotency_key} : {files,idempotency_key,expected_revision:saved.revision,expected_state_sha256:saved.state_sha256}, claimId:saved?.claim_id};
          if (intake) pendingIntake = operation; else pendingArrival = operation;
        }
        submitted = true;
        const response = await request(intake ? '/claims' : `/claims/${key(operation.claimId)}/sources`, {method:'POST',body:JSON.stringify(operation.body)});
        const accepted = readState(response, intake ? undefined : operation.claimId);
        if (intake) { rememberClaim(accepted.state,'native_intake'); pendingIntake = null; form.reset?.(); lockForm(form,false); } else { pendingArrival = null; arrivals.delete(operation.claimId); form.reset?.(); lockForm(form,false); }
        if (!disposed && token === epoch && !pendingRoute()) await openClaim(accepted.state.claim_id);
      } catch (error) {
        if (!disposed && token === epoch) {
          const uncertain = submitted && (!error.status || error.status >= 500);
          if (!uncertain) { if (intake) pendingIntake = null; else pendingArrival = null; }
          lockForm(form, uncertain, uncertain); message.textContent = uncertain ? `${error.message} The response is unconfirmed. Retry reuses the same request key.` : error.message;
        }
      } finally { busy = false; routeChanged(); }
    }
    async function controlWork(target, action) {
      if (busy || !current || presentationMode === 'replay' || (action === 'pause' ? current.status !== 'running' : current.status !== 'deferred' || current.deferral?.code !== 'paused')) return;
      if (pendingControl?.action !== action) pendingControl = null;
      const token = epoch, saved = current;
      pendingControl ||= {action,claimId:saved.claim_id,body:{expected_revision:saved.revision,expected_state_sha256:saved.state_sha256,idempotency_key:`browser.${root.crypto.randomUUID()}`}};
      busy = true; target.disabled = true;
      try {
        const accepted = readState(await request(`/claims/${key(pendingControl.claimId)}/${action}`,{method:'POST',body:JSON.stringify(pendingControl.body)}),pendingControl.claimId);
        pendingControl = null;
        if (!disposed && token === epoch) await poll();
      } catch (error) {
        if (error.status && error.status < 500) pendingControl = null;
        if (!disposed && token === epoch) notice(`${error.message}${pendingControl ? ` ${words(action)} response unconfirmed; retry uses the same request.` : ' Refreshing the saved claim.'}`,true);
        if (!pendingControl && !disposed && token === epoch) await poll();
      } finally { busy = false; routeChanged(); if (target.isConnected) { target.disabled = false; target.textContent = pendingControl ? `Retry ${action}` : `${words(action)} work`; } }
    }
    async function openSource(id, citation, trigger) {
      if (!current) return;
      const saved = current, token = epoch, sourceToken = ++sourceEpoch, descriptor = list(saved.source_descriptors).find(source => source.artifact_id === id);
      if (!descriptor) { notice('This source is not part of the saved claim.',true); return; }
      dialogReturn = {element:trigger,token:focusToken(trigger)}; container.querySelector('#auSourceTitle').textContent = descriptor.file_name || 'Original source';
      const body = container.querySelector('[data-au-source-content]'), url = `${base}/sources/${key(saved.claim_id)}/${key(id)}`;
      const native = descriptor.media_type?.split(';')[0];
      let nativeMarkup = '', nativeViewable = false; clearNativeSource();
      body.innerHTML = `<div class="au-source-meta"><span>${h(descriptor.media_type || 'Original file')}</span><a href="${h(url)}" download="${h(descriptor.file_name || 'source')}">Download original</a></div>${nativeMarkup}<p class="au-empty">Checking source identity…</p>`;
      motion?.cancel(); selectionMotion?.cancel();
      if (!dialog.open) dialog.showModal();
      try {
        let acquired = list(saved.acquired_sources).some(source => source.artifact_id === id), response;
        try { response = await request(`${url.slice(base.length)}/${acquired ? 'text' : 'preview'}`); }
        catch (error) {
          if (acquired || saved.revision === 0 || ![404,405,501].includes(error.status)) throw error;
          // Older servers expose only admitted text. Its independent identity
          // checks remain mandatory; unavailable extraction never admits it.
          response = await request(`${url.slice(base.length)}/text`); acquired = true;
        }
        const checked = acquired ? await checkedSource(saved,descriptor,response,citation) : {source:await checkedPreview(saved,descriptor,response),span:null};
        if (!acquired && citation) throw new Error('The cited source has no admitted acquisition record.');
        if (disposed || token !== epoch || sourceToken !== sourceEpoch || !dialog.open) return;
        if (native === 'application/pdf' || native?.startsWith('image/')) {
          try {
            const blob = await nativeSource(url.slice(base.length),descriptor,token,sourceToken);
            if (!blob) return;
            nativeViewable = true;
            nativeMarkup = native === 'application/pdf' ? `<iframe class="au-native-document" src="${h(blob)}" title="${h(descriptor.file_name || 'Original PDF')}"></iframe>` : `<img class="au-native-image" src="${h(blob)}" alt="Original file: ${h(descriptor.file_name)}">`;
          } catch (error) { nativeMarkup = `<p class="au-meta">${h(error.message)}</p>`; }
        }
        if (disposed || token !== epoch || sourceToken !== sourceEpoch || !dialog.open) return;
        const source = checked.source, unsupported = source.extraction === 'unsupported_metadata';
        const extraction = unsupported ? 'Received · interpretation unsupported' : source.complete ? 'Extracted text' : 'Extraction incomplete';
        const identity = `<details class="au-source-identity"><summary>Source identity and extraction</summary><p class="au-meta">${acquired ? 'Source text verified' : 'Read-only preview verified'}${checked.span ? ' · exact cited span verified' : ''} · ${h(extraction)}</p>${!acquired ? '<p class="au-meta">Preview does not admit evidence or establish understanding or sufficiency.</p>' : ''}<dl class="au-chain"><div><dt>Original filename</dt><dd>${h(descriptor.file_name)}</dd></div><div><dt>Media type</dt><dd>${h(descriptor.media_type)}</dd></div><div><dt>Original bytes · SHA-256</dt><dd class="au-hash">${h(descriptor.sha256)}</dd></div><div><dt>Extracted text · SHA-256</dt><dd class="au-hash">${h(source.text_sha256)}</dd></div>${!acquired ? `<div><dt>Preview · SHA-256</dt><dd class="au-hash">${h(source.preview_sha256)}</dd></div>` : ''}</dl><pre class="au-record-body">${h(JSON.stringify({descriptor,preview_only:source.preview_only,evidence_admitted:source.evidence_admitted,receipt_sha256:source.receipt_sha256,preview_sha256:source.preview_sha256,extraction:source.extraction,complete:source.complete,coverage:source.coverage,reason:source.reason,limitation:source.limitation},null,2))}</pre>${!source.text ? '<p class="au-meta">No readable text was extracted.</p>' : ''}</details>`;
        const unsupportedImage = unsupported && native?.startsWith('image/');
        body.innerHTML = unsupportedImage ? `<div class="au-source-meta"><a href="${h(url)}" download="${h(descriptor.file_name || 'source')}">Download original</a></div><p class="au-source-capability">${nativeViewable ? 'Original image viewable.' : 'Original image preview unavailable.'} The agent cannot interpret this image.</p>${nativeMarkup}${identity}` : `<div class="au-source-meta"><span>${acquired ? 'Source text verified' : 'Read-only preview verified'}${checked.span ? ' · exact cited span verified' : ''}</span><span>${h(extraction)}</span><a href="${h(url)}" download="${h(descriptor.file_name || 'source')}">Download original</a></div>${nativeMarkup}${!acquired ? '<p class="au-meta">Preview does not admit evidence or establish understanding or sufficiency.</p>' : ''}${!source.complete ? `<p class="au-notice">${h(source.reason || source.limitation || words(source.coverage?.limitation) || 'This source does not have a complete text extraction.')}</p>` : ''}${source.text ? `<pre class="au-source-body">${checked.span ? `${h(checked.span.before)}<mark tabindex="-1">${h(checked.span.quote)}</mark>${h(checked.span.after)}` : h(source.text)}</pre>` : '<p class="au-meta">No readable text was extracted.</p>'}${identity}`;
        body.querySelector('mark')?.scrollIntoView({block:'center'});
      } catch (error) { if (!disposed && token === epoch && sourceToken === sourceEpoch && dialog.open) body.innerHTML = `<div class="au-source-meta"><a href="${h(url)}" download="${h(descriptor.file_name || 'source')}">Download original</a></div>${nativeMarkup}<p class="au-error" role="alert">${h(error.message)}</p>`; }
    }
    function click(event) {
      const target = event.target.closest('button,[data-au-nav]'); if (!target || !container.contains(target)) return;
      if (target.hasAttribute('data-au-nav')) { if (busy) return; target.dataset.auNav === 'knowledge' ? showKnowledge() : target.dataset.auNav === 'intake' ? showIntake() : target.dataset.auNav === 'demonstration' ? showDemonstration() : showWork(); }
      else if (target.hasAttribute('data-au-claim')) { if (!busy) openClaim(target.dataset.auClaim); }
      else if (target.hasAttribute('data-au-demo-mode')) { demoMode = target.dataset.auDemoMode === 'live' ? 'live' : 'replay'; refreshDemonstration(); route(`#autonomous/demonstration?mode=${demoMode}`); }
      else if (target.hasAttribute('data-au-demo-play')) beginPresentation();
      else if (target.hasAttribute('data-au-demo-stop')) { stopPresentation(); renderClaim(); }
      else if (target.hasAttribute('data-au-start')) startOriginal(target);
      else if (target.hasAttribute('data-au-collection-scope')) { if (busy) return; collection.scope = target.dataset.auCollectionScope === 'added' ? 'added' : 'originals'; collection.domain = 'all'; collection.search = ''; collection.filter = 'all'; showWork(); }
      else if (target.hasAttribute('data-au-domain')) { collection.domain = target.dataset.auDomain; refreshCollection(); rememberCollectionRoute(); }
      else if (target.hasAttribute('data-au-pause')) controlWork(target,'pause');
      else if (target.hasAttribute('data-au-resume')) controlWork(target,'resume');
      else if (target.hasAttribute('data-au-refresh-claims')) { const token = epoch; loadClaims(token).catch(error => { if (!disposed && token === epoch) notice(error.message,true); }); }
      else if (target.hasAttribute('data-au-knowledge')) { if (!busy) showKnowledge(true,{knowledge_id:target.dataset.auKnowledge,version:target.dataset.auVersion,knowledge_sha256:target.dataset.auKnowledgeSha}); }
      else if (target.hasAttribute('data-au-add-files')) setDetail('sources',true);
      else if (target.hasAttribute('data-au-detail')) setDetail(target.dataset.auDetail);
      else if (target.hasAttribute('data-au-back-process')) {
        const node = [...host.querySelectorAll('[data-au-node]')].find(element => element.dataset.auNode === selected);
        node?.focus({preventScroll:true}); revealGraphNode(node); drawEdges();
      }
      else if (target.hasAttribute('data-au-fact-select') || target.hasAttribute('data-au-document-select')) {
        if (view !== 'claim') return;
        const relations=evidenceRelationships(current,selected,evidenceContext);
        if (target.hasAttribute('data-au-fact-select')) {
          const id=target.dataset.auFactSelect;if (!relations.facts.some(fact => fact.fact_id === id)) return;
          evidenceContext={...evidenceContext,fact:id,trace:relations.fact?.fact_id === id ? !evidenceContext.trace : true};
        } else {
          const type=target.dataset.auDocumentSelect;if (!relations.documents.some(item => item.document_type === type)) return;
          evidenceContext={...evidenceContext,document:type};
        }
        renderClaim();
      }
      else if (target.hasAttribute('data-au-node-previous') || target.hasAttribute('data-au-node-next')) {
        if (view !== 'claim' || !current?.graph || target.disabled) return;
        const nodes = layoutGraph(current.graph).nodes, index = nodes.findIndex(node => node.node_id === selected), direction = target.hasAttribute('data-au-node-previous') ? -1 : 1, node = nodes[index+direction];
        if (!node) return;
        selected = node.node_id; evidenceContext = {}; setDetail('step'); renderClaim(null,true);
        const control = host.querySelector(direction < 0 ? '[data-au-node-previous]' : '[data-au-node-next]'), selectedNode = [...host.querySelectorAll('[data-au-node]')].find(element => element.dataset.auNode === selected);
        (control && !control.disabled ? control : selectedNode)?.focus({preventScroll:true});
        revealGraphNode(selectedNode,true); drawEdges();
      }
      else if (target.hasAttribute('data-au-node') || target.hasAttribute('data-au-select')) {
        const id=target.dataset.auNode || target.dataset.auSelect;
        if (!list(current?.graph?.nodes).some(node => node.node_id === id)) return;
        const changed=selected !== id; selected=id; setDetail('step'); if (changed) evidenceContext={}; renderClaim(null,changed);
        const node=[...host.querySelectorAll('[data-au-node]')].find(element => element.dataset.auNode === selected);
        node?.focus({preventScroll:true});
      } else if (target.hasAttribute('data-au-source')) {
        let citation; try { citation = target.dataset.auCitation ? JSON.parse(target.dataset.auCitation) : null; } catch (_) { notice('The source reference is invalid.',true); return; }
        openSource(target.dataset.auSource,citation,target);
      } else if (target.hasAttribute('data-au-close')) dialog.close();
    }
    function input(event) {
      if (view === 'work' && event.target.matches?.('[data-au-claim-search]')) { collection.search = event.target.value; refreshCollection(); rememberCollectionRoute(); }
    }
    function closed() { (dialogReturn?.element?.isConnected && focusEligible(dialogReturn.element,dialogReturn.token) ? dialogReturn.element : focusTarget(dialogReturn?.token) || host.querySelector('[data-au-claim-title]'))?.focus({preventScroll:true}); dialogReturn = null; sourceEpoch++; clearNativeSource(); resumeLivePresentation(); }
    function visibility() { motion?.cancel(); selectionMotion?.cancel(); if (!doc.hidden && view === 'claim' && presentationMode !== 'replay') { disconnected = true; cancelPoll(); resumeLivePresentation(); current ? poll() : openingId ? loadOpenedClaim(openingId,epoch) : schedule(); } }
    function keyboardInput(event) { if (event.key === 'Tab' || event.key?.startsWith('Arrow')) { keyboard=true;motion?.cancel();selectionMotion?.cancel(); } }
    function pointerInput() { keyboard=false; }
    function motionPreference() { if (reduced?.matches) { motion?.cancel();selectionMotion?.cancel(); } }
    doc.addEventListener('keydown',keyboardInput);container.addEventListener('pointerdown',pointerInput);reduced?.addEventListener?.('change',motionPreference);
    function geometryEvent(event) { if (event.type === 'toggle' || event.target?.hasAttribute?.('data-au-graph-pan')) drawEdges(); }
    container.addEventListener('scroll',geometryEvent,true);container.addEventListener('toggle',geometryEvent,true);
    doc.fonts?.ready?.then(() => { if (!disposed) drawEdges(); });
    container.addEventListener('click',click); container.addEventListener('submit',submit); container.addEventListener('change',change); container.addEventListener('input',input); dialog.addEventListener('close',closed); doc.addEventListener('visibilitychange',visibility);
    root.addEventListener?.('hashchange',routeChanged); root.addEventListener?.('popstate',routeChanged);
    function resized() {
      const area=host.querySelector('.au-graph-viewport')?.getBoundingClientRect?.();
      if (area && graphViewportWidth !== null && area.width !== graphViewportWidth) revealGraphNode([...host.querySelectorAll('[data-au-node]')].find(element => element.dataset.auNode === selected));
      drawEdges();
    }
    const resize = root.ResizeObserver ? new root.ResizeObserver(resized) : null; resize?.observe(host); root.addEventListener?.('resize',resized);
    const controller = {openClaim,showWork,showIntake,showKnowledge,showDemonstration,refresh:poll,destroy() { if (disposed) return; disposed = true; epoch++; cancelPoll(); stopPresentation(); clearNativeSource(); motion?.cancel(); selectionMotion?.cancel();root.removeEventListener?.('resize',resized);root.removeEventListener?.('hashchange',routeChanged);root.removeEventListener?.('popstate',routeChanged);doc.removeEventListener('keydown',keyboardInput);container.removeEventListener('pointerdown',pointerInput);reduced?.removeEventListener?.('change',motionPreference); for (const controller of controllers) controller.abort(); resize?.disconnect();container.removeEventListener('scroll',geometryEvent,true);container.removeEventListener('toggle',geometryEvent,true); container.removeEventListener('click',click); container.removeEventListener('submit',submit); container.removeEventListener('change',change); container.removeEventListener('input',input); dialog.removeEventListener('close',closed); doc.removeEventListener('visibilitychange',visibility); if (dialog.open) dialog.close(); mounts.delete(container); if (activeMount === controller) activeMount = null; container.innerHTML = ''; }};
    mounts.set(container,controller); activeMount = controller;
    routeChanged();
    return controller;
  }
  function destroy(container) { (container ? mounts.get(container) : activeMount)?.destroy(); }
  return {DEMO_CASES,DOMAINS,demoItineraryMarkup,canonicalJSON,checkedPreview,readSnapshot,readReplay,demonstrationMarkup,liveAvailability,preferredNode,evidenceRelationships,evidencePathMarkup,knowledgeUses,edgeState,mount,destroy,demoAssetURL,checkedExamples,prefillExample,progressModel,progressMarkup,transitionPlan,animateTransition,mediaType,readState,layoutGraph,acceptEvents,eventIdentity,changedTargets,conditionFlags,checkedSource,graphMarkup,obligationMarkup,inspectorMarkup,workMarkup,knowledgeMarkup,claimsMarkup,collectionMarkup,matchingClaims,actionRows};
});
