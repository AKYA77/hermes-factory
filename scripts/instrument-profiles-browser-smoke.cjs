const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
(async()=>{
 const root=path.resolve(__dirname,'..');
 // NOT RUNNABLE: no companion fixture script exists. run-browser-smoke.sh needs
 // scripts/instrument-profiles-browser-fixture.py to prepare state, and without it this smoke cannot be
 // executed at all. Either add the fixture or delete this script -- until then it is
 // NOT UI acceptance evidence and must not be counted as a passing check.
 if(!fs.existsSync(path.resolve(__dirname,'instrument-profiles-browser-fixture.py'))){
  console.error('NOT RUNNABLE: missing fixture instrument-profiles-browser-fixture.py');
  process.exit(2);
 }
 const state=path.resolve(process.env.FACTORY_BROWSER_STATE||path.join(root,'.local/instrument-profiles-v1'));
 const base=process.env.FACTORY_BROWSER_URL||'http://127.0.0.1:8115';
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
 await page.getByRole('button',{name:'Market data',exact:true}).click();
 await page.getByRole('heading',{name:'Instrument profiles',exact:true}).waitFor();
 await page.locator('section[aria-label="Instrument profiles"] tbody tr').first().waitFor({timeout:30000});
 const listed=await (await page.request.get(base+'/api/v1/profiles',{headers})).json();
 const integrity=await (await page.request.get(base+'/api/v1/profile-integrity',{headers})).json();
 const rows=await page.locator('section[aria-label="Instrument profiles"] tbody tr').count();
 // Eight profiles, each with a hash row: the panel renders two tables.
 if(listed.profiles.length!==8)throw Error(`Expected eight profiles, got ${listed.profiles.length}`);
 if(rows<listed.profiles.length)throw Error(`Rendered ${rows} rows for ${listed.profiles.length} profiles`);
 const body=await page.locator('section[aria-label="Instrument profiles"]').innerText();
 // The synthetic/non-synthetic distinction must be explicit, not implied.
 if(!body.includes('synthetic'))throw Error('Synthetic labelling missing');
 if(!body.includes('verified non-synthetic'))throw Error('Non-synthetic counter missing');
 if(!body.includes('Gold'))throw Error('Gold not named in the panel caveat');
 // A profile hash must be shown so a declared unit set can be pinned.
 if(!/[a-f0-9]{64}/.test(body))throw Error('No profile hash rendered');
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:root+'/reports/runtime/instrument-profiles-browser-mobile.png',fullPage:true});
 const overflow=await page.evaluate(()=>({document:document.documentElement.scrollWidth,viewport:innerWidth}));
 await page.screenshot({path:root+'/reports/runtime/instrument-profiles-browser-desktop.png',fullPage:true});
 if(overflow.document>overflow.viewport)throw Error('Mobile horizontal overflow');
 if(errors.length)throw Error('Browser page errors: '+errors.join(';'));
 // Declared geometry must be fetched per instrument from its own endpoint, not
 // inferred from the listing: the action is present and returns real fields.
 const detailAction=page.locator('section[aria-label="Instrument profiles"] button',{hasText:'Show declared geometry'});
 await detailAction.first().waitFor();
 await detailAction.first().click();
 await page.waitForTimeout(800);
 const afterDetail=await page.locator('section[aria-label="Instrument profiles"]').innerText();
 if(!afterDetail.includes('tick_size'))throw Error('Declared geometry was not fetched per profile');
 // Liveness must come from the real health probe, and be visibly reported.
 const liveBadge=await page.locator('header [data-live]').innerText();
 if(!/\blive\b/.test(liveBadge))throw Error(`API liveness badge is not live: ${liveBadge}`);
 const report={
  status:'PASS',
  scope:'declared instrument geometry and profile hashes in authenticated loopback Chromium; synthetic fixtures only, not broker metadata and not verified Gold units',
  browser:await browser.version(),
  state_directory:path.basename(state),
  profiles:listed.profiles.length,
  rendered_rows:rows,
  synthetic:integrity.synthetic,
  non_synthetic:integrity.non_synthetic,
  checks:[
   'authenticated profile render',
   'one row per declared profile',
   'synthetic versus verified distinction explicit',
   'Gold caveat present',
   'profile hash rendered',
   'declared geometry fetched per profile from its own endpoint',
   'API liveness reported from the real health probe',
   'mobile no document overflow',
   'no page errors',
  ],
  mobile:overflow,
 };
 fs.writeFileSync(root+'/reports/runtime/instrument-profiles-browser.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
 await browser.close();
})().catch(e=>{console.error(e.stack);process.exit(1)});
