'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {createHash,webcrypto}=require('node:crypto');
const ui=require('../casepath/assets/claims-workspace-presentation-v1.js');
const source=fs.readFileSync(path.join(__dirname,'../casepath/assets/claims-workspace-v1.js'),'utf8');
const sha=value=>createHash('sha256').update(value).digest('hex');
const quote="My form arrived on Monday and says the end of June; My wife's arrived on Wednesday and says the end of July";
const body='Hello 👋\n'+quote+'\nPlease check <both> notices.';
const raw=Buffer.from('MIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=fixture\r\n\r\n--fixture\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\nHello =F0=9F=91=8B\r\nMy form arrived on Monday and says the end of June; My wife=\r\n\'s arrived on Wednesday and says the end of July\r\nPlease check <both> notices.\r\n--fixture\r\nContent-Type: application/octet-stream\r\nContent-Transfer-Encoding: base64\r\n\r\nYWJj\r\n--fixture--\r\n');
function fixture(){
 const artifact={artifact_id:'message-a',role:'customer_message',media_type:'message/rfc822',file_name:'original.eml',download_url:'/api/claim-loops/v1/workspace/claims/claim-a/artifacts/message-a',sha256:sha(raw),size_bytes:raw.length};
 const detail={state:{claim_id:'claim-a',binding:{source_documents:[]}},message:{message_id:'message-a',body},artifacts:[artifact]};
 const state={detail,loop:null,sourceRequest:0,sourceSelection:null,inspectorOpen:false};
 const nodes={'#cwSourceContent':{innerHTML:''},'#cwSourceHeading':{textContent:''}},requests=[],scrolls=[];
 const context={state,ui,URL,location:new URL('http://localhost/'),AbortController,TextDecoder,TextEncoder,Uint8Array,crypto:webcrypto,setTimeout,clearTimeout,
  esc:ui.h,sha256Bytes:async bytes=>sha(bytes),focusSource(){state.inspectorOpen=true;},resetSource(){throw Error('Unexpected source reset');},
  $:selector=>selector==='#cpExactSourcePassage'?(nodes['#cwSourceContent'].innerHTML.includes('id="cpExactSourcePassage"')?{scrollIntoView:options=>scrolls.push(options)}:null):nodes[selector],
  fetch:async(url,options)=>{requests.push({url:String(url),options});return{ok:true,arrayBuffer:async()=>Uint8Array.from(raw).buffer};}};
 vm.createContext(context);
 for(const[from,to]of[['  function releaseSourcePreview() {','  function focusSource('],['  async function showSourceArtifact(','  function handleWorkspaceClick(']]){
  const start=source.indexOf(from),end=source.indexOf(to,start);assert.ok(start>=0&&end>start);vm.runInContext(source.slice(start,end),context);
 }
 const open=source.match(/    openSource:(span=>[^\n]+),\n    assign:/);assert.ok(open);vm.runInContext('globalThis.openSource='+open[1],context);
 const show=context.showSourceArtifact;context.showSourceArtifact=(...args)=>(context.sourcePending=show(...args));
 const retryStart=source.indexOf("    if(button.hasAttribute('data-source-artifact')){");const retryEnd=source.indexOf('\n',retryStart);
 vm.runInContext('globalThis.retrySource=button=>{'+source.slice(retryStart,retryEnd)+'}',context);
 const start=Array.from(body.slice(0,body.indexOf(quote))).length;
 const span={...artifact,source_id:artifact.artifact_id,source_sha256:artifact.sha256,text_sha256:sha(body),claim_id:detail.state.claim_id,extraction:'message_body',start,end:start+Array.from(quote).length,quote};
 const settled=()=>context.sourcePending;
 return{context,state,detail,artifact,span,nodes,requests,scrolls,settled,html:()=>nodes['#cwSourceContent'].innerHTML,open:async value=>{context.openSource(value);await settled();}};
}

test('a paid decoded-message citation highlights its exact codepoint span and preserves the original MIME/download',async()=>{
 const f=fixture();assert.equal(raw.toString().includes(quote),false);
 assert.notEqual(body.indexOf(quote),f.span.start,'fixture distinguishes UTF-16 from Python codepoint offsets');
 const before=JSON.stringify(f.detail);await f.open(f.span);
 assert.match(f.html(),/<mark class="cp-source-exact" id="cpExactSourcePassage">My form arrived/);
 assert.match(f.html(),/Readable text from the verified email/);assert.match(f.html(),/Original email formatting/);
 assert.match(f.html(),/Content-Transfer-Encoding: base64/);assert.match(f.html(),/YWJj/);
 assert.match(f.html(),/download="original.eml">Download original/);assert.match(f.html(),/Please check &lt;both&gt; notices/);
 assert.equal(f.requests.length,1);assert.equal(f.requests[0].options.method,undefined);assert.equal(JSON.stringify(f.detail),before);
 assert.equal(f.scrolls.length,1);
});

test('decoded display refuses mismatched claim, artifact, bytes, text hash, extraction and exact offsets',async()=>{
 const changes=[{claim_id:'other'},{claim_id:undefined},{artifact_id:'other'},{source_id:'other'},{source_sha256:'0'.repeat(64)},{sha256:'0'.repeat(64)},{text_sha256:'0'.repeat(64)},{extraction:'pdf_text'},{start:9},{end:9999},{start:-1},{end:8},{start:8.5},{quote:'Other statement'}];
 for(const change of changes){const f=fixture();await f.open({...f.span,...change});assert.doesNotMatch(f.html(),/Readable text from the verified email|id="cpExactSourcePassage"/,JSON.stringify(change));}
 const f=fixture();f.artifact.sha256='0'.repeat(64);await f.open(f.span);assert.match(f.html(),/file does not match the saved source record/);assert.doesNotMatch(f.html(),/id="cpExactSourcePassage"/);
 const size=fixture();size.artifact.size_bytes++;await size.open(size.span);assert.match(size.html(),/file does not match the saved source record/);
 const plain=fixture();await plain.open({artifact_id:plain.artifact.artifact_id,quote});assert.doesNotMatch(plain.html(),/Readable text from the verified email|id="cpExactSourcePassage"/);
});

test('a repeated quote highlights the cited occurrence, not the first matching text',async()=>{
 const f=fixture(),prefix='Earlier: '+quote+'\nCurrent 👋: ';
 f.detail.message.body=prefix+quote+'\nEnd.';
 const start=Array.from(prefix).length;
 await f.open({...f.span,text_sha256:sha(f.detail.message.body),start,end:start+Array.from(quote).length});
 assert.ok(f.html().includes(ui.h(prefix)+'<mark class="cp-source-exact" id="cpExactSourcePassage">'+ui.h(quote)+'</mark>\nEnd.'));
 assert.equal((f.html().match(/id="cpExactSourcePassage"/g)||[]).length,1);
});

test('refresh and preview retry retain the citation but recheck the current message body',async()=>{
 const f=fixture();await f.open(f.span);
 f.context.restoreSourceSelection();await f.settled();assert.match(f.html(),/id="cpExactSourcePassage"/);
 const retry={dataset:{sourceArtifact:'0'},hasAttribute:key=>key==='data-source-artifact'};
 f.context.retrySource(retry);await f.settled();assert.match(f.html(),/id="cpExactSourcePassage"/);
 f.detail.message.body+=' Changed after the cited read.';
 f.context.restoreSourceSelection();await f.settled();assert.doesNotMatch(f.html(),/Readable text from the verified email|id="cpExactSourcePassage"/);
});

test('a late verified file cannot repaint after another source selection',async()=>{
 const f=fixture();let release;
 f.context.fetch=async()=>({ok:true,arrayBuffer:()=>new Promise(resolve=>{release=()=>resolve(Uint8Array.from(raw).buffer);})});
 f.context.openSource(f.span);await new Promise(resolve=>setImmediate(resolve));
 f.context.releaseSourcePreview();f.nodes['#cwSourceContent'].innerHTML='New selection';release();
 await f.settled();assert.equal(f.html(),'New selection');
});

test('a late source read cannot repaint a refreshed snapshot of the same claim',async()=>{
 const f=fixture();let release;
 f.context.fetch=async()=>({ok:true,arrayBuffer:()=>new Promise(resolve=>{release=()=>resolve(Uint8Array.from(raw).buffer);})});
 f.context.openSource(f.span);await new Promise(resolve=>setImmediate(resolve));
 f.state.detail=structuredClone(f.detail);f.nodes['#cwSourceContent'].innerHTML='Refreshed claim';release();
 await f.settled();assert.equal(f.html(),'Refreshed claim');
});
