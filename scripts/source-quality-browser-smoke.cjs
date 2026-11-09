const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),crypto=require('crypto');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const state=path.resolve(process.env.FACTORY_BROWSER_STATE||path.join(root,'.local/real-source-quality-v1'));
 const base=process.env.FACTORY_BROWSER_URL||'http://127.0.0.1:8105';
 if(!['127.0.0.1','localhost','[::1]'].includes(new URL(base).hostname))throw Error('Loopback QA only');
 const token=fs.readFileSync(state+'/operator-1.token','utf8').trim();
 const browser=await chromium.launch({executablePath:require('./lib/chromium-path.cjs').resolveChromium(),headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},acceptDownloads:true});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/');await page.getByLabel('Access token',{exact:true}).fill(token);
 await page.getByRole('button',{name:'Connect / refresh',exact:true}).click();
 await page.getByText('Application evidence',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Market data',exact:true}).click();
 await page.getByRole('heading',{name:'Source quality evidence',exact:true}).waitFor();
 const headers={Authorization:'Bearer '+token};
 const rows=await (await page.request.get(base+'/api/v1/data/quality',{headers})).json();
 if(rows.length!==8||rows.some(r=>r.synthetic||r.historical_admission||r.source_structural_status!=='PASS'))throw Error('Expected eight real structural scans with metadata admission blocked');
 const gold=rows.find(r=>r.instrument==='XAUUSD');
 await page.getByRole('button',{name:'Inspect source '+gold.run_id.slice(0,8),exact:true}).click();
 await page.getByRole('heading',{name:'XAUUSD scan receipt',exact:true}).waitFor();
 const raw=await (await page.request.get(base+'/api/v1/data/quality/'+gold.run_id+'/events',{headers})).body();
 const downloading=page.waitForEvent('download');
 await page.getByRole('button',{name:'Download all gap and issue events',exact:true}).click();
 const artifact=await downloading;
 const destination=root+'/reports/runtime/source-quality-browser-events.jsonl';await artifact.saveAs(destination);
 if(!fs.readFileSync(destination).equals(raw))throw Error('Exported event bytes differ');
 await page.screenshot({path:root+'/reports/runtime/source-quality-browser-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 const overflow=await page.evaluate(()=>({document:document.documentElement.scrollWidth,viewport:innerWidth}));
 await page.screenshot({path:root+'/reports/runtime/source-quality-browser-mobile.png',fullPage:true});
 if(overflow.document>overflow.viewport||errors.length)throw Error('Browser error/overflow: '+JSON.stringify({errors,overflow}));
 const report={status:'PASS',scope:'real historical source QA receipts + authenticated loopback Chromium; not market strategy/calendar/broker validation or complete C7',
   browser:await browser.version(),state_directory:path.basename(state),source_receipts:rows.length,total_source_rows:rows.reduce((sum,r)=>sum+r.counts.rows_scanned,0),
   inspected_instrument:'XAUUSD',inspected_run_id:gold.run_id,source_metadata_blocked:rows.every(r=>r.calendar_status==='UNKNOWN_CALENDAR'&&r.profile_status==='UNKNOWN_SPEC'),
   exported_events_sha256:crypto.createHash('sha256').update(raw).digest('hex'),
   frontend_sha256:Object.fromEntries(['apps/dashboard/src/routes/+page.svelte','apps/dashboard/src/lib/SourceQualityPanel.svelte'].map(p=>[p,crypto.createHash('sha256').update(fs.readFileSync(root+'/'+p)).digest('hex')])),
   checks:['authenticated actual real-source scan list','explicit historical/synthetic distinction','actual Gold source counters','unknown metadata remains blocked','exact full-event export','mobile no document overflow','no page errors'],mobile:overflow};
 fs.writeFileSync(root+'/reports/runtime/source-quality-browser.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));await browser.close();
})().catch(e=>{console.error(e.stack);process.exit(1)});
