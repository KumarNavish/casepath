import fs from 'node:fs/promises';

const API_URL=(process.env.API_URL||'https://casepath-agentic-api.onrender.com').replace(/\/$/,'');
const response=await fetch(`${API_URL}/api/demo/reset`,{method:'POST'});
const text=await response.text();
if(!response.ok) throw new Error(`Demo reset failed: ${response.status} ${text}`);
await fs.rm('reset-out',{recursive:true,force:true});
await fs.mkdir('reset-out',{recursive:true});
await fs.writeFile('reset-out/index.html',`<!doctype html><meta charset="utf-8"><title>CasePath demo reset</title><h1>Fresh demo state restored</h1><pre>${text}</pre>`);
console.log(text);
