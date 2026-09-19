"""Shared semantic input projection and explicit native reference tables.

Long locator hashes/paths are not repeatedly verbalized. Source selectors refer
to the exact immutable registry retained in the codebook. This input projection
is NOT claimed byte-identical/lossless relative to original wire JSON. All source
assertion texts, case texts, inventories and evidence coverage remain available.
"""
from __future__ import annotations
import copy
import re
import ast
from ..wire import digest
from .codec import STATES,MODES,PRESENCE


def simplified(expression, aliases):
    text=re.sub(r"\btrue\b","True",expression)
    text=re.sub(r"\bfalse\b","False",text)
    tree=ast.parse(text,mode='eval').body
    def rec(n):
        if isinstance(n,ast.Name):return aliases.get(n.id,n.id)
        if isinstance(n,ast.Constant) and type(n.value) is bool:return 'true' if n.value else 'false'
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.Not):return 'not ('+rec(n.operand)+')'
        if isinstance(n,ast.BoolOp):
            vals=[rec(x) for x in n.values];op='and' if isinstance(n.op,ast.And) else 'or'
            neutral='true' if op=='and' else 'false';absorbing='false' if op=='and' else 'true'
            if absorbing in vals:return absorbing
            vals=list(dict.fromkeys(v for v in vals if v!=neutral))
            return neutral if not vals else vals[0] if len(vals)==1 else '('+(' '+op+' ').join(vals)+')'
        raise ValueError('source compiler emitted unsupported display predicate')
    return rec(tree)


def make_view(sources,book):
    labels=[];label_index={};exprs=[];expr_index={}; var_alias={v:'v'+str(i) for i,v in enumerate(book.variables)}
    def label(s):
        if s not in label_index:
            value=s
            for prefix,code in [('Decide whether ','Q'),('Evidence state for ','F'),('Evidence capable of resolving ','E')]:
                if s.startswith(prefix):
                    tail=s[len(prefix):]
                    if code=='Q' and tail.endswith(' is needed'):tail=tail[:-len(' is needed')]
                    value=[code,label(tail)];break
            label_index[s]=len(labels);labels.append(value)
        return label_index[s]
    def expr(s):
        if s not in expr_index:expr_index[s]=len(exprs);exprs.append(simplified(s,var_alias))
        return expr_index[s]
    refs={r:i for i,r in enumerate(book.source_refs)}
    locus={}
    templates=[]
    # Templates expose all semantic fields; formula assertions are reconstructed
    # below and compared exactly. A nonformula assertion is preserved literally.
    assertion_overrides=[]
    for ti,t in enumerate(sources['rules']['templates']):
        cat=t['process_catalog'];nodes={n['node_id']:n for n in cat['nodes']}
        entry={'domain':t['domain'],'title':t['title'],'policy':t['content'],
               'nodes':[],'transitions':[],'documents':[]}
        node_number={n['node_id']:i for i,n in enumerate(cat['nodes'])}
        for ni,n in enumerate(cat['nodes']):
            entry['nodes'].append([n['node_id'],label(n['label']),n['responsibility'],n['terminal']])
            expected=f"The {t['domain']} process includes the step '{n['label']}' owned by {n['responsibility']}."
            locus[n['assertion']]=['node',ti,ni]
            if expected!=n['assertion']:assertion_overrides.append([locus[n['assertion']],n['assertion']])
        for ei,e in enumerate(cat['transitions']):
            entry['transitions'].append([e['edge_id'],node_number[e['source_node_id']],node_number[e['target_node_id']],e['condition'],e['optional_path']])
            expected=f"After '{nodes[e['source_node_id']]['label']}', proceed to '{nodes[e['target_node_id']]['label']}' when '{e['condition']}'."
            locus[e['assertion']]=['edge',ti,ei]
            if expected!=e['assertion']:assertion_overrides.append([locus[e['assertion']],e['assertion']])
        for di,d in enumerate(cat['documents']):
            entry['documents'].append([d['document_type'],label(d['label']),d['requirement_class'],d['condition'],[node_number[n] for n in d['required_at_node_ids']]])
            cond=' when '+d['condition'] if d['condition'] else ''
            expected=f"'{d['label']}' is a {d['requirement_class']} evidence item{cond} for process step(s) {', '.join(d['required_at_node_ids'])}."
            locus[d['assertion']]=['document',ti,di]
            if expected!=d['assertion']:assertion_overrides.append([locus[d['assertion']],d['assertion']])
        templates.append(entry)
    def prov(row):
        return [book.locator_ids[digest(x)] for x in row.get('provenance',[])]
    c=book.tables['c'];d=book.tables['d']; endpoint={r['concept_id']:'c'+str(i) for i,r in enumerate(c)}
    endpoint.update({r['item_id']:'d'+str(i) for i,r in enumerate(d)})
    native={'c':[[{'process_step':'s','decision':'q','outcome':'o','fact':'f','evidence_capability':'e','document':'d'}[r['kind']],label(r['label']),expr(r['active_when']),prov(r)] for r in c],
      'r':[[{'precedes':'p','branches_to':'b','requires_fact':'f','supported_by':'e','satisfied_by':'d','contradicts':'x'}[r['relation_type']],endpoint[r['source_id']],endpoint[r['target_id']],expr(r['active_when'])] for r in book.tables['r']],
      'b':[[expr(r['expression']),prov(r)] for r in book.tables['b']],
      'd':[[r['document_id'],label(r['label']),expr(r['active_when']),prov(r)] for r in d]}
    material=book.case['visible']['materials'];materials=[[m,material[m]] for m in book.material_ids]
    source_rows=[]
    for ref in book.source_refs:
        row=book.case['registry'][ref];text=row['text']
        if text in locus:where=locus[text]
        else:
            found=None
            for mi,m in enumerate(book.material_ids):
                if text and text in material[m]:
                    start=material[m].find(text);found=['span',mi,start,start+len(text)];break
            where=found or ['text',text]
        source_rows.append([{'case_invariant_rule':'n','swiss_authority_passage':'a','observable_message_span':'m','observable_attachment_inventory':'i'}[row['source_kind']],where])
    original=book.case['visible']
    message={k:v for k,v in original['customer_message'].items() if k!='body'}
    attachments=[]
    for a in original['attachments']:
        attachments.append({k:v for k,v in a.items() if k not in {'text','sha256'}})
        attachments[-1]['material_index']=book.material_ids.index(a['artifact_id'])
    view={'templates':templates,'assertion_overrides':assertion_overrides,'labels':labels,'expressions':exprs,
      'source_selectors':source_rows,'native_prototypes':native,
      'variables':[book.preparation['prepared']['variable_descriptions'][v] for v in book.variables],
      'capabilities':[[label(c['fact_statement']),label(c['must_show']),
                       [[book.documents.index(x) for x in r['document_ids']] for r in c['routes']]] for c in book.capabilities],
      'document_order':book.documents,'materials':materials,'message_metadata':message,
      'submission':{k:v for k,v in original['submission'].items() if k!='claim_id'},'attachments':attachments,
      'enums':{'document_state':STATES,'request_mode':MODES,'presence':PRESENCE},
      'preparation_kind':'public-template compilation, not model induction',
      'source_reference_rule':'Every source selector expands to its exact bound registry locator; no target-derived selection.',
      'legend':{'assertion_expansion':{'node':"The {domain} process includes the step '{label}' owned by {responsibility}.",'edge':"After '{source_label}', proceed to '{target_label}' when '{condition}'.",'document':"'{label}' is a {requirement_class} evidence item{condition_suffix} for process step(s) {node_ids_comma_space}.",'condition_suffix':"empty for null; otherwise ' when '+condition",'overrides':'assertion_overrides replace the corresponding whole sentence exactly'},'label_prefixes':{'Q':'Decide whether LABEL is needed','F':'Evidence state for LABEL','E':'Evidence capable of resolving LABEL'},'source_kind':{'n':'normative public rule','a':'authority','m':'case message span','i':'availability inventory'},'concept_columns':['kind(s=step,q=decision,o=outcome,f=fact,e=capability,d=document)','label_index','expression_index','source_indices'],'relation_columns':['type(p=precedes,b=branches_to,f=requires_fact,e=supported_by,d=satisfied_by,x=contradicts)','source_symbol','target_symbol','expression_index'],'predicate_columns':['expression_index','source_indices'],'document_columns':['document_id','label_index','expression_index','source_indices'],'template_columns':{'nodes':['id','label_index','responsibility','terminal'],'transitions':['id','source_node_index','target_node_index','condition','optional_path'],'documents':['id','label_index','requirement_class','condition','required_node_indices']},'variable_names':'vN denotes variables[N]; indices are presentation codes, never family answers; expression displays remove Boolean identities only; output selectors retain exact originals','endpoint_symbols':'cN,dN,bN,rN refer exactly to rows in native_prototypes; native IDs are expanded by the codebook'},
      'omitted_redundant_fields':['full cryptographic hashes and duplicated paths; retained in immutable input/codec bindings'],
      'case_input_coverage':'full existing text projection; JPEG opaque; PDF text not visual completeness'}
    # labels appended while capabilities are built refer to the same list object.
    return view


def expand_source_text(view, index):
    """Recover the exact source assertion text, not merely its paraphrase."""
    where = view['source_selectors'][index][1]
    if where[0] == 'text':return where[1]
    if where[0] == 'span':return view['materials'][where[1]][1][where[2]:where[3]]
    for key, text in view['assertion_overrides']:
        if key == where:return text
    def label(index):
        value=view['labels'][index]
        if isinstance(value,str):return value
        code,child=value
        return {'Q':'Decide whether '+label(child)+' is needed','F':'Evidence state for '+label(child),'E':'Evidence capable of resolving '+label(child)}[code]
    template=view['templates'][where[1]]
    if where[0]=='node':
        n=template['nodes'][where[2]]
        return f"The {template['domain']} process includes the step '{label(n[1])}' owned by {n[2]}."
    if where[0]=='edge':
        e=template['transitions'][where[2]]
        return f"After '{label(template['nodes'][e[1]][1])}', proceed to '{label(template['nodes'][e[2]][1])}' when '{e[3]}'."
    if where[0]=='document':
        d=template['documents'][where[2]];suffix=' when '+d[3] if d[3] else ''
        return f"'{label(d[1])}' is a {d[2]} evidence item{suffix} for process step(s) {', '.join(template['nodes'][i][0] for i in d[4])}."
    raise ValueError('unknown source text locator')
