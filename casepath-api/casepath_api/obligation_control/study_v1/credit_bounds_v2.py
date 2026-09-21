"""Opt-in, source-bound reservation correction; no network or spend authority.

Cache-read, cache-write and ordinary input are token categories, not three
charges to impose on every token. No cache hit is assumed: all reserved input
uses max(category rates). Unknown future outputs retain a UTF-8 byte envelope.
"""
from __future__ import annotations
from decimal import Decimal
from .wire import Invalid

POLICY = 'exclusive_categories_text_bounds_v2'
BILLING_SOURCE = 'https://openrouter.ai/docs/guides/best-practices/prompt-caching'


def input_rate(config: dict) -> Decimal:
    rates = [Decimal(config[k]) for k in ('input_rate','cache_read_rate','cache_write_rate')]
    if any(not r.is_finite() or r < 0 for r in rates):
        raise Invalid('invalid input category rate')
    return max(rates)


def message_bound(messages: list[dict], protocol_allowance: int) -> int:
    """Text bytes bound text token count; JSON wire escaping is not model text.

    The separate protocol allowance remains bound by the existing external
    tokenizer/usage attestation. This is NOT characters/4, a native-token count,
    a claim about model-specific framing, or a cache-discount estimate.
    """
    if type(protocol_allowance) is not int or protocol_allowance < 0:
        raise Invalid('invalid protocol allowance')
    for m in messages:
        if set(m) != {'role','content'} or not isinstance(m['content'],str) or m['role'] not in ('system','user','assistant'):
            raise Invalid('only the bound text-message transport is supported')
    return protocol_allowance + sum(len(m['content'].encode('utf-8')) + len(m['role'].encode('ascii')) for m in messages)


def token_categories(usage: dict) -> dict:
    """Reject malformed category accounting; do not overwrite actual charge."""
    total = usage.get('prompt_tokens')
    detail = usage.get('prompt_tokens_details')
    if type(total) is not int or total < 0 or not isinstance(detail,dict):
        raise Invalid('complete prompt category usage is unavailable')
    read, write = detail.get('cached_tokens'), detail.get('cache_write_tokens')
    if type(read) is not int or type(write) is not int or min(read,write) < 0 or read+write > total:
        raise Invalid('cache categories cannot exceed total prompt tokens')
    return {'uncached':total-read-write, 'cache_read':read, 'cache_write':write, 'total':total}


def category_cost(usage: dict, config: dict) -> Decimal:
    parts=token_categories(usage)
    completion=usage.get('completion_tokens')
    if type(completion) is not int or completion < 0:
        raise Invalid('completion usage unavailable')
    return (parts['uncached']*Decimal(config['input_rate']) + parts['cache_read']*Decimal(config['cache_read_rate'])
            + parts['cache_write']*Decimal(config['cache_write_rate']) + completion*Decimal(config['output_rate'])
            + Decimal(config['request_rate']))
