const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const state=path.resolve(process.env.FACTORY_BROWSER_STATE||path.join(root,'.local/instrument-status-v1'));
 const base=process.env.FACTORY_BROWSER_URL||'http://127.0.0.1:8120';
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
 const section='section[aria-label="Instrument data and profile status"]';
 await page.getByRole('heading',{name:'Instrument data and profile status',exact:true}).waitFor();
 await page.locator(section+' tbody tr').first().waitFor({timeout:30000});
 const status=await (await page.request.get(base+'/api/v1/instruments',{headers})).json();
 const profiles=await (await page.request.get(base+'/api/v1/profiles',{headers})).json();
 const rows=await page.locator(section+' tbody tr').count();
 if(status.length!==8)throw Error(`Expected eight instruments, got ${status.length}`);
 if(rows!==status.length)throw Error(`Rendered ${rows} rows for ${status.length} instruments`);
 const body=await page.locator(section).innerText();
 // Declared status must be shown, and unavailable must not read as a defect.
 if(!body.includes('DATA_UNAVAILABLE'))throw Error('Data status not rendered');
 if(!body.includes('UNKNOWN_SPEC'))throw Error('Profile spec status not rendered');
 if(!body.includes('does not grant admission'))throw Error('Admission caveat missing');
 // Every instrument's declared profile version must be visible.
 for(const p of profiles.profiles){
  if(!body.includes(p.version))throw Error(`Profile version ${p.version} not rendered`);
 }
 // Synthetic declarations must be labelled per instrument.
 const syntheticCells=await page.locator(section+' tbody tr td:nth-child(5)').allInnerTexts();
 if(syntheticCells.length!==status.length)throw Error('Synthetic column not rendered for every instrument');
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:root+'/reports/runtime/instrument-status-browser-mobile.png',fullPage:true});
 const overflow=await page.evaluate(()=>({document:document.documentElement.scrollWidth,viewport:innerWidth}));
 await page.screenshot({path:root+'/reports/runtime/instrument-status-browser-desktop.png',fullPage:true});
 if(overflow.document>overflow.viewport)throw Error('Mobile horizontal overflow');
 if(errors.length)throw Error('Browser page errors: '+errors.join(';'));
 const report={
  status:'PASS',
  scope:'per-instrument declared data status and profile version in authenticated loopback Chromium; no instrument has verified data admission and the panel does not grant it',
  browser:await browser.version(),
  state_directory:path.basename(state),
  instruments:status.length,
  rendered_rows:rows,
  synthetic_profiles:profiles.profiles.filter(p=>p.synthetic).length,
  checks:[
   'authenticated status render',
   'one row per instrument',
   'data status and profile spec rendered',
   'admission caveat present',
   'declared profile version per instrument',
   'synthetic column per instrument',
   'mobile no document overflow',
   'no page errors',
  ],
  mobile:overflow,
 };
 fs.writeFileSync(root+'/reports/runtime/instrument-status-browser.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
 await browser.close();
})().catch(e=>{console.error(e.stack);process.exit(1)});
