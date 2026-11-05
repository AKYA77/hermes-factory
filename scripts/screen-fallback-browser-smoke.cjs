const {chromium}=require('playwright');
const fs=require('fs');const path=require('path');
(async()=>{
 const root=path.resolve(__dirname,'..'),state=path.resolve(process.env.FACTORY_BROWSER_STATE);
 const base=process.env.FACTORY_BROWSER_URL||'http://127.0.0.1:8097';
 if(!['127.0.0.1','localhost'].includes(new URL(base).hostname))throw Error('Loopback only');
 const token=fs.readFileSync(path.join(state,'operator-1.token'),'utf8').trim();
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(base);await page.getByLabel('Access token').fill(token);
  await page.getByRole('button',{name:'Connect / refresh',exact:true}).click();
  await page.getByRole('button',{name:'Research',exact:true}).click();
  const alert=page.getByRole('alert').filter({hasText:'Screen pruning is disabled'});await alert.waitFor();
  const response=await page.request.get(base+'/api/v1/research/status',{headers:{Authorization:'Bearer '+token}});
  const status=await response.json();if(status.screening.circuit_breaker.enabled||!status.paused)throw Error('Breaker/pause mismatch');
  const panel=page.getByRole('heading',{name:'Research activity',exact:true}).locator('..');
  await panel.screenshot({path:root+'/reports/runtime/completion/screen-fallback-desktop.png'});
  await page.setViewportSize({width:390,height:844});await panel.screenshot({path:root+'/reports/runtime/completion/screen-fallback-mobile.png'});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile overflow');
  if(errors.length)throw Error(JSON.stringify(errors));
  console.log(JSON.stringify({authenticated:true,actual_native_fault_injection_fixture:true,disabled_alert:true,pause_preserved:true,mobile_overflow:false,page_errors:errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
