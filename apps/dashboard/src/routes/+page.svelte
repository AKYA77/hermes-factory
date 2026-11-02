<script lang="ts">
 let token = $state('');
 let view = $state('Overview');
 let symbol = $state('EURUSD');
 let data = $state<unknown>(null);
 let error = $state('');
 let pending = $state(false);
 const symbols=['EURUSD','GBPUSD','USDJPY','USDCHF','USDCAD','AUDUSD','NZDUSD','XAUUSD'];
 const routes:Record<string,string>={Overview:'overview',Leaderboards:'leaderboards/',Research:'jobs',Experiments:'experiments',Coverage:'coverage','Market data':'data/manifest',Audit:'audit',Operations:'health/ready'};
 async function request(path:string,method='GET') {
  const r=await fetch('/api/v1/'+path,{method,headers:{Authorization:'Bearer '+token}});
  if(!r.ok) throw new Error(`${r.status}: ${JSON.stringify(await r.json())}`);
  return r.json();
 }
 async function load(name=view){
  view=name;pending=true;error='';
  try {data=await request(routes[name]+(name==='Leaderboards'?symbol:''));}
  catch(e){error=String(e);data=null;}finally{pending=false;}
 }
 async function control(action:string){
  pending=true;error='';
  try{await request('research/'+action,'POST');await load('Overview');}
  catch(e){error=String(e);}finally{pending=false;}
 }
 async function inspect(run:string){pending=true;error='';try{data=await request('experiments/'+run);}catch(e){error=String(e);}finally{pending=false;}}
</script>
<svelte:head><title>Hermes Factory · Research</title><meta name="description" content="Historical and paper research control plane"/></svelte:head>
<div class="shell">
 <aside><div class="brand">HERMES <span>FACTORY</span></div><p>Historical & paper research</p>
  <nav aria-label="Main navigation">{#each Object.keys(routes) as name}<button class:active={view===name} onclick={()=>load(name)}>{name}</button>{/each}</nav>
  <div class="notice">Development checkpoint<br/><strong>NOT_READY</strong><br/>No verified release</div>
 </aside>
 <main>
  <header><div><small>RESEARCH CONTROL PLANE</small><h1>{view}</h1></div><span class="badge">Historical / paper only</span></header>
  <section class="auth"><label>Access token <input type="password" bind:value={token} autocomplete="off" placeholder="Local operator or viewer token"/></label><button onclick={()=>load()} disabled={pending}>Connect / refresh</button><p>Token stays in memory. Use a secure tunnel. No default credentials.</p></section>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if pending}<p role="status">Loading application state…</p>{/if}
  {#if view==='Overview'}<section class="controls"><button onclick={()=>control('pause')} disabled={pending}>Pause after current job</button><button onclick={()=>control('resume')} disabled={pending}>Resume queued research</button></section>{/if}
  {#if view==='Leaderboards'}<label>Instrument <select bind:value={symbol} onchange={()=>load()}>{#each symbols as s}<option>{s}</option>{/each}</select></label><p>Five maximum per instrument. Empty slots stay empty. Synthetic runs are labeled; validation is separate.</p>{/if}
  {#if view==='Experiments' && Array.isArray(data)}<ul>{#each data as run}<li><button onclick={()=>inspect(run.run_id)}>{run.instrument} · {run.status} · {run.run_id.slice(0,12)}</button></li>{/each}</ul>{/if}
  {#if data!==null}<section class="panel"><h2>Verified application response</h2><pre>{JSON.stringify(data,null,2)}</pre></section>{:else}<section class="panel"><h2>Connect to inspect state</h2><p>No strategy metrics are displayed until deterministic jobs produce them.</p></section>{/if}
  <footer>2025 / 2026 research · no brokerage execution · independent evidence required for validation</footer>
 </main>
</div>
<style>
 :global(body){margin:0;background:#10151e;color:#e3e8f0;font:15px system-ui,sans-serif} :global(*){box-sizing:border-box}.shell{display:flex;min-height:100vh}aside{width:230px;padding:32px 22px;background:#151d29;border-right:1px solid #293447}.brand{font-weight:800;letter-spacing:2px}.brand span{color:#65d9bf}aside p,small,footer{color:#9eacbf;font-size:12px}nav{display:grid;gap:7px;margin-top:35px}button,select,input{font:inherit;border:1px solid #3a4b61;border-radius:7px;padding:10px 14px;background:#1c293b;color:#e3e8f0}button{cursor:pointer}button:hover,button.active{background:#244c4a;border-color:#65d9bf}button:disabled{opacity:.5}nav button{text-align:left}.notice{margin-top:35px;font-size:12px;line-height:1.8;color:#e5c37c}main{padding:32px 5%;width:calc(100% - 230px)}header{display:flex;justify-content:space-between;align-items:center}h1{font-size:32px;margin:10px 0 25px}h2{font-size:17px}.badge{font-size:12px;color:#65d9bf}.auth,.panel{background:#151d29;border:1px solid #293447;border-radius:12px;padding:22px;margin-bottom:22px}.auth label{display:inline-flex;gap:12px;align-items:center;margin-right:12px}.auth input{width:320px}.auth p{font-size:12px;color:#9eacbf}.controls{display:flex;gap:12px;margin-bottom:24px}pre{font-size:12px;overflow:auto;max-height:65vh;line-height:1.6}.error{color:#ffa69e}footer{margin-top:30px}label select{margin-left:10px}li{margin:10px 0}@media(max-width:760px){.shell{display:block}aside{width:100%;padding:20px}nav{display:flex;flex-wrap:wrap;margin-top:15px}.notice{margin-top:12px}main{width:100%;padding:22px}header{align-items:start}.auth input{width:100%}.auth label{display:block;margin-bottom:10px}.controls{flex-wrap:wrap}}
</style>
