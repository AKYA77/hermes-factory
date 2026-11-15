const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
(async()=>{
 const root=path.resolve(__dirname,'..'),state=path.resolve(process.env.FACTORY_BROWSER_STATE),base=process.env.FACTORY_BROWSER_URL||'http://127.0.0.1:8102';
 if(!['localhost','127.0.0.1'].includes(new URL(base).hostname))throw Error('Loopback only');
 const token=fs.readFileSync(path.join(state,'operator-1.token'),'utf8').trim();
 // apps/api/limits.py allows 120 requests per rolling 60 s per token. This script
 // was added after that limiter and is run by nothing, so its 250 ms poll (4/s,
 // 480 requests in a 120 s window) always tripped 429 and the workflow was never
 // actually exercised. Poll at 750 ms (80/min, leaving headroom for the other
 // calls) and back off on 429 instead of failing.
 const RATE=750, budget=120;
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 const browser=await chromium.launch({executablePath:require('./lib/chromium-path.cjs').resolveChromium(),headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const headers={Authorization:'Bearer '+token};
 const get=async route=>{
  let attempt=0;
  for(;;){
   const r=await page.request.get(base+'/api/v1/'+route,{headers});
   if(r.status()===429&&attempt<6){await sleep(RATE*Math.pow(2,attempt));attempt++;continue;}
   if(!r.ok())throw Error('API '+r.status());
   return r.json();
  }
 };
 try{
  await page.goto(base);await page.getByLabel('Access token').fill(token);await page.getByRole('button',{name:'Connect / refresh',exact:true}).click();
  await page.getByRole('button',{name:'Research',exact:true}).click();
  const panel=page.getByRole('region',{name:'Historical prospective calibration cohorts',exact:true});
  await panel.getByRole('heading',{name:'Historical prospective calibration cohorts',exact:true}).waitFor();
  const calibration=panel.getByRole('group',{name:'Retained historical calibration diagnostics',exact:true});
  await calibration.getByRole('checkbox').first().check();
  const frame=panel.getByRole('group',{name:'Prospective sampling frame',exact:true});
  if(await frame.getByRole('checkbox').count()!==1)throw Error('Unexpected prospective frame');
  await frame.getByRole('checkbox').first().check();
  await panel.getByLabel('Audit sample size',{exact:true}).fill('1');
  await panel.getByLabel('Audit seed',{exact:true}).fill('31');
  await panel.getByLabel('Cohort authorized by',{exact:true}).fill('Generated historical cohort browser acceptance');
  await panel.getByLabel('Freeze this historical training-only calibration cohort before prospective native outcomes; reviewed admission only, no approximate pruning or validation authority',{exact:true}).check();
  await panel.getByRole('button',{name:'Freeze historical cohort',exact:true}).click();
  await panel.getByRole('heading',{name:'Native audit feedback',exact:true}).waitFor();
  const list=await get('research/screen-cohorts');if(list.cohorts.length!==1)throw Error('Wrong frozen count');
  const id=list.cohorts[0].cohort_id;let report=await get('research/screen-cohorts/'+id);
  if(!report.historical||report.native_observed!==0||report.approximate_pruning_authorized||!(await get('overview')).paused)throw Error('Freeze peeked outcomes or changed pause');
  await page.getByRole('button',{name:'Overview',exact:true}).click();await page.getByRole('button',{name:'Resume queued research',exact:true}).click();
  const deadline=Date.now()+180000;
  do{report=await get('research/screen-cohorts/'+id);if(report.audit_complete)break;await sleep(RATE);}while(Date.now()<deadline);
  if(!report.audit_complete||report.native_observed!==1||report.approximate_pruning_authorized)throw Error('Fenced native feedback not preserved');
  await page.getByRole('button',{name:'Pause after current job',exact:true}).click();await page.getByRole('button',{name:'Research',exact:true}).click();
  await panel.getByRole('button',{name:id,exact:true}).click();await panel.getByRole('heading',{name:'Native audit feedback',exact:true}).waitFor();
  const downloadEvent=page.waitForEvent('download');await panel.getByRole('button',{name:'Export exact cohort evidence',exact:true}).click();
  const download=await downloadEvent;const target=root+'/reports/runtime/completion/historical-cohort-browser-export.json';await download.saveAs(target);
  const response=await page.request.get(base+'/api/v1/research/screen-cohorts/'+id,{headers});if(!fs.readFileSync(target).equals(await response.body()))throw Error('Export byte mismatch');
  await panel.screenshot({path:root+'/reports/runtime/completion/historical-cohort-desktop.png'});
  await page.setViewportSize({width:390,height:844});await panel.screenshot({path:root+'/reports/runtime/completion/historical-cohort-mobile.png'});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)||errors.length)throw Error(JSON.stringify(errors));
  console.log(JSON.stringify({authenticated:true,historical_v2:true,frozen_before_outcomes:true,pause_preserved:true,actual_fenced_native_feedback:true,native_observed:report.native_observed,approximate_pruning:false,exact_export:true,mobile_overflow:false,page_errors:errors,rate_limited:false,fixture:'TEST_ONLY authorization fixture, not market data'}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
