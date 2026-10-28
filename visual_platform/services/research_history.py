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
    snapshot=clean({k:config.get(k) for k in ('revision_id','workspace_id','source_revision_id','merged_source_revision_ids','mode','region','prompt','selected_nodes','reference_nodes','initial_population_nodes','method','llm')})
    digest=hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    if previous and previous[-1]['payload']['configurationSha256']==digest:return previous[-1]['id']
    return append_event(revision_dir,'strategy_changed' if previous else 'configuration_recorded',dict(configurationSha256=digest,configuration=snapshot,previousEventId=previous[-1]['id'] if previous else None))
