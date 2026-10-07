const {test}=require('node:test');
const assert=require('node:assert/strict');
const {draftEditForProjection}=require('../casepath/assets/claims-workspace-v1.js');
test('a process correction replaces untouched draft wording with the new saved scope',()=>{
 const original={body_markdown:'Request the separate spouse notice.'};
 const current={body_markdown:'Not requested: separate spouse notice is not applicable.'};
 assert.equal(draftEditForProjection(original.body_markdown,original,current),current.body_markdown);
 assert.equal(draftEditForProjection(null,original,current),current.body_markdown);
});
test('a newer saved projection retains actual unsaved handler wording for explicit review',()=>{
 const original={body_markdown:'Request the notice.'};
 const next={body_markdown:'Request proof of receipt.'};
 const edited='Please send the full notice scan.';
 assert.equal(draftEditForProjection(edited,original,next),edited);
});
test('an untouched historical draft is removed when no draft belongs to the current assessment',()=>{
 const original={body_markdown:'Old request.'};
 assert.equal(draftEditForProjection(original.body_markdown,original,null),null);
});
