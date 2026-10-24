import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
import {isDeepStrictEqual} from 'node:util';
const ROOT="/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-northstar-20261024",BASE="/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-northstar-20261024/.runtime/commander-northstar/release",OUT=path.join(BASE,'operation-trace-forensics');
const SHA='b20685d1670b33b941b1bfcb902638a879c01b93',SITE='https://casepath-autonomous.kumarnavish.chatgpt.site';
const require=createRequire('/Users/kumar0002/Documents/Die Mobiliar/casepath-canonical/casepath-qa/package.json'),{chromium}=require('playwright'),ui=require(path.join(ROOT,'casepath/assets/autonomous-workspace-v1.js'));
const hash=b=>createHash('sha256').update(b).digest('hex'),digest=p=>hash(fs.readFileSync(p));
const fixturePath=path.join(ROOT,'casepath-qa/fixtures/desk-v3.json.gz'),fixture=JSON.parse(gunzipSync(fs.readFileSync(fixturePath)));
assert.equal(fs.existsSync(OUT),false);fs.mkdirSync(OUT);
const report={contract:'casepath.operation-trace-identity-review/1',source_commit:SHA,started_at:new Date().toISOString(),status:'running',errors:[],writes:[],claims:[],fixture_sha256:digest(fixturePath),official_validator_sha256:digest(path.join(ROOT,'casepath/assets/autonomous-workspace-v1.js'))};
let browser,context,page;const traces=new Map(),states=new Map(),pending=[];
try{
 browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 context=await browser.newContext({viewport:{width:1440,height:900},serviceWorkers:'block'});
 page=await context.newPage();
 page.on('pageerror',e=>report.errors.push(e.message));
 await page.route('**/*',r=>{const q=r.request(),u=new URL(q.url());if(['GET','HEAD'].includes(q.method())||(u.origin===SITE&&u.pathname.startsWith('/cdn-cgi/')))return r.continue();report.writes.push(q.method()+' '+u.href);return r.abort();});
 await page.goto(SITE+'/#autonomous/demonstration',{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.CasepathPresentation?.active,undefined,{timeout:90000});
 const manifest=await page.evaluate(()=>CasepathPresentation.active.manifest);
 for(const cid of manifest.claims){
  const received=await page.evaluate(async id=>{
   const base='/api/claim-loops/v1/autonomous/claims/'+encodeURIComponent(id);
   const [operations,claim]=await Promise.all([fetch(base+'/operations?mode=recorded',{cache:'no-store'}),fetch(base,{cache:'no-store'})]);
   if(!operations.ok||!claim.ok)throw Error('Actual read HTTP '+operations.status+'/'+claim.status);
   return {body:await operations.text(),claim:await claim.json(),url:operations.url};
  },cid);
  traces.set(cid,{url:received.url,body:received.body,frames:received.body.trim().split('\n').filter(Boolean).map(JSON.parse)});
  states.set(cid,received.claim.state);

  const actual=traces.get(cid),state=states.get(cid);assert.ok(actual&&state,'actual trace and actual graph state required');
  const frames=actual.frames,binding=frames[0],result=frames.at(-1),rows=frames.filter(x=>x.type==='operation');
  assert.equal(binding.type,'binding');assert.equal(result.type,'result');
  assert.equal(binding.claim_id,cid);assert.equal(state.claim_id,cid);
  assert.equal(binding.current_state_sha256,state.state_sha256);
  assert.equal(binding.current_revision,state.revision);
  assert.equal(binding.current_event_sha256,state.last_event_sha256);
  assert.equal(result.current_event_sha256,state.last_event_sha256);
  assert.equal(result.state_sha256,state.state_sha256);
  assert.equal(state.state_sha256,manifest.stateHashes[manifest.claims.indexOf(cid)]);
  assert.equal(result.exact_output_verified,true);
  const trace={binding,rows:[],sources:new Map(),bytes:0};
  for(const row of rows)await ui.checkedOperation(row,trace,state);
  assert.equal(result.operation_count,rows.length);assert.equal(result.operation_chain_sha256,rows.at(-1).operation_sha256);
  assert.equal(result.trace_sha256,hash(ui.canonicalJSON(frames.slice(0,-1).map(f=>hash(ui.canonicalJSON(f))))));
  const ref=fixture.cases.find(c=>c.id===cid),old=ref.trace.trim().split('\n').map(JSON.parse).filter(x=>x.type==='operation'),byId=new Map(old.map(x=>[x.id,x]));
  const diffs=[];
  for(const row of rows){const other=byId.get(row.id);if(!other){diffs.push({id:row.id,seq:row.seq,kind:row.kind,missing_in_fixture:true});continue;}const keys=[...new Set([...Object.keys(row),...Object.keys(other)])].filter(k=>!isDeepStrictEqual(row[k],other[k]));if(keys.length)diffs.push({id:row.id,seq:row.seq,kind:row.kind,keys,values:Object.fromEntries(keys.filter(k=>!['operation_sha256','previous_operation_sha256'].includes(k)).map(k=>[k,{actual:row[k],fixture:other[k]}]))});}
  const name=cid+'.ndjson',stateName=cid+'-state.json',diffName=cid+'-fixture-differences.json';
  fs.writeFileSync(path.join(OUT,name),actual.body);fs.writeFileSync(path.join(OUT,stateName),JSON.stringify(state,null,2)+'\n');fs.writeFileSync(path.join(OUT,diffName),JSON.stringify(diffs,null,2)+'\n');
  report.claims.push({claim_id:cid,trace_url:actual.url,trace_file:name,trace_sha256:digest(path.join(OUT,name)),state_file:stateName,state_file_sha256:digest(path.join(OUT,stateName)),state_sha256:state.state_sha256,operation_count:rows.length,fixture_operation_count:old.length,operation_chain_sha256:result.operation_chain_sha256,frame_trace_sha256:result.trace_sha256,official_checkedOperation_all_passed:true,final_binding_verified:true,difference_file:diffName,difference_sha256:digest(path.join(OUT,diffName)),differences:diffs.length,difference_fields:[...new Set(diffs.flatMap(x=>x.keys||[]))],first_semantic_differences:diffs.filter(x=>x.missing_in_fixture||x.keys.some(k=>!['operation_sha256','previous_operation_sha256'].includes(k))).slice(0,3)});
 }
 assert.deepEqual(report.errors,[]);assert.deepEqual(report.writes,[]);report.status='passed';
}catch(e){report.status='failed';report.failure=String(e.stack||e);throw e;}finally{await context?.close();await browser?.close();report.finished_at=new Date().toISOString();fs.writeFileSync(path.join(OUT,'identity-review.json'),JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify(report));
