const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const state=path.resolve(process.env.FACTORY_BROWSER_STATE||path.join(root,'.local/independent-ranking-v1'));
 const base=process.env.FACTORY_BROWSER_URL||'http://127.0.0.1:8121';
 if(!['127.0.0.1','localhost','[::1]'].includes(new URL(base).hostname))throw Error('Browser QA permits loopback only');
 const token=fs.readFileSync(state+'/operator-1.token','utf8').trim();
 const headers={Authorization:'Bearer '+token};
 const browser=await chromium.launch({executablePath:require('./lib/chromium-path.cjs').resolveChromium(),headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/');
 await page.getByLabel('Access token',{exact:true}).fill(token);
 await page.getByRole('button',{name:'Connect / refresh',exact:true}).click();
 await page.getByText('Application evidence',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Research',exact:true}).click();
 const section='section[aria-label="Independent qualified ranking"]';
 await page.getByRole('heading',{name:'Independent qualified ranking',exact:true}).waitFor();
 const button=page.locator(section+' button',{hasText:'Rank independent evaluations'});
 if(await button.isEnabled())throw Error('Ranking enabled before the declaration was accepted');
 await page.locator(section+' input[aria-label="Ranking authorized by"]').fill('independent ranking acceptance');
 await page.locator(section+' input[aria-label="Ranking declaration"]').check();
 await button.click();
 await page.locator(section+' h3',{hasText:'Ranking report'}).waitFor({timeout:30000});
 const report=await (await page.request.post(base+'/api/v1/research/independent-ranking',{headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},data:{max_slots:5,per_key_limit:2,authorized_by:'independent ranking acceptance',attestation:'Rank retained non-synthetic independent evaluations descriptively only; no qualification or promotion'}})).json();
 if(report.descriptive_only!==true)throw Error('Ranking did not declare itself descriptive');
 if(report.qualification_authorized!==false)throw Error('Ranking claimed qualification authority');
 const body=await page.locator(section).innerText();
 if(!body.includes('Descriptive only: yes'))throw Error('Descriptive status not rendered');
 if(!body.includes('Qualification authorized: no'))throw Error('Qualification status not rendered');
 if(!body.includes('independent evaluations'))throw Error('Evaluation count not rendered');
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:root+'/reports/runtime/independent-ranking-browser-mobile.png',fullPage:true});
 const overflow=await page.evaluate(()=>({document:document.documentElement.scrollWidth,viewport:innerWidth}));
 await page.screenshot({path:root+'/reports/runtime/independent-ranking-browser-desktop.png',fullPage:true});
 if(overflow.document>overflow.viewport)throw Error('Mobile horizontal overflow');
 if(errors.length)throw Error('Browser page errors: '+errors.join(';'));
 const report_out={
  status:'PASS',
  scope:'descriptive ranking over retained non-synthetic independent evaluations in authenticated loopback Chromium; a ranked candidate is not qualified or validated',
  browser:await browser.version(),
  state_directory:path.basename(state),
  evaluations_considered:report.evaluations_considered,
  selected:report.selected.length,
  skipped:report.skipped.length,
  qualification_authorized:report.qualification_authorized,
  checks:[
   'authenticated ranking render',
   'action disabled before declaration',
   'report rendered with evaluation counts',
   'descriptive-only and no-qualification rendered',
   'mobile no document overflow',
   'no page errors',
  ],
  mobile:overflow,
 };
 fs.writeFileSync(root+'/reports/runtime/independent-ranking-browser.json',JSON.stringify(report_out,null,2));
 console.log(JSON.stringify(report_out));
 await browser.close();
})().catch(e=>{console.error(e.stack);process.exit(1)});
