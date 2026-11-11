const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),crypto=require('crypto');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const state=path.resolve(process.env.FACTORY_BROWSER_STATE||path.join(root,'.local/source-coverage-v1'));
 const base=process.env.FACTORY_BROWSER_URL||'http://127.0.0.1:8112';
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
 await page.getByRole('heading',{name:'Source coverage and storage',exact:true}).waitFor();
 // Coverage is fetched after the heading mounts; wait for the rows rather than
 // reading immediately, or the check races the panel's own load.
 await page.locator('section[aria-label="Source coverage and storage"] tbody tr').first().waitFor({timeout:30000});
 // The panel must render a row per reported instrument, from the real ledger.
 const rows=await page.locator('section[aria-label="Source coverage and storage"] tbody tr').count();
 const coverage=await (await page.request.get(base+'/api/v1/source-coverage',{headers})).json();
 const instruments=Object.keys(coverage.instruments);
 if(rows!==instruments.length)throw Error(`Rendered ${rows} instrument rows for ${instruments.length} instruments`);
 if(instruments.length!==8)throw Error(`Expected eight instruments, got ${instruments.length}`);
 // Coverage is reported, never implied: no period may be selected by this panel.
 const selected=Object.values(coverage.instruments).reduce((n,i)=>n+i.selected,0);
 if(selected!==0)throw Error(`Expected zero selected periods, found ${selected}`);
 // Storage reporting must be present and numeric.
 const storage=await (await page.request.get(base+'/api/v1/storage',{headers})).json();
 if(typeof storage.partitions!=='number'||typeof storage.rows!=='number')throw Error('Storage report missing partitions/rows');
 const body=await page.locator('section[aria-label="Source coverage and storage"]').innerText();
 if(!body.includes('catalog partitions'))throw Error('Storage metrics not rendered');
 // A gap count must be shown for every instrument; a missing one reads as a defect.
 const gapCells=await page.locator('section[aria-label="Source coverage and storage"] tbody tr td:last-child').allInnerTexts();
 if(gapCells.length!==instruments.length||gapCells.some(v=>v.trim()===''))throw Error('Gap counts not rendered for every instrument');
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:root+'/reports/runtime/source-coverage-browser-mobile.png',fullPage:true});
 const overflow=await page.evaluate(()=>({document:document.documentElement.scrollWidth,viewport:innerWidth}));
 await page.screenshot({path:root+'/reports/runtime/source-coverage-browser-desktop.png',fullPage:true});
 if(overflow.document>overflow.viewport)throw Error('Mobile horizontal overflow');
 if(errors.length)throw Error('Browser page errors: '+errors.join(';'));
 const report={
  status:'PASS',
  scope:'real acquired source coverage and canonical storage in authenticated loopback Chromium; reports coverage for review only and does not select, admit or validate anything',
  browser:await browser.version(),
  state_directory:path.basename(state),
  instruments:instruments.length,
  rendered_rows:rows,
  selected_periods:selected,
  storage_partitions:storage.partitions,
  storage_rows:storage.rows,
  gap_counts:gapCells.map(v=>Number(v.trim())),
  checks:[
   'authenticated real source-coverage render',
   'one row per reported instrument',
   'selected counts reported, never implied',
   'canonical storage partitions and rows',
   'gap count per instrument',
   'mobile no document overflow',
   'no page errors',
  ],
  mobile:overflow,
 };
 fs.writeFileSync(root+'/reports/runtime/source-coverage-browser.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
 await browser.close();
})().catch(e=>{console.error(e.stack);process.exit(1)});
