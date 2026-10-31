"""Read-only projection of recorded events. Never invent missing links or scores."""
from __future__ import annotations
from collections import Counter
import json,math

def build_history_view(events):
    attempts={};references={};changes=[];unlinked=[];request_meta={};graph=None;strategies={}
    def add_reference(node):
        if not isinstance(node,dict):return
        key=node.get('id') or node.get('node_id')
        if key:references[str(key)]={**references.get(str(key),{}),**node}
    for event in events:
        kind=event['eventType'];p=event.get('payload',{})
        if kind in ('configuration_recorded','strategy_changed'):
            config=p.get('configuration',{});changes.append(dict(id=event['id'],timestamp=event['timestampUtc'],kind=kind,configuration=config,configurationSha256=p.get('configurationSha256'),previousEventId=p.get('previousEventId')))
            graph=config.get('source_graph_identity') or graph
            for field in ('selected_nodes','reference_nodes','initial_population_nodes'):
                for node in config.get(field) or []:add_reference(node)
        elif kind=='reference_programs_recorded':
            for node in p.get('references',[]):add_reference(node)
        elif kind=='comparison_registered':
            manifest=p.get('manifest',{})
            for r in manifest.get('unique_requests',[]):request_meta[r['request_id']]=r
            for slot in manifest.get('analytical_slots',[]):
                key=slot.get('request_id');strategy=slot.get('strategy')
                if key and strategy and strategy not in strategies.setdefault(key,[]):strategies[key].append(strategy)
            for pool in manifest.get('parent_pools',{}).values():
                for node in pool:add_reference(node)
            if manifest.get('amendment') or manifest.get('previous_condition'):
                changes.append(dict(id=event['id'],timestamp=event['timestampUtc'],kind='registered_study_design',configuration={k:manifest.get(k) for k in ('previous_condition','amendment','stopping_rule','factors','budget','limitations')}))
    relevant={'llm_request','llm_response','llm_failure','pipeline_failure','program_generated','evaluation_started','packing_output','evaluation_exception','evaluation_finished','sample_recorded','trial_completed'}
    for event in events:
        kind=event['eventType'];p=event.get('payload',{})
        if kind not in relevant:continue
        cid=p.get('callId') or p.get('call_id') or p.get('research_call_id')
        if kind=='llm_request':cid=cid or event['id']
        if not cid:
            unlinked.append(dict(eventId=event['id'],eventType=kind,reason='No originating LLM call ID recorded (may be a seed or separate evaluation)'));continue
        cid=str(cid)
        a=attempts.setdefault(cid,dict(id=cid,status='pending',score=None,error=None,prompt=None,promptFormat='text',request=None,response=None,program=None,evaluatedProgram=None,parents=[],profile=None,events=[],evaluations=[],packing=None,startedAt=event['timestampUtc'],finishedAt=None))
        a['events'].append(event['id']);meta=request_meta.get(cid,{})
        parent=p.get('parent') or meta.get('parent')
        if isinstance(parent,dict):
            a['parents']=[parent];add_reference(parent)
        a['profile']=p.get('promptProfile') or meta.get('prompt_profile') or a['profile']
        a['strategies']=strategies.get(cid,[])
        if kind=='llm_request':
            request=p.get('request') or {};a['request']=request
            if isinstance(p.get('prompt'),str):a['prompt']=p['prompt']
            elif isinstance(request.get('prompt'),str):a['prompt']=request['prompt']
            elif 'messages' in request:a.update(prompt=json.dumps(request['messages'],ensure_ascii=False,indent=2),promptFormat='messages')
        elif kind=='llm_response':a['response']=p.get('response')
        elif kind in ('llm_failure','pipeline_failure'):
            a.update(status=p.get('status') or 'generation_failure',error=p.get('error') or p.get('errorType'),finishedAt=event['timestampUtc'])
        elif kind=='program_generated':a['program']=p.get('code') or p.get('program')
        elif kind=='evaluation_started':
            if p.get('program'):a['evaluatedProgram']=p['program']
            a['evaluations'].append(dict(id=p.get('evaluationId') or event['id'],startedAt=event['timestampUtc'],status='started'))
        elif kind=='packing_output':a['packing']={k:p.get(k) for k in ('circles','shape','finite','programSha256','provenance')}
        elif kind=='evaluation_exception':a['error']=p.get('error');a['status']='evaluation_exception'
        elif kind=='evaluation_finished':
            status=p.get('status') or 'evaluated'
            if status=='no_score' and a['status']=='evaluation_exception':status='evaluation_exception'
            a.update(status=status,score=p.get('score'),finishedAt=event['timestampUtc'])
            evaluation=next((e for e in a['evaluations'] if e['id']==p.get('evaluationId')),None)
            if evaluation is not None:evaluation.update(status=a['status'],score=a['score'],runtimeSeconds=p.get('runtimeSeconds'),finishedAt=event['timestampUtc'])
        elif kind=='sample_recorded':
            a['program']=a['program'] or p.get('program') or p.get('function') or None
            if p.get('score') is not None or a['score'] is None:a['score']=p.get('score')
            a['finishedAt']=event['timestampUtc']
            if 'parse_failed' in str(p.get('operator','')):a['status']='parse_failure'
            elif a['status']=='pending':a['status']='finite_score' if isinstance(a['score'],(int,float)) and math.isfinite(a['score']) else 'no_finite_score'
            if not a['parents']:
                a['parents']=[references.get(str(key),{'id':key}) for key in p.get('selected_node_ids',[]) if key]
        elif kind=='trial_completed':
            a.update(status=p.get('status') or 'completed',score=p.get('score'),finishedAt=event['timestampUtc'],error=p.get('error') or (p.get('screening') or {}).get('reason'))
            if 'circles' in p:a['packing']={k:p.get(k) for k in ('circles','shape','finite')}
            a['runtimeSeconds']=p.get('runtime_seconds') or p.get('wall_runtime_seconds')
    rows=list(attempts.values());valid_statuses={'valid','valid_score','finite_score'}
    scored=[a for a in rows if a['status'] in valid_statuses and isinstance(a['score'],(int,float)) and math.isfinite(a['score'])]
    pending=sum(a['status']=='pending' for a in rows)
    return dict(attempts=rows,references=list(references.values()),changes=changes,sourceGraph=graph,unlinkedEvents=unlinked,
        summary=dict(attempts=len(rows),scored=len(scored),failed=len(rows)-len(scored)-pending,pending=pending,referencePrograms=len(references),configurationRecords=len(changes),bestScore=max((a['score'] for a in scored),default=None),outcomes=dict(Counter(a['status'] for a in rows))))
