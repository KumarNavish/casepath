"""Deterministic PUBLIC-template preparation, not generative process induction.

Only named public catalogue fields are compiled. Temporal transitions remain
native graph relations, never implicit document-acquisition prerequisites.
Document sufficiency is a later model assessment; no case enters this compiler.
"""
from __future__ import annotations
import copy
import re
from ..wire import digest, Invalid
from ..preparation import runtime_registry
from ...source_only_runtime_v1 import SourceOnlyRuntime

TRUE = {"const": True}


def variable(text: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    if not name:
        raise Invalid("empty public condition")
    return ("condition_" if name[0].isdigit() else "") + name


def compile_public(sources: dict) -> dict:
    """Versioned transparent task adaptation; does not fill missing semantics."""
    rules = sources['rules']
    if rules.get('case_activation_values_included') is not False or rules.get('model_visibility') != 'all_three_templates_identical_for_every_case':
        raise Invalid('not the shared public rule library')
    templates = rules['templates']
    if len(templates) != 3 or len({t['domain'] for t in templates}) != 3:
        raise Invalid('all three public templates required')
    index = {}
    for ref, row in sources['registry'].items():
        if row['source_kind'] not in {'case_invariant_rule', 'swiss_authority_passage'}:
            raise Invalid('non-public source in preparation')
        index.setdefault(row['text'], []).append(ref)
    def refs(assertion):
        found = index.get(assertion)
        if not found:
            raise Invalid('public assertion has no exact registry binding')
        return sorted(found)
    descriptions, scopes, obligations, actions, caps = {}, [], [], [], []
    binding = {'contract':'casepath.native150-binding/1.0.0', 'control_concepts':[], 'control_relations':[],
               'branch_predicates':[], 'documents':[], 'decision_by_obligation':{}, 'terminal_outcome_ids':[]}
    documents = {}; trace = []
    for template in templates:
        domain = template['domain']; catalog=template['process_catalog']; nodes=catalog['nodes']
        domain_var='domain_'+domain; descriptions[domain_var]='This claim concerns '+domain.replace('_',' ')+'. Infer from the case; no family or domain answer is supplied.'
        root='scope_'+domain
        all_refs=sorted({r for n in nodes for r in refs(n['assertion'])})
        scopes.append({'scope_id':root,'when':{'var':domain_var},'parents':[],'join':'all','source_refs':all_refs})
        conditional_sources={e['source_node_id'] for e in catalog['transitions'] if str(e.get('condition') or '').lower() not in ('','true')}
        node_ids={n['node_id']: 'node_'+n['node_id'] for n in nodes}
        for n in nodes:
            sid='scope_'+n['node_id']
            scopes.append({'scope_id':sid,'when':copy.deepcopy(TRUE),'parents':[root],'join':'all','source_refs':refs(n['assertion'])})
            kind='outcome' if n['terminal'] else 'decision' if n['node_id'] in conditional_sources else 'process_step'
            binding['control_concepts'].append({'concept_id':node_ids[n['node_id']], 'kind':kind,'label':n['label'],
                    'activation':{'control_id':sid},'source_refs':refs(n['assertion'])})
            if n['terminal']:binding['terminal_outcome_ids'].append(node_ids[n['node_id']])
        for e in catalog['transitions']:
            condition=str(e.get('condition') or 'true')
            conditional=condition.strip().lower()!='true'
            expr=copy.deepcopy(TRUE)
            if conditional:
                name=variable(condition); descriptions.setdefault(name,condition); expr={'var':name}
                binding['branch_predicates'].append({'predicate_id':'predicate_'+e['edge_id'], 'expression':expr,'source_refs':refs(e['assertion'])})
            binding['control_relations'].append({'relation_id':'edge_'+e['edge_id'],
                    'relation_type':'branches_to' if conditional else 'precedes',
                    'source_id':node_ids[e['source_node_id']], 'target_id':node_ids[e['target_node_id']],
                    'activation':{'expression':{'all':[{'var':domain_var},expr]}}})
        for i, row in enumerate(catalog['documents']):
            stem=domain+'_'+str(i); support=refs(row['assertion']); doc=row['document_type']
            condition=row.get('condition'); when=copy.deepcopy(TRUE)
            if condition:
                m=re.fullmatch(r"scenario flag '([A-Za-z_][A-Za-z0-9_]*)' is active",condition)
                name=m.group(1) if m else variable(condition)
                descriptions.setdefault(name,condition);when={'var':name}
            if row['requirement_class']=='optional':
                name='optional_needed_'+stem
                descriptions[name]='The optional source-described evidence '+row['label']+' is needed to resolve this case; null when not established.'
                when={'var':name}
            if row['requirement_class'] not in {'mandatory','conditional','optional'}:
                raise Invalid('unsupported requirement class')
            # Source-listed locations are placement, not extra milestones.
            parent_scopes=['scope_'+n for n in row['required_at_node_ids']]
            if not parent_scopes or any(n not in node_ids for n in row['required_at_node_ids']):raise Invalid('unknown public attachment node')
            sid='need_scope_'+stem
            scopes.append({'scope_id':sid,'when':copy.deepcopy(TRUE),'parents':parent_scopes,'join':'any' if len(parent_scopes)>1 else 'all','source_refs':support})
            oid='obligation_'+stem; cid='cap_'+stem; fid='fact_'+stem; decision='need_'+stem
            obligations.append({'obligation_id':oid,'scope_id':sid,'when':when,'acquire_when':copy.deepcopy(TRUE),'capability_ids':[cid],'source_refs':support})
            # Explicit catalogue-to-task naming, not a discovered material fact.
            caps.append({'capability_id':cid,'fact_id':fid,'fact_statement':'Evidence state for '+row['label'],
                         'must_show':'Evidence capable of resolving '+row['label'],'source_refs':support,
                         'routes':[{'route_id':'route_'+stem,'document_ids':[doc],'source_refs':support}]})
            binding['control_concepts'].append({'concept_id':decision,'kind':'decision','label':'Decide whether '+row['label']+' is needed',
                    'activation':{'control_id':oid},'source_refs':support})
            binding['decision_by_obligation'][oid]=decision
            # This is an evidence-need decision, NOT the renamed parent process step.
            documents.setdefault(doc,{'item_id':'document_'+doc,'document_id':doc,'label':row['label'],'source_refs':[]})
            if documents[doc]['label']!=row['label']:raise Invalid('ambiguous public document name')
            documents[doc]['source_refs']=sorted(set(documents[doc]['source_refs'])|set(support))
            trace.append({'obligation_id':oid,'public_domain':domain,'public_document_index':i,'source_refs':support,
                          'fact_capability_semantics':'catalogue evidence-state task adaptation; no inferred document contents'})
    control={'contract':'casepath.obligation-control/1.0.0','variables':sorted(descriptions),'scopes':scopes,'obligations':obligations,'actions':actions}
    binding['documents']=[documents[k] for k in sorted(documents)]
    prepared={'control':control,'capabilities':caps,'native_binding':binding,'variable_descriptions':dict(sorted(descriptions.items())),
              'source_accounting':{r:{'status':'used','reason':'public source remains visible; compiler does not certify entailment'} for r in sources['registry']}}
    runtime=SourceOnlyRuntime(control,caps,binding,runtime_registry(sources))
    manifest={'contract':'casepath.compiled-public-preparation/3.0.0','source_identity':sources['identity'],
      'preparation_kind':'deterministic_public_catalogue_compilation_not_model_induction',
      'case_inputs_used':False,'model_calls':0,'provider_cost_usd':'0.00','prepared_sha256':digest(prepared),
      'runtime_pack_identity':runtime.pack_identity,'trace':trace,
      'semantic_limits':['one source-listed document per compiled capability; no extra proof alternatives invented',
       'unknown temporal transitions preserved symbolically; not converted to acquisition gates',
       'no substantive fact content or adequacy can be learned by source compilation',
       'optional requests require explicit case assessment',
       'all three domains supplied; domain routing is model-inferred',
       'action execution and interactive success not measured by this compilation']}
    return {'prepared':prepared,'manifest':manifest,'runtime':runtime}
