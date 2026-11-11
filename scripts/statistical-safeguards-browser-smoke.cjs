const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const state=path.resolve(process.env.FACTORY_BROWSER_STATE||path.join(root,'.local/statistical-safeguards-v1'));
 const base=process.env.FACTORY_BROWSER_URL||'http://127.0.0.1:8117';
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
 await page.getByRole('heading',{name:'Statistical selection safeguards',exact:true}).waitFor();
 const section='section[aria-label="Statistical selection safeguards"]';
 const actorInput=page.locator(section+' input[aria-label="Authorized by"]');
 await actorInput.fill('statistical safeguards acceptance');
 await page.locator(section+' input[aria-label="p-values (comma separated)"]').fill('0.01,0.04,0.03,0.20');
 // The buttons must stay disabled until the independence declaration is made.
 const testingButton=page.locator(section+' button',{hasText:'Report multiple-testing correction'});
 if(await testingButton.isEnabled())throw Error('Action enabled before the declaration was accepted');
 await page.locator(section+' input[aria-label="Descriptive reporting declaration"]').check();
 // Selection funnel has no parameters beyond the authorization.
 await page.locator(section+' button',{hasText:'Report selection funnel'}).click();
 await page.locator(section+' h3',{hasText:'Selection funnel'}).waitFor();
 // Multiple-testing must reflect the supplied family and never authorize qualification.
 await testingButton.click();
 const testing=await (await page.request.post(base+'/api/v1/research/multiple-testing',{headers,header:{Authorization:'Bearer '+token,'Content-Type':'application/json'},data:{candidate_ids:['0'.repeat(64),'1'.repeat(64),'2'.repeat(64),'3'.repeat(64)],p_values:[0.01,0.04,0.03,0.20],authorized_by:'statistical safeguards acceptance',attestation:'Report descriptive multiple-testing corrections for retained candidate evidence only; no qualification, ranking or promotion'}})).json();
 if(testing.candidates!==4)throw Error(`Expected four candidates, got ${testing.candidates}`);
 if(testing.qualification_authorized!==false)throw Error('A descriptive report claimed qualification authority');
 if(testing.descriptive_only!==true)throw Error('A descriptive report did not declare itself descriptive');
 await page.locator(section+' h3',{hasText:'Multiple-testing correction'}).waitFor();
 const body=await page.locator(section).innerText();
 if(!body.includes('Descriptive only: yes'))throw Error('Descriptive-only status not rendered');
 if(!body.includes('Qualification authorized: no'))throw Error('Qualification status not rendered');
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:root+'/reports/runtime/statistical-safeguards-browser-mobile.png',fullPage:true});
 const overflow=await page.evaluate(()=>({document:document.documentElement.scrollWidth,viewport:innerWidth}));
 await page.screenshot({path:root+'/reports/runtime/statistical-safeguards-browser-desktop.png',fullPage:true});
 if(overflow.document>overflow.viewport)throw Error('Mobile horizontal overflow');
 if(errors.length)throw Error('Browser page errors: '+errors.join(';'));
 const report={
  status:'PASS',
  scope:'descriptive selection funnel and multiple-testing corrections in authenticated loopback Chromium; no qualification, ranking or promotion',
  browser:await browser.version(),
  state_directory:path.basename(state),
  candidates:testing.candidates,
  uncorrected:testing.uncorrected_passes,
  bonferroni:testing.bonferroni_passes,
  benjamini_hochberg:testing.benjamini_hochberg_passes,
  qualification_authorized:testing.qualification_authorized,
  checks:[
   'authenticated safeguards render',
   'action disabled before declaration',
   'selection funnel reported',
   'multiple-testing reflects the supplied family',
   'descriptive-only and no-qualification rendered',
   'mobile no document overflow',
   'no page errors',
  ],
  mobile:overflow,
 };
 fs.writeFileSync(root+'/reports/runtime/statistical-safeguards-browser.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
 await browser.close();
})().catch(e=>{console.error(e.stack);process.exit(1)});
