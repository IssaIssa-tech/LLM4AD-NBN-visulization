"""Reuse the established Chromium CDP harness for the new saved review."""
from pathlib import Path
root=Path(__file__).resolve().parent
s=(root/'check_ael_parent_review_20261031.mjs').read_text(encoding='utf-8')
prefix=s.split(" await rpc('Runtime.enable');")[0].replace("output/ael_parent_eligibility_20261031","output/ael_operator_pilot_20261031")
tail=r'''
 await rpc('Runtime.enable');await rpc('Page.enable');await rpc('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});await rpc('Page.navigate',{url:pathToFileURL(path.join(out,'ael_operator_pilot_review.html')).href});
 for(let i=0;i<100;i++){if(await run('document.querySelectorAll("#attempts tr").length===12'))break;await delay(50);}
 assert(await run('document.querySelectorAll("#attempts tr").length===12'),'12 saved calls');assert(await run('document.querySelectorAll("#cells tr").length===4'),'4 selection/operator cells');
 assert(await run('document.querySelector("#cards").textContent.includes("2.533807")'),'Measured best score');
 assert(await run('document.querySelector("#mechanism").textContent.includes("all six crossover bodies")'),'Source-inspection finding visible');
 const filter=async (id,value)=>run(`document.querySelector('#${id}').value=${JSON.stringify(value)};document.querySelector('#${id}').dispatchEvent(new Event('change'));document.querySelectorAll('#attempts tr').length`);
 assert(await filter('policy','uniform')===6,'Uniform six calls');assert(await filter('status','exception')===1,'Uniform one exception');assert(await filter('policy','nbn_stratified')===3,'NBN three exceptions');assert(await filter('policy','all')===4,'All four exceptions');assert(await filter('status','valid')===8,'Eight valid');await filter('status','all');
 await run(`document.querySelector('#attempts button').click()`);assert(await run(`document.querySelector('#selected').textContent.includes('nbnNodeId') && document.querySelector('#selected').textContent.includes('7510')`),'Both historical parent metadata');
 await run(`document.querySelectorAll('#attempts button')[1].click()`);assert(await run(`document.querySelector('#selected').textContent.includes('originCallId') && document.querySelector('#selected').textContent.includes('uniform-1-cross')`),'Actual generated-parent lineage');
 await run('window.scrollTo(0,0)');await rpc('Page.bringToFront');await run('document.fonts.ready.then(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))))');await delay(500);await rpc('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false}).then(r=>fs.writeFile(path.join(out,'ael_operator_pilot_preview.png'),Buffer.from(r.data,'base64')));
 await rpc('Emulation.setDeviceMetricsOverride',{width:400,height:900,deviceScaleFactor:1,mobile:true});assert(await run('document.documentElement.scrollWidth<=window.innerWidth'),'Responsive page width');assert(!errors.length,'No browser errors');
 await fs.writeFile(path.join(out,'BROWSER_VERIFICATION.json'),JSON.stringify({passed:true,calls:12,cells:4,validFilter:8,exceptionFilter:4,selectionFilters:true,twoParentMetadata:true,mutationLineage:true,mechanismFindingVisible:true,desktopScreenshot:true,mobileLayout:true,errors},null,2));console.log('Browser checks passed: 12 calls, 4 cells, filters, both parent records, mutation lineage, desktop/mobile');await rpc('Browser.close');
}finally{if(socket)socket.close();if(browser.exitCode===null)browser.kill();}
'''
(root/'check_ael_operator_pilot_20261031.mjs').write_text(prefix+tail,encoding='utf-8',newline='\n')
