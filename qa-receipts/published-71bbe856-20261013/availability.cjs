const { chromium } = require('playwright');
const fs = require('fs');
const crypto = require('crypto');
const path = '/workspace/op-published-71-acceptance-20261013';
const url = 'https://casepath-autonomous.kumarnavish.chatgpt.site';
const receipt = {task:'published browser availability only',source_commit:'71bbe856a022252e9b3f327aa9e41de28d51ab04',url,started_at:new Date().toISOString(),native_chromium:'/usr/bin/chromium',fresh_anonymous_context:true,ignore_https_errors:false,virtual_timers:false,request_guard:'GET/HEAD only',requests:[],responses:[],failed_requests:[],console:[],page_errors:[],blocked_mutations:[]};
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
for (const file of ['autonomous-workspace-v1.js','autonomous-workspace-v1.css']) receipt[file] = {expected_local_sha256:hash(fs.readFileSync('/workspace/casepath-release-ae0-shard2/casepath/assets/'+file))};
const policy=JSON.parse(fs.readFileSync('/etc/codex/network-policy.json','utf8'));
receipt.network_policy={version:policy.version,type:policy.http_network_policy.type,hostname_in_startup_allowed_hosts:policy.http_network_policy.egress_rules.some(rule => rule.host === new URL(url).hostname),vpn_configured:policy.vpn_configured,tcp_domain_grants:policy.tcp_network_access.domains.length,tcp_ip_grants:policy.tcp_network_access.ip_ranges.length};
(async()=>{
 let browser,context,page;
 try {
  const proxyUrl=new URL(process.env.HTTPS_PROXY || process.env.HTTP_PROXY);
  if (proxyUrl.username || proxyUrl.password) throw new Error('Configured proxy contains authentication; anonymous browser check will not extract or pass credentials.');
  receipt.configured_proxy_used=true;
  browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,proxy:{server:proxyUrl.origin},args:['--no-sandbox']});
  context=await browser.newContext({viewport:{width:1360,height:900},ignoreHTTPSErrors:false});
  await context.route('**/*',async route=>{
   const request=route.request();
   if(!['GET','HEAD'].includes(request.method())) {receipt.blocked_mutations.push({at:new Date().toISOString(),method:request.method(),url:request.url()}); await route.abort('blockedbyclient');return;}
   await route.continue();
  });
  page=await context.newPage();
  page.on('request',r=>receipt.requests.push({at:new Date().toISOString(),method:r.method(),url:r.url(),resource_type:r.resourceType()}));
  page.on('response',r=>receipt.responses.push({at:new Date().toISOString(),url:r.url(),status:r.status(),headers:r.headers()}));
  page.on('requestfailed',r=>receipt.failed_requests.push({at:new Date().toISOString(),method:r.method(),url:r.url(),failure:r.failure()}));
  page.on('console',m=>receipt.console.push({type:m.type(),text:m.text()}));
  page.on('pageerror',e=>receipt.page_errors.push(String(e)));
  try {const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000}); receipt.navigation={status:response?.status(),final_url:page.url()};receipt.document_html_sha256=hash(await page.content());receipt.document_title=await page.title();}
  catch(e){receipt.navigation_error=String(e);}
  receipt.cookie_count=(await context.cookies()).length;
  receipt.final_page_url=page.url();
  try {await page.screenshot({path:path+'/availability.png'});receipt.screenshot='availability.png';}catch(e){receipt.screenshot_error=String(e);}
 }catch(e){receipt.setup_error=String(e);}
 finally {if(context)await context.close();if(browser)await browser.close();receipt.finished_at=new Date().toISOString();receipt.available=Boolean(receipt.navigation && receipt.navigation.status>=200 && receipt.navigation.status<400 && !receipt.navigation_error);fs.writeFileSync(path+'/availability.json',JSON.stringify(receipt,null,2));console.log(JSON.stringify({available:receipt.available,navigation:receipt.navigation,navigation_error:receipt.navigation_error,failed_requests:receipt.failed_requests,requests:receipt.requests.length,blocked_mutations:receipt.blocked_mutations.length,cookies:receipt.cookie_count,source_js_sha256:receipt['autonomous-workspace-v1.js'].expected_local_sha256,source_css_sha256:receipt['autonomous-workspace-v1.css'].expected_local_sha256}));}
})().catch(e=>{console.error(e);process.exitCode=1;});
