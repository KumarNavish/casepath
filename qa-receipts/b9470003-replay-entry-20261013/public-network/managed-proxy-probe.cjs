const fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{
 const out='/tmp/casepath-replay-entry-session-20261013/public-network-capability.json';fs.renameSync(out,out.replace('.json','-initial-runtime-path.json'));
 const url='https://casepath-autonomous.kumarnavish.chatgpt.site/#autonomous/demonstration?mode=replay';
 const result={host:require('node:os').hostname(),url,expected_commit:'e104c2d3e6ea85993249dfaf38b0e5f70cdbd079',fresh_context:true,proxy_mode:'inherited managed HTTPS proxy',tls_verification:true,cookies_loaded:false,requests:[],responses:[],reachable:false,verified_commit:null};let browser;
 try{
  browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox'],proxy:{server:process.env.HTTPS_PROXY}});
  const context=await browser.newContext({serviceWorkers:'block'});const page=await context.newPage();
  await page.route('**/*',route=>{const r=route.request();result.requests.push({method:r.method(),url:r.url()});return r.method()==='GET'?route.continue():route.abort('blockedbyclient');});
  page.on('response',response=>result.responses.push({url:response.url(),status:response.status()}));
  const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:20000});result.document_status=response?.status();result.reachable=Boolean(response?.ok());
  if(result.reachable){const identity=await page.evaluate(async()=>{const response=await fetch('/deployment.json',{cache:'no-store'});return {status:response.status,payload:response.ok?await response.json():null};});result.identity_status=identity.status;result.verified_commit=identity.payload?.source_commit||null;result.commit_matches=result.verified_commit===result.expected_commit;}
 }catch(error){result.error=String(error.message).split('\n').slice(0,3).join('\n');}finally{if(browser)await browser.close();}
 result.non_get_requests=result.requests.filter(row=>row.method!=='GET').length;fs.writeFileSync(out,JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({reachable:result.reachable,document_status:result.document_status??null,verified_commit:result.verified_commit,error:result.error??null,requests:result.requests.length,non_get_requests:result.non_get_requests,evidence:out}));
})().catch(error=>{console.error(String(error.message));process.exitCode=1});
