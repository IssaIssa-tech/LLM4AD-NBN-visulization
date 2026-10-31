// Isolated headless Edge profile; no user browser or research execution.
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {spawn} from 'node:child_process';
const root=process.cwd(),out=path.resolve(process.argv[2]||path.join(root,'output/history_feature_verification_20261031'));
const profile=path.join(out,'browser_profile_'+Date.now()),downloads=path.join(out,'export_check');
await fs.mkdir(profile,{recursive:true});await fs.mkdir(downloads,{recursive:true});
const browser=spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',['--headless=new','--no-first-run','--disable-background-networking','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
const delay=ms=>new Promise(r=>setTimeout(r,ms));let socket,id=0,callbacks=new Map(),errors=[];
try {
  let endpoint;
  for(let i=0;i<100;i++){try{const [port]=String(await fs.readFile(path.join(profile,'DevToolsActivePort'))).split('\n');endpoint='http://127.0.0.1:'+port;break;}catch{await delay(100);}}
  if(!endpoint)throw Error('Browser did not start');
  const pages=await (await fetch(endpoint+'/json/list')).json();socket=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const c=callbacks.get(m.id);if(c){callbacks.delete(m.id);m.error?c.reject(Error(JSON.stringify(m.error))):c.resolve(m.result);}}else if(m.method==='Runtime.exceptionThrown')errors.push(m.params);};
  const rpc=(method,params={})=>new Promise((resolve,reject)=>{const current=++id;const timer=setTimeout(()=>{callbacks.delete(current);reject(Error('CDP timed out: '+method));},15000);callbacks.set(current,{resolve:v=>{clearTimeout(timer);resolve(v);},reject:e=>{clearTimeout(timer);reject(e);}});socket.send(JSON.stringify({id:current,method,params}));});
  const evaluate=async expression=>{const r=await rpc('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
  const assert=(v,msg)=>{if(!v)throw Error(msg);};
  console.log('Browser connected');await rpc('Runtime.enable');await rpc('Page.enable');
  await rpc('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloads});
  await rpc('Emulation.setDeviceMetricsOverride',{width:1440,height:1080,deviceScaleFactor:1,mobile:false});
  const open=async filename=>{await rpc('Page.navigate',{url:pathToFileURL(path.join(out,filename)).href});for(let i=0;i<100;i++){if(await evaluate('window.__historyReady===true'))return;await delay(50);}throw Error('History screen did not load');};
  await open('research_history_review.html');console.log('Research history rendered');
  assert(await evaluate('document.querySelectorAll("#attemptList>.record").length===14'),'Expected all 14 real attempts');
  assert(await evaluate('!document.querySelector("#snapshotLabel").hidden && document.querySelector("#verification").hidden'),'Snapshot / research labels');
  const filter=async value=>evaluate(`document.querySelector('#outcome').value=${JSON.stringify(value)};document.querySelector('#outcome').dispatchEvent(new Event('change'));document.querySelectorAll('#attemptList>.record').length`);
  assert(await filter('scored')===1,'Scored filter');assert(await filter('failed')===13,'Failure filter');assert(await filter('pending')===0,'Pending filter');await filter('all');
  assert(await evaluate('document.querySelectorAll("#referenceList>.record").length===7'),'Seven selected programs');
  assert(await evaluate('document.querySelectorAll("#changeList>.record").length===2'),'Configuration history');
  assert(await evaluate('window.__historySnapshot.view.sourceGraph!==null'),'Source graph identity');
  await evaluate(`document.querySelector('#search').value=window.__historySnapshot.view.attempts[0].id;document.querySelector('#search').dispatchEvent(new Event('input'));`);
  assert(await evaluate('document.querySelectorAll("#attemptList>.record").length===1'),'Search matches one call');
  await evaluate(`document.querySelector('#search').value='';document.querySelector('#search').dispatchEvent(new Event('input'));document.querySelector('#attemptList>.record').open=true;`);
  assert(await evaluate(`Array.from(document.querySelectorAll('#attemptList>.record .body details')).some(d=>d.querySelector('summary').textContent.startsWith('Exact prompt') && d.querySelector('pre').textContent.length>20)`),'Exact prompt is visible');
  await rpc('Page.captureScreenshot',{format:'png',captureBeyondViewport:false}).then(r=>fs.writeFile(path.join(out,'history_review_desktop.png'),Buffer.from(r.data,'base64')));
  await evaluate(`document.querySelector('#export').click()`);
  const actual=JSON.parse(await fs.readFile(path.join(out,'gpu_study_snapshot.json'),'utf8'));let exported;
  for(let i=0;i<100;i++){try{exported=JSON.parse(await fs.readFile(path.join(downloads,'research-history-'+actual.revisionId+'.json'),'utf8'));break;}catch{await delay(50);}}
  assert(exported && JSON.stringify(exported.events)===JSON.stringify(actual.events),'Export preserves every raw event');
  await evaluate(`window.__historySnapshot.view.attempts[0].prompt='<img src=x onerror="window.__injected=true">';document.querySelector('#search').dispatchEvent(new Event('input'));document.querySelector('#attemptList>.record').open=true;`);
  assert(await evaluate('!window.__injected && document.querySelectorAll("#attemptList img").length===0'),'Prompts render as text, not executable HTML');
  await open('tracking_feature_demo.html');console.log('Verification history rendered');
  assert(await evaluate('!document.querySelector("#verification").hidden'),'Synthetic verification prominently labelled');
  assert(await evaluate('document.querySelectorAll("#attemptList>.record").length===8'),'All eight verification calls');
  assert(await evaluate('window.__historySnapshot.view.references.every(n=>n.recordedSource && n.nbnNodeId!=null)'),'Original sources and NBN identities');
  assert(await evaluate('window.__historySnapshot.view.changes.length===2'),'Original and changed prompt retained');
  await evaluate(`document.querySelector('#attemptList>.record').open=true;document.querySelector('#attemptList>.record .body details').open=true;`);
  await rpc('Page.captureScreenshot',{format:'png',captureBeyondViewport:false}).then(r=>fs.writeFile(path.join(out,'tracking_feature_desktop.png'),Buffer.from(r.data,'base64')));
  await rpc('Emulation.setDeviceMetricsOverride',{width:400,height:900,deviceScaleFactor:1,mobile:true});await delay(100);
  const dimensions=await evaluate('({viewport:window.innerWidth,content:document.documentElement.scrollWidth})');assert(dimensions.content<=dimensions.viewport,'Mobile view overflows');
  await rpc('Page.captureScreenshot',{format:'png',captureBeyondViewport:false}).then(r=>fs.writeFile(path.join(out,'tracking_feature_mobile.png'),Buffer.from(r.data,'base64')));
  assert(errors.length===0,'Browser errors: '+JSON.stringify(errors));
  const report={passed:true,browser:'Microsoft Edge headless, isolated profile',researchAttempts:14,verificationAttempts:8,checks:['status filters','call search','parent references','source graph identity','prompt and configuration changes','exact prompt text','full JSON export with unchanged raw events','HTML injection protection','desktop and mobile rendering','verification labels'],rawEventCount:actual.events.length,errors};
  await fs.writeFile(path.join(out,'browser_verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));await rpc('Browser.close');
}finally{if(socket)socket.close();if(browser.exitCode===null)browser.kill();}
