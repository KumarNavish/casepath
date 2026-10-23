import {registerHooks} from 'node:module';
import {createHash} from 'node:crypto';
import {writeFileSync} from 'node:fs';
const target="file:///Users/kumar0002/Documents/Die%20Mobiliar/.work/casepath-codex-northstar-20261022/design-plans/w8-20261021-mac-r1/verify-acceptance.mjs";
registerHooks({load(url,context,nextLoad){
 const result=nextLoad(url,context);
 if(url!==target)return result;
 const source=Buffer.from(result.source).toString('utf8');
 const before=createHash('sha256').update(source).digest('hex');
 if(before!=="4162766ef0955adc8c3c9f919d562026f18b4f0d572a9dd0f96008a8c28a1118")throw new Error('Acceptance verifier source changed');
 const old="base='http://127.0.0.1:4180'", replacement='base=proofOrigin';
 if(source.split(old).length!==2)throw new Error('Unexpected verifier origin declarations');
 const revised=source.replace(old,replacement);
 writeFileSync(process.env.CASEPATH_PROOF_OUTPUT+'/origin-adapter.json',JSON.stringify({target,sourceSha256:before,executedSha256:createHash('sha256').update(revised).digest('hex'),from:old,to:replacement,origin:process.env.CASEPATH_PROOF_ORIGIN,assertionsUnchanged:true},null,2));
 return {...result,source:revised};
}});
