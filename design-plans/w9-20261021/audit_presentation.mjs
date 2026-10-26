// The outgoing crossfade layer and source-highlight rectangles intentionally
// overlay their corresponding view/text. A W10 checklist token also deliberately
// travels over the view into its recorded document target; browser tests check
// its exact target and landing count. All stationary content remains audited.
// The documentary focus window deliberately outlines its target. Dedicated
// browser/pixel checks audit its exact target, visibility and scene bounds.
// The coach-mark caption deliberately floats over the dimmed scene beside its
// spotlight; browser tests check it never covers that spotlight or leaves the scene.
// Audit visible, clipped boxes and text; closed disclosures are excluded.
export function auditPresentation(){
 // Inline text can wrap around its siblings. Its enclosing rectangle includes
 // empty space occupied by those siblings; compare line fragments instead.
 const rects=e=>{const raw=getComputedStyle(e).display==='inline'?[...e.getClientRects()]:[e.getBoundingClientRect()];return raw.map(r=>{let q={left:r.left,right:r.right,top:r.top,bottom:r.bottom};for(let p=e.parentElement;p;p=p.parentElement){const s=getComputedStyle(p);if(/auto|scroll|hidden|clip/.test(s.overflow+s.overflowY+s.overflowX)){const c=p.getBoundingClientRect();q={left:Math.max(q.left,c.left),right:Math.min(q.right,c.right),top:Math.max(q.top,c.top),bottom:Math.min(q.bottom,c.bottom)};}}return q;});};
 // A modal occupies the top layer; its inert page is intentionally behind it.
 const root=[...document.querySelectorAll('dialog[open]')].at(-1)||document.querySelector('.au-workspace');
 const els=[...(root?.querySelectorAll('*')||[])].filter(e=>{if(e.closest('.au-executive-transition,.au-executive-ink,.au-ns-memory-flight,.au-ns-slip,.au-shelf-card[data-flying=true],.au-doc-focus-layer,.au-doc-card,svg,[hidden],dialog:not([open])')||e.closest('details:not([open])')&&!e.closest('summary'))return false;for(let p=e;p;p=p.parentElement){const s=getComputedStyle(p);if(s.visibility==='hidden'||s.display==='none'||+s.opacity===0)return false;}const s=getComputedStyle(e);if(!rects(e).some(r=>r.right-r.left>=4&&r.bottom-r.top>=4&&r.bottom>=0&&r.top<=innerHeight))return false;return s.borderTopStyle!=='none'&&parseFloat(s.borderTopWidth)>0||!["rgba(0, 0, 0, 0)",'transparent'].includes(s.backgroundColor)||[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim());});
 const name=e=>`${e.className} ${e.textContent.trim().replace(/\s+/g,' ').slice(0,45)}`,hits=[];
 for(let i=0;i<els.length;i++)for(let j=i+1;j<els.length;j++){const a=els[i],b=els[j];if(a.contains(b)||b.contains(a))continue;let hit=null;for(const r of rects(a))for(const q of rects(b)){const x=Math.min(r.right,q.right)-Math.max(r.left,q.left),y=Math.min(r.bottom,q.bottom)-Math.max(r.top,q.top);if(x>2&&y>2)hit=[name(a),name(b),Math.round(x),Math.round(y)];}if(hit)hits.push(hit);}
 return hits;
}
