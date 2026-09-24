'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const view=require('../casepath/assets/claims-workspace-presentation-v1.js');
const message={artifact_id:'message-a',role:'customer_message',media_type:'message/rfc822',file_name:'email.eml',size_bytes:340,sha256:'a'.repeat(64),download_url:'/api/claim-loops/v1/workspace/claims/c/artifacts/message-a'};
const pdf={artifact_id:'pdf-a',role:'attachment',media_type:'application/pdf',file_name:'Receipt.pdf',size_bytes:8000,sha256:'b'.repeat(64),download_url:'/api/claim-loops/v1/workspace/claims/c/artifacts/pdf-a'};
const detail={artifacts:[message,pdf],state:{binding:{received_at:'2026-08-01T10:00:00Z',language:'en'}},message:{body:'Original customer account, preserved without introducing any conclusion.'}};
const cases=[['application/pdf','pdf'],['image/jpeg','image'],['image/tiff','image'],['message/rfc822','email'],['application/msword','word'],['application/vnd.openxmlformats-officedocument.wordprocessingml.document','word'],['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','spreadsheet'],['text/csv','spreadsheet'],['text/plain','text'],['application/octet-stream','document']];
for(const [media,kind]of cases)test('file treatment for '+media,()=>assert.equal(view.fileTreatment({media_type:media,file_name:'attachment.bin'}).kind,kind));
test('declared file type governs the preview',()=>assert.equal(view.fileTreatment({media_type:'application/octet-stream',file_name:'attachment.pdf'}).kind,'document'));
test('the message and real attachment are visible without expanding a section',()=>{
 const html=view.packetLibrary(detail);
 assert.match(html,/Customer message/);assert.match(html,/Receipt.pdf/);
 assert.equal((html.match(/data-packet-artifact=/g)||[]).length,1);
 assert.doesNotMatch(html,/<details|<button/);
});
test('a message-only claim does not acquire an attachment',()=>{
 const html=view.packetLibrary({...detail,artifacts:[message]});
 assert.match(html,/Customer message/);assert.doesNotMatch(html,/data-packet-artifact=|<button/);
});
test('thumbnail URLs bind the original source hash and stay in the claim',()=>{
 assert.equal(view.packetPreviewUrl(pdf),pdf.download_url+'/preview/page?source_sha256='+pdf.sha256+'&page=1&width=180');
 assert.equal(view.packetPreviewUrl({...pdf,download_url:'https://example.org/document'}),null);
 assert.equal(view.packetPreviewUrl({...pdf,sha256:'invalid'}),null);
});
test('attachment names are escaped rather than inserted as HTML',()=>{
 const html=view.packetAttachment({...pdf,file_name:'<img src=x>.pdf'},1);
 assert.match(html,/&lt;img src=x&gt;.pdf/);assert.doesNotMatch(html,/<img src=x>/);
});
test('Word content is escaped and its text-only scope is explicit',()=>{
 const html=view.packetContentMarkup({kind:'word',content:{paragraphs:['<script>not markup</script>']},truncated:false});
 assert.match(html,/&lt;script&gt;/);assert.match(html,/original layout/);assert.doesNotMatch(html,/<script>/);
});
test('spreadsheet values retain addresses and cached formula status',()=>{
 const html=view.packetContentMarkup({kind:'spreadsheet',content:{sheets:[{name:'Payments',rows:[[{address:'D5',value:'247',formula:'B5*2'}]]}]},truncated:false});
 assert.match(html,/D5/);assert.match(html,/247/);assert.match(html,/not recalculated/);assert.match(html,/B5\*2/);
});
test('human file sizes preserve missing metadata',()=>{
 assert.equal(view.fileSize(340),'340 B');assert.equal(view.fileSize(8192),'8 KB');assert.equal(view.fileSize(-1),'Size not recorded');
});
