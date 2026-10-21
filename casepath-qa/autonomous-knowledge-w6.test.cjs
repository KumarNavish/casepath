'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{gunzipSync}=require('node:zlib');
const ui=require('../casepath/assets/autonomous-workspace-v1.js');
const data=JSON.parse(gunzipSync(fs.readFileSync(path.join(__dirname,'fixtures/knowledge-w6.json.gz'))));
for(const entry of ui.knowledgeLibrary(data))test(`domain checklist preserves recorded definitions and deduplicates actual uses: ${entry.family}`,()=>{
 const v=entry.current,before=JSON.stringify(v),html=ui.knowledgeChecklistMarkup(v,data),cases=ui.checklistCases(v,data);
 assert.equal(cases.length,3);assert.ok(ui.knowledgeUses(v,ui.knowledgeLearningModel(data).uses).length>cases.length);
 for(const n of v.graph.nodes)assert.ok(html.includes(`data-au-checklist-step="${n.node_id}"`));
 for(const d of v.graph.document_catalog){assert.ok(html.includes(`data-au-checklist-document="${d.document_type}"`));assert.ok(html.includes(d.label));}
 for(const p of v.source_outcome.legal_predicates){assert.ok(html.includes(ui.deskLegalLabel(p.predicate_id)));assert.ok(html.includes(ui.deskLaw(p.rule_refs)));}
 for(const id of cases)assert.ok(html.includes(`data-au-claim="${id}"`));
 assert.doesNotMatch(html,/All legal tests met|Does not meet|data-status="(?:supported|failed)"|Riley Foster|Taylor Miller|CHF/);
 assert.equal(JSON.stringify(v),before);
 const mismatched={...data,uses:[]};assert.deepEqual(ui.checklistCases(v,mismatched),[]);
 assert.equal(ui.knowledgeChecklistMarkup({...v,qualification:{status:'rejected'}},data),'');
 const unavailable=ui.libraryEntryMarkup(entry,data,{pin:{knowledge_id:v.knowledge_id,version:999}});assert.match(unavailable,/exact saved version is unavailable/);assert.doesNotMatch(unavailable,/data-au-knowledge-checklist/);
});
test('article labels sort naturally without changing their record',()=>{
 const refs=['CO:259d','CO:259a','CO:259','CO:259a','CO:10','CO:2'],before=JSON.stringify(refs);
 assert.equal(ui.deskLaw(refs),'CO 2 · 10 · 259 · 259a · 259d');assert.equal(JSON.stringify(refs),before);
 const state={run_id:'run',graph:{family:'defect_mold_heating'},semantic_contexts:{run:{execution_mode:'deterministic_reference',rule_packs:[{family:'defect_mold_heating',legal_authority:[{article:'259d',text:'D'},{article:'259a',text:'A'},{article:'259',text:'Base'}]}]}}};
 const html=ui.legalBasisMarkup(state);assert.ok(html.indexOf('art. 259 ·')<html.indexOf('art. 259a'));assert.ok(html.indexOf('art. 259a')<html.indexOf('art. 259d'));
});
test('next-action symbols reflect only explicitly recorded document needs',()=>{
 assert.match(ui.deskNextStepMarkup({outcome:{missing_evidence:[]}}),/data-status="clear".*aria-hidden="true">✓/);
 assert.match(ui.deskNextStepMarkup({outcome:{missing_evidence:[{label:'Notice'}]}}),/data-status="missing".*aria-hidden="true">!/);
 assert.doesNotMatch(ui.deskNextStepMarkup({outcome:{}}),/data-status="clear"|✓/);
});
