"""Real single-shot OpenRouter adapter, called only through BoundExecutor.

There is deliberately no paid CLI, fallback, retry, model search or credential
inspection. The canonical gateway injects its authorization checker and its
secret supplier. Engineering fixtures never instantiate this transport.
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable
from .wire import canonical, decode, save, immutable, sha, digest, Invalid
from .schedule import render_request, implementation_identity, money
from .journal import Journal


class OpenRouterOnce:
    origin='canonical_managed_run'
    def __init__(self, key_supplier: Callable[[],str], timeout_seconds: int=240):
        self.key_supplier=key_supplier;self.timeout=timeout_seconds
    def __call__(self, request: dict) -> dict:
        import sys
        if sys.platform!='linux':raise Invalid('scientific provider execution is restricted to the admitted Linux gateway')
        key=self.key_supplier()
        if not isinstance(key,str) or not key.strip():raise Invalid('gateway secret supplier unavailable')
        req=urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',data=canonical(request['payload']),
            headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
        try:
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self,*args,**kwargs):
                    return None
            opener=urllib.request.build_opener(NoRedirect())
            with opener.open(req,timeout=self.timeout) as resp:
                body=resp.read(8*1024*1024+1)
                if len(body)>8*1024*1024:raise Invalid('provider body bound exceeded; response remains uncertain')
                return {'http_status':resp.status,'raw_body':body}
        except urllib.error.HTTPError as exc:
            return {'http_status':exc.code,'raw_body':exc.read(8*1024*1024+1)}


class BoundExecutor:
    def __init__(self, plan:dict,journal:Journal,output:Path,authorize:Callable[[dict,dict],dict],transport:Callable):
        self.plan,self.journal,self.output,self.authorize,self.transport=plan,journal,Path(output),authorize,transport
        if not callable(authorize) or not callable(transport):raise Invalid('canonical authorizer and transport required')
    def render(self,slot_id:str,parents:dict[str,bytes]) -> dict:
        return render_request(self.plan,slot_id,parents)
    def recover(self,slot_id:str,parents:dict[str,bytes]) -> tuple[bytes,str] | None:
        """Read an exactly completed request; never resend or accept unknown state."""
        if self.plan['bindings']['code_identity']!=implementation_identity():
            raise Invalid('implementation changed since request freeze')
        request=self.render(slot_id,parents)
        rows=self.journal.facts(self.plan['plan_id'],include_events=False)['requests']
        matches=[r for r in rows if r['slot_id']==slot_id]
        if not matches:return None
        if len(matches)!=1 or matches[0]['request_id']!=request['request_id']:
            raise Invalid('existing slot binds a different physical request')
        if matches[0]['state']!='completed' or matches[0]['actual'] is None:
            raise Invalid('existing non-successful request must be preserved/reconciled, never retried')
        directory=self.output/'calls'/request['request_id']
        receipt_raw=(directory/'RECEIPT.json').read_bytes()
        receipt=decode(receipt_raw);body_raw=(directory/'PROVIDER.raw').read_bytes()
        if receipt.get('plan_id')!=self.plan['plan_id'] or receipt.get('request_id')!=request['request_id'] or receipt.get('payload_sha256')!=request['payload_sha256'] or receipt.get('body_sha256')!=sha(body_raw) or receipt.get('state')!='completed':
            raise Invalid('recovered receipt differs from exact request/result binding')
        evidence=self.journal.last_observation(request['request_id'])
        if not evidence or evidence.get('evidence',{}).get('receipt_sha256')!=sha(receipt_raw):
            raise Invalid('receipt is not the journaled successful observation')
        body=decode(body_raw);raw=body['choices'][0]['message']['content'].encode('utf-8')
        if raw!=(directory/'MODEL_OUTPUT.raw').read_bytes():raise Invalid('recovered model output changed')
        return raw,sha(receipt_raw)
    def call(self,slot_id:str,parents:dict[str,bytes]) -> tuple[bytes,str]:
        if self.plan['bindings']['code_identity']!=implementation_identity():raise Invalid('implementation changed since request freeze')
        request=self.render(slot_id,parents)
        # Authorizer must verify actual owner, canonical experiment/admission,
        # run token, phase/target history, remaining shared credits, route prices,
        # effective parameters and exact command/code bindings. No JSON flag here
        # grants any of that authority.
        auth=self.authorize(self.plan,request)
        if auth.get('origin')!=getattr(self.transport,'origin',None):raise Invalid('transport/authorization origin mismatch')
        if self.plan['bindings']['origin']=='engineering_fixture' and self.transport.origin!='engineering_fixture':
            raise Invalid('fixture cannot use live transport')
        directory=self.output/'calls'/request['request_id']
        save(directory/'REQUEST.json',request)
        self.journal.begin(self.plan,request,auth)
        try:
            response=self.transport(request)
        except BaseException as exc:
            evidence={'error_type':type(exc).__name__,'request_id':request['request_id'],'retry':False}
            save(directory/'UNCERTAIN.json',evidence)
            self.journal.observe(request['request_id'],state='uncertain',actual_usd=None,evidence=evidence)
            raise
        raw=response['raw_body']
        immutable(directory/'PROVIDER.raw',raw)
        actual=None;state='failed';failure=None;content=None
        try:
            body=decode(raw)
            usage=body.get('usage') or {}
            cost=usage.get('cost')
            if cost is not None: actual=str(money(str(cost)))
            if response['http_status']!=200:raise Invalid('non-200 provider outcome')
            config=self.plan['bindings']['config']
            if body.get('model')!=config['returned_model'] or body.get('provider')!=config['returned_provider']:
                raise Invalid('returned model/provider differs from bound route')
            choices=body.get('choices')
            if not isinstance(choices,list) or len(choices)!=1:raise Invalid('exactly one model sample required')
            if choices[0].get('finish_reason')!='stop':raise Invalid('truncated or nonterminal completion')
            text=choices[0]['message']['content']
            if not isinstance(text,str):raise Invalid('no textual model output')
            content=text.encode('utf-8')
            immutable(directory/'MODEL_OUTPUT.raw',content)
            if len(content)>request['max_response_bytes']:raise Invalid('response byte bound exceeded; preserved, not truncated')
            decode(content)
            if type(usage.get('prompt_tokens')) is not int or type(usage.get('completion_tokens')) is not int:
                raise Invalid('token usage unknown')
            if usage['prompt_tokens']>request['input_tokens_upper'] or usage['completion_tokens']>request['payload']['max_tokens']:
                raise Invalid('actual usage exceeded admitted token bound')
            if actual is None:raise Invalid('cost unknown; do not coerce to zero')
            if money(actual)>money(request['reserved_usd']):raise Invalid('charge exceeds reservation')
            state='completed'
        except (ValueError,KeyError,TypeError,IndexError,ArithmeticError) as exc:
            failure=str(exc)
        receipt={'request_id':request['request_id'],'slot_id':slot_id,'plan_id':self.plan['plan_id'],
            'http_status':response['http_status'],'body_sha256':sha(raw),'state':state,
            'actual_cost_usd':actual,'failure':failure,'physical_attempts':1,
            'origin':self.transport.origin, 'payload_sha256':request['payload_sha256']}
        receipt_sha=save(directory/'RECEIPT.json',receipt)
        self.journal.observe(request['request_id'],state=state,actual_usd=actual,evidence={'receipt_sha256':receipt_sha})
        if state!='completed':raise Invalid(f'provider output retained as failure: {failure}')
        return content,receipt_sha
