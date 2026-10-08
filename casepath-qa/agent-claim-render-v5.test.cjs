'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const ui=require('../casepath/assets/agent-claim-v2.js');

// A connected tree makes an actual remove/reinsert distinguishable from keeping
// a pointer target mounted. It does not start the application or an API server.
function fixture(){
 const document={activeElement:null};
 class Node{
  constructor(tag,text=''){this.tagName=tag.toUpperCase();this.nodeValue=text;this.ownerDocument=document;this.parentNode=null;this.childNodes=[];this.attrs={};this.dataset={};this.disconnects=0;this.listeners=new Map();if(tag==='template')this.content=new Node('#fragment');}
  get parentElement(){return this.parentNode;}
  get firstElementChild(){return this.childNodes.find(node=>!node.tagName.startsWith('#'))||null;}
  get isConnected(){return this===document.body||Boolean(this.parentNode?.isConnected);}
  get id(){return this.getAttribute('id')||'';}
  setAttribute(name,value){this.attrs[name]=String(value);if(name.startsWith('data-'))this.dataset[name.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=String(value);}
  getAttribute(name){return this.attrs[name]??null;}
  hasAttribute(name){return Object.hasOwn(this.attrs,name);}
  contains(node){return this===node||this.childNodes.some(child=>child.contains(node));}
  matches(selector){if(this.tagName.startsWith('#'))return false;if(selector.startsWith('.'))return (this.attrs.class||'').split(' ').includes(selector.slice(1));if(selector.startsWith('#'))return this.id===selector.slice(1);const attr=selector.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/);return attr?this.hasAttribute(attr[1])&&(attr[2]===undefined||this.getAttribute(attr[1])===attr[2]):this.tagName===selector.toUpperCase();}
  querySelectorAll(selector){const rows=[];for(const node of this.childNodes){if(node.matches(selector))rows.push(node);rows.push(...node.querySelectorAll(selector));}return rows;}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
  closest(selector){return this.matches(selector)?this:this.parentNode?.closest(selector)||null;}
  append(...nodes){for(const node of nodes){if(node.tagName==='#FRAGMENT'){this.append(...node.childNodes);continue;}node.remove();this.childNodes.push(node);node.parentNode=this;}}
  remove(){if(!this.parentNode)return;if(this.isConnected){const mark=node=>{node.disconnects++;node.childNodes.forEach(mark);};mark(this);if(this.contains(document.activeElement))document.activeElement=document.body;}const siblings=this.parentNode.childNodes;siblings.splice(siblings.indexOf(this),1);this.parentNode=null;}
  replaceWith(node){const parent=this.parentNode,index=parent.childNodes.indexOf(this);node.remove();this.remove();parent.childNodes.splice(index,0,node);node.parentNode=parent;}
  isEqualNode(other){return !!other&&this.tagName===other.tagName&&this.nodeValue===other.nodeValue&&JSON.stringify(Object.entries(this.attrs).sort())===JSON.stringify(Object.entries(other.attrs).sort())&&this.childNodes.length===other.childNodes.length&&this.childNodes.every((child,index)=>child.isEqualNode(other.childNodes[index]));}
  set innerHTML(html){const target=this.content||this;for(const node of [...target.childNodes])node.remove();const stack=[target];for(const token of html.match(/<[^>]+>|[^<]+/g)||[]){if(token.startsWith('</')){stack.pop();continue;}if(!token.startsWith('<')){stack.at(-1).append(new Node('#text',token));continue;}const [,tag,attributes]=token.match(/^<([\w-]+)([^>]*)>/)||[];if(!tag)continue;const node=new Node(tag);for(const [,name,value]of attributes.matchAll(/([\w-]+)(?:="([^"]*)")?/g))node.setAttribute(name,value??'');stack.at(-1).append(node);if(!['input','br','hr'].includes(tag))stack.push(node);}}
  addEventListener(type,fn){this.listeners.set(type,fn);}
  removeEventListener(type,fn){if(this.listeners.get(type)===fn)this.listeners.delete(type);}
  focus(){if(this.isConnected)document.activeElement=this;}
 }
 document.createElement=tag=>new Node(tag);document.body=new Node('body');document.activeElement=document.body;
 const mount=new Node('div');document.body.append(mount);return {document,mount};
}
const input=(id='render-claim')=>({claim:{claim_id:id,owner:'Handler'},agent:{claim_id:id,state:'working',owner:{accountable:'Handler'},run:{run_id:'run',facts_worker:'reference',completed_roles:1,role_count:6,currentness:'current'},questions:[],coverage:{},activity:[],learning:{}}});

test('progress renders never disconnect unchanged Controls or its focused native pointer target',()=>{
 const {mount,document}=fixture(),value=input('render-progress');ui.renderInto(mount,ui.render(value));
 const claim=mount.firstElementChild,header=claim.querySelector('.av-claim-header'),controls=header.querySelector('.av-supervision'),button=controls.querySelector('[data-av-control]'),summary=controls.querySelector('summary');
 const oldWork=claim.querySelector('.av-work-mount');button.focus();
 for(let roles=2;roles<=5;roles++){
  value.agent.run.completed_roles=roles;value.agent.activity=[{type:'SOURCE_OPENED',label:'Recorded source '+roles}];
  ui.renderInto(mount,ui.render(value));
  assert.equal(mount.firstElementChild,claim);assert.equal(claim.querySelector('.av-claim-header'),header);
  assert.equal(header.querySelector('.av-supervision'),controls);assert.equal(controls.querySelector('[data-av-control]'),button);assert.equal(controls.querySelector('summary'),summary);
  assert.equal(button.isConnected,true);assert.equal(button.disconnects,0);assert.equal(summary.disconnects,0);assert.equal(document.activeElement,button);
  assert.ok(header.querySelector('.av-review-summary').childNodes.some(node=>node.nodeValue.includes(roles+'/6 roles finished')));
 }
 assert.equal(oldWork.isConnected,false,'Recorded work still refreshes');
 assert.equal(claim.getAttribute('aria-busy'),'false');
});
test('a real control change replaces that subtree and updates busy metadata',()=>{
 const {mount}=fixture(),value=input('render-change');ui.renderInto(mount,ui.render(value));
 const claim=mount.firstElementChild,header=claim.querySelector('.av-claim-header'),controls=header.querySelector('.av-supervision'),button=controls.querySelector('[data-av-control]');
 value.agent.state='paused';value.agent.pause_requested=true;value.agent.run={...value.agent.run,status:'interrupted',recovery:{can_resume:true}};
 ui.session(value.claim.claim_id).busy=true;ui.renderInto(mount,ui.render(value));
 assert.equal(mount.firstElementChild,claim);assert.equal(claim.querySelector('.av-claim-header'),header);
 assert.notEqual(header.querySelector('.av-supervision'),controls);assert.equal(button.isConnected,false);
 const resume=header.querySelector('[data-av-control]');assert.equal(resume.getAttribute('data-av-control'),'resume');assert.equal(resume.hasAttribute('disabled'),true);assert.equal(claim.getAttribute('aria-busy'),'true');
});
test('loading, error and another claim replace the entire old view without carrying Controls across identities',()=>{
 for(const kind of ['loading','error','claim']){
  const {mount}=fixture(),value=input('render-fallback-'+kind);ui.renderInto(mount,ui.render(value));
  const claim=mount.firstElementChild,button=claim.querySelector('[data-av-control]');
  const next=kind==='loading'?{claim:value.claim}:kind==='error'?{claim:value.claim,agent:{...value.agent,error:'Saved read failed'}}:input('different-claim');
  ui.renderInto(mount,ui.render(next));
  assert.notEqual(mount.firstElementChild,claim);assert.equal(claim.isConnected,false);assert.equal(button.isConnected,false);
  assert.equal(mount.firstElementChild.dataset.avClaim,next.claim.claim_id);
  assert.equal(!!mount.querySelector('.av-claim-header'),kind==='claim');
 }
});
