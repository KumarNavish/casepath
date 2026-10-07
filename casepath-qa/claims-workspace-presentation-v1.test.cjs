'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const view = require('../casepath/assets/claims-workspace-presentation-v1.js');
const hash = 'a'.repeat(64), rawHash = 'b'.repeat(64);
const detail = {message:{message_id:'message-one',body:'Customer account'},state:{binding:{source_documents:[{sha256:hash}]},intake_assessment:{policy_clause_refs:[]}},artifacts:[{artifact_id:'message-one',role:'customer_message',sha256:rawHash}]};
const projectionRef = {source_id:'message-one.message-body-projection',source_version:'casepath.message-body-projection/1.0.0',source_sha256:hash};
test('provisional plan coverage never certifies claim readiness',()=>{
 assert.equal(view.readiness({readiness_state:'decision_ready',readiness_scope:'provisional_plan'}),'Plan covered · review needed');
});
test('a conflicting record is shown independently of its unknown class',()=>{
 assert.equal(view.evidenceStatus({evidence_class:'unknown',raw_status:'conflicting'}),'Conflicting information');
});
test('an uncertain action outcome takes precedence over readiness',()=>{
 assert.equal(view.readiness({failure_or_unknown_effect:true,readiness_state:'decision_ready'}),'Action needs checking');
});
test('an unresolved requirement without an action calls for handler review',()=>{
 assert.equal(view.copy('mandatory evidence is unresolved and no bounded action remains'),'The evidence remains unresolved. A handler must review it before the process can advance.');
});
test('HTML in source material is escaped',()=>{
 assert.equal(view.h('<script>"&'), '&lt;script&gt;&quot;&amp;');
});
test('correction summaries do not expose normalized branch identifiers',()=>{
 const text=view.semanticText({fact_state:'known',normalized_value:'lt_e01',evidence_status:'provided_sufficient',explanation:'A fixed-version server interpreter'});
 assert.equal(text,'Established · Sufficient evidence');
});
test('original byte-matched source is linked',()=>{
 assert.equal(view.sourceArtifactIndex({source_id:'message-one',source_sha256:rawHash},detail),0);
});
test('artifact identifiers alone cannot bind altered source bytes',()=>{
 assert.equal(view.sourceArtifactIndex({source_id:'message-one',source_sha256:'c'.repeat(64)},detail),-1);
});
test('a registered message projection links to its original message',()=>{
 assert.equal(view.sourceArtifactIndex(projectionRef,detail),0);
});
test('an unregistered projection hash cannot link to an original',()=>{
 assert.equal(view.sourceArtifactIndex({...projectionRef,source_sha256:'d'.repeat(64)},detail),-1);
});
test('a projection from another claim cannot inherit the original link',()=>{
 assert.equal(view.sourceArtifactIndex({...projectionRef,source_id:'other.message-body-projection'},detail),-1);
});
const item=(evidenceClass,mandatory)=>({evidence_item_id:'item',title:'First question',fact_state:'unknown',raw_status:evidenceClass,evidence_class:evidenceClass,mandatory_now:mandatory,current_path:mandatory});
const loop=(id,revision,items,observations=[])=>({claim_id:id,revision,loop_state:{observations},operational_projection:{evidence_items:items,readiness_state:'blocked',pending_evidence_count:items.filter(i=>i.mandatory_now).length,current_process:{node_title:'Current question'}}});
test('replanning distinguishes resolved and newly active requirements',()=>{
 const before=loop('one',2,[item('missing',true)]);
 const after=loop('one',4,[item('received',false)],[{}]);
 const delta=view.compareLoops(before,after);
 assert.equal(delta.accepted,true);assert.equal(delta.changes.length,1);
 assert.equal(delta.changes[0].wasRequired,true);assert.equal(delta.changes[0].isRequired,false);
});
test('no cross-claim replan comparison is presented',()=>{
 assert.equal(view.compareLoops(loop('one',2,[]),loop('two',4,[])),null);
});
test('a rejected source is never described as a new observation',()=>{
 const delta=view.compareLoops(loop('one',2,[item('missing',true)]),loop('one',2,[item('missing',true)]));
 assert.equal(delta.accepted,false);assert.equal(delta.changes.length,0);
 assert.match(view.changeMarkup(delta),/Evidence not accepted/);
});
test('queue activation is confined to queue rows, not the claim panel',()=>{
 const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'../casepath/assets/claims-workspace-v1.js'),'utf8');
 assert.doesNotMatch(source,/panel\.dataset\.claimId/);
 assert.doesNotMatch(source,/root\.querySelectorAll\('\[data-claim-id\]'\)/);
});
test('scrollable source text remains reachable by keyboard',()=>{
 const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'../casepath/assets/claims-workspace-presentation-v1.js'),'utf8');
 assert.match(source,/class="cw-message(?: [^"]+)?" tabindex="0"/);
});
test('PDFs open the verified original instead of an unusable sandboxed plug-in',()=>{
 const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'../casepath/assets/claims-workspace-v1.js'),'utf8');
 assert.match(source,/data-open-original-pdf/);
 assert.match(source,/rel="noopener noreferrer"/);
 assert.doesNotMatch(source,/<iframe class="cw-document-preview" sandbox=""/);
});
test('source text has no duplicated focus attributes',()=>{
 for(const name of ['claims-workspace-presentation-v1.js','claims-workspace-v1.js']) {
  const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'../casepath/assets/'+name),'utf8');
  assert.doesNotMatch(source,/tabindex="0" tabindex="0"/);
 }
});
const assessment={language:'en',next_step:'Ask for the receipt date.',noticed:[],conflicts:[],candidate_deadline:null,conditions:{termination_received:{verdict:'true',quote:'My form arrived on Monday'}},steps:[
 {node_id:'done',label:'Capture notice details',state:'done',condition_chips:[],authority:null},
 {node_id:'now',label:'Preserve the deadline',state:'active',condition_chips:[{condition_flag:'termination_received',label:'termination received',verdict:'true',quote:'My form arrived on Monday'}],authority:{article:'Art. 273'}},
 {node_id:'later',label:'Check service',state:'not_reached',condition_chips:[],authority:null},
],documents:[
 {document_type:'proof_of_receipt',label:'Proof of receipt',route_state:'needed_now',required_at_node_ids:['now'],held_files:[],authority:{article:'Art. 273'}},
 {document_type:'spouse_notice_copy',label:'Separate spouse notice',route_state:'held_not_reviewed',required_at_node_ids:['later'],held_files:[{file_name:'Spouse notice.pdf'}],authority:{article:'Art. 266n'}},
]};
const assessedDetail={...detail,state:{...detail.state,intake_assessment:{claim_assessment:assessment}}};
test('why chain uses distinct need, step, quote and article',()=>{
 const markup=view.canvasTrace(null,assessedDetail,'now');
 assert.match(markup,/Proof of receipt/);
 assert.match(markup,/Preserve the deadline/);
 assert.match(markup,/My form arrived on Monday/);
 assert.match(markup,/Art. 273/);
 const values=[...markup.matchAll(/<strong(?: [^>]*)?>([^<]*)<\/strong>/g)].map(match=>match[1]);
 assert(values.every((value,index)=>index===0||value!==values[index-1]));
});
test('graph next-action why follows its focus and actual dependencies, not a legacy selection',()=>{
 const graph={...assessment,process_graph_sha256:hash,focus_node_id:'permission',next_step:'Verify handling authority',
   nodes:[{node_id:'permission',label:'Verify handling authority',meaning:'Confirm who may handle this claim.',condition:{const:'true'},blocked_by:[]},
          {node_id:'now',label:'Preserve the deadline',blocked_by:['permission']}],
   steps:[...assessment.steps,{node_id:'permission',label:'Verify handling authority',state:'active',condition_chips:[]}],
   edges:[{source_node_id:'permission',target_node_id:'now',relation:'requires',condition_verdict:'true'}]};
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:assessment}},{detail:assessedDetail,canvasNodeId:assessment.steps[0].node_id,causal:{effective_assessment:graph,evaluation:graph}});
 const why=markup.match(/<details class="cp-a-why"[\s\S]*?<\/details>/)[0];
 assert.match(why,/data-selected-node="permission"/);
 assert.match(view.canvasTrace(null,assessedDetail,assessment.steps[0].node_id,graph),/data-selected-node="permission"/);
 assert.match(why,/Verify handling authority/);
 assert.match(why,/Confirm who may handle this claim\./);
 assert.match(why,/Always applies/);
 assert.match(why,/Required before<\/small><strong>Preserve the deadline/);
 assert.doesNotMatch(why,/Capture notice details|Proof of receipt|My form arrived on Monday|termination received|Art\. 273/);
 graph.inconsistent_completed_node_ids=['now'];graph.next_step='Review the completed step: Preserve the deadline.';
 const review=view.workbench(null,{intake_assessment:{claim_assessment:assessment}},{detail:assessedDetail,causal:{effective_assessment:graph,evaluation:graph}}).match(/<details class="cp-a-why"[\s\S]*?<\/details>/)[0];
 assert.match(review,/data-selected-node="now"/);assert.match(review,/Waiting for<\/small><strong>Verify handling authority/);
});
test('canvas shows all steps and separates needed from held documents',()=>{
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:assessment}},{detail:assessedDetail});
 assert.match(markup,/Capture notice details/);
 assert.match(markup,/Preserve the deadline/);
 assert.match(markup,/Check service/);
 assert.match(markup,/data-path-state="active"/);
 assert.match(markup,/data-condition-state="true"/);
 assert.match(markup,/data-need-state="now"/);
 assert.match(markup,/data-route-state="held_not_reviewed"/);
 assert.match(markup,/Spouse notice copy/);
 assert.doesNotMatch(markup,/All steps|data-workbench-tab/);
});
test('assessed claim has one next action and a source-only record control',()=>{
 const oldAction={title:'Capture issuer, receipt and end date',action_sha256:hash,evidence_item_id:'old-item'};
 const savedLoop={outcome:'blocked',loop_state:{selected_action:oldAction,checklist:{items:[]}},operational_projection:{readiness_scope:'current',evidence_items:[],pending_evidence_count:0}};
 const markup=view.workbench(savedLoop,{intake_assessment:{claim_assessment:assessment}},{detail:assessedDetail});
 assert.match(markup,/Ask for the receipt date/);
 assert.match(markup,/Source record/);
 assert.doesNotMatch(markup,/id="cwLoopCommit"/);
 assert.doesNotMatch(markup,/Capture issuer, receipt and end date|supporting evidence is still missing/i);
});
test('noticed dates and both sides of a conflict open exact source spans',()=>{
 const changed={...assessment,noticed:[{text:'Tenant notice: 30. Juni',source_id:'tenant-pdf',source_kind:'pdf_text'}],conflicts:[{fact:'termination end date',message:'The two notices give different end dates.',sources:[{artifact_id:'tenant-pdf',quote:'30. Juni',value:'30. Juni'},{artifact_id:'spouse-pdf',quote:'31. Juli',value:'31. Juli'}]}]};
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:changed}},{detail:assessedDetail});
 assert.match(markup,/class="cp-a-review-ready" data-status="completed"/);
 assert.match(markup,/data-noticed-source="tenant-pdf" data-noticed-quote="30. Juni"/);
 assert.match(markup,/data-noticed-source="spouse-pdf" data-noticed-quote="31. Juli"/);
 assert.doesNotMatch(markup,/Review saved/);
});
test('noticed facts name the party, start date and PDF page without losing source spans',()=>{
 const changed={...assessment,noticed:[
  {text:'Robin Foster',source_id:'tenant-pdf',source_kind:'pdf_text',page:1,fact_kind:'named_party_candidate'},
  {text:'Casey Foster',source_id:'spouse-pdf',source_kind:'pdf_text',page:1,fact_kind:'named_party_candidate'},
  {text:'19 August 2025',source_id:'message-one',source_kind:'customer_message',fact_kind:'reported_date'},
  {text:'Tenant_termination_notice.pdf: 30. Juni',source_id:'tenant-pdf',source_kind:'pdf_text',page:1},
 ],attachment_pages:[{artifact_id:'tenant-pdf',file_name:'Tenant_termination_notice.pdf'},{artifact_id:'spouse-pdf',file_name:'Spouse_termination_notice.pdf'}]};
 const source={...assessedDetail,message:{...assessedDetail.message,body:'As far as I remember, it started around 19 August 2025.'}};
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:changed}},{detail:source});
 for(const [name,value] of [['Tenant','Robin Foster'],['Spouse','Casey Foster'],['Started','19 August 2025'],['Tenant notice, page 1','end date 30 June']])assert.match(markup,new RegExp(name+'<\\/span>.*>'+value.replaceAll(' ','\\s*')));
 assert.match(markup,/data-noticed-source="tenant-pdf" data-noticed-quote="30. Juni"/);
});
test('path chips name the transition whose verdict they show',()=>{
 const step={node_id:'later',label:'Build the dated timeline',state:'not_reached',condition_chips:[{condition_flag:'health_effects',label:'no immediate health escalation',verdict:'false',quote:'Mein Sohn hustet mehr'}],authority:null};
 const changed={...assessment,conditions:{...assessment.conditions,health_effects:{verdict:'false',quote:'Mein Sohn hustet mehr'}},steps:[...assessment.steps.slice(0,-1),step]};
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:changed}},{detail:assessedDetail});
 assert.match(markup,/Health effects <em>false<\/em>/);
});
test('candidate deadlines display the paragraph from the cited authority',()=>{
 const changed={...assessment,candidate_deadline:{date:null,question:'When did the notice arrive?',authority:{article:'Art. 273',authority_id:'or-art-273-para1-20260101-de'}}};
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:changed}},{detail:assessedDetail});
 assert.match(markup,/Candidate deadline · Art\. 273 Abs\. 1/);
 assert.match(markup,/When did the notice arrive/);
});
test('resize callbacks do not measure a replaced claim header',()=>{
 const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'../casepath/assets/claims-workspace-v1.js'),'utf8');
 assert.match(source,/measuredHeader\?\.isConnected && panel\.contains\(measuredHeader\)/);
 assert.doesNotMatch(source,/panel\.querySelector\('\.cw-detail-head'\)\.getBoundingClientRect/);
});

test('minimal claim presentation guards',()=>{
 const fs=require('node:fs'),path=require('node:path');
 const css=fs.readFileSync(path.join(__dirname,'../casepath/assets/claims-workspace-presentation-v1.css'),'utf8');
 const agentCss=fs.readFileSync(path.join(__dirname,'../casepath/assets/agent-work-v1.css'),'utf8');
 assert.doesNotMatch(css,/text-transform\s*:\s*uppercase|\.cp-card\b/);
 assert.doesNotMatch(agentCss,/\.cp-a-[^{}]*\{[^}]*text-transform\s*:\s*uppercase/);
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:assessment}},{detail:assessedDetail});
 const top=markup.split('<footer class="cp-a-footer"')[0];
 const regions=[...top.matchAll(/<(?:section)\b[^>]*class="(cp-a-(?:next|review|path|questions|needs|draft))"/g)].length+1;
 assert(regions<=9,`claim has ${regions} regions`);
 assert.equal([...top.matchAll(/<button\b/g)].length,1);
 assert.doesNotMatch(view.packetLibrary(assessedDetail),/<button\b/);
 const visibleText=top.replace(/<[^>]*>/g,' ').replace(/\s+/g,' ');
 assert.doesNotMatch(visibleText,/deterministic|assessment|journal|projection|authority|saved claim record|workspace/i);
 assert.doesNotMatch(markup,/class="[^"]*cp-card|class="[^"]*bordered-panel/);
});
test('queue groups claims as list items without table headers or chevrons',()=>{
 const markup=view.queueRows([{claim_id:'one',subject:'Test claim',received_at:'2026-09-24',language:'en',owner:null,triage:{waiting_on:'Customer',noticed_fact:'The notice is incomplete.',next_step:'Ask for the missing page.'}}]);
 assert.match(markup,/<h2 class="cp-triage-group">Waiting on customer/);
 assert.match(markup,/<ul><li tabindex="0" data-claim-id="one"/);
 assert.doesNotMatch(markup,/<table|<th|cp-row-chevron/);
});

test('an unavailable process exposes recovery and withholds a potentially stale draft',()=>{
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:assessment}},{detail:assessedDetail,causal:{error:'Offline'},causalMarkup:'<section>Process unavailable</section>',draft:{latest:{}}});
 assert.match(markup,/id="cpReviewStep"\s*>Open process/);
 assert.match(markup,/Open Process to retry before preparing a request/);
 assert.doesNotMatch(markup,/id="cwDraftOpen"|id="cpDraftPanel"/);
});

test('the causal workbench preserves the What-if sandbox beside the working graph',()=>{
 const working={...assessment,conditions:{termination_received:{verdict:'false',quote:'An independent working-process edit'}},next_step:'Review the working graph.'};
 const scenario={...assessment,conditions:{termination_received:{verdict:'unresolved'}}};
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:assessment}},{detail:assessedDetail,
  causal:{effective_assessment:working,evaluation:working},causalMarkup:'<section id="working-graph">Current causal graph</section>',
  whatIf:{flag:'termination_received',verdict:'unresolved',result:{scenario,changes:[{sign:'−',label:'Receipt proof',reason:'Receipt is not yet confirmed.'}]}},
  handlerDrafts:{'condition:termination_received':'Please check the original receipt.'}});
 const process=markup.match(/<section id="cpPane-process"[\s\S]*?(?=<section id="cpPane-documents")/)[0];
 assert.match(process,/id="working-graph"/);
 assert.equal((process.match(/id="cpWhatIfPanel"/g)||[]).length,1);
 assert.match(process,/Accepted intake reading: Applies · “My form arrived on Monday”/);
 assert.doesNotMatch(process,/Where it stands|Saved:|Study A|research\.html|An independent working-process edit/);
 assert.match(process,/This preview leaves the working process unchanged\./);
 for(const value of ['true','false','unresolved'])assert.match(process,new RegExp('data-what-if-value="'+value+'"'));
 assert.match(process,/data-what-if-close/);
 assert.match(process,/id="cwHandlerConditionForm"/);
 assert.match(process,/Please check the original receipt\./);
 assert.match(process,/<button type="submit" >Record as handler assessment<\/button>/);
 assert.match(process,/Receipt is not yet confirmed\./);
 assert.match(markup,/Review the working graph\./);
 assert.doesNotMatch(markup,/data-condition-state="unresolved"/);
});

test('draft actions precede the editable letter without changing saved line semantics',()=>{
 const saved='Dear customer,\n## Please send\n- Original notice';
 const edited='Dear <reviewed customer>,\n## Please send\n- Original notice\nHandler wording still being edited.';
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:assessment}},{detail:assessedDetail,
  draft:{latest:{language:'en',body_markdown:saved}},draftEdit:edited});
 const draft=markup.match(/<section class="cp-a-draft"[\s\S]*?<\/section>/)[0];
 assert.ok(draft.indexOf('class="cp-draft-actions"')<draft.indexOf('id="cwDraftBody"'));
 assert.match(draft,/role="group" aria-label="Draft actions"/);
 assert.match(draft,/id="cwDraftForm"/);
 assert.equal((draft.match(/data-draft-copy/g)||[]).length,1);
 assert.equal((draft.match(/data-draft-export="markdown"/g)||[]).length,1);
 assert.match(draft,/<button type="submit">Save edits<\/button>/);
 assert.match(draft,/Saving edits keeps it as an unsent draft\./);
 assert.match(draft,/Dear &lt;reviewed customer&gt;,/);
 assert.match(draft,/data-draft-prefix="## ">Please send/);
 assert.match(draft,/data-draft-prefix="- ">Original notice/);
 assert.match(draft,/Handler wording still being edited\./);
 assert.equal(saved,'Dear customer,\n## Please send\n- Original notice');
});

test('What-if names actual requirement and applicability transitions while retaining typed values',()=>{
 const saved={...assessment,conditions:{...assessment.conditions,family_home:{verdict:'true',quote:'A separate spouse notice was reported.'}}};
 const result={from_verdict:'false',to_verdict:'unresolved',scenario:saved,changes:[
  {kind:'document',sign:'?',label:'Separate spouse notice',from:'held_not_reviewed',to:'held_behind_question',reason:'family-home service set to unresolved',authority:{article:'Art. 266n'}},
  {kind:'document',sign:'+',label:'Receipt proof',from:'needed_later',to:'needed_now',reason:'family-home service set to unresolved'},
  {kind:'step',sign:'?',label:'Check separate service <unconfirmed>',from:'true',to:'unresolved',reason:'family-home service set to unresolved'},
  {kind:'document',sign:'?',label:'Unrecognized requirement state',from:'new_state',to:'optional'},
 ]};
 const original=JSON.stringify(result);
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:saved}},{detail:assessedDetail,
  causal:{effective_assessment:assessment},causalMarkup:'<section>Working graph</section>',
  whatIf:{flag:'family_home',verdict:'unresolved',result}});
 const panel=markup.match(/<section class="cp-a-what-if"[\s\S]*?<\/section>/)[0];
 assert.match(panel,/data-what-if-value="true"[^>]*>Applies<\/button>/);
 assert.match(panel,/data-what-if-value="false"[^>]*>Does not apply<\/button>/);
 assert.match(panel,/data-what-if-value="unresolved" aria-pressed="true">Unresolved<\/button>/);
 assert.match(panel,/Condition comparison: Does not apply → Unresolved/);
 assert.match(panel,/Document requirement: Received, not reviewed → Requirement unresolved · Art\. 266n/);
 assert.match(panel,/Document requirement: Needed later → Needed now/);
 assert.match(panel,/Process step applicability: Applies → Unresolved/);
 assert.match(panel,/Document requirement: Unknown requirement state → Optional/);
 assert.match(panel,/Check separate service &lt;unconfirmed&gt;/);
 assert.doesNotMatch(panel,/<strong>\?|family-home service set to unresolved|<unconfirmed>/);
 assert.match(panel,/id="cwHandlerConditionForm"/);
 assert.equal(JSON.stringify(result),original);
});

test('paired conflicts retain exact original spans and escaped values',()=>{
 const changed={...assessment,conflicts:[{message:'The dates differ.',sources:[{artifact_id:'tenant-pdf',quote:'30. Juni',value:'30. Juni'},{artifact_id:'spouse-pdf',quote:'31. Juli <script>',value:'31. Juli <script>'}]}],attachment_pages:[{artifact_id:'tenant-pdf',file_name:'Tenant_notice.pdf'},{artifact_id:'spouse-pdf',file_name:'Spouse_notice.pdf'}]};
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:changed}},{detail:assessedDetail});
 assert.match(markup,/aria-label="Conflicting source values"/);
 assert.match(markup,/Tenant notice.pdf/);
 assert.match(markup,/data-noticed-source="tenant-pdf" data-noticed-quote="30. Juni"/);
 assert.match(markup,/31 July &lt;script&gt;/);
 assert.doesNotMatch(markup,/<script>|Notice invalid|Deadline expired/);
});
test('document visuals distinguish received from established without changing requirement links',()=>{
 const changed={...assessment,process_graph_sha256:hash,documents:[...assessment.documents,{document_type:'lease_contract',label:'Lease',route_state:'established',required_at_node_ids:['now'],held_files:[]}]};
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:assessment}},{detail:assessedDetail,causal:{effective_assessment:changed,evaluation:changed}});
 const received=markup.match(/<li data-route-state="held_not_reviewed">[\s\S]*?<\/li>/)[0];
 assert.match(received,/Received · review needed/);
 assert.doesNotMatch(received,/Established|cp-icon[^>]*>[^<]*check/);
 assert.match(received,/data-document-node="later"/);
 assert.match(markup,/<span class="cp-doc-state">Established<\/span>/);
});

test('document timing never hides an insufficient source review',()=>{
 const changed={...assessment,documents:[{...assessment.documents[0],route_state:'needed_now',review_state:'insufficient'}]};
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:changed}},{detail:assessedDetail});
 assert.match(markup,/data-route-state="needed_now"/);assert.match(markup,/Received · insufficient/);
});

test('repeated source spans are not presented as unequal values',()=>{
 const first={artifact_id:'tenant-pdf',quote:'30. Juni',value:'30. Juni'},second={artifact_id:'spouse-pdf',quote:'31. Juli',value:'31. Juli'};
 const render=sources=>view.workbench(null,{intake_assessment:{claim_assessment:{...assessment,conflicts:[{message:'Dates differ.',sources}]}}},{detail:assessedDetail});
 const pair=render([first,first,second]);assert.equal((pair.match(/class="cp-source-fork"/g)||[]).length,1);
 const repeated=render([first,{...first,artifact_id:'third-pdf'}]);assert.doesNotMatch(repeated,/class="cp-source-fork"/);
 const many=render([first,second,{artifact_id:'third-pdf',quote:'1 August',value:'1 August'}]);assert.match(many,/data-paired="false"/);assert.doesNotMatch(many,/class="cp-source-fork"/);
});
