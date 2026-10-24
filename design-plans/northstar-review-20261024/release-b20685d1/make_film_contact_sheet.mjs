import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
const ROOT="/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-northstar-20261024",BASE=path.join(ROOT,'.runtime/commander-northstar/release/public-film-review');
const index=JSON.parse(fs.readFileSync(path.join(BASE,'frames-index.json'),'utf8'));
assert.equal(index.status,'passed');assert.equal(index.frames.length,24);
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const files=index.frames.map(row=>{const bytes=fs.readFileSync(path.join(BASE,row.file));assert.equal(hash(bytes),row.sha256);return {number:row.number,at:row.at_seconds,image:'data:image/png;base64,'+bytes.toString('base64')};});
const target=path.join(BASE,'film-contact-sheet.png');assert.equal(fs.existsSync(target),false);
const {chromium}=createRequire('/Users/kumar0002/Documents/Die Mobiliar/casepath-canonical/casepath-qa/package.json')('playwright');
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
try{
 const page=await browser.newPage();
 const data=await page.evaluate(async files=>{
  const cols=4,w=360,h=225,gap=16,label=24,rows=6,canvas=document.createElement('canvas');
  canvas.width=cols*w+(cols+1)*gap;canvas.height=rows*(h+label)+(rows+1)*gap;
  const ctx=canvas.getContext('2d');ctx.fillStyle='#eceef1';ctx.fillRect(0,0,canvas.width,canvas.height);
  for(let i=0;i<files.length;i++){const item=files[i],image=await new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=reject;img.src=item.image;});const x=gap+(i%cols)*(w+gap),y=gap+Math.floor(i/cols)*(h+label+gap);ctx.drawImage(image,x,y,w,h);ctx.fillStyle='#141516';ctx.font='14px system-ui';ctx.fillText(String(item.number).padStart(2,'0')+' · '+item.at.toFixed(2)+' s',x,y+h+18);}
  return canvas.toDataURL('image/png');
 },files);
 const bytes=Buffer.from(data.split(',')[1],'base64');fs.writeFileSync(target,bytes,{flag:'wx'});
 const receipt={source_commit:index.source_commit,frame_index_sha256:hash(fs.readFileSync(path.join(BASE,'frames-index.json'))),file:path.basename(target),sha256:hash(bytes),bytes:bytes.length,source_frames:index.frames.map(row=>({number:row.number,sha256:row.sha256})),scope:'Contact sheet only; original decoded full-size frames and continuous video remain unchanged.'};
 fs.writeFileSync(path.join(BASE,'contact-sheet.json'),JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({status:'passed',source_commit:index.source_commit,frames:24,contact_sheet_sha256:receipt.sha256}));
}finally{await browser.close();}
