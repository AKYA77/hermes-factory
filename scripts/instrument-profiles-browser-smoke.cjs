const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
(async()=>{
 const root=path.resolve(__dirname,'..');
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
   'mobile no document overflow',
   'no page errors',
  ],
  mobile:overflow,
 };
 fs.writeFileSync(root+'/reports/runtime/instrument-profiles-browser.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
 await browser.close();
})().catch(e=>{console.error(e.stack);process.exit(1)});
