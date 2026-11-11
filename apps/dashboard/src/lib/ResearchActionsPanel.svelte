<script lang="ts">
 import {onMount} from 'svelte';
 type Plan={plan_hash:string;created_at:number;policy_hash:string|null;summary:string|null;[key:string]:unknown};
 let {request}:{request:(path:string,method?:string,body?:unknown)=>Promise<any>}=$props();

 // Each attestation is copied verbatim from the pinned Literal in the
 // corresponding factory module. The endpoints reject any other string.
 const ATTEST={
  sensitivity:'Report descriptive parameter sensitivity for controlled training comparisons only; no qualification, ranking or promotion',
  diversity:'Report descriptive candidate diversity for a registered search protocol only; no qualification, ranking or promotion',
  lineage:'Reconstruct retained training improvement lineage only; no qualification, ranking or promotion',
  confirmation:'Bind a training improvement to a retained independent evaluation only; no qualification, ranking or promotion',
  comparability:'Retain a typed comparability contract only; no qualification, ranking or promotion',
  cohorts:'Aggregate retained verified training diagnostics into descriptive cohorts only; no qualification, ranking or strategy evidence',
  annual:'Report descriptive annual and pooled aggregates over retained independent evaluations only; no qualification, ranking or promotion',
 };

 let plans=$state<Plan[]>([]),result=$state<any>(null),error=$state(''),busy=$state(false);
 let actor=$state('');
 let policyHash=$state(''),protocolHash=$state(''),experimentHash=$state('');
 let edgeId=$state(''),evaluationId=$state('');
 let instrument=$state('EURUSD'),datasetHash=$state('');

 const TASKS=[
  {id:'improvement-sensitivity',label:'Improvement sensitivity',needs:['policyHash'],attest:ATTEST.sensitivity},
  {id:'candidate-diversity',label:'Candidate diversity',needs:['protocolHash'],attest:ATTEST.diversity},
  {id:'improvement-lineage',label:'Improvement lineage',needs:['policyHash'],attest:ATTEST.lineage},
  {id:'improvement-confirmation',label:'Improvement confirmation',needs:['edgeId','evaluationId'],attest:ATTEST.confirmation},
  {id:'diagnostic-cohorts',label:'Diagnostic cohorts',needs:['experimentHash'],attest:ATTEST.cohorts},
  {id:'annual-reporting',label:'Annual reporting',needs:[],attest:ATTEST.annual},
 ];

 function hasValue(name:string):boolean{
  const map:Record<string,string>={policyHash,protocolHash,experimentHash,edgeId,evaluationId};
  return !!map[name].trim();
 }
 function ready(t:any):boolean{
  if(!actor.trim())return false;
  return t.needs.every((n:string)=>hasValue(n));
 }
 function bodyFor(t:any):Record<string,unknown>{
  const b:Record<string,unknown>={authorized_by:actor.trim(),attestation:t.attest};
  if(t.id==='improvement-sensitivity')b.policy_hash=policyHash.trim();
  if(t.id==='candidate-diversity')b.protocol_hash=protocolHash.trim();
  if(t.id==='improvement-lineage')b.policy_hash=policyHash.trim();
  if(t.id==='improvement-confirmation'){b.edge_id=edgeId.trim();b.evaluation_id=evaluationId.trim();}
  if(t.id==='diagnostic-cohorts')b.experiment_hash=experimentHash.trim();
  return b;
 }
 async function run(t:any){busy=true;error='';result=null;
  try{result=await request('research/'+t.id,'POST',bodyFor(t));}
  catch(e){error=String(e);}finally{busy=false;}}
 async function refreshPlans(){busy=true;error='';
  try{plans=await request('improvement/plans?limit=50&offset=0');}
  catch(e){error=String(e);}finally{busy=false;}}
 onMount(refreshPlans);
</script>
<section class="actions" aria-label="Research actions and improvement plans">
 <header><h2>Research actions and improvement plans</h2><button onclick={refreshPlans} disabled={busy}>Refresh plans</button></header>
 <p>These report descriptive analyses over retained training records. None of them qualifies, ranks or promotes anything, and none is a strategy verdict.</p>
 <label>Actor <input aria-label="Actor identity" bind:value={actor} maxlength="120" placeholder="Named accountable actor"/></label>
 {#if error}<p role="alert">{error}</p>{/if}

 <div class="fields">
  <label>Policy hash <input aria-label="Policy hash" bind:value={policyHash} maxlength="200" placeholder="strategy or policy identity"/></label>
  <label>Protocol hash <input aria-label="Protocol hash" bind:value={protocolHash} maxlength="200" placeholder="registered search protocol"/></label>
  <label>Experiment hash <input aria-label="Experiment hash" bind:value={experimentHash} maxlength="200"/></label>
  <label>Edge id <input aria-label="Edge identity" bind:value={edgeId} maxlength="200"/></label>
  <label>Evaluation id <input aria-label="Evaluation identity" bind:value={evaluationId} maxlength="200"/></label>
 </div>

 <div class="buttons">
  {#each TASKS as t}
   <button disabled={busy||!ready(t)} onclick={()=>run(t)}>{t.label}</button>
  {/each}
 </div>
 <p class="hint">A button is disabled until its required identity fields and the actor are supplied, so a request cannot be sent half-formed.</p>

 {#if result}
  <article>
   <h3>Report</h3>
   <pre>{JSON.stringify(result,null,2)}</pre>
  </article>
 {/if}

 <article>
  <h3>Improvement plans · {plans.length}</h3>
  {#if plans.length}
   <div class="tablewrap"><table><thead><tr><th>Plan</th><th>Created</th><th>Policy</th></tr></thead>
    <tbody>{#each plans as p}
     <tr><td>{p.plan_hash.slice(0,12)}</td><td>{new Date(p.created_at).toISOString().slice(0,10)}</td><td>{p.policy_hash?p.policy_hash.slice(0,12):'—'}</td></tr>
    {/each}</tbody></table></div>
  {:else}<p>No improvement plans are retained. An empty list is a valid result, not a missing feature.</p>{/if}
 </article>
</section>
<style>
 .actions{margin:1.2rem 0;padding:1rem;background:#151e29;border:1px solid #304158;border-radius:12px;overflow-wrap:anywhere}
 header{display:flex;flex-wrap:wrap;gap:.8rem;align-items:center;justify-content:space-between}
 .fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.8rem;margin-top:1rem}
 label{display:grid;gap:.4rem}
 input{display:block;max-width:100%;box-sizing:border-box;padding:.6rem}
 .buttons{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:1rem}
 article{margin-top:1rem}
 .tablewrap{overflow-x:auto;margin-top:.6rem}
 table{width:100%;border-collapse:collapse;font-size:.85rem}
 th,td{text-align:left;padding:.5rem .4rem;border-bottom:1px solid #304158}
 th{color:#b5c2d3;font-weight:600}
 pre{font-size:.8rem;overflow:auto;max-height:50vh}
 .hint{color:#7c8ea6;font-size:.8rem}
 button{padding:.6rem;margin:.2rem;max-width:100%}
</style>
