<script lang="ts">
 import ValidationLab from '../lib/ValidationLab.svelte';
 import SourceCoveragePanel from '../lib/SourceCoveragePanel.svelte';
 import InstrumentProfilesPanel from '../lib/InstrumentProfilesPanel.svelte';
 import SourceRegistryPanel from '../lib/SourceRegistryPanel.svelte';
 import StatisticalSafeguardsPanel from '../lib/StatisticalSafeguardsPanel.svelte';
 import InstrumentStatusPanel from '../lib/InstrumentStatusPanel.svelte';
 import IndependentRankingPanel from '../lib/IndependentRankingPanel.svelte';
 import QualifiedRankingPanel from '../lib/QualifiedRankingPanel.svelte';
 import ValidationEvaluationsPanel from '../lib/ValidationEvaluationsPanel.svelte';
 import StrategyDetailPanel from '../lib/StrategyDetailPanel.svelte';
 import ResearchTrialsPanel from '../lib/ResearchTrialsPanel.svelte';
 import SourceQualityPanel from '../lib/SourceQualityPanel.svelte';
 import InputReviews from '../lib/InputReviews.svelte';
 import DiscoveryPanel from '../lib/DiscoveryPanel.svelte';
 import ScreenCohortsPanel from '../lib/ScreenCohortsPanel.svelte';
 import HistoricalScreenCohortsPanel from '../lib/HistoricalScreenCohortsPanel.svelte';
 import ScreenComparabilityPanel from '../lib/ScreenComparabilityPanel.svelte';
 import ResearchReportsPanel from '../lib/ResearchReportsPanel.svelte';
 let token = $state('');
 let view = $state('Overview');
 let symbol = $state('EURUSD');
 let data = $state<unknown>(null);
 let evidencePath = $state('');
 let error = $state('');
 let pending = $state(false);
 const symbols=['EURUSD','GBPUSD','USDJPY','USDCHF','USDCAD','AUDUSD','NZDUSD','XAUUSD'];
 type ProtocolRow={protocol_hash:string;enabled:number;reason:string|null;protocol_json:string};
 type PolicyRow={policy_hash:string;enabled:number;policy_json:string};
 type ChildRow={edge_id:string;child_experiment_hash:string;hypothesis:string;status:string|null;evidence_json:string|null};
 type ResearchStatus={trials_considered:number;exact_duplicates_skipped:number;distinct_referenced_simulations:number;screening:{recovery_budget:{admitted:number;max_rechecks:number;measured_cpu_seconds:number;max_cpu_seconds:number;admission_stopped:boolean};circuit_breaker:{enabled:boolean;reason:string|null};native_rechecks:{state:string;count:number}[];pruned_completed_jobs:number;native_rejection_audits_passed:number;false_negative_failed_jobs:number}};
 type ImprovementStatus={policies:PolicyRow[];plans:number;children:number;measured_worker_cpu_seconds:number};
 let protocols=$state<ProtocolRow[]>([]);
 let children=$state<ChildRow[]>([]);
 let research=$state<ResearchStatus|null>(null);
 let improvement=$state<ImprovementStatus|null>(null);
 let selectedProtocol=$state('');
 let maxParents=$state(8);
 let maxChildren=$state(4);
 let cpuBudget=$state(300);
 const routes:Record<string,string>={Overview:'overview',Leaderboards:'leaderboards/',Research:'research/status',Improvements:'improvement/status',Validation:'validation/protocols',Queue:'jobs',Experiments:'experiments',Coverage:'coverage','Market data':'data/manifest',Audit:'audit',Operations:'health/ready'};
 async function request(path:string,method='GET',body?:unknown) {
  const r=await fetch('/api/v1/'+path,{method,headers:{Authorization:'Bearer '+token,...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
  if(!r.ok) throw new Error(`${r.status}: ${JSON.stringify(await r.json())}`);
  return r.json();
 }
 async function download(path:string,name:string){
  try{const response=await fetch('/api/v1/'+path,{headers:{Authorization:'Bearer '+token}});if(!response.ok)throw Error('Evidence download failed: '+response.status);const url=URL.createObjectURL(await response.blob());const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){error=String(e);}
 }
 async function load(name=view){
  view=name;pending=true;error='';
  try {
   const path=routes[name]+(name==='Leaderboards'?symbol:'');
   data=await request(path);evidencePath=path;
   if(name==='Research'||name==='Improvements') protocols=await request('research/protocols');
   if(name==='Research') research=data as ResearchStatus;
   if(name==='Improvements'){improvement=data as ImprovementStatus;children=await request('improvement/children');}
  }
  catch(e){error=String(e);data=null;}finally{pending=false;}
 }
 async function control(action:string){
  pending=true;error='';
  try{await request('research/'+action,'POST');await load('Overview');}
  catch(e){error=String(e);}finally{pending=false;}
 }
 function protocolName(row:ProtocolRow){
  const p=JSON.parse(row.protocol_json);return `${p.profile.instrument} · ${p.family} · ${p.timeframe} · ${row.protocol_hash.slice(0,10)}`;
 }
 function nativeChildRun(child:ChildRow):string|null{return child.evidence_json?JSON.parse(child.evidence_json).child_run_id??null:null;}
 async function stop(path:string){pending=true;error='';try{await request(path,'POST');await load();}catch(e){error=String(e);}finally{pending=false;}}
 async function registerImprovement(event:SubmitEvent){
  event.preventDefault();pending=true;error='';
  try{await request('improvement/policies','POST',{search_protocol_hash:selectedProtocol,max_parent_plans:maxParents,max_children:maxChildren,cpu_budget_seconds:cpuBudget});await load('Improvements');}
  catch(e){error=String(e);}finally{pending=false;}
 }
 async function inspect(run:string){pending=true;error='';try{data=await request('experiments/'+run);evidencePath='experiments/'+run;}catch(e){error=String(e);}finally{pending=false;}}
</script>
<svelte:head><title>Hermes Factory · Research</title><meta name="description" content="Historical and paper research control plane"/></svelte:head>
<div class="shell">
 <aside><div class="brand">HERMES <span>FACTORY</span></div><p>Historical & paper research</p>
  <nav aria-label="Main navigation">{#each Object.keys(routes) as name}<button class:active={view===name} disabled={pending} onclick={()=>load(name)}>{name}</button>{/each}</nav>
  <div class="notice">Development checkpoint<br/><strong>NOT_READY</strong><br/>No verified release</div>
 </aside>
 <main>
  <header><div><small>RESEARCH CONTROL PLANE</small><h1>{view}</h1></div><span class="badge">Historical / paper only</span></header>
  <section class="auth"><label>Access token <input type="password" bind:value={token} autocomplete="off" placeholder="Local operator or viewer token"/></label><button onclick={()=>load()} disabled={pending}>Connect / refresh</button><p>Token stays in memory. Use a secure tunnel. No default credentials.</p></section>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if pending}<p role="status">Loading application state…</p>{/if}
  {#if view==='Overview'}<section class="controls"><button onclick={()=>control('pause')} disabled={pending}>Pause after current job</button><button onclick={()=>control('resume')} disabled={pending}>Resume queued research</button></section>{/if}
  {#if view==='Leaderboards'}<label>Instrument <select bind:value={symbol} onchange={()=>load()}>{#each symbols as s}<option>{s}</option>{/each}</select></label><p>Five maximum per instrument. Empty slots stay empty. Synthetic runs are labeled; validation is separate.</p>{/if}
  {#if view==='Research' && research && data!==null}
   <DiscoveryPanel {request} {download}/>
   <IndependentRankingPanel {request}/>
   <QualifiedRankingPanel {request}/>
   <ValidationEvaluationsPanel {request}/>
   <StrategyDetailPanel {request}/>
   <ResearchTrialsPanel {request}/>
   <StatisticalSafeguardsPanel {request}/>
   <ScreenCohortsPanel {request} {download}/>
   <HistoricalScreenCohortsPanel {request} {download}/>
   <ScreenComparabilityPanel {request}/>
   <ResearchReportsPanel {request}/>
   <section class="panel"><h2>Research activity</h2>{#if !research.screening.circuit_breaker.enabled}<p role="alert">Screen pruning is disabled after a native audit disagreement. New candidates use native replay. Prior rejections remain visible while bounded native rechecks run.</p><p>{research.screening.circuit_breaker.reason}</p><p>{research.screening.recovery_budget.admitted} / {research.screening.recovery_budget.max_rechecks} rechecks admitted · {research.screening.recovery_budget.measured_cpu_seconds.toFixed(1)} / {research.screening.recovery_budget.max_cpu_seconds} measured CPU seconds. {research.screening.recovery_budget.admission_stopped ? 'Recovery admission stopped at its budget.' : 'Bounded in-flight work may finish.'}</p>{#each research.screening.native_rechecks as recheck}<p>{recheck.count} native rechecks: {recheck.state}</p>{/each}{/if}<div class="metrics"><p><strong>{research.trials_considered}</strong> hypotheses</p><p><strong>{research.distinct_referenced_simulations}</strong> native runs</p><p><strong>{research.exact_duplicates_skipped}</strong> exact duplicates</p><p><strong>{research.screening.pruned_completed_jobs}</strong> no-signal rejections</p><p><strong>{research.screening.native_rejection_audits_passed}</strong> passed native rejection audits</p><p><strong>{research.screening.false_negative_failed_jobs}</strong> false-negative failed jobs</p></div><p>Exploratory training results require independent evaluation. A rejected screen has no simulated return.</p></section>
   <section class="panel"><h2>Registered research regions</h2>{#if protocols.length===0}<p>No regions registered.</p>{/if}{#each protocols as row}<div class="row"><span>{protocolName(row)} · {row.enabled?'enabled':'disabled'}</span>{#if row.enabled}<button disabled={pending} onclick={()=>stop('research/protocols/'+row.protocol_hash+'/disable')}>Stop new proposals</button>{/if}</div>{/each}</section>
  {/if}
  {#if view==='Improvements' && improvement && data!==null}
   <section class="panel"><h2>Controlled training improvement</h2><div class="metrics"><p><strong>{improvement.plans}</strong> diagnosis plans</p><p><strong>{improvement.children}</strong> children preserved</p><p><strong>{improvement.measured_worker_cpu_seconds.toFixed(2)}</strong> worker CPU seconds</p></div><p>Parents remain intact. Each bounded round tests a stated hypothesis on its original training span. Training gains require untouched independent evaluation.</p>
    <form onsubmit={registerImprovement}>
     <label>Research region <select bind:value={selectedProtocol} required><option value="">Select a registered region</option>{#each protocols.filter(p=>p.enabled) as row}<option value={row.protocol_hash}>{protocolName(row)}</option>{/each}</select></label>
     <div class="fields"><label>Maximum parent plans <input type="number" min="1" max="32" bind:value={maxParents} required/></label><label>Children per parent <input type="number" min="1" max="4" bind:value={maxChildren} required/></label><label>Worker CPU budget (seconds) <input type="number" min="1" max="86400" bind:value={cpuBudget} required/></label></div>
     <button disabled={pending||!selectedProtocol} type="submit">Enable bounded improvement</button>
    </form>
   </section>
   <section class="panel"><h2>Improvement policies</h2>{#if improvement.policies.length===0}<p>No policies registered.</p>{/if}{#each improvement.policies as policy}<div class="row"><span>{policy.policy_hash.slice(0,12)} · {policy.enabled?'enabled':'disabled'}</span>{#if policy.enabled}<button disabled={pending} onclick={()=>stop('improvement/policies/'+policy.policy_hash+'/disable')}>Stop new children</button>{/if}</div>{/each}</section>
   <section class="panel"><h2>Children and paired comparisons</h2>{#if children.length===0}<p>No controlled children have been planned.</p>{/if}{#each children as child}<article><h3>{child.status??'Awaiting execution or budget'}</h3><p>{child.hypothesis}</p><button onclick={()=>{view='Experiments';inspect(child.child_experiment_hash);}} disabled={pending||!nativeChildRun(child)}>Inspect native run</button><details><summary>Paired evidence</summary><pre>{child.evidence_json?JSON.stringify(JSON.parse(child.evidence_json),null,2):'No completed comparison yet.'}</pre></details></article>{/each}</section>
  {/if}
  {#if view==='Market data' && data!==null}<SourceCoveragePanel {request}/><InstrumentStatusPanel {request}/><InstrumentProfilesPanel {request}/><SourceRegistryPanel {request}/><SourceQualityPanel {request} {download}/><InputReviews {request} {download}/>{/if}
  {#if view==='Validation' && data!==null}<ValidationLab {request} {download}/>{/if}
  {#if view==='Queue' && Array.isArray(data)}<section class="panel"><h2>Jobs</h2>{#if data.length===0}<p>No queued jobs.</p>{/if}{#each data as job}<div class="row"><span>{job.job_id.slice(0,12)} · {job.state}</span>{#if ['QUEUED','RUNNING','FAILED_RETRYABLE'].includes(job.state)}<button disabled={pending} onclick={()=>stop('jobs/'+job.job_id+'/cancel')}>Cancel job</button>{/if}</div>{/each}</section>{/if}
  {#if view==='Experiments' && Array.isArray(data)}<ul>{#each data as run}<li><button onclick={()=>inspect(run.run_id)}>{run.instrument} · {run.status} · {run.run_id.slice(0,12)}</button></li>{/each}</ul>{/if}
  {#if data!==null}<section class="panel"><button disabled={pending||!evidencePath} onclick={()=>download(evidencePath,'hermes-'+view.toLowerCase().replaceAll(' ','-')+'.json')}>Download exact API response</button><details><summary>Application evidence</summary><p>Display only: browser numbers may round nanosecond timestamps. The download preserves exact API response bytes.</p><pre>{JSON.stringify(data,null,2)}</pre></details></section>{:else}<section class="panel"><h2>Connect to inspect state</h2><p>No strategy metrics are displayed until deterministic jobs produce them.</p></section>{/if}
  <footer>2025 / 2026 research · no brokerage execution · independent evidence required for validation</footer>
 </main>
</div>
<style>
 .metrics,.fields{display:flex;flex-wrap:wrap;gap:20px}.metrics strong{display:block;font-size:26px;color:#65d9bf}.fields label{display:grid;gap:8px;margin:20px 0}.fields input{width:180px}.row{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 0;border-bottom:1px solid #293447}article{padding:12px 0;border-top:1px solid #293447}details{margin-top:16px}summary{cursor:pointer}form>label{display:grid;gap:10px}form select{max-width:100%;min-width:0;margin-left:0} :global(body){margin:0;background:#10151e;color:#e3e8f0;font:15px system-ui,sans-serif} :global(*){box-sizing:border-box}.shell{display:flex;min-height:100vh}aside{width:230px;padding:32px 22px;background:#151d29;border-right:1px solid #293447}.brand{font-weight:800;letter-spacing:2px}.brand span{color:#65d9bf}aside p,small,footer{color:#9eacbf;font-size:12px}nav{display:grid;gap:7px;margin-top:35px}button,select,input{font:inherit;border:1px solid #3a4b61;border-radius:7px;padding:10px 14px;background:#1c293b;color:#e3e8f0}button{cursor:pointer}button:hover,button.active{background:#244c4a;border-color:#65d9bf}button:disabled{opacity:.5}nav button{text-align:left}.notice{margin-top:35px;font-size:12px;line-height:1.8;color:#e5c37c}main{padding:32px 5%;width:calc(100% - 230px)}header{display:flex;justify-content:space-between;align-items:center}h1{font-size:32px;margin:10px 0 25px}h2{font-size:17px}.badge{font-size:12px;color:#65d9bf}.auth,.panel{background:#151d29;border:1px solid #293447;border-radius:12px;padding:22px;margin-bottom:22px}.auth label{display:inline-flex;gap:12px;align-items:center;margin-right:12px}.auth input{width:320px}.auth p{font-size:12px;color:#9eacbf}.controls{display:flex;gap:12px;margin-bottom:24px}pre{font-size:12px;overflow:auto;max-height:65vh;line-height:1.6}.error{color:#ffa69e}footer{margin-top:30px}label select{margin-left:10px}li{margin:10px 0}@media(max-width:760px){.shell{display:block}aside{width:100%;padding:20px}nav{display:flex;flex-wrap:wrap;margin-top:15px}.notice{margin-top:12px}main{width:100%;padding:22px}header{align-items:start}.auth input{width:100%}.auth label{display:block;margin-bottom:10px}.controls{flex-wrap:wrap}}
</style>
