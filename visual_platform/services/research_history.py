"""Append-only per-revision research events, independent of sample validity."""
from __future__ import annotations
import hashlib
import json
import math
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from contextvars import ContextVar

current_call_id=ContextVar('research_history_call_id',default=None)

_SECRETS={'key','api_key','apikey','authorization','password','token','access_token','secret'}

def clean(value):
    if isinstance(value,dict):
        return {str(k):('[REDACTED]' if str(k).lower() in _SECRETS else clean(v)) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value):return {'nonfinite':str(value)}
    if isinstance(value,Path):return str(value)
    if value is None or isinstance(value,(str,int,float,bool)):return value
    return repr(value)

def append_event(revision_dir,event_type,payload,*,event_id=None):
    directory=Path(revision_dir)/'research_history';directory.mkdir(parents=True,exist_ok=True)
    event_id=event_id or uuid.uuid4().hex
    if not event_id.isalnum():raise ValueError('Invalid event id')
    record=dict(schemaVersion=1,id=event_id,revisionId=Path(revision_dir).name,
        timestampUtc=datetime.now(timezone.utc).isoformat(),eventType=event_type,payload=clean(payload))
    text=json.dumps(record,ensure_ascii=False,allow_nan=False,sort_keys=True)
    # Write and fsync before publishing. Exclusive hard-link refuses duplicate ids.
    fd,name=tempfile.mkstemp(prefix='.pending-',dir=directory)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            stream.write(text);stream.flush();os.fsync(stream.fileno())
        os.link(name,directory/f'{event_id}.json')
    finally:Path(name).unlink(missing_ok=True)
    return event_id

def read_events(revision_dir):
    records=[]
    for path in (Path(revision_dir)/'research_history').glob('*.json'):
        records.append(json.loads(path.read_text(encoding='utf-8')))
    return sorted(records,key=lambda e:(e['timestampUtc'],e['id']))

def capture_configuration(revision_dir,config):
    previous=[e for e in read_events(revision_dir) if e['eventType'] in ('configuration_recorded','strategy_changed')]
    snapshot=clean({k:config.get(k) for k in ('revision_id','workspace_id','source_revision_id','merged_source_revision_ids','source_graph_identity','source_graph_artifact_id','source_graph_sha256','source_graph_content_sha256','source_archive_sha256','mode','region','prompt','selected_nodes','reference_nodes','initial_population_nodes','method','llm')})
    digest=hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    if previous and previous[-1]['payload']['configurationSha256']==digest:return previous[-1]['id']
    return append_event(revision_dir,'strategy_changed' if previous else 'configuration_recorded',dict(configurationSha256=digest,configuration=snapshot,previousEventId=previous[-1]['id'] if previous else None))

def source_graph_identity(revision_id):
    """Freeze the identity of the current ready full graph, without rebuilding it."""
    if not revision_id:return None
    from visual_platform.repositories.artifact_repository import list_artifacts_for_revision
    artifacts=list_artifacts_for_revision(revision_id,artifact_type='graph',artifact_role='full',status='ready')
    if not artifacts:return dict(sourceRevisionId=revision_id,status='no_ready_graph_artifact')
    artifact=artifacts[0]
    identity=dict(sourceRevisionId=revision_id,artifactId=artifact['artifact_id'],contentSha256=artifact.get('content_digest'),inputDigest=artifact.get('input_digest'),metadata=artifact.get('metadata',{}),status='recorded')
    uri=artifact.get('storage_uri')
    if uri and Path(uri).is_absolute() and Path(uri).is_file():
        actual=hashlib.sha256(Path(uri).read_bytes()).hexdigest()
        identity['observedFileSha256']=actual
        if identity['contentSha256'] and actual!=identity['contentSha256']:raise ValueError('Source graph content digest mismatch')
    return identity

def capture_references(revision_dir,**groups):
    """Freeze hydrated selected source, keeping node IDs and source hashes."""
    references=[]
    for role,nodes in groups.items():
        for node in nodes or []:
            snapshot=clean(dict(node));source=str(snapshot.get('functionPreview') or snapshot.get('program') or snapshot.get('function') or '')
            snapshot.update(referenceRole=role,recordedSource=source or None,recordedSourceSha256=hashlib.sha256(source.encode()).hexdigest() if source else None)
            references.append(snapshot)
    payload=dict(references=references)
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    previous=[e for e in read_events(revision_dir) if e['eventType']=='reference_programs_recorded']
    if previous and previous[-1]['payload'].get('referencesSha256')==digest:return previous[-1]['id']
    return append_event(revision_dir,'reference_programs_recorded',dict(**payload,referencesSha256=digest))
