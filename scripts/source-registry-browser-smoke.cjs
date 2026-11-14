const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const state=path.resolve(process.env.FACTORY_BROWSER_STATE||path.join(root,'.local/source-registry-v1'));
 const base=process.env.FACTORY_BROWSER_URL||'http://127.0.0.1:8116';
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
 await page.getByRole('heading',{name:'Source registry',exact:true}).waitFor();
 await page.locator('section[aria-label="Source registry"] tbody tr').first().waitFor({timeout:30000});
 const listed=await (await page.request.get(base+'/api/v1/sources',{headers})).json();
 const rows=await page.locator('section[aria-label="Source registry"] tbody tr').count();
 if(listed.sources.length<8)throw Error(`Expected at least eight datasets, got ${listed.sources.length}`);
 if(rows!==listed.sources.length)throw Error(`Rendered ${rows} rows for ${listed.sources.length} datasets`);
 const body=await page.locator('section[aria-label="Source registry"]').innerText();
 // Provenance must be visible, not just row counts.
 if(!body.includes('HistData.com'))throw Error('Provider name not rendered');
 if(!body.includes('SOURCE_BID_ASK')&&!body.includes('SOURCE_'))throw Error('Fidelity not rendered');
 if(!/histdata-ascii-ticks\/v\d+/.test(body))throw Error('Parser version not rendered');
 // The provider's own limitation about Gold must be carried through. It sits in
 // a collapsed disclosure, so open it before reading visible text.
 await page.locator('section[aria-label="Source registry"] summary').click();
 await page.locator('section[aria-label="Source registry"] article').first().waitFor();
 const full=await page.locator('section[aria-label="Source registry"]').innerText();
 if(!full.includes('Gold pip/contract/margin metadata remains UNKNOWN_SPEC'))throw Error('Gold limitation not carried into the panel');
 // Synthetic datasets must be labelled, never blended in silently.
 if(!body.includes('synthetic'))throw Error('Synthetic labelling missing');
 // A test-fixture dataset must not be silently counted as provider-sourced.
 const kinds=await page.locator('section[aria-label="Source registry"] tbody tr td:nth-child(2)').allInnerTexts();
 const testFixtures=kinds.filter(k=>k.trim()==='test fixture').length;
 const declaredTestOnly=listed.sources.filter(s=>/TEST ONLY/i.test(String(s.provenance.source??''))).length;
 if(testFixtures!==declaredTestOnly)throw Error(`Rendered ${testFixtures} test-fixture rows for ${declaredTestOnly} declared TEST ONLY datasets`);
 if(!body.includes('unattributed'))throw Error('Datasets with no provider are not labelled');
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:root+'/reports/runtime/source-registry-browser-mobile.png',fullPage:true});
 const overflow=await page.evaluate(()=>({document:document.documentElement.scrollWidth,viewport:innerWidth}));
 await page.screenshot({path:root+'/reports/runtime/source-registry-browser-desktop.png',fullPage:true});
 if(overflow.document>overflow.viewport)throw Error('Mobile horizontal overflow');
 if(errors.length)throw Error('Browser page errors: '+errors.join(';'));
 const report={
  status:'PASS',
  scope:'acquired source registry and declared provenance in authenticated loopback Chromium; provider quotes, not brokerage fills, and no broker metadata is claimed',
  browser:await browser.version(),
  state_directory:path.basename(state),
  datasets:listed.sources.length,
  rendered_rows:rows,
  providers:[...new Set(listed.sources.map(s=>s.provenance.provider))],
  synthetic:listed.sources.filter(s=>s.provenance.synthetic).length,
  checks:[
   'authenticated registry render',
   'one row per acquired dataset',
   'provider and fidelity rendered',
   'parser version rendered',
   'Gold metadata limitation carried through',
   'synthetic labelling present',
   'mobile no document overflow',
   'no page errors',
  ],
  mobile:overflow,
 };
 fs.writeFileSync(root+'/reports/runtime/source-registry-browser.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
 await browser.close();
})().catch(e=>{console.error(e.stack);process.exit(1)});
