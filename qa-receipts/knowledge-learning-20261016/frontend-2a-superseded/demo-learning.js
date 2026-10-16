  function recordedReuseMoment(state, trace, knowledge = {}) {
    if(!trace || trace.finished || trace.current?.kind!=='knowledge.reuse')return null;
    const use=list(state.knowledge_uses).findLast(row=>row.workflow_id===state.run_id && row.knowledge_id===trace.current.object.id && row.version===trace.current.input?.version);
    if(!use || !isHash(use.definition_sha256))return null;
    const event=[...list(trace.journal)].reverse().find(row=>row.kind==='knowledge.used' && row.seq<=state.revision && row.claim_id===state.claim_id && row.payload?.knowledge?.knowledge_id===use.knowledge_id && row.payload.knowledge.version===use.version && row.payload.knowledge.definition_sha256===use.definition_sha256);
    const context=state.semantic_contexts?.[state.run_id],pin=list(context?.compatible_knowledge).find(row=>row.knowledge_id===use.knowledge_id && row.version===use.version && row.rule_pack_sha256===use.rule_pack_sha256 && isHash(row.knowledge_sha256));
    if(!event || !pin || trace.current.input.knowledge_sha256!==pin.knowledge_sha256 || trace.current.input.definition_sha256!==use.definition_sha256)return null;
    const version=list(knowledge.versions).find(row=>knowledgePinMatches(row,{...use,knowledge_sha256:pin.knowledge_sha256}));
    const plan=trace.plannedProcess, planned=plan?.claim_id===state.claim_id && plan.procedure?.knowledge_id===use.knowledge_id && plan.procedure.version===use.version && plan.procedure.definition_sha256===use.definition_sha256 && plan.procedure.knowledge_sha256===pin.knowledge_sha256;
    const graph=version?.graph || (planned?plan.graph:null);
    if(!graph)return null;
    return {event,use,pin:{...use,knowledge_sha256:pin.knowledge_sha256},graph,recipes:version?.evidence_recipes || pin.evidence_recipes || []};
  }
  function recordedReuseMomentMarkup(moment) {
    if(!moment)return '';
    return `<section class="au-stage-knowledge-moment" data-au-knowledge-moment="${h(moment.event.event_sha256)}" data-au-knowledge-use="${h(moment.pin.knowledge_sha256)}"><p>Procedure reused · ${knowledgeLink(moment.pin,`Version ${moment.use.version} · ${String(moment.pin.knowledge_sha256).slice(0,10)}`)}</p><ol aria-label="Pinned procedure skeleton">${layoutGraph(moment.graph).nodes.map(node=>`<li>${h(name(node))}</li>`).join('')}</ol><div aria-label="Known evidence recipe slots">${list(moment.recipes).map(recipe=>`<span data-au-recipe-slot="${h(recipe.document_type)}">${h(words(recipe.document_type))} · known requirement</span>`).join('')}</div><p>Receiving-case source support is checked separately.</p><p>Recorded knowledge.used receipt ${recordButton(moment.event.event_sha256.slice(0,12),'event',String(moment.event.seq))}</p></section>`;
  }
