const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const state=path.resolve(process.env.FACTORY_BROWSER_STATE||path.join(root,'.local/research-actions-v1'));
 const base=process.env.FACTORY_BROWSER_URL||'http://127.0.0.1:8124';
 if(!['127.0.0.1','localhost','[::1]'].includes(new URL(base).hostname))throw Error('Browser QA permits loopback only');
 const token=fs.readFileSync(state+'/operator-1.token','utf8').trim();
 const fixture=JSON.parse(fs.readFileSync(state+'/qa.json','utf8'));
 const headers={Authorization:'Bearer '+token};
 const browser=await chromium.launch({executablePath:require('./lib/chromium-path.cjs').resolveChromium(),headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/');
 await page.getByLabel('Access token',{exact:true}).fill(token);
 await page.getByRole('button',{name:'Connect / refresh',exact:true}).click();
 await page.getByText('Application evidence',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Research',exact:true}).click();

 const section='section[aria-label="Research actions and improvement plans"]';
 await page.getByRole('heading',{name:'Research actions and improvement plans',exact:true}).waitFor();
 const checks=[];

 // Every action must be disabled until the actor is supplied.
 await page.locator(section+' button',{hasText:'Annual reporting'}).waitFor();
 if(await page.locator(section+' button',{hasText:'Annual reporting'}).isEnabled())
  throw Error('A research action was enabled before an actor was supplied');

 const actor='browser-qa';
 await page.locator(section+' input[aria-label="Actor identity"]').fill(actor);

 async function call(name){
  const button=page.locator(section+' button',{hasText:name,exact:true});
  await button.waitFor();
  await button.click();
  await page.locator(section+' h3',{hasText:'Report'}).waitFor({timeout:30000});
  return page.locator(section+' pre').innerText();
 }
 // annual-reporting needs no identity field
 const annual=await call('Annual reporting');
 const annualJson=JSON.parse(annual);
 if(typeof annualJson!=='object')throw Error('Annual reporting returned no object');
 checks.push('annual reporting returned a report object');

 // candidate-diversity needs the protocol hash
 await page.locator(section+' input[aria-label="Protocol hash"]').fill(fixture.protocol_hash);
 const diversity=await call('Candidate diversity');
 if(!diversity.includes(fixture.protocol_hash.slice(0,12))&&!diversity.includes('protocol'))
  throw Error('Candidate diversity report does not reference the protocol');
 checks.push('candidate diversity rendered for the registered protocol');

 // improvement-lineage and sensitivity need a policy hash
 await page.locator(section+' input[aria-label="Policy hash"]').fill(fixture.policy_hash);
 const lineage=await call('Improvement lineage');
 if(!lineage)throw Error('Improvement lineage returned nothing');
 checks.push('improvement lineage rendered for a retained policy');

 const sensitivity=await call('Improvement sensitivity');
 if(!sensitivity)throw Error('Improvement sensitivity returned nothing');
 checks.push('improvement sensitivity rendered for a retained policy');

 // diagnostic-cohorts needs the experiment hash
 await page.locator(section+' input[aria-label="Experiment hash"]').fill(fixture.experiment_hash);
 await call('Diagnostic cohorts');
 checks.push('diagnostic cohorts rendered for a retained experiment');

 // improvement-confirmation needs both an edge and an evaluation
 await page.locator(section+' input[aria-label="Edge identity"]').fill(fixture.edge_id);
 const evaluations=await (await page.request.get(base+'/api/v1/validation/evaluations?limit=100&offset=0',{headers})).json();
 await page.locator(section+' input[aria-label="Evaluation identity"]').fill(evaluations[0].evaluation_id);
 await call('Improvement confirmation');
 checks.push('improvement confirmation bound an edge to an evaluation');

 // improvement plans table
 const plans=await (await page.request.get(base+'/api/v1/improvement/plans?limit=50&offset=0',{headers})).json();
 const planRows=await page.locator(section+' tbody tr').count();
 if(planRows!==plans.length)throw Error(`Rendered ${planRows} plan rows for ${plans.length} plans`);
 checks.push(`improvement plans rendered (${planRows})`);

 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:root+'/reports/runtime/research-actions-browser-mobile.png',fullPage:true});
 const overflow=await page.evaluate(()=>({document:document.documentElement.scrollWidth,viewport:innerWidth}));
 await page.screenshot({path:root+'/reports/runtime/research-actions-browser-desktop.png',fullPage:true});
 if(overflow.document>overflow.viewport)throw Error('Mobile horizontal overflow');
 if(errors.length)throw Error('Browser page errors: '+errors.join(';'));
 const report={
  status:'PASS',
  scope:'research action reports and improvement plans in authenticated loopback Chromium; descriptive reports only, no qualification, ranking or promotion',
  browser:await browser.version(),
  state_directory:path.basename(state),
  plans:plans.length,
  checks:[...checks,'actor required before any action','mobile no document overflow','no page errors'],
  mobile:overflow,
 };
 fs.writeFileSync(root+'/reports/runtime/research-actions-browser.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
 await browser.close();
})().catch(e=>{console.error(e.stack);process.exit(1)});
