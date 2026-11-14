<script lang="ts">
 import {onMount} from 'svelte';
 type Candidate={strategy_id:string;run_id:string;status:string;operator:string;timeframe:string;metrics:Record<string,unknown>};
 type Report={schema_version:string;instrument:string;max_slots:number;per_key_limit:number;candidates_considered:number;selected:Candidate[];skipped:{strategy_id:string;operator:string;timeframe:string;reason:string}[];diversity_counts:Record<string,number>;selection_policy:string;descriptive_only:boolean;qualification_authorized:boolean;limitations:string[]};
 let {request}:{request:(path:string,method?:string,body?:unknown)=>Promise<any>}=$props();
 // Pinned to factory/ranking/qualified.py::ATTESTATION. The endpoint rejects any
 // other string with 422, so this literal is copied exactly rather than paraphrased.
 const ATTESTATION='Select a descriptive diversity-aware training shortlist only; no qualification, ranking promotion or validation';
 const symbols=['EURUSD','GBPUSD','USDJPY','USDCHF','USDCAD','AUDUSD','NZDUSD','XAUUSD'];
 let instrument=$state('EURUSD'),maxSlots=$state(5),perKeyLimit=$state(2),actor=$state(''),agree=$state(false);
 let report=$state<Report|null>(null),error=$state(''),busy=$state(false);
 async function run(){busy=true;error='';report=null;
  try{report=await request('research/qualified-ranking','POST',{instrument,max_slots:maxSlots,per_key_limit:perKeyLimit,authorized_by:actor,attestation:ATTESTATION});}
  catch(e){error=String(e);}finally{busy=false;}}
 onMount(()=>{});
</script>
<section class="qualified" aria-label="Qualified training shortlist">
 <header><h2>Qualified training shortlist</h2></header>
 <p>Selects a descriptive, diversity-aware shortlist over retained training experiments for one instrument. It does not qualify, rank for promotion or validate a strategy, and an empty shortlist is a valid result.</p>
 {#if error}<p role="alert">{error}</p>{/if}
 <div class="fields">
  <label>Instrument <select aria-label="Qualified ranking instrument" bind:value={instrument}>{#each symbols as s}<option>{s}</option>{/each}</select></label>
  <label>Maximum slots <input aria-label="Qualified ranking maximum slots" type="number" min="1" max="5" bind:value={maxSlots}/></label>
  <label>Per key limit <input aria-label="Qualified ranking per key limit" type="number" min="1" max="5" bind:value={perKeyLimit}/></label>
  <label>Authorized by <input aria-label="Qualified ranking authorized by" bind:value={actor} maxlength="200" required/></label>
 </div>
 <label class="choice"><input type="checkbox" aria-label="Qualified ranking declaration" bind:checked={agree}/><span>I authorize a descriptive training shortlist only, with no qualification, ranking promotion or validation.</span></label>
 <div class="actions"><button disabled={busy||!agree||!actor} onclick={run}>Rank qualified shortlist</button></div>
 {#if report}
 <article>
  <h3>Shortlist report · {report.instrument}</h3>
  <div class="metrics">
   <p><strong>{report.candidates_considered}</strong> candidates considered</p>
   <p><strong>{report.selected.length}</strong> selected</p>
   <p><strong>{report.skipped.length}</strong> skipped by the diversity guard</p>
  </div>
  <p>Selection policy: {report.selection_policy}.</p>
  {#if report.selected.length}
   <div class="tablewrap"><table><thead><tr><th>Strategy</th><th>Operator</th><th>Timeframe</th><th>Status</th></tr></thead>
    <tbody>{#each report.selected as c}<tr><td>{c.strategy_id.slice(0,12)}</td><td>{c.operator}</td><td>{c.timeframe}</td><td>{c.status}</td></tr>{/each}</tbody></table></div>
  {:else}<p>No retained candidate is available for this instrument. An empty shortlist is a valid result.</p>{/if}
  {#if report.skipped.length}
   <details><summary>Diversity guard skips</summary>
    <div class="tablewrap"><table><thead><tr><th>Strategy</th><th>Operator</th><th>Timeframe</th><th>Reason</th></tr></thead>
     <tbody>{#each report.skipped as s}<tr><td>{s.strategy_id.slice(0,12)}</td><td>{s.operator}</td><td>{s.timeframe}</td><td>{s.reason}</td></tr>{/each}</tbody></table></div>
   </details>
  {/if}
  <p>Diversity counts: {Object.entries(report.diversity_counts).map(([key,count])=>key+' '+count).join(', ')||'none'}.</p>
  <p>Descriptive only: {report.descriptive_only?'yes':'no'}. Qualification authorized: {report.qualification_authorized?'yes':'no'}.</p>
  <ul>{#each report.limitations as limitation}<li>{limitation}</li>{/each}</ul>
 </article>
 {/if}
</section>
<style>
 .qualified{margin:1.2rem 0;padding:1rem;background:#151e29;border:1px solid #304158;border-radius:12px;overflow-wrap:anywhere}
 header{display:flex;flex-wrap:wrap;gap:.8rem;align-items:center;justify-content:space-between}
 .fields{display:flex;flex-wrap:wrap;gap:1rem;margin-top:1rem}
 .fields label{display:grid;gap:.4rem;flex:1;min-width:160px}
 .choice{display:flex;align-items:flex-start;gap:.6rem;margin:.8rem 0}
 .actions{display:flex;flex-wrap:wrap;gap:.6rem}
 input,select{display:block;max-width:100%;box-sizing:border-box;padding:.6rem}
 article{margin-top:1rem}
 .tablewrap{overflow-x:auto;margin-top:.6rem}
 table{width:100%;border-collapse:collapse;font-size:.85rem}
 th,td{text-align:left;padding:.5rem .4rem;border-bottom:1px solid #304158;overflow-wrap:anywhere}
 th{color:#b5c2d3;font-weight:600}
 .metrics{display:flex;flex-wrap:wrap;gap:1rem}
 button{padding:.6rem;margin:.2rem;max-width:100%}
</style>
