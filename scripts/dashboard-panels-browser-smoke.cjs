const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const state=path.resolve(process.env.FACTORY_BROWSER_STATE||path.join(root,'.local/dashboard-panels-v1'));
 const base=process.env.FACTORY_BROWSER_URL||'http://127.0.0.1:8122';
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

 const checks=[];
 const qSection='section[aria-label="Qualified training shortlist"]';
 await page.getByRole('heading',{name:'Qualified training shortlist',exact:true}).waitFor();
 const qButton=page.locator(qSection+' button',{hasText:'Rank qualified shortlist'});
 if(await qButton.isEnabled())throw Error('Qualified ranking enabled before the declaration');
 await page.locator(qSection+' input[aria-label="Qualified ranking authorized by"]').fill('qualified ranking acceptance');
 await page.locator(qSection+' input[aria-label="Qualified ranking declaration"]').check();
 await qButton.click();
 await page.locator(qSection+' h3',{hasText:'Shortlist report'}).waitFor({timeout:30000});
 const qBody=await page.locator(qSection).innerText();
 if(!qBody.includes('Descriptive only: yes'))throw Error('Qualified ranking descriptive status missing');
 if(!qBody.includes('Qualification authorized: no'))throw Error('Qualified ranking qualification status missing');
 checks.push('qualified ranking reported with descriptive-only status');

 const eSection='section[aria-label="Validation evaluations"]';
 await page.getByRole('heading',{name:'Validation evaluations',exact:true}).waitFor();
 await page.locator(eSection+' tbody tr').first().waitFor({timeout:30000});
 const evaluations=await (await page.request.get(base+'/api/v1/validation/evaluations?limit=100&offset=0',{headers})).json();
 const eRows=await page.locator(eSection+' tbody tr').count();
 if(evaluations.length<1)throw Error('Fixture seeded no evaluations to render');
 if(eRows!==evaluations.length)throw Error(`Rendered ${eRows} evaluation rows for ${evaluations.length} records`);
 await page.locator(eSection+' button',{hasText:'Inspect'}).first().click();
 await page.locator(eSection+' h3',{hasText:'Evaluation'}).waitFor();
 checks.push(`validation evaluations rendered (${eRows}) and detail inspected`);

 const sSection='section[aria-label="Strategy detail and lineage"]';
 await page.getByRole('heading',{name:'Strategy detail and lineage',exact:true}).waitFor();
 const fixture=JSON.parse(fs.readFileSync(state+'/qa.json','utf8'));
 await page.locator(sSection+' input[aria-label="Strategy id"]').fill(fixture.parent_strategy_id);
 await page.locator(sSection+' button',{hasText:'Load strategy'}).click();
 await page.locator(sSection+' h3',{hasText:'Lineage'}).waitFor({timeout:30000});
 const sBody=await page.locator(sSection).innerText();
 if(!sBody.includes('Parent:'))throw Error('Strategy parent not rendered');
 if(!sBody.includes('Changed fields:'))throw Error('Strategy changed fields not rendered');
 checks.push('strategy detail and lineage rendered from a real identity');

 const tSection='section[aria-label="Research trials"]';
 await page.getByRole('heading',{name:'Research trials',exact:true}).waitFor();
 await page.locator(tSection+' tbody tr').first().waitFor({timeout:30000});
 const trials=await (await page.request.get(base+'/api/v1/research/trials?limit=200&offset=0',{headers})).json();
 const tRows=await page.locator(tSection+' tbody tr').count();
 if(tRows!==trials.length)throw Error(`Rendered ${tRows} trial rows for ${trials.length} trials`);
 if(!(await page.locator(tSection).innerText()).includes('measured CPU seconds'))throw Error('Trial cost totals missing');
 checks.push(`research trials rendered (${tRows}) with measured cost`);

 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:root+'/reports/runtime/dashboard-panels-browser-mobile.png',fullPage:true});
 const overflow=await page.evaluate(()=>({document:document.documentElement.scrollWidth,viewport:innerWidth}));
 await page.screenshot({path:root+'/reports/runtime/dashboard-panels-browser-desktop.png',fullPage:true});
 if(overflow.document>overflow.viewport)throw Error('Mobile horizontal overflow');
 if(errors.length)throw Error('Browser page errors: '+errors.join(';'));
 const report={
  status:'PASS',
  scope:'qualified ranking, validation evaluation detail, strategy lineage and research trials in authenticated loopback Chromium; descriptive records only, no qualification or promotion',
  browser:await browser.version(),
  state_directory:path.basename(state),
  evaluations:evaluations.length,
  trials:trials.length,
  checks:[...checks,'mobile no document overflow','no page errors'],
  mobile:overflow,
 };
 fs.writeFileSync(root+'/reports/runtime/dashboard-panels-browser.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
 await browser.close();
})().catch(e=>{console.error(e.stack);process.exit(1)});
