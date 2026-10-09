/* Autonomous work is rendered from persisted state and its matching event cursor. */
(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CasePathAutonomous = api;
})(typeof globalThis === 'object' ? globalThis : this, function (root) {
  'use strict';
  const BASE = '/api/claim-loops/v1/autonomous';
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
  const active = status => ['received', 'queued', 'running', 'working', 'investigating'].includes(status);
  const tone = status => ['completed', 'complete', 'resolved', 'established', 'satisfied', 'qualified'].includes(status) ? 'done' : ['deferred', 'blocked', 'failed', 'unresolved', 'unknown', 'quarantined'].includes(status) ? 'blocked' : active(status) || status === 'ready' ? 'active' : 'neutral';
  const statusLabel = status => ({received:'Received', queued:'Queued', running:'Working', working:'Working', completed:'Completed', resolved:'Resolved', deferred:'Deferred', failed:'Stopped', ready:'Ready', true:'Applies', false:'Does not apply', insufficient:'Insufficient evidence', prepared_not_sent:'Prepared · not sent', not_reached:'Not reached', inactive:'Does not apply', unresolved:'Evidence needed', blocked:'Waiting for prerequisites', established:'Established', satisfied:'Satisfied', needed_now:'Needed now', needed_later:'Needed later', held_behind_question:'Depends on unresolved evidence', held_not_reviewed:'Acquired · not established', not_needed:'Not required', optional:'Optional'})[status] || words(status) || 'Not recorded';

  function readState(response, claimId) {
    const state = response?.state && typeof response.state === 'object' ? response.state : response;
    if (!state || typeof state.claim_id !== 'string' || !Number.isSafeInteger(state.revision) || state.revision < 1 || !/^[a-f0-9]{64}$/i.test(state.state_sha256 || '')) throw new Error('The saved claim identity is incomplete.');
    if (claimId && state.claim_id !== claimId) throw new Error('The response belongs to another claim.');
    if (state.graph?.claim_id && state.graph.claim_id !== state.claim_id) throw new Error('The process belongs to another claim.');
    const projection = response.projection || {};
    // Older envelopes omitted projection identity; present bindings must match.
    for (const field of ['claim_id','revision','state_sha256']) if (Object.prototype.hasOwnProperty.call(projection, field) && projection[field] !== state[field]) throw new Error('The capability projection belongs to a different saved claim revision.');
    if (Object.prototype.hasOwnProperty.call(projection, 'parent_revision') && projection.parent_revision !== state.revision) throw new Error('The capability projection belongs to a different saved claim revision.');
    if (Object.prototype.hasOwnProperty.call(projection, 'parent_state_sha256') && projection.parent_state_sha256 !== state.state_sha256) throw new Error('The capability projection belongs to a different saved claim revision.');
    return {state, projection};
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
    const changes=changedTargets(before,after),layout=layoutGraph(after.graph),ranks=new Map(layout.rows.flatMap((row,rank)=>row.map(node=>[node.node_id,rank])));
    const minimum=changes.nodes.length ? Math.min(...changes.nodes.map(id=>ranks.get(id) || 0)) : 0;
    const nodes=changes.nodes.map(id=>({id,delay:180+Math.min(140,((ranks.get(id)||0)-minimum)*20),duration:220}));
    const edges=list(after.graph?.edges).filter(edge=>changes.nodes.includes(edge.target_node_id)).map(edge=>({id:edge.edge_id,delay:0,duration:160}));
    const facts=list(after.facts).filter(fact=>JSON.stringify(list(before.facts).find(row=>row.fact_id===fact.fact_id))!==JSON.stringify(fact)).map(fact=>({id:fact.fact_id,delay:360,duration:180}));
    const documents=changes.documents.map(id=>({id,delay:580,duration:180}));
    const previousStages=progressModel(before,history).stages;
    const stages=progressModel(after,history.concat(accepted.events)).stages.filter((stage,index)=>JSON.stringify(stage)!==JSON.stringify(previousStages[index])).map(stage=>({id:stage.id,delay:0,duration:280}));
    return {nodes,edges,facts,documents,stages,duration:760};
  }
  function animateTransition(host,plan,environment={}) {
    const animations=new Set(),overlays=new Set();
    const cancel=()=>{for(const animation of animations)animation.cancel();animations.clear();for(const overlay of overlays)overlay.remove();overlays.clear();};
    if (!plan || environment.reducedMotion || environment.hidden || environment.dialogOpen || environment.keyboard) return {cancel,count:0};
    const run=(element,frames,timing,cleanup=()=>{})=>{
      if (!element?.animate || element.closest?.('[hidden]') || element===environment.activeElement || element.contains?.(environment.activeElement)) { cleanup(); return; }
      const animation=element.animate(frames,{...timing,easing:'cubic-bezier(.2,.65,.3,1)',fill:'none'});animations.add(animation);
      animation.finished?.then(()=>{animations.delete(animation);cleanup();},()=>{animations.delete(animation);cleanup();});
    };
    for(const edge of host.querySelectorAll('[data-au-edge]')) {
      const timing=plan.edges.find(row=>row.id===edge.dataset.auEdge);if(!timing)continue;
      const length=edge.getTotalLength?.();if(!Number.isFinite(length)||length<=0)continue;
      const overlay=edge.cloneNode(false);overlay.setAttribute('class','au-live-edge');overlay.removeAttribute?.('data-au-edge');edge.parentNode.appendChild(overlay);overlays.add(overlay);overlay.removeAttribute?.('data-state');overlay.removeAttribute?.('data-selected');
      run(overlay,[{strokeDasharray:`${length} ${length}`,strokeDashoffset:String(length),opacity:1},{strokeDasharray:`${length} ${length}`,strokeDashoffset:'0',opacity:1}],timing,()=>{overlay.remove();overlays.delete(overlay);});
    }
    for(const [selector,field,rows]of [['[data-au-node]','auNode',plan.nodes],['[data-au-fact]','auFact',plan.facts],['[data-au-document]','auDocument',plan.documents],['[data-au-stage]','auStage',plan.stages]]) {
      for(const element of host.querySelectorAll(selector)) {
        const timing=rows.find(row=>row.id===element.dataset[field]);if(!timing)continue;
        run(element,[{backgroundColor:'#f4e6eb'},{backgroundColor:'rgba(244,230,235,0)'}],timing);
      }
    }
    return {cancel,count:animations.size};
  }

  const citationRows = item => list(item?.citations || item?.sources || item?.source_spans);
  const sourceLabel = (state, id) => name(list(state.source_descriptors).find(source => source.artifact_id === id)) || list(state.source_descriptors).find(source => source.artifact_id === id)?.file_name || 'Original source';
  function sourceButtons(state, item) {
    return citationRows(item).map(citation => `<button type="button" class="au-source-link" data-au-source="${h(citation.artifact_id)}" data-au-citation="${h(JSON.stringify(citation))}">${h(sourceLabel(state, citation.artifact_id))}${citation.quote ? `<q>${h(citation.quote)}</q>` : ''}</button>`).join('');
  }
  const compactLabels = {
    'Capture issuer, receipt and end date':'Notice details',
    'Preserve challenge or extension deadline':'Preserve deadline',
    'Check form and service':'Form & service',
    'Classify termination type':'Termination type',
    'Check arrears cure preconditions':'Arrears conditions',
    'Check separate family-home service':'Separate service',
    'Screen stated reason and good-faith concerns':'Grounds & good faith',
    'Assess extension evidence':'Extension evidence',
    'Collect type-specific evidence':'Required evidence',
    'Prepare challenge, extension or settlement':'Prepare resolution',
    'Record termination outcome':'Record outcome'
  };
  function graphMarkup(state, selected, projection = {}) {
    const graph = state.graph;
    if (!graph) return '<p class="au-empty">The packet is saved. No process has been committed yet.</p>';
    const layout = layoutGraph(graph), evaluation = new Map(list(state.evaluation?.nodes).map(node => [node.node_id, node]));
    return `<div class="au-graph-viewport" data-au-graph-pan tabindex="0" role="region" aria-label="Working process diagram"><div class="au-graph" data-au-graph data-orientation="vertical" style="--au-ranks:${Math.max(1,layout.rows.length)}"><svg class="au-graph-lines" aria-hidden="true"></svg>${layout.rows.map((row, rank) => `<div class="au-graph-rank" data-rank="${rank}">${row.map(node => {
      const evaluated = evaluation.get(node.node_id) || {}, status = evaluated.execution_state || evaluated.state || 'pending';
      const statusText = statusLabel(status) + (status === 'ready' && projection.node_capabilities?.[node.node_id]?.authorized === false ? ' · execution unavailable' : '');
      const parents = layout.parents.get(node.node_id).map(id => name(layout.byId.get(id))), fullName = name(node);
      return `<button type="button" class="au-node" data-au-node="${h(node.node_id)}" data-status="${h(status)}" aria-pressed="${selected === node.node_id}" aria-label="${h(fullName)}. ${h(statusText)}${parents.length ? `. After ${h(parents.join(' + '))}` : ''}" title="${h(fullName)}"><span class="au-node-index">${status === 'completed' ? '✓' : String(layout.nodes.indexOf(node) + 1).padStart(2, '0')}</span><span class="au-node-copy"><strong class="au-node-title">${h(compactLabels[fullName] || fullName)}</strong><span class="au-node-state">${h(statusText)}</span><span class="au-node-deps au-sr-only">${parents.length ? `After ${h(parents.join(' + '))}` : 'Starting point'}</span></span></button>`;
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
  function actionRows(state, events = []) {
    let start = null;
    const runId = typeof state.run_id === 'string' && state.run_id.trim() ? state.run_id : null;
    if (runId) for (const event of events) if (event.kind === 'work.started' && event.payload?.run_id === runId) start = event.seq;
    return list(state.actions).map(entry => {
      const result = entry.result || entry, receipt = entry.receipt || {};
      const revision = receipt.parent_revision;
      const scope = Number.isSafeInteger(start) && Number.isSafeInteger(revision) ? revision >= start ? 'current' : 'historical' : 'unassociated';
      return {result, receipt, scope};
    });
  }
  function actionMarkup(state, rows) {
    return rows.map(({result:action,receipt,scope}) => `<article class="au-action" data-au-action-scope="${scope}"><div class="au-action-heading"><strong>${h(name(action))}</strong><span>${h(statusLabel(action.status))}</span></div><p class="au-meta">${scope === 'current' ? 'Recorded in this run' : scope === 'historical' ? 'Recorded in an earlier run' : 'Recorded action · run association not recorded'}</p><p>${h(action.summary || action.reason || '')}</p>${sourceButtons(state,action)}${Object.keys(receipt).length ? `<details class="au-receipt" data-au-disclosure="action:${h(action.action_id || receipt.receipt_sha256 || name(action))}"><summary>Action receipt</summary>${Number.isSafeInteger(receipt.parent_revision) ? `<p>Recorded after revision ${h(receipt.parent_revision)}.</p>` : ''}${receipt.operation ? `<p>${h(words(receipt.operation))}</p>` : ''}<pre class="au-record-body">${h(JSON.stringify(receipt,null,2))}</pre></details>` : ''}</article>`).join('') || '<p class="au-empty">No action result recorded for this step.</p>';
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
  function inspectorMarkup(state, selected, projection = {}, events = []) {
    const node = list(state.graph?.nodes).find(item => item.node_id === selected);
    if (!node) return '<div class="au-empty">Select a process step to inspect its evidence and consequences.</div>';
    const relates = item => item.node_id === selected || item.decision_node_id === selected || list(item.node_ids).includes(selected) || list(item.required_at_node_ids).includes(selected);
    const obligations = list(state.obligations).filter(relates);
    const ids = new Set(obligations.flatMap(item => list(item.required_fact_ids)));
    for (const flag of conditionFlags(node.condition).concat(list(state.graph?.edges).filter(edge => edge.target_node_id === selected).flatMap(edge => conditionFlags(edge.condition)))) ids.add(`condition:${flag}`);
    const facts = list(state.facts).filter(item => ids.has(item.fact_id) || relates(item)).sort((a,b) => Number(b.fact_id?.startsWith('condition:')) - Number(a.fact_id?.startsWith('condition:')));
    const actions = actionRows(state,events).filter(({result:item}) => relates(item) || obligations.some(obligation => item.obligation_id === obligation.obligation_id));
    const evaluation = list(state.evaluation?.nodes).find(item => item.node_id === selected) || {};
    const required = list(evaluation.blocked_by || evaluation.unresolved_dependencies);
    const capability = projection.node_capabilities?.[selected];
    const executionState = evaluation.execution_state || evaluation.state;
    const stepStatus = executionState === 'ready' ? `Process ready${capability?.authorized === false ? ' · execution unavailable' : ''}` : statusLabel(executionState);
    const execution = capability ? `<section class="au-capability" data-authorized="${capability.authorized === true}"><strong>${capability.authorized === true ? ['ready','completed'].includes(executionState) ? 'Available capability' : 'Available after prerequisites' : 'Execution limit'}</strong><p>${h(capability.reason || words(capability.id))}</p></section>` : '';
    return `<div class="au-inspector" data-au-selected-step="${h(selected)}"><button type="button" class="au-link au-back-process" data-au-back-process="${h(selected)}">← Back to process</button><header class="au-step-heading"><p class="au-eyebrow">Selected step</p><h3 tabindex="-1" data-au-inspector-heading="${h(selected)}">${h(name(node))}</h3><p class="au-step-status">${h(stepStatus)}</p>${required.length ? `<p>Waiting for ${h(required.map(id => name(list(state.graph?.nodes).find(n => n.node_id === id)) || words(id)).join(', '))}.</p>` : ''}</header>${execution}<div class="au-step-evidence"><section class="au-step-facts"><h4>Facts this step requires</h4>${facts.map(fact => `<article class="au-fact" data-au-fact="${h(fact.fact_id)}"><strong>${h(name(fact) || words(fact.flag))}</strong><span>${h(statusLabel(fact.verdict || fact.status))}</span>${fact.summary || fact.reason ? `<p>${h(fact.summary || fact.reason)}</p>` : ''}${sourceButtons(state,fact)}${['unresolved','unknown','insufficient'].includes(fact.verdict || fact.status) ? button('Add evidence','data-au-add-files') : ''}</article>`).join('') || '<p class="au-empty">No fact dependencies recorded for this step.</p>'}</section><section class="au-step-documents"><h4>Required documents</h4>${obligationMarkup(state,selected,obligations)}${obligations.length ? `<details class="au-document-rules" data-au-disclosure="document-rules:${h(selected)}"><summary>Document rules and acquisition</summary>` : ''}${obligations.map(item => `<p class="au-meta">${list(item.rule_refs).length ? `Rule ${h(list(item.rule_refs).map(ref => typeof ref === 'string' ? ref : ref.rule_id || ref.title || ref.authority_id).join(' · '))} · ` : ''}${item.capability_id ? `Acquisition: ${h(words(item.capability_id))}` : 'No acquisition capability recorded'}</p>`).join('')}${obligations.length ? '</details>' : ''}</section><section class="au-step-actions"><h4>Recorded actions</h4>${actionMarkup(state,actions)}</section></div>${routeMarkup(state,selected)}<details class="au-rule-trace" data-au-disclosure="rules:${h(selected)}"><summary>Admitted rules</summary>${node.authority?.title ? `<strong>${h(node.authority.title)}</strong>` : ''}${node.authority?.quote ? `<blockquote>${h(node.authority.quote)}</blockquote>` : ''}${node.meaning && node.meaning !== node.authority?.quote ? `<p>${h(node.meaning)}</p>` : ''}${list(node.provenance?.rule_refs).map(ref => `<p>${h(typeof ref === 'string' ? ref : ref.title || ref.rule_id || ref.authority_id)}</p>`).join('')}${node.authority?.source_id ? `<p class="au-meta">${h(node.authority.source_id)}</p>` : ''}</details></div>`;
  }
  function eventLabel(event) {
    if (event.kind === 'knowledge.published') return event.payload?.knowledge?.qualification?.status === 'qualified' ? 'Qualified knowledge version published' : 'Knowledge candidate withheld';
    return event.payload?.summary || event.payload?.reason || ({'intake':'Incoming packet saved', 'intake.received':'Incoming packet saved', 'work.started':'Autonomous investigation started', 'sources.acquired':'Original sources acquired', 'interpretation.accepted':'Source-grounded process accepted', 'graph.advanced':'Process advanced', 'action.completed':'Action result saved', 'outcome.recorded':'Operational outcome saved', 'work.completed':'Operational outcome saved', 'work.deferred':'Work deferred', 'knowledge.published':'Qualified knowledge version published', 'knowledge.used':'Qualified knowledge reused', 'knowledge.reused':'Qualified knowledge reused'})[event.kind] || words(event.kind);
  }
  function outcomeMarkup(state, outcome) {
    if (!outcome) return '';
    const gaps = list(outcome.missing_evidence).length, limits = list(outcome.authority_limits).length;
    const summary = [statusLabel(state.status), gaps ? `${gaps} evidence gap${gaps === 1 ? '' : 's'}` : '', limits ? `${limits} execution limit${limits === 1 ? '' : 's'}` : ''].filter(Boolean).join(' · ');
    const reason = outcome.reason || outcome.authority_limits?.[0] || outcome.summary || outcome.title;
    return `<details class="au-outcome" data-status="${h(state.status)}" data-au-disclosure="outcome"><summary><strong>${h(summary)}</strong><span>${h(reason)}</span></summary><div class="au-outcome-body"><p class="au-eyebrow">${state.status === 'deferred' ? 'Why work stopped' : 'Recorded outcome'}</p><h2>${h(outcome.title || statusLabel(outcome.status || state.status))}</h2><p>${h(outcome.summary || outcome.reason || '')}</p>${list(outcome.authority_limits).map(reason => `<p>${h(reason)}</p>`).join('')}${gaps ? `<p><strong>Evidence still needed:</strong> ${h(outcome.missing_evidence.map(item => item.label || words(item.document_type)).join('; '))}.</p>${button('Add supporting files','data-au-add-files')}` : ''}${list(outcome.unresolved_facts).length ? `<p><strong>Unresolved:</strong> ${h(outcome.unresolved_facts.map(item => item.summary || words(item.fact_id)).join('; '))}.</p>` : ''}${outcome.next_action ? `<p>${h(outcome.next_action)}</p>` : ''}${sourceButtons(state,outcome)}${outcome.request_draft ? `<details data-au-disclosure="request-draft"><summary>Evidence request · ${h(statusLabel(outcome.request_draft.status))}</summary><p><strong>${h(outcome.request_draft.subject)}</strong></p><pre class="au-draft-body">${h(outcome.request_draft.body)}</pre></details>` : ''}<details class="au-technical-record" data-au-disclosure="outcome-record"><summary>Full public ${state.outcome ? 'outcome' : state.deferral ? 'deferral' : 'outcome'} record</summary><pre class="au-record-body">${h(JSON.stringify(state.outcome || state.deferral || outcome,null,2))}</pre></details></div></details>`;
  }
  function sourcesMarkup(state) {
    return `<section class="au-supporting"><div class="au-section-heading"><h2>Original sources</h2><span>${list(state.acquired_sources).length} of ${list(state.source_descriptors).length} acquired</span></div><ul class="au-source-list">${list(state.source_descriptors).map(source => `<li>${button(source.file_name || name(source) || 'Original source', `data-au-source="${h(source.artifact_id)}"`)}<span>${list(state.acquired_sources).some(row => row.artifact_id === source.artifact_id) ? 'Acquired' : 'In packet'}</span></li>`).join('') || '<li>No original source recorded.</li>'}</ul><form data-au-arrival class="au-arrival"><label for="auAdditionalFiles">Add supporting files</label><input id="auAdditionalFiles" name="files" type="file" multiple required><button class="au-secondary" type="submit">Add files</button><p class="au-form-status" role="status"></p></form></section>`;
  }
  function activityMarkup(state, events) {
    return `<section class="au-activity"><h2>Activity</h2><p class="au-meta">The saved journal records work in sequence.</p><details class="au-history" data-au-disclosure="history"><summary>Recorded work <span>${events.length} events</span></summary><ol class="au-event-list">${events.slice().reverse().map(event => `<li><span class="au-event-seq">${h(event.seq)}</span><div><strong>${h(eventLabel(event))}</strong><time datetime="${h(event.timestamp || '')}">${h(dateLabel(event.timestamp))}</time></div></li>`).join('') || '<li>No events loaded.</li>'}</ol></details><section class="au-recorded-actions"><h3>Action record</h3>${actionMarkup(state,actionRows(state,events))}</section>${list(state.knowledge_uses).length ? `<section class="au-reuse"><h3>Knowledge used here</h3>${list(state.knowledge_uses).map(use => `<article><strong>${h(use.name || use.knowledge_id || use.version_id)} · version ${h(use.version || use.version_id)}</strong>${reuseDetails(use)}${knowledgeLink(use)}</article>`).join('')}${button('Inspect knowledge','data-au-nav="knowledge"')}</section>` : '<p class="au-empty">No knowledge reuse recorded for this claim.</p>'}</section>`;
  }
  function workMarkup(state, projection, selected, events, detail = 'step') {
    const outcome = state.outcome || (state.deferral ? {title:words(state.deferral.code),reason:state.deferral.reason,status:'deferred',details:state.deferral.details} : null);
    const panels = [['step','This step',inspectorMarkup(state,selected,projection,events)],['documents','All documents',`<section aria-labelledby="auDocumentsTitle" class="au-documents"><div class="au-section-heading"><h2 id="auDocumentsTitle">All documents</h2><span>${new Set([...list(state.obligations),...list(state.evaluation?.documents)].map(item => item.document_type)).size} documents</span></div>${obligationMarkup(state,selected)}</section>`],['sources','Sources',sourcesMarkup(state)],['activity','Activity',activityMarkup(state,events)]];
    return `<header class="au-work-head"><div><p class="au-eyebrow"><button type="button" class="au-back-work" data-au-nav="work">Work</button><span aria-hidden="true"> / </span>Claim · revision ${h(state.revision)}</p><h1 class="au-page-heading" id="auClaimTitle" data-au-claim-title tabindex="-1">${h(state.title)}</h1></div><div class="au-work-controls"><span class="au-status" data-tone="${tone(state.status)}">${h(statusLabel(state.status))}</span>${state.status === 'running' ? button('Pause work','data-au-pause') : state.deferral?.code === 'paused' ? button('Resume work','data-au-resume') : ''}</div></header>${progressMarkup(state,events)}${outcomeMarkup(state,outcome)}<div class="au-causal-layout"><section class="au-process-hero au-path-panel" aria-labelledby="auProcessTitle"><div class="au-section-heading"><h2 id="auProcessTitle">Working process</h2><span>${list(state.graph?.nodes).length} step${list(state.graph?.nodes).length === 1 ? '' : 's'}</span></div>${graphMarkup(state,selected,projection)}</section><div class="au-work-layout au-context-panel au-detail-panel" aria-label="Step evidence and consequences" data-au-context="${h(detail)}"><nav class="au-context-nav" aria-label="Claim details">${panels.map(([id,label]) => `<button type="button" data-au-detail="${id}" aria-pressed="${detail === id}" aria-controls="auPanel-${id}">${h(label)}</button>`).join('')}</nav><div class="au-context-body">${panels.map(([id,label,body]) => `<section class="au-context-view" id="auPanel-${id}" data-au-panel="${id}" aria-label="${h(label)}"${detail === id ? '' : ' hidden'}>${body}</section>`).join('')}</div></div></div>`;
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
  function knowledgeMarkup(data, claims = []) {
    const claimLabel = (id, fallback) => list(claims).find(claim => claim.claim_id === id)?.title || `${fallback} · ${String(id).slice(-8)}`;
    const versions = list(data?.versions), uses = list(data?.uses), quarantined = list(data?.quarantined), groups = new Map();
    for (const version of versions) { const id = version.knowledge_id || version.version_id; if (!groups.has(id)) groups.set(id,[]); groups.get(id).push(version); }
    const versionMarkup = (version,history,latest) => {
      const receiving = uses.filter(use => (use.knowledge_id || use.version_id) === (version.knowledge_id || version.version_id) && (use.knowledge_sha256 ? use.knowledge_sha256 === version.knowledge_sha256 : String(use.version || use.version_id) === String(version.version || version.version_id)));
      const identity = `${version.knowledge_id || version.version_id || name(version)}:${version.version || version.version_id || ''}`;
      return `<li class="au-knowledge-version au-version-row" data-au-version="${h(version.version || version.version_id)}" data-au-knowledge-identity="${h(identity)}" data-current="${latest}"><div class="au-version-heading"><strong>Version ${h(version.version || version.version_id)}</strong><span>${latest ? 'Latest recorded version' : 'Earlier recorded version'}</span>${version.created_at ? `<time datetime="${h(version.created_at)}" title="${h(version.created_at)}">${h(dateLabel(version.created_at))}</time>` : ''}</div>${version.source_claim_id ? `<div class="au-knowledge-claims"><div><h4>Source claim</h4>${button(claimLabel(version.source_claim_id,'Open source claim'),`data-au-claim="${h(version.source_claim_id)}"`)}</div><div><h4>Reused in ${new Set(receiving.map(use => use.claim_id).filter(Boolean)).size} claims</h4>${[...new Set(receiving.map(use => use.claim_id).filter(Boolean))].map(id => button(claimLabel(id,'Open receiving claim'),`data-au-claim="${h(id)}"`)).join('') || '<p class="au-meta">No receiving claim recorded yet</p>'}</div></div>` : '<p class="au-meta">Source claim not recorded</p>'}${lineageMarkup(version,history)}${definitionMarkup(version)}<details class="au-qualification" data-au-disclosure="qualification:${h(identity)}"><summary>Qualification checks</summary><p>${h(version.qualification?.summary || statusLabel(version.qualification?.status || version.validation?.status || version.status))}</p>${version.qualification?.regression_cases ? `<p>${h(version.qualification.regression_cases)} branch assignments checked</p>` : ''}<ul>${list(version.qualification?.checks).map(check => `<li>${h(typeof check === 'string' ? words(check) : check.summary || check.name || check.check || check.status)}</li>`).join('') || '<li>No qualification checks recorded.</li>'}</ul></details><details class="au-provenance" data-au-disclosure="provenance:${h(identity)}"><summary>Provenance and receipts</summary><dl class="au-chain">${['source_claim_id','parent_knowledge_sha256','parent_definition_sha256','knowledge_sha256','rule_pack_sha256','source_state_sha256','proposer_receipt_sha256','verifier_receipt_sha256','regression_receipt_sha256'].filter(field => version[field]).map(field => `<div><dt>${h(words(field.replace('_sha256','')))}</dt><dd class="${field.endsWith('sha256') ? 'au-hash' : ''}">${h(version[field])}</dd></div>`).join('')}</dl><details class="au-technical-record"><summary>Full public version record</summary><pre class="au-record-body">${h(JSON.stringify(version,null,2))}</pre></details></details></li>`;
    };
    const cards = [...groups.values()].map(history => {
      history.sort((a,b) => Number(b.version) - Number(a.version));
      const version = history[0], identity = version.knowledge_id || version.version_id || name(version);
      return `<article class="au-knowledge-card"><p class="au-eyebrow">${h(words(version.category || version.family || 'Process knowledge'))}</p><h2>${h(name(version) || version.knowledge_id || version.version_id)}</h2><p>${h(version.summary || version.description || '')}</p><p class="au-knowledge-status">${h(version.qualification?.summary || statusLabel(version.qualification?.status || version.validation?.status || version.status))}</p><ol class="au-version-lineage">${versionMarkup(version,history,true)}</ol><details class="au-version-disclosure" data-au-disclosure="versions:${h(identity)}"><summary>Version history <span>${history.length}</span></summary><ol class="au-version-history">${history.slice(1).map(item => versionMarkup(item,history,false)).join('') || '<li>No earlier recorded version.</li>'}</ol></details></article>`;
    }).join('');
    return `<header class="au-work-head"><div><p class="au-eyebrow">From recorded investigations</p><h1 class="au-page-heading" tabindex="-1">Knowledge</h1></div></header><p class="au-lead">Qualified process knowledge keeps its version, source and applicability record each time it is reused.</p><div class="au-knowledge-summary"><span><strong>${versions.length}</strong> qualified versions</span><span><strong>${uses.length}</strong> recorded uses</span><span><strong>${quarantined.length}</strong> quarantined candidates</span></div><div class="au-knowledge-grid">${cards || '<p class="au-empty">No qualified knowledge version has been published.</p>'}</div>${uses.length ? `<section class="au-knowledge-reuse"><h2>Recorded reuse</h2><ul class="au-event-list">${uses.map(use => `<li><div><strong>${h(use.name || use.knowledge_id || use.version_id)} · version ${h(use.version || use.version_id)}</strong>${reuseDetails(use)}${knowledgeLink(use)}${use.claim_id ? button(claimLabel(use.claim_id,'Open receiving claim'),`data-au-claim="${h(use.claim_id)}"`) : ''}</div></li>`).join('')}</ul></section>` : ''}<details class="au-history au-quarantine" data-au-disclosure="quarantine"><summary>Quarantined candidates <span>${quarantined.length}</span></summary><ul class="au-event-list">${quarantined.map(item => `<li><div><strong>${h(name(item) || item.candidate_id)}</strong><p>${h(item.qualification?.reason || item.reason || item.summary || 'No qualification recorded')}</p>${item.source_claim_id ? button('Open source claim',`data-au-claim="${h(item.source_claim_id)}"`) : ''}<details class="au-technical-record"><summary>Public quarantine record</summary><pre class="au-record-body">${h(JSON.stringify(item,null,2))}</pre></details></div></li>`).join('') || '<li>No quarantined candidates.</li>'}</ul></details>`;
  }
  function matchingClaims(claims, {search = '', filter = 'all'} = {}) {
    const query = search.trim().toLocaleLowerCase();
    return list(claims).filter(claim => (filter === 'all' || filter === 'working' && active(claim.status) || claim.status === filter) && (!query || [claim.title,statusLabel(claim.status),claim.phase,claim.phase_summary,claim.outcome?.summary,claim.outcome?.reason,claimConstraint(claim)].filter(Boolean).join(' ').toLocaleLowerCase().includes(query)));
  }
  function claimConstraint(claim) {
    const outcome = claim.outcome;
    const missing = list(outcome?.missing_evidence).map(item => item.label || words(item.document_type)).filter(Boolean);
    return outcome?.reason || (missing.length ? `Evidence needed: ${missing.join('; ')}` : '') || list(outcome?.authority_limits)[0] || outcome?.next_action || '';
  }
  function claimsMarkup(claims, options = {}) {
    return matchingClaims(claims,options).map(claim => {
      const constraint = claimConstraint(claim) || claim.outcome?.summary || (active(claim.status) ? claim.phase_summary : 'Open the claim to inspect its recorded outcome.');
      return `<article class="au-claim-row" data-au-claim-row="${h(claim.claim_id)}"><button type="button" class="au-claim-open" data-au-claim="${h(claim.claim_id)}"><strong>${h(claim.title || 'Untitled claim')}</strong>${constraint ? `<span class="au-claim-constraint">${h(constraint)}</span>` : ''}<span class="au-claim-phase">${claim.phase ? `Recorded phase: ${h(words(claim.phase))}` : 'No phase recorded'}${Number.isSafeInteger(claim.revision) ? ` · revision ${h(claim.revision)}` : ''}</span></button><span class="au-status" data-tone="${tone(claim.status)}">${h(statusLabel(claim.status))}</span></article>`;
    }).join('') || `<p class="au-empty">${list(claims).length ? 'No saved claims match this search.' : 'Your incoming claims will appear here.'}</p>`;
  }
  function collectionMarkup(claims, {search = '', filter = 'all'} = {}) {
    const rows = list(claims), filters = [...new Set(['all','working','deferred','resolved',...rows.map(claim => claim.status).filter(status => status && !active(status))])];
    const counts = [['Saved claims',rows.length],['In progress',rows.filter(claim => active(claim.status)).length],['Deferred',rows.filter(claim => claim.status === 'deferred').length],['Resolved',rows.filter(claim => claim.status === 'resolved').length]];
    return `<section class="au-collection"><header class="au-collection-head"><div><p class="au-eyebrow">Claim workspace</p><h1 class="au-page-heading" tabindex="-1">Work</h1><p class="au-lead">Follow saved claims from their original evidence to a recorded outcome.</p></div>${button('New claim','data-au-nav="intake"',true)}</header><div class="au-collection-summary">${counts.map(([label,count]) => `<span><strong>${count}</strong> ${h(label)}</span>`).join('')}</div><div class="au-collection-tools"><label for="auClaimSearch">Search claims<input id="auClaimSearch" type="search" data-au-claim-search value="${h(search)}" placeholder="Title or recorded work" autocomplete="off"></label><label for="auClaimFilter">Status<select id="auClaimFilter" data-au-claim-filter>${filters.map(value => `<option value="${h(value)}"${filter === value ? ' selected' : ''}>${h(value === 'all' ? 'All statuses' : value === 'working' ? 'In progress' : statusLabel(value))}</option>`).join('')}</select></label><button type="button" class="au-link" data-au-refresh-claims>Refresh</button></div><div class="au-section-heading"><h2>Saved claims</h2><span data-au-collection-count>${matchingClaims(rows,{search,filter}).length} of ${rows.length}</span></div><div class="au-claim-list" data-au-claims>${claimsMarkup(rows,{search,filter})}</div></section>`;
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
    let disposed = false, epoch = 0, timer = null, selected = null, current = null, projection = {}, cursor = null, history = [], detail = 'step', view = 'work', disconnected = false, busy = false, status = null, pendingIntake = null, pendingArrival = null, pendingControl = null, dialogReturn = null, sourceEpoch = 0, polling = false;
    const controllers = new Set();
    const reduced = root.matchMedia?.('(prefers-reduced-motion: reduce)');
    let motion = null, keyboard = false, edgeFrame = null, examples = null, routedFragment = null, intakeForm = null, claims = [], claimsLoaded = false, claimsRead = 0;
    const claimViews = new Map(), arrivalForms = new Map(), arrivals = new Map(), controls = new Map();
    const collection = {search:'',filter:'all'};
    container.classList.add('au-workspace');
    container.innerHTML = `<div class="au-shell"><aside class="au-rail"><header class="au-header"><a class="au-brand" href="/">CasePath<span>Claim workspace</span></a></header><nav class="au-nav" aria-label="Workspace"><button type="button" data-au-nav="work" aria-current="page">Work</button><button type="button" data-au-nav="knowledge">Knowledge</button><button type="button" data-au-nav="intake">New claim</button></nav><section class="au-recent-queue" aria-label="Recent claims"><h2>Recent claims</h2><div data-au-recent-claims><p class="au-empty">Loading saved claims.</p></div></section>${root.CASEPATH_HOSTED_AUTONOMOUS ? '' : '<a class="au-review-link" href="/?journey=review">Review workspace</a>'}</aside><${mainTag} class="au-main"><div class="au-global-status" role="status" aria-live="polite"></div><div class="au-body" data-au-view data-au-view-state="work"></div></${mainTag}></div><dialog class="au-source-dialog" aria-labelledby="auSourceTitle"><header class="au-dialog-header"><div><p class="au-eyebrow">Original source</p><h2 id="auSourceTitle">Source</h2></div><button type="button" class="au-secondary" data-au-close>Close source</button></header><div data-au-source-content></div></dialog>`;
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
        try { const id = decodeURIComponent(fragment.slice('#autonomous/claim/'.length)); id ? openClaim(id,false) : showWork(false); }
        catch (_) { showWork(false); }
      } else if (['#autonomous/new','#autonomous/intake'].includes(fragment)) showIntake(false);
      else showWork(false);
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
    function schedule() { cancelPoll(); if (!disposed && view === 'claim' && current) timer = root.setTimeout(poll, active(current.status) ? 1600 : 6000); }
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
      for (const attr of ['data-au-node','data-au-select','data-au-source','data-au-nav','data-au-pause','data-au-resume','data-au-graph-pan','data-au-claim-title','data-au-inspector-heading','data-au-back-process','data-au-detail','data-au-add-files']) if (element.hasAttribute(attr)) return {attr,value:element.getAttribute(attr),citation:element.getAttribute('data-au-citation'),panel};
      const details = element.matches('summary') ? element.parentElement : null;
      return details?.hasAttribute('data-au-disclosure') ? {disclosure:details.dataset.auDisclosure,panel} : null;
    }
    function focusTarget(token) {
      if (!token) return null;
      if (token.disclosure) return [...host.querySelectorAll('[data-au-disclosure]')].find(el => el.dataset.auDisclosure === token.disclosure && focusEligible(el.querySelector('summary'),token))?.querySelector('summary');
      return [...host.querySelectorAll(`[${token.attr}]`)].find(el => el.getAttribute(token.attr) === token.value && el.getAttribute('data-au-citation') === token.citation && focusEligible(el,token));
    }
    function nav(name) { container.querySelectorAll('.au-nav [data-au-nav]').forEach(item => { if (item.dataset.auNav === name) item.setAttribute('aria-current','page'); else item.removeAttribute('aria-current'); }); }
    function drawEdges() {
      const graph = host.querySelector('[data-au-graph]'), svg = graph?.querySelector('svg');
      if (!graph || !svg || !current?.graph) return;
      const frame = graph.getBoundingClientRect();
      const signature = `${frame.width}:${frame.height}:${selected}`;
      if (edgeFrame?.graph === graph && edgeFrame.signature === signature) return;
      edgeFrame = {graph,signature};
      svg.setAttribute('viewBox', `0 0 ${frame.width} ${frame.height}`);
      const nodes = new Map([...graph.querySelectorAll('[data-au-node]')].map(el => [el.dataset.auNode, el]));
      const horizontal = graph.dataset?.orientation !== 'vertical' && root.matchMedia?.('(min-width: 801px)').matches;
      const evaluated = new Map(list(current.evaluation?.edges).map(edge => [edge.edge_id,edge]));
      svg.innerHTML = list(current.graph.edges).map((edge,index) => {
        const source = nodes.get(edge.source_node_id), target = nodes.get(edge.target_node_id);
        const from = source?.getBoundingClientRect(), to = target?.getBoundingClientRect();
        if (!from || !to) return '';
        const skip = Number(target.parentElement.dataset.rank) - Number(source.parentElement.dataset.rank) > 1;
        let path;
        if (horizontal) {
          const x1=from.right-frame.left,y1=from.top+from.height/2-frame.top,x2=to.left-frame.left,y2=to.top+to.height/2-frame.top,lane=frame.height-8-index%2*8;
          path=skip ? `M${x1},${y1} C${x1+7},${y1} ${x1+7},${lane} ${x1+14},${lane} L${x2-14},${lane} C${x2-7},${lane} ${x2-7},${y2} ${x2},${y2}` : `M${x1},${y1} C${(x1+x2)/2},${y1} ${(x1+x2)/2},${y2} ${x2},${y2}`;
        } else {
          const x1=from.left+from.width/2-frame.left,y1=from.bottom-frame.top,x2=to.left+to.width/2-frame.left,y2=to.top-frame.top,lane=frame.width-4;
          path=skip ? `M${x1},${y1} C${x1},${y1+10} ${lane},${y1+10} ${lane},${y1+20} L${lane},${y2-20} C${lane},${y2-10} ${x2},${y2-10} ${x2},${y2}` : `M${x1},${y1} C${x1},${(y1+y2)/2} ${x2},${(y1+y2)/2} ${x2},${y2}`;
        }
        const view = evaluated.get(edge.edge_id);
        return `<path d="${path}" data-au-edge="${h(edge.edge_id)}" data-state="${h(view?.activation || view?.condition_verdict || 'unresolved')}" data-selected="${edge.source_node_id === selected || edge.target_node_id === selected}"/>`;
      }).join('');
    }
    function preserveClaimView() {
      if (view !== 'claim' || !current) return;
      const viewport = host.querySelector('.au-graph-viewport');
      claimViews.set(current.claim_id,{selected,detail,scrollLeft:viewport?.scrollLeft || 0,scrollTop:viewport?.scrollTop || 0,open:new Set([...host.querySelectorAll('details[open][data-au-disclosure]')].map(el => el.dataset.auDisclosure))});
      const arrival = host.querySelector('[data-au-arrival]');
      if (arrival) { arrivalForms.set(current.claim_id,arrival); arrival.remove?.(); }
      if (pendingArrival) arrivals.set(current.claim_id,pendingArrival); else arrivals.delete(current.claim_id);
      if (pendingControl) controls.set(current.claim_id,pendingControl); else controls.delete(current.claim_id);
    }
    function leaveView() {
      motion?.cancel();
      if (view === 'intake') { intakeForm = host.querySelector('[data-au-intake]') || intakeForm; intakeForm?.remove?.(); }
      if (view === 'work') { const main = container.querySelector('.au-main'); collection.scrollTop = host.scrollTop || 0; collection.mainTop = main?.scrollTop || 0; collection.mainLeft = main?.scrollLeft || 0; collection.scrollX = root.scrollX || 0; collection.scrollY = root.scrollY || 0; }
      preserveClaimView();
    }
    function setView(name) { view = name; host.setAttribute?.('data-au-view-state',name); }
    function revealGraphNode(node) {
      const viewport = host.querySelector('.au-graph-viewport');
      const area = viewport?.getBoundingClientRect?.(), bounds = node?.getBoundingClientRect?.();
      if (!area || !bounds) return;
      if (bounds.top < area.top) viewport.scrollTop += bounds.top - area.top;
      else if (bounds.bottom > area.bottom) viewport.scrollTop += bounds.bottom - area.bottom;
    }
    function renderClaim(changes = null) {
      if (!current || view !== 'claim') return;
      motion?.cancel();
      const focused = doc.activeElement, focusKey = focusToken(focused);
      const previous = claimViews.get(current.claim_id);
      const open = new Set([...host.querySelectorAll('details[open][data-au-disclosure]')].map(el => el.dataset.auDisclosure));
      if (!host.querySelector('[data-au-claim-title]') && previous) for (const id of previous.open) open.add(id);
      const priorViewport = host.querySelector('.au-graph-viewport');
      const scrollLeft = priorViewport?.scrollLeft ?? previous?.scrollLeft ?? 0, scrollTop = priorViewport?.scrollTop ?? previous?.scrollTop ?? 0;
      const arrival = host.querySelector('[data-au-arrival]') || arrivalForms.get(current.claim_id), focusInArrival = arrival?.contains?.(focused);
      // Moving the original node keeps native FileList, entered text and retry state.
      arrival?.remove?.();
      host.innerHTML = workMarkup(current,projection,selected,history,detail);
      if (arrival) host.querySelector('[data-au-arrival]')?.replaceWith(arrival);
      const presentArrival = host.querySelector('[data-au-arrival]');
      if (presentArrival) arrivalForms.set(current.claim_id,presentArrival);
      if (pendingArrival && presentArrival) { lockForm(presentArrival,true,true); presentArrival.querySelector('.au-form-status').textContent ||= 'The prior response was not confirmed. Retry sends the same saved supporting-file request.'; }
      if (focusInArrival) focused?.focus?.({preventScroll:true});
      const viewport = host.querySelector('.au-graph-viewport'); if (viewport) { viewport.scrollLeft = scrollLeft; viewport.scrollTop = scrollTop; }
      for (const disclosure of host.querySelectorAll('[data-au-disclosure]')) disclosure.open = open.has(disclosure.dataset.auDisclosure);
      focusTarget(focusKey)?.focus({preventScroll:true});
      drawEdges();
      motion = animateTransition(host,changes,{hidden:doc.hidden,dialogOpen:dialog.open,reducedMotion:reduced?.matches,keyboard,activeElement:doc.activeElement});
    }
    function setDetail(value, focusFiles = false) {
      if (view !== 'claim' || !['step','documents','sources','activity'].includes(value)) return;
      motion?.cancel(); detail = value;
      host.querySelector('[data-au-context]')?.setAttribute('data-au-context',value);
      for (const panel of host.querySelectorAll('[data-au-panel]')) panel.hidden = panel.dataset.auPanel !== value;
      for (const control of host.querySelectorAll('.au-context-nav [data-au-detail]')) control.setAttribute('aria-pressed',String(control.dataset.auDetail === value));
      if (focusFiles) host.querySelector('#auAdditionalFiles')?.focus({preventScroll:true});
    }
    async function poll() {
      const token = epoch, id = current?.claim_id;
      if (!id || disposed || view !== 'claim' || polling) return;
      polling = true;
      try {
        const response = await request(`/claims/${key(id)}`);
        const incoming = readState(response, id);
        const batch = await request(`/claims/${key(id)}/events?after=${cursor ?? 0}`);
        if (disposed || token !== epoch || view !== 'claim') return;
        const accepted = acceptEvents(cursor, batch, incoming.state, disconnected);
        if (!accepted.ready) { schedule(); return; }
        if (current && incoming.state.revision < current.revision) throw new Error('A stale claim revision was returned.');
        if (current && incoming.state.revision === current.revision && incoming.state.state_sha256 !== current.state_sha256) throw new Error('A saved revision changed identity.');
        const changed = disconnected || !current || current.state_sha256 !== incoming.state.state_sha256 || cursor !== accepted.cursor || JSON.stringify(projection) !== JSON.stringify(incoming.projection);
        const changes = transitionPlan(current,incoming.state,accepted,history);
        current = incoming.state; projection = incoming.projection; cursor = accepted.cursor;
        const existing = new Map(history.map(event => [event.seq,event])); for (const event of accepted.events) existing.set(event.seq,event);
        history = [...existing.values()].sort((a,b) => a.seq-b.seq);
        if (!list(current.graph?.nodes).some(node => node.node_id === selected)) selected = list(current.evaluation?.nodes).find(node => node.execution_state === 'ready')?.node_id || current.graph?.nodes?.[0]?.node_id || null;
        if (changed) { renderClaim(changes); rememberClaim(current); }
        if (disconnected) notice('Connection restored. Showing saved work.'); else notice('');
        disconnected = false;
      } catch (error) { if (!disposed && token === epoch) { disconnected = true; notice(`Updates paused: ${error.message} Saved work remains visible.`, true); } }
      finally { polling = false; if (!disposed && view === 'claim') schedule(); }
    }
    async function openClaim(id, writeHistory = true) {
      leaveView(); route(`#autonomous/claim/${key(id)}`,writeHistory);
      epoch++; const token = epoch; cancelPoll(); motion?.cancel(); setView('claim'); current = null; selected = null; cursor = null; history = []; disconnected = false; pendingArrival = arrivals.get(id) || null; pendingControl = controls.get(id) || null; nav('work'); notice('Opening saved claim…');
      host.innerHTML = '<p class="au-empty">Loading the saved claim.</p>';
      try {
        let incoming, accepted;
        // A live writer can advance between reads. Retry only this read pair, bounded.
        for (let attempt = 0; attempt < 3; attempt++) {
          incoming = readState(await request(`/claims/${key(id)}`),id);
          if (disposed || token !== epoch) return;
          const batch = await request(`/claims/${key(id)}/events?after=0`);
          if (disposed || token !== epoch) return;
          accepted = acceptEvents(null,batch,incoming.state);
          if (accepted.ready) break;
        }
        if (!accepted?.ready) throw new Error('The saved claim and event cursor have not matched. Retry opening the claim to load a verified record.');
        current = incoming.state; projection = incoming.projection; cursor = accepted.cursor; history = accepted.events;
        const previous = claimViews.get(id);
        selected = list(current.graph?.nodes).some(node => node.node_id === previous?.selected) ? previous.selected : list(current.evaluation?.nodes).find(node => node.execution_state === 'ready')?.node_id || current.graph?.nodes?.[0]?.node_id || null;
        detail = previous?.detail || 'step';
        renderClaim(); rememberClaim(current); notice(''); focusTitle(); schedule();
        if (!claimsLoaded) loadClaims(token).catch(() => {});
      } catch (error) { if (!disposed && token === epoch) { notice(error.message,true); host.innerHTML = button('Retry opening claim',`data-au-claim="${h(id)}"`); } }
    }
    function railClaims() {
      const queue = container.querySelector('[data-au-recent-claims]');
      if (!queue) return;
      queue.innerHTML = claims.slice(0,6).map(claim => `<button type="button" class="au-recent-claim" data-au-claim="${h(claim.claim_id)}"${current?.claim_id === claim.claim_id && view === 'claim' ? ' aria-current="page"' : ''}><strong>${h(claim.title || 'Untitled claim')}</strong><span data-tone="${tone(claim.status)}">${h(statusLabel(claim.status))}</span></button>`).join('') || '<p class="au-empty">No saved claims yet.</p>';
    }
    function rememberClaim(state) {
      const summary = {claim_id:state.claim_id,title:state.title,status:state.status,phase:state.phase,phase_summary:state.phase_summary,revision:state.revision,state_sha256:state.state_sha256,updated_at:state.updated_at,outcome:state.outcome};
      const index = claims.findIndex(row => row.claim_id === state.claim_id);
      if (index >= 0) {
        if (!Number.isSafeInteger(claims[index].revision) || claims[index].revision <= summary.revision) claims[index] = summary;
      } else claims.unshift(summary);
      railClaims();
    }
    function refreshCollection() {
      if (view !== 'work') return;
      const output = host.querySelector('[data-au-claims]'); if (output) output.innerHTML = claimsMarkup(claims,collection);
      const count = host.querySelector('[data-au-collection-count]'); if (count) count.textContent = `${matchingClaims(claims,collection).length} of ${claims.length}`;
      const summary = host.querySelector('.au-collection-summary');
      if (summary) summary.innerHTML = [['Saved claims',claims.length],['In progress',claims.filter(claim => active(claim.status)).length],['Deferred',claims.filter(claim => claim.status === 'deferred').length],['Resolved',claims.filter(claim => claim.status === 'resolved').length]].map(([label,count]) => `<span><strong>${count}</strong> ${h(label)}</span>`).join('');
      const filter = host.querySelector('[data-au-claim-filter]');
      if (filter) { const options = [...new Set(['all','working','deferred','resolved',...claims.map(claim => claim.status).filter(status => status && !active(status))])]; filter.innerHTML = options.map(value => `<option value="${h(value)}"${collection.filter === value ? ' selected' : ''}>${h(value === 'all' ? 'All statuses' : value === 'working' ? 'In progress' : statusLabel(value))}</option>`).join(''); }
    }
    async function loadClaims(token = epoch) {
      const read = ++claimsRead;
      const data = await request('/claims');
      if (disposed || token !== epoch || read !== claimsRead) return;
      const remembered = new Map(claims.map(row => [row.claim_id,row]));
      claims = list(data.claims).map(row => {
        const known = remembered.get(row.claim_id);
        if (!known || !Number.isSafeInteger(known.revision)) return row;
        const verified = current?.claim_id === row.claim_id && current.revision === row.revision && known.revision === current.revision && known.state_sha256 === current.state_sha256;
        return !Number.isSafeInteger(row.revision) || known.revision > row.revision || verified ? known : row;
      });
      if (current && !claims.some(row => row.claim_id === current.claim_id) && remembered.has(current.claim_id)) claims.unshift(remembered.get(current.claim_id));
      claimsLoaded = true; railClaims(); refreshCollection();
    }
    async function serviceStatus(token) {
      const data = await request('/status');
      if (disposed || token !== epoch) return;
      status = data;
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
    async function showWork(writeHistory = true) {
      leaveView(); route('#autonomous/work',writeHistory);
      epoch++; const token = epoch; cancelPoll(); setView('work'); nav('work'); current = null; notice('');
      host.innerHTML = collectionMarkup(claims,collection);
      if (collection.scrollTop !== undefined) { host.scrollTop = collection.scrollTop; const main = container.querySelector('.au-main'); if (main) { main.scrollTop = collection.mainTop; main.scrollLeft = collection.mainLeft; } root.scrollTo?.({left:collection.scrollX,top:collection.scrollY,behavior:'instant'}); }
      if (!claimsLoaded) { const output = host.querySelector('[data-au-claims]'); if (output) output.innerHTML = '<p class="au-empty">Loading saved claims.</p>'; }
      const results = await Promise.allSettled([serviceStatus(token),loadClaims(token)]);
      if (!disposed && token === epoch) for (const result of results) if (result.status === 'rejected') notice(result.reason.message,true);
    }
    async function showIntake(writeHistory = true) {
      if (view === 'intake' && host.querySelector('[data-au-intake]')) { route('#autonomous/new',writeHistory); return; }
      leaveView(); route('#autonomous/new',writeHistory);
      epoch++; const token = epoch; cancelPoll(); setView('intake'); nav('intake'); current = null; notice('');
      host.innerHTML = `<div class="au-intake-layout"><section><p class="au-eyebrow">New claim</p><h1 class="au-page-heading" tabindex="-1">Introduce the claim</h1><p class="au-lead">Add the original message and files. The recorded work will show the evidence, process, actions and any limits.</p><form class="au-intake" data-au-intake><div class="au-examples" data-au-examples hidden><label for="auExample">Try a fictional claim</label><select id="auExample" data-au-example><option value="">Choose a fictional example</option></select></div><label for="auTitle">Claim title</label><input id="auTitle" name="title" required maxlength="300" autocomplete="off" placeholder="A short name for this claim"><label for="auMessage">Incoming message</label><textarea id="auMessage" name="message" required maxlength="100000" rows="7" placeholder="Paste the original message"></textarea><label class="au-upload" for="auFiles">Supporting files <span>Optional · original files stay available for inspection</span></label><input id="auFiles" name="files" type="file" multiple><div class="au-intake-controls"><button class="au-primary" type="submit">Start autonomous work <span aria-hidden="true">↗</span></button><button type="button" class="au-secondary" data-au-nav="work">Cancel</button></div><p class="au-form-status" role="status"></p></form></section><aside class="au-intake-aside"><p class="au-eyebrow">From evidence to outcome</p><ol class="au-intake-path"><li>Original sources</li><li>Verified facts</li><li>Process &amp; documents</li><li>Qualified knowledge</li></ol><p class="au-meta" data-au-service>Checking service availability…</p></aside></div>`;
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
      if (select.matches?.('[data-au-claim-filter]') && view === 'work') { collection.filter = select.value; refreshCollection(); return; }
      if (!select.matches?.('[data-au-example]') || view !== 'intake' || busy || pendingIntake || select.disabled || !/^\d+$/.test(select.value)) return;
      const packet = examples?.[Number(select.value)], form = host.querySelector('[data-au-intake]');
      if (!packet || !form) return;
      try { prefillExample(form,packet); form.querySelector('.au-form-status').textContent = 'Fictional example loaded. Start autonomous work when ready.'; }
      catch (error) { form.querySelector('.au-form-status').textContent = error.message; }
    }
    async function showKnowledge(writeHistory = true, pin = null) {
      leaveView();
      const fragment = pin ? `#autonomous/knowledge?knowledge=${key(pin.knowledge_id)}&version=${key(pin.version)}&sha256=${key(pin.knowledge_sha256 || '')}` : '#autonomous/knowledge';
      route(fragment,writeHistory);
      epoch++; const token = epoch; cancelPoll(); setView('knowledge'); nav('knowledge'); current = null; notice('Loading recorded knowledge…'); host.innerHTML = '';
      try {
        const results = await Promise.allSettled([request('/knowledge'),claimsLoaded ? Promise.resolve() : loadClaims(token)]);
        if (disposed || token !== epoch) return;
        if (results[0].status === 'rejected') throw results[0].reason;
        const data = results[0].value;
        host.innerHTML = knowledgeMarkup(data,claims); notice(''); focusTitle();
        if (pin) {
          const version = list(data.versions).find(item => String(item.knowledge_id || item.version_id) === String(pin.knowledge_id) && String(item.version || item.version_id) === String(pin.version) && (!pin.knowledge_sha256 || item.knowledge_sha256 === pin.knowledge_sha256));
          if (!version) { notice('The exact reused knowledge version is not available in this record.',true); return; }
          const row = [...host.querySelectorAll('[data-au-knowledge-identity]')].find(element => element.dataset.auKnowledgeIdentity === `${pin.knowledge_id}:${pin.version}`);
          if (row) { let parent = row.parentElement; while (parent && parent !== host) { if (parent.tagName === 'DETAILS') parent.open = true; parent = parent.parentElement; } row.setAttribute('data-pinned','true'); row.setAttribute('tabindex','-1'); row.focus({preventScroll:true}); row.scrollIntoView?.({block:'nearest',behavior:'instant'}); }
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
      if (!intake && !saved) return;
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
        if (intake) { pendingIntake = null; form.reset?.(); lockForm(form,false); } else { pendingArrival = null; arrivals.delete(operation.claimId); form.reset?.(); lockForm(form,false); }
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
      if (busy || !current || (action === 'pause' ? current.status !== 'running' : current.status !== 'deferred' || current.deferral?.code !== 'paused')) return;
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
      const body = container.querySelector('[data-au-source-content]'); body.innerHTML = '<p class="au-empty">Checking source identity…</p>';
      motion?.cancel();
      if (!dialog.open) dialog.showModal();
      try {
        const response = await request(`/sources/${key(saved.claim_id)}/${key(id)}/text`);
        const checked = await checkedSource(saved,descriptor,response,citation);
        if (disposed || token !== epoch || sourceToken !== sourceEpoch || !dialog.open) return;
        body.innerHTML = `<div class="au-source-meta"><span>${checked.source.complete ? 'Extracted text' : 'Extraction incomplete'}</span><a href="${h(base)}/sources/${key(saved.claim_id)}/${key(id)}" download="${h(descriptor.file_name || 'source')}">Download original</a></div>${!checked.source.complete ? `<p class="au-notice">${h(checked.source.reason || checked.source.limitation || 'This source does not have a complete text extraction.')}</p>` : ''}<pre class="au-source-body">${checked.span ? `${h(checked.span.before)}<mark tabindex="-1">${h(checked.span.quote)}</mark>${h(checked.span.after)}` : h(checked.source.text) || 'No readable text was extracted.'}</pre><details><summary>Source identity</summary><dl class="au-chain"><div><dt>Original bytes · SHA-256</dt><dd class="au-hash">${h(descriptor.sha256)}</dd></div><div><dt>Extracted text · SHA-256</dt><dd class="au-hash">${h(checked.source.text_sha256)}</dd></div></dl></details>`;
        body.querySelector('mark')?.scrollIntoView({block:'center'});
      } catch (error) { if (!disposed && token === epoch && sourceToken === sourceEpoch && dialog.open) body.innerHTML = `<p class="au-error" role="alert">${h(error.message)}</p><a href="${h(base)}/sources/${key(saved.claim_id)}/${key(id)}" download>Download original</a>`; }
    }
    function click(event) {
      const target = event.target.closest('button,[data-au-nav]'); if (!target || !container.contains(target)) return;
      if (target.hasAttribute('data-au-nav')) { if (busy) return; target.dataset.auNav === 'knowledge' ? showKnowledge() : target.dataset.auNav === 'intake' ? showIntake() : showWork(); }
      else if (target.hasAttribute('data-au-claim')) { if (!busy) openClaim(target.dataset.auClaim); }
      else if (target.hasAttribute('data-au-pause')) controlWork(target,'pause');
      else if (target.hasAttribute('data-au-resume')) controlWork(target,'resume');
      else if (target.hasAttribute('data-au-refresh-claims')) { const token = epoch; loadClaims(token).catch(error => { if (!disposed && token === epoch) notice(error.message,true); }); }
      else if (target.hasAttribute('data-au-knowledge')) { if (!busy) showKnowledge(true,{knowledge_id:target.dataset.auKnowledge,version:target.dataset.auVersion,knowledge_sha256:target.dataset.auKnowledgeSha}); }
      else if (target.hasAttribute('data-au-add-files')) setDetail('sources',true);
      else if (target.hasAttribute('data-au-detail')) setDetail(target.dataset.auDetail);
      else if (target.hasAttribute('data-au-back-process')) {
        const node = [...host.querySelectorAll('[data-au-node]')].find(el => el.dataset.auNode === selected);
        node?.focus({preventScroll:true}); node?.scrollIntoView({block:'center',behavior:'instant'});
      }
      else if (target.hasAttribute('data-au-node') || target.hasAttribute('data-au-select')) {
        selected = target.dataset.auNode || target.dataset.auSelect; detail = 'step'; renderClaim();
        if (target.hasAttribute('data-au-select')) { const node = [...host.querySelectorAll('[data-au-node]')].find(el => el.dataset.auNode === selected); node?.focus({preventScroll:true}); if (root.matchMedia?.('(max-width: 800px)').matches) node?.scrollIntoView({block:'nearest'}); else revealGraphNode(node); }
        else if (root.matchMedia?.('(max-width: 800px)').matches) {
          host.querySelector('[data-au-inspector-heading]')?.focus({preventScroll:true});
          host.querySelector('.au-inspector')?.scrollIntoView({block:'start',behavior:'instant'});
        }
      } else if (target.hasAttribute('data-au-source')) {
        let citation; try { citation = target.dataset.auCitation ? JSON.parse(target.dataset.auCitation) : null; } catch (_) { notice('The source reference is invalid.',true); return; }
        openSource(target.dataset.auSource,citation,target);
      } else if (target.hasAttribute('data-au-close')) dialog.close();
    }
    function input(event) {
      if (view === 'work' && event.target.matches?.('[data-au-claim-search]')) { collection.search = event.target.value; refreshCollection(); }
    }
    function closed() { (dialogReturn?.element?.isConnected && focusEligible(dialogReturn.element,dialogReturn.token) ? dialogReturn.element : focusTarget(dialogReturn?.token) || host.querySelector('[data-au-claim-title]'))?.focus({preventScroll:true}); dialogReturn = null; sourceEpoch++; }
    function visibility() { motion?.cancel(); if (!doc.hidden && view === 'claim') { disconnected = true; cancelPoll(); poll(); } }
    function keyboardInput(event) { if (event.key === 'Tab' || event.key?.startsWith('Arrow')) { keyboard=true;motion?.cancel(); } }
    function pointerInput() { keyboard=false; }
    function motionPreference() { if (reduced?.matches) motion?.cancel(); }
    doc.addEventListener('keydown',keyboardInput);container.addEventListener('pointerdown',pointerInput);reduced?.addEventListener?.('change',motionPreference);
    container.addEventListener('click',click); container.addEventListener('submit',submit); container.addEventListener('change',change); container.addEventListener('input',input); dialog.addEventListener('close',closed); doc.addEventListener('visibilitychange',visibility);
    root.addEventListener?.('hashchange',routeChanged); root.addEventListener?.('popstate',routeChanged);
    const resize = root.ResizeObserver ? new root.ResizeObserver(drawEdges) : null; resize?.observe(host);
    const controller = {openClaim,showWork,showIntake,showKnowledge,refresh:poll,destroy() { if (disposed) return; disposed = true; epoch++; cancelPoll(); motion?.cancel();root.removeEventListener?.('hashchange',routeChanged);root.removeEventListener?.('popstate',routeChanged);doc.removeEventListener('keydown',keyboardInput);container.removeEventListener('pointerdown',pointerInput);reduced?.removeEventListener?.('change',motionPreference); for (const controller of controllers) controller.abort(); resize?.disconnect(); container.removeEventListener('click',click); container.removeEventListener('submit',submit); container.removeEventListener('change',change); container.removeEventListener('input',input); dialog.removeEventListener('close',closed); doc.removeEventListener('visibilitychange',visibility); if (dialog.open) dialog.close(); mounts.delete(container); if (activeMount === controller) activeMount = null; container.innerHTML = ''; }};
    mounts.set(container,controller); activeMount = controller;
    routeChanged();
    return controller;
  }
  function destroy(container) { (container ? mounts.get(container) : activeMount)?.destroy(); }
  return {mount,destroy,demoAssetURL,checkedExamples,prefillExample,progressModel,progressMarkup,transitionPlan,animateTransition,mediaType,readState,layoutGraph,acceptEvents,eventIdentity,changedTargets,conditionFlags,checkedSource,graphMarkup,obligationMarkup,inspectorMarkup,workMarkup,knowledgeMarkup,claimsMarkup,collectionMarkup,matchingClaims,actionRows};
});
