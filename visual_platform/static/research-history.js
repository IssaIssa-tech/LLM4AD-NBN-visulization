/* Recorded text uses textContent; code and prompts never become HTML. */
(() => {
  const $=id=>document.getElementById(id),el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  const json=v=>typeof v==='string'?v:JSON.stringify(v,null,2),scored=a=>['valid','valid_score','finite_score'].includes(a.status)&&typeof a.score==='number'&&Number.isFinite(a.score);
  const label=s=>String(s||'unknown').replaceAll('_',' '),score=v=>typeof v==='number'?v.toFixed(5):v&&v.nonfinite?v.nonfinite:'No score';let snapshot=null;
  function section(parent,title,value,open=false){const d=el('details');d.open=open;d.append(el('summary',title),el('pre',value==null?'Not recorded.':json(value)));parent.append(d);return d;}
  function fact(parent,title,value){const n=el('div',null,'fact');n.append(el('span',title),el('div',value==null||value===''?'Not recorded':String(value)));parent.append(n);}
  const referenceId=n=>n.id||n.node_id||'Unidentified reference';
  function renderAttempts(){
    if(!snapshot)return;const query=$('search').value.toLowerCase(),filter=$('outcome').value,rows=snapshot.view.attempts;
    const visible=rows.filter(a=>(!query||JSON.stringify([a.id,a.profile,a.parents,a.strategies,a.prompt,a.program]).toLowerCase().includes(query))&&(filter==='all'||filter==='scored'&&scored(a)||filter==='pending'&&a.status==='pending'||filter==='failed'&&!scored(a)&&a.status!=='pending'));
    $('visibleCount').textContent=visible.length+' / '+rows.length+' attempts';$('attemptList').replaceChildren();
    for(const a of visible){
      const card=el('details',null,'record');card.dataset.callId=a.id;const head=el('summary'),title=el('div',null,'title');title.append(el('b',a.id),el('small',[a.profile,...(a.strategies||[])].filter(Boolean).join(' · ')||a.startedAt));
      head.append(title,el('span',label(a.status),'badge '+(scored(a)?'scored':a.status==='pending'?'':'failed')),el('span',score(a.score),'score'));card.append(head);
      const body=el('div',null,'body'),facts=el('div',null,'facts');
      fact(facts,'Selected programs',a.parents.length?a.parents.map(referenceId).join(', '):'No call-specific link recorded; see run references and exact prompt');
      fact(facts,'NBN references',a.parents.map(p=>p.nbn_node_id??p.nbnNodeId??p.ofecIndex??'Not recorded').join(', ')||'Not recorded');
      fact(facts,'Started (recorded UTC)',a.startedAt);fact(facts,'Finished (recorded UTC)',a.finishedAt);body.append(facts);if(a.error)body.append(el('p',a.error,'error'));
      section(body,a.promptFormat==='messages'?'Exact prompt messages':'Exact prompt',a.prompt);section(body,'Generated program',a.program||a.evaluatedProgram);
      if(a.evaluatedProgram&&a.program&&a.evaluatedProgram!==a.program)section(body,'Evaluated program',a.evaluatedProgram);
      section(body,'Evaluation records and packing output',{evaluations:a.evaluations,packing:a.packing,recordedStatus:a.status,recordedScore:a.score});section(body,'Raw model response',a.response);section(body,'Linked event IDs',a.events);card.append(body);$('attemptList').append(card);
    }
    if(!visible.length)$('attemptList').append(el('p','No matching attempts.','empty'));
  }
  function render(data){
    if(!data.view)throw Error('This response needs the updated platform history API.');snapshot=data;window.__historySnapshot=data;const view=data.view;$('summary').replaceChildren();
    for(const [title,value] of [['Attempts',view.summary.attempts],['Scored outputs',view.summary.scored],['Unsuccessful',view.summary.failed],['Pending',view.summary.pending],['Selected programs',view.summary.referencePrograms],['Best recorded score',view.summary.bestScore==null?'—':score(view.summary.bestScore)]]){const card=el('div',null,'metric');card.append(el('span',title),el('strong',value));$('summary').append(card);}
    $('verification').hidden=!view.changes.some(c=>/synthetic|verification|smoke/.test(c.configuration?.mode||'')||c.configuration?.method?.verificationOnly);
    $('referenceList').replaceChildren();for(const node of view.references){const card=el('details',null,'record'),head=el('summary'),title=el('div',null,'title');title.append(el('b',referenceId(node)),el('small','NBN node: '+(node.nbn_node_id??node.nbnNodeId??node.ofecIndex??'not recorded')));head.append(title);card.append(head);const body=el('div',null,'body');section(body,'Recorded parent source',node.recordedSource||node.functionPreview||node.program||node.function||'No separate source snapshot in this older record. The exact model prompt remains available on its attempt.');section(body,'Reference identity and archived metadata',node);card.append(body);$('referenceList').append(card);}
    if(!view.references.length)$('referenceList').append(el('p','No selected programs were recorded for this revision.','empty'));$('graphIdentity').textContent=view.sourceGraph?json(view.sourceGraph):'No source graph identity was recorded.';
    $('changeList').replaceChildren();for(const change of view.changes){const card=el('details',null,'record'),head=el('summary');head.append(el('div',label(change.kind)+' · '+change.timestamp,'title'));card.append(head);const body=el('div',null,'body');section(body,'Recorded configuration',change.configuration,true);section(body,'Change identity',change);card.append(body);$('changeList').append(card);}
    $('rawList').replaceChildren();$('coverage').textContent=data.coverage+' '+view.unlinkedEvents.length+' events have no originating LLM call link (for example seed evaluations). They remain in this export.';
    for(const event of data.events){const card=el('details',null,'record'),head=el('summary');head.append(el('div',label(event.eventType)+' · '+event.timestampUtc,'title'));card.append(head);const body=el('div',null,'body');body.append(el('pre',json(event)));card.append(body);$('rawList').append(card);}
    $('revision').value=data.revisionId;$('status').textContent=data.count+' preserved events · '+view.summary.attempts+' linked attempts · '+data.revisionId;$('export').disabled=false;renderAttempts();window.__historyReady=true;
  }
  async function load(revision){if(!/^[A-Za-z0-9_-]+$/.test(revision))throw Error('Enter a valid revision ID.');$('status').textContent='Loading history…';$('export').disabled=true;window.__historyReady=false;const response=await fetch('/api/revisions/'+encodeURIComponent(revision)+'/research-history');if(!response.ok)throw Error('Unable to load history: HTTP '+response.status);render(await response.json());history.replaceState(null,'','?revision='+encodeURIComponent(revision));}
  const failure=e=>{$('status').textContent=String(e);};$('form').onsubmit=e=>{e.preventDefault();load($('revision').value.trim()).catch(failure);};$('runs').onchange=()=>{if($('runs').value)load($('runs').value).catch(failure);};$('search').oninput=renderAttempts;$('outcome').onchange=renderAttempts;
  for(const button of document.querySelectorAll('[data-tab]'))button.onclick=()=>{for(const tab of document.querySelectorAll('.tab'))tab.hidden=tab.id!==button.dataset.tab;for(const b of document.querySelectorAll('[data-tab]'))b.classList.toggle('active',b===button);};
  $('export').onclick=()=>{if(!snapshot)return;const url=URL.createObjectURL(new Blob([JSON.stringify(snapshot,null,2)],{type:'application/json'})),a=el('a');a.href=url;a.download='research-history-'+snapshot.revisionId+'.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  async function boot(){
    if(window.HISTORY_SNAPSHOT){$('snapshotLabel').hidden=false;const option=el('option',window.HISTORY_SNAPSHOT.revisionId);option.value=window.HISTORY_SNAPSHOT.revisionId;$('runs').append(option);$('runs').value=option.value;$('runs').disabled=true;$('revision').readOnly=true;$('form').querySelector('button').disabled=true;render(window.HISTORY_SNAPSHOT);return;}
    const requested=new URLSearchParams(location.search).get('revision'),response=await fetch('/api/research-history');if(!response.ok)throw Error('Unable to list experiments: HTTP '+response.status);const data=await response.json();
    for(const run of data.runs){const option=el('option',run.revisionId+' · '+run.eventCount+' events');option.value=run.revisionId;$('runs').append(option);}
    const first=requested||data.runs.find(r=>!/history-(smoke|acceptance|verification)/.test(r.revisionId))?.revisionId||data.runs[0]?.revisionId;
    if(first){$('runs').value=first;await load(first);}else{$('status').textContent='No recorded experiments yet. New instrumented runs will appear here automatically.';window.__historyReady=true;}
  }
  boot().catch(failure);
})();
