<script lang="ts">
 import {onMount} from 'svelte';
 type Candidate={strategy_id:string;evaluation_id:string;operator:string;timeframe:string;ending_equity:string;status?:string};
 type Report={schema_version:string;evaluations_considered:number;selected:Candidate[];skipped:{strategy_id:string;reason:string}[];diversity_counts:Record<string,number>;descriptive_only:boolean;qualification_authorized:boolean;limitations:string[]};
 let {request}:{request:(path:string,method?:string,body?:unknown)=>Promise<any>}=$props();
 const ATTESTATION='Rank retained non-synthetic independent evaluations descriptively only; no qualification or promotion';
 let actor=$state(''),agree=$state(false),report=$state<Report|null>(null),error=$state(''),busy=$state(false);
 async function run(){busy=true;error='';
  try{report=await request('research/independent-ranking','POST',{max_slots:5,per_key_limit:2,authorized_by:actor,attestation:ATTESTATION});}
  catch(e){error=String(e);}finally{busy=false;}}
 onMount(()=>{});
</script>
<section class="ranking" aria-label="Independent qualified ranking">
 <header><h2>Independent qualified ranking</h2></header>
 <p>Ranks retained non-synthetic independent evaluations with the same diversity guard. A ranked candidate is not qualified or validated, and pooled equity is not a paired comparison.</p>
 {#if error}<p role="alert">{error}</p>{/if}
 <div class="fields">
  <label>Authorized by <input aria-label="Ranking authorized by" bind:value={actor} maxlength="200" required/></label>
 </div>
 <label class="choice"><input type="checkbox" aria-label="Ranking declaration" bind:checked={agree}/><span>I authorize descriptive ranking only, with no qualification or promotion.</span></label>
 <div class="actions"><button disabled={busy||!agree||!actor} onclick={run}>Rank independent evaluations</button></div>
 {#if report}
 <article>
  <h3>Ranking report</h3>
  <div class="metrics">
   <p><strong>{report.evaluations_considered}</strong> independent evaluations</p>
   <p><strong>{report.selected.length}</strong> selected</p>
   <p><strong>{report.skipped.length}</strong> skipped by the diversity guard</p>
  </div>
  {#if report.selected.length}
   <table><thead><tr><th>Strategy</th><th>Operator</th><th>Timeframe</th><th>Ending equity</th></tr></thead>
   <tbody>{#each report.selected as c}<tr><td>{c.strategy_id.slice(0,12)}</td><td>{c.operator}</td><td>{c.timeframe}</td><td>{c.ending_equity}</td></tr>{/each}</tbody></table>
  {:else}<p>No retained non-synthetic independent evaluation is available to rank. An empty ranking is a valid result.</p>{/if}
  <p>Descriptive only: {report.descriptive_only?'yes':'no'}. Qualification authorized: {report.qualification_authorized?'yes':'no'}.</p>
 </article>
 {/if}
</section>
<style>
 .ranking{margin:1.2rem 0;padding:1rem;background:#151e29;border:1px solid #304158;border-radius:12px;overflow-wrap:anywhere}
 header{display:flex;flex-wrap:wrap;gap:.8rem;align-items:center;justify-content:space-between}
 .fields{display:flex;flex-wrap:wrap;gap:1rem;margin-top:1rem}
 .fields label{display:grid;gap:.4rem;flex:1;min-width:180px}
 .choice{display:flex;align-items:flex-start;gap:.6rem;margin:.8rem 0}
 .actions{display:flex;flex-wrap:wrap;gap:.6rem}
 input{display:block;max-width:100%;box-sizing:border-box;padding:.6rem}
 article{margin-top:1rem}
 table{width:100%;border-collapse:collapse;margin-top:1rem;font-size:.9rem}
 th,td{text-align:left;padding:.5rem .4rem;border-bottom:1px solid #304158}
 th{color:#b5c2d3;font-weight:600}
 .metrics{display:flex;flex-wrap:wrap;gap:1rem}
 button{padding:.6rem;margin:.2rem;max-width:100%}
</style>
