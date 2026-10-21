// The outgoing crossfade layer and source-highlight rectangles intentionally
// overlay their corresponding view/text. All other visible boxes are audited.
// Audit visible, clipped boxes and text; closed disclosures are excluded.
export function auditPresentation(){
 const rect=e=>{const r=e.getBoundingClientRect();let q={left:r.left,right:r.right,top:r.top,bottom:r.bottom};for(let p=e.parentElement;p;p=p.parentElement){const s=getComputedStyle(p);if(/auto|scroll|hidden|clip/.test(s.overflow+s.overflowY+s.overflowX)){const c=p.getBoundingClientRect();q={left:Math.max(q.left,c.left),right:Math.min(q.right,c.right),top:Math.max(q.top,c.top),bottom:Math.min(q.bottom,c.bottom)};}}return q;};
 // A modal occupies the top layer; its inert page is intentionally behind it.
 const root=[...document.querySelectorAll('dialog[open]')].at(-1)||document.querySelector('.au-workspace');
 const els=[...(root?.querySelectorAll('*')||[])].filter(e=>{if(e.closest('.au-executive-transition,.au-executive-ink,svg,[hidden],dialog:not([open])')||e.closest('details:not([open])')&&!e.closest('summary'))return false;for(let p=e;p;p=p.parentElement){const s=getComputedStyle(p);if(s.visibility==='hidden'||s.display==='none'||+s.opacity===0)return false;}const s=getComputedStyle(e),r=rect(e);if(r.right-r.left<4||r.bottom-r.top<4||r.bottom<0||r.top>innerHeight)return false;return s.borderTopStyle!=='none'&&parseFloat(s.borderTopWidth)>0||!["rgba(0, 0, 0, 0)",'transparent'].includes(s.backgroundColor)||[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim());});
 const name=e=>`${e.className} ${e.textContent.trim().replace(/\s+/g,' ').slice(0,45)}`,hits=[];
 for(let i=0;i<els.length;i++)for(let j=i+1;j<els.length;j++){const a=els[i],b=els[j];if(a.contains(b)||b.contains(a))continue;const r=rect(a),q=rect(b),x=Math.min(r.right,q.right)-Math.max(r.left,q.left),y=Math.min(r.bottom,q.bottom)-Math.max(r.top,q.top);if(x>2&&y>2)hits.push([name(a),name(b),Math.round(x),Math.round(y)]);}
 return hits;
}
