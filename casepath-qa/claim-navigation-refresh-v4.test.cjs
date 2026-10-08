'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../casepath/assets/claims-workspace-v1.js'),'utf8');
const presentation=require('../casepath/assets/claims-workspace-presentation-v1.js');

// A small connected tree exercises the real render/read/navigation functions.
// No timers, provider, browser, API server or external DOM dependency is needed.
function fixture({mobile=false}={}){
 const document={activeElement:null};
 const dataName=name=>name.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase());
 class Node{
  constructor(tag='div'){this.tagName=tag.toUpperCase();this.childNodes=[];this.parentNode=null;this.attrs={};this.dataset={};this.style={setProperty(){}};this.listeners={};this.scrollTop=0;this.value='';if(tag==='template')this.content=new Node('fragment');}
  get parentElement(){return this.parentNode;}
  get isConnected(){return this===document.body||Boolean(this.parentNode?.isConnected);}
  get id(){return this.attrs.id||'';}
  get className(){return this.attrs.class||'';}
  get open(){return this.hasAttribute('open');}
  set open(value){if(value)this.attrs.open='';else delete this.attrs.open;}
  setAttribute(name,value){this.attrs[name]=String(value);if(name.startsWith('data-'))this.dataset[dataName(name)]=String(value);if(name==='value')this.value=String(value);}
  hasAttribute(name){return Object.hasOwn(this.attrs,name);}
  getAttribute(name){return this.attrs[name]??null;}
  removeAttribute(name){delete this.attrs[name];}
  append(...nodes){for(const node of nodes){if(node.tagName==='FRAGMENT'){this.append(...node.childNodes);continue;}node.remove();this.childNodes.push(node);node.parentNode=this;}}
  remove(){if(!this.parentNode)return;const parent=this.parentNode;parent.childNodes.splice(parent.childNodes.indexOf(this),1);this.parentNode=null;if(this.contains(document.activeElement))document.activeElement=document.body;}
  replaceWith(node){const parent=this.parentNode,index=parent.childNodes.indexOf(this);node.remove();this.remove();parent.childNodes.splice(index,0,node);node.parentNode=parent;}
  contains(node){return this===node||this.childNodes.some(child=>child.contains(node));}
  matches(selector){
   if(selector.includes(','))return selector.split(',').some(part=>this.matches(part));
   const last=selector.trim().split(/\s+/).at(-1);
   if(last.startsWith('#'))return this.id===last.slice(1);
   if(last.startsWith('.'))return this.className.split(' ').includes(last.slice(1));
   const tag=last.match(/^[a-z]+/i)?.[0];if(tag&&this.tagName!==tag.toUpperCase())return false;
   const attrs=[...last.matchAll(/\[([^\]=]+)(?:="?([^\]"]+)"?)?\]/g)];
   return Boolean(tag||attrs.length)&&attrs.every(([,name,value])=>this.hasAttribute(name)&&(value===undefined||this.getAttribute(name)===value));
  }
  querySelectorAll(selector){const result=[];for(const node of this.childNodes){if(node.matches(selector))result.push(node);result.push(...node.querySelectorAll(selector));}return result;}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
  closest(selector){return this.matches(selector)?this:this.parentNode?.closest(selector)||null;}
  set innerHTML(html){const root=this.content||this;for(const child of [...root.childNodes])child.remove();parse(html,root);}
  insertAdjacentHTML(position,html){assert.equal(position,'afterbegin');const fragment=new Node('fragment');parse(html,fragment);for(const child of [...fragment.childNodes].reverse()){child.remove();this.childNodes.unshift(child);child.parentNode=this;}}
  addEventListener(type,fn){this.listeners[type]=fn;}
  focus(){if(this.isConnected)document.activeElement=this;}
  showModal(){this.open=true;}
  getBoundingClientRect(){return {height:96};}
 }
 function parse(html,root){
  const stack=[root];for(const match of html.matchAll(/<\/?([a-z][\w-]*)\b([^>]*)>/gi)){
   if(match[0].startsWith('</')){stack.pop();continue;}
   const node=new Node(match[1]);for(const attr of match[2].matchAll(/([\w-]+)(?:="([^"]*)")?/g))node.setAttribute(attr[1],attr[2]??'');
   stack.at(-1).append(node);if(!['input','br','hr'].includes(match[1]))stack.push(node);
  }
 }
 document.body=new Node('body');document.activeElement=document.body;document.createElement=tag=>new Node(tag);
 const panel=new Node();panel.setAttribute('id','cwDetailPanel');document.body.append(panel);
 const storage=new Map(),events=[],reads=[];
 const assessment={domain_scores:[],policy_template:{title:'Saved policy'},current_node:{label:'Deadline'},outgoing_branches:[],policy_clause_refs:[],claim_assessment:{conditions:{}}};
 const detail={state:{claim_id:'claim-a',revision:4,state_sha256:'state-a',workflow_state:'in_review',owner:'Original handler',intake_assessment:assessment,binding:{language:'en'}},artifacts:[],message:{body:'Original customer message.'}};
 const c={document,root:document.body,mobileWorkbench:{matches:mobile},URLSearchParams,CSS:{escape:value=>value},location:{hash:'#claim=claim-a'},
  state:{detail,items:[{claim_id:'claim-a',state_sha256:'state-a'}],detailEpoch:1,claimSection:'process',sectionScroll:{},motion:0},
  window:{dispatchEvent:event=>events.push(event),CasePathMotion:{enter(){}},CasePathAgentClaim:{session:()=>({sources:[]})}},
  sessionStorage:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)},
  $:selector=>selector==='#cwDetailPanel'?panel:document.body.querySelector(selector),
  ui:{detail:(_detail,_loop,opts)=>`<header class="cw-detail-head"><div class="cp-claim-title" data-owner="${_detail.state.owner}"><h1>${_detail.state.owner}</h1></div><nav class="cp-claim-tabs">${['overview','process','documents'].map(name=>`<button id="cpTab-${name}" data-claim-section="${name}"></button>`).join('')}</nav></header>${presentation.sourceRecord(_detail)}<div class="cp-work-column"><main class="cp-a-main">${['overview','process','documents'].map(name=>`<section id="cpPane-${name}" data-claim-pane="${name}"></section>`).join('')}</main><form data-apply-memory="memory-a"><textarea name="note"></textarea></form></div><dialog id="cpOwnerDialog"><form id="cwOwnerForm"><input id="cwOwnerInput" value="${opts.ownerValue}"></form></dialog>`},
  storedCommandIdentity:()=>null,clearCommandIdentity(){},esc:String,label:String,loopWorkbenchMarkup:()=>'',priorityList:()=>'',
  activeDetailContext:()=>({claimId:c.state.detail.state.claim_id,epoch:c.state.detailEpoch}),
  isActiveDetail:context=>context.claimId===c.state.detail.state.claim_id&&context.epoch===c.state.detailEpoch,
  verifyCausalResponse:async value=>value,loadCausalEditor:async()=>{},
  request:()=>new Promise(resolve=>reads.push(resolve)),
  ResizeObserver:class{observe(){}disconnect(){}},CustomEvent:class{constructor(type,opts){this.type=type;this.detail=opts.detail;}},
 };
 for(const name of ['assignOwner','bindNativeInvestigationActions','restoreSourceSelection','syncReviewerMode','renderGuide','revealFragmentLibrary','applyInspectorState','setAdjacentClaims','syncReasoning'])c[name]=()=>{};
 vm.createContext(c);
 for(const [from,to] of [['  function claimScrollRegion(', '  function savePresentation('],['  function renderDetail(', '  async function verifyCausalResponse('],['  let causalRead;', '  async function reloadCausalProcess('],['  function savePresentation(', '  function syncReasoning('],['  function selectClaimSection(', '  function showWorkspaceSection('],['  function restoreWorkbenchPresentation(', "  compactWorkbench.addEventListener('change'"],['  function presentationClick(', '  function workspaceKeyboard(']]){
  assert.ok(source.indexOf(from)>=0&&source.indexOf(to)>source.indexOf(from));vm.runInContext(source.slice(source.indexOf(from),source.indexOf(to)),c);
 }
 return {c,panel,document,detail,storage,events,reads,async arrive(){const pending=c.loadCausalProcess(c.activeDetailContext());reads.shift()({claim_id:c.state.detail.state.claim_id,workspace_revision:4,workspace_state_sha256:'state-a'});await pending;}};
}

test('a cold restored Process claim keeps tab buttons connected while the graph arrives',async()=>{
 const f=fixture(),{c,panel}=f;
 c.renderDetail(f.detail);assert.equal(f.reads.length,1);
 const pressed=panel.querySelector('#cpTab-overview'),header=panel.querySelector('.cw-detail-head');pressed.focus();
 await f.arrive();
 // A refresh between pointerdown and pointerup must not remove the activation
 // target. The browser cannot deliver its normal click to an obsolete button.
 assert.equal(pressed.isConnected,true);assert.equal(panel.querySelector('#cpTab-overview'),pressed);
 assert.equal(panel.querySelector('.cw-detail-head'),header);assert.equal(f.document.activeElement,pressed);
 assert.equal(c.presentationClick(pressed),true);
 assert.equal(c.state.claimSection,'overview');assert.equal(panel.querySelector('#cpPane-overview').hidden,false);
 c.renderDetail(f.detail);
 assert.equal(c.state.claimSection,'overview');assert.equal(panel.querySelector('#cpPane-process').hidden,true);
 assert.equal(JSON.parse(f.storage.get('casepath:presentation:claim-a')).claimSection,'overview');
});

test('a selected tab survives graph arrival and later refreshes without losing draft input focus',async()=>{
 const f=fixture(),{c,panel}=f;c.renderDetail(f.detail);
 c.selectClaimSection('documents');const tab=panel.querySelector('#cpTab-documents');tab.focus();
 await f.arrive();assert.equal(c.state.claimSection,'documents');assert.equal(f.document.activeElement,tab);
 const owner=panel.querySelector('#cwOwnerInput');panel.querySelector('#cpOwnerDialog').open=true;
 owner.value='Unsaved handler';owner.focus();
 const note=panel.querySelector('[data-apply-memory] textarea');note.value='Keep my explanation';
 const column=panel.querySelector('.cp-work-column');column.scrollTop=157;
 c.renderDetail({...f.detail,state:{...f.detail.state,owner:'New saved handler'}});
 assert.equal(panel.querySelector('#cwOwnerInput').value,'Unsaved handler');
 assert.equal(f.document.activeElement,panel.querySelector('#cwOwnerInput'));
 assert.equal(panel.querySelector('[data-apply-memory] textarea').value,'Keep my explanation');
 assert.equal(panel.querySelector('.cp-claim-title').dataset.owner,'New saved handler');
 assert.equal(panel.querySelector('.cp-work-column').scrollTop,157);assert.equal(c.state.claimSection,'documents');
});

test('mobile graph arrival and refresh preserve page position and the focused unsaved owner',async()=>{
 const f=fixture({mobile:true}),{c,panel}=f;c.renderDetail(f.detail);
 c.selectClaimSection('documents');panel.scrollTop=236;
 f.document.body.listeners.scroll({target:panel});
 await f.arrive();
 assert.equal(panel.scrollTop,236);assert.equal(c.state.claimSection,'documents');
 const owner=panel.querySelector('#cwOwnerInput');panel.querySelector('#cpOwnerDialog').open=true;
 owner.value='Unsaved mobile handler';owner.focus();
 panel.scrollTop=319;panel.querySelector('.cp-work-column').scrollTop=57;
 c.renderDetail({...f.detail,state:{...f.detail.state,owner:'New saved handler'}});
 assert.equal(panel.scrollTop,319,'The mobile page keeps its actual position across refresh');
 assert.equal(panel.querySelector('.cp-work-column').scrollTop,0,'The rebuilt desktop column must not acquire mobile scroll state');
 assert.equal(panel.querySelector('#cwOwnerInput').value,'Unsaved mobile handler');
 assert.equal(f.document.activeElement,panel.querySelector('#cwOwnerInput'));
 assert.equal(panel.querySelector('.cp-claim-title').dataset.owner,'New saved handler');
 assert.equal(panel.querySelector('#cpPane-documents').hidden,false);
});

test('opening another claim replaces its header and restores that claim section separately',()=>{
 const f=fixture(),{c,panel}=f;c.renderDetail(f.detail);const oldTab=panel.querySelector('#cpTab-process');
 c.state.detail={state:{claim_id:'claim-b',revision:1,state_sha256:'state-b',binding:{language:'en'}},artifacts:[],message:{body:'Another original customer message.'}};c.state.items.push({claim_id:'claim-b',state_sha256:'state-b'});
 c.recoverPresentation('claim-b');c.renderDetail(c.state.detail);
 assert.equal(oldTab.isConnected,false);assert.notEqual(panel.querySelector('#cpTab-process'),oldTab);
 assert.equal(c.state.claimSection,'overview');assert.equal(panel.querySelector('#cpPane-overview').hidden,false);
});

for(const mobile of [false,true])test(`source library preserves same-claim disclosure state and starts closed on another claim (${mobile?'mobile':'desktop'})`,async()=>{
 const f=fixture({mobile}),{c,panel}=f;c.renderDetail(f.detail);
 const library=panel.querySelector('#cwSourceLibrary');assert.ok(library,'The real source rail supplies the library disclosure');
 assert.equal(library.open,false);
 library.open=true;
 assert.equal(library.hasAttribute('open'),true,'The DOM fixture reflects the native open property used by renderDetail');
 await f.arrive();
 const refreshed=panel.querySelector('#cwSourceLibrary');
 assert.notEqual(refreshed,library);assert.equal(library.isConnected,false);
 assert.equal(refreshed.open,true,'A passive graph arrival preserves an explicitly expanded library');
 refreshed.open=false;
 assert.equal(refreshed.hasAttribute('open'),false);
 c.renderDetail({...f.detail,state:{...f.detail.state,owner:'New saved handler'}});
 assert.equal(panel.querySelector('#cwSourceLibrary').open,false,'A later same-claim refresh preserves a closed library');
 panel.querySelector('#cwSourceLibrary').open=true;
 c.state.detail={state:{claim_id:'claim-b',revision:1,state_sha256:'state-b',binding:{language:'en'}},artifacts:[],message:{body:'Another original customer message.'}};
 c.state.items.push({claim_id:'claim-b',state_sha256:'state-b'});
 c.recoverPresentation('claim-b');c.renderDetail(c.state.detail);
 assert.equal(panel.querySelector('#cwSourceLibrary').open,false,'The previous claim does not expand the new claim source library');
});
