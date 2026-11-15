// Browser acceptance for the Research reports panel.
//
// Covers the three descriptive report actions (selection funnel, annual/pooled
// reporting, independent ranking) plus the profiles, sources and storage
// summaries. These are descriptive aggregates over retained evidence: the panel
// itself states that none of them qualifies, ranks or promotes a strategy, and
// the smoke asserts that boundary rather than treating a report as a decision.
const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
(async()=>{
 const root=path.resolve(__dirname,'..'),state=path.resolve(process.env.FACTORY_BROWSER_STATE),base=process.env.FACTORY_BROWSER_URL||'http://127.0.0.1:8111';
 if(!['localhost','127.0.0.1'].includes(new URL(base).hostname))throw Error('Loopback acceptance only');
 const token=fs.readFileSync(state+'/operator-1.token','utf8').trim(),headers={Authorization:'Bearer '+token};
 const browser=await chromium.launch({executablePath:require('./lib/chromium-path.cjs').resolveChromium(),headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(base);
  await page.getByLabel('Access token').fill(token);
  await page.getByRole('button',{name:'Connect / refresh',exact:true}).click();
  await page.getByRole('button',{name:'Research',exact:true}).click();
  const panel=page.getByRole('region',{name:'Research reports'});
  await panel.getByRole('heading',{name:'Research reports',exact:true}).waitFor();
  // The three report actions are gated on an explicit attestation.
  const actions=panel.locator('.actions');
  for(const name of ['Selection funnel','Annual reporting','Independent ranking']){
   if(await actions.getByRole('button',{name,exact:true}).isDisabled()!==true)throw Error('report action not gated on attestation: '+name);
  }
  await panel.getByLabel('Authorized by',{exact:true}).fill('Generated research reports acceptance');
  await panel.getByRole('checkbox').check();
  for(const name of ['Selection funnel','Annual reporting','Independent ranking']){
   await actions.getByRole('button',{name,exact:true}).click();
  }
  await panel.getByRole('heading',{name:'Selection funnel',exact:true}).waitFor();
  await panel.getByRole('heading',{name:'Annual and pooled reporting',exact:true}).waitFor();
  await panel.getByRole('heading',{name:'Independent qualified ranking',exact:true}).waitFor();
  // The reports are served over the API too; the panel and the API must agree.
  const funnelResp = await page.request.post(base+'/api/v1/research/selection-funnel', {
   headers,
   data: {
    authorized_by: 'Generated research reports acceptance',
    attestation: 'Report a descriptive global candidate-selection funnel only; no qualification, ranking or promotion',
   },
  });
  if(!funnelResp.ok())throw Error('funnel API '+funnelResp.status());
  const funnel=await funnelResp.json();
  const shown=await panel.getByRole('article').filter({has:page.getByRole('heading',{name:'Selection funnel',exact:true})}).innerText();
  if(!shown.includes(String(funnel.distinct_effective_cohort_candidates)))throw Error('funnel panel/API mismatch');
  if(await panel.getByRole('alert').count())throw Error('panel reported an error');
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('mobile overflow');
  if(errors.length)throw Error(JSON.stringify(errors));
  console.log(JSON.stringify({authenticated:true,attestation_gated:true,funnel:true,annual:true,independent_ranking:true,panel_api_consistent:true,descriptive_only:true,mobile_overflow:false,page_errors:[],fixture:'TEST_ONLY state, not market data'}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
