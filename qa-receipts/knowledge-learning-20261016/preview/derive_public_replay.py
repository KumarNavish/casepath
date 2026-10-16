"""Read-only external comparison helper; filtered exports are not native replay authority."""
import json
from hashlib import sha256
from pathlib import Path
import sys
import inspect
from casepath_api.autonomous_knowledge_v1 import _learning_replay

source = Path(sys.argv[1])
output = Path(sys.argv[2])
knowledge = json.loads((source / 'knowledge.json').read_text())
claims = json.loads((source / 'claims.json').read_text())['claims']
filtered = json.loads((source / 'knowledge-events.json').read_text())
pins = json.loads((source / 'knowledge-pins.json').read_text())
states = {claim['claim_id']: {'claim_id': claim['claim_id'], 'title': claim['title'],
          'knowledge_published': [], 'knowledge_uses': [], 'events': []} for claim in claims}
for claim_id, exported in filtered['claims'].items():
    state = states.setdefault(claim_id, {'claim_id': claim_id, 'title': None,
        'knowledge_published': [], 'knowledge_uses': [], 'events': []})
    state.update(revision=exported['current_revision'], state_sha256=exported['current_state_sha256'],
                 last_event_sha256=exported['cursor_sha256'])
    for event in exported['events']:
        field = {'knowledge.used': 'knowledge_uses', 'knowledge.published': 'knowledge_published'}[event['kind']]
        state[field].append(event['payload']['knowledge'])
        state['events'].append({key: event.get(key) for key in
            ('kind', 'sequence', 'created_at', 'event_sha256', 'command_sha256', 'idempotency_key')})
for claim_id, exported in pins['claims'].items():
    if claim_id in states:
        states[claim_id]['semantic_contexts'] = exported['semantic_contexts']
result = {**knowledge, 'learning_replay': _learning_replay(list(states.values()), knowledge)}
output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
receipt = {'purpose': 'External filtered public synthetic comparison; no complete native journal/source validation',
           'generator_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
           'projection_module_sha256': sha256(Path(inspect.getsourcefile(_learning_replay)).read_bytes()).hexdigest(),
           'projection_function_sha256': sha256(inspect.getsource(_learning_replay).encode()).hexdigest(),
           'output_sha256': sha256(output.read_bytes()).hexdigest(), 'output_bytes': output.stat().st_size,
           'inputs': {name: sha256((source / name).read_bytes()).hexdigest() for name in
                      ('knowledge.json', 'claims.json', 'knowledge-events.json', 'knowledge-pins.json')},
           'totals': result['learning_replay']['totals'],
           'unavailable_use_pins': sum(event['kind'] == 'knowledge.used' and event['pin_status'] == 'unavailable'
                                       for event in result['learning_replay']['events'])}
output.with_suffix('.receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, sort_keys=True))
