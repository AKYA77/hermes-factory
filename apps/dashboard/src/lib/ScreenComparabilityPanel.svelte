<script lang="ts">
 import {onMount} from 'svelte';
 type Cohort={cohort_id:string};
 type Pair={left:string;right:string;comparable:boolean;differences:string[]};
 type Bias={distinct_effective_experiments:number;selected_for_native_audit:number;selected_and_observed:number;selected_but_unobserved:number;unselected_frame_members:number;selection_ratio:number|null};
 type Report={request_hash:string;all_comparable:boolean;pairwise:Pair[];selection_bias:Bias;pooled_claim_authorized:boolean;approximate_pruning_authorized:boolean;limitations:string[]};
 let {request}:{request:(path:string,method?:string,body?:unknown)=>Promise<any>}=$props();
 const ATTESTATION='Compare frozen screening cohorts for evaluation-semantics comparability only; no pooling into qualification, ranking or strategy evidence';
 let cohorts=$state<Cohort[]>([]),selected=$state<string[]>([]),actor=$state(''),attest=$state(false),report=$state<Report|null>(null),error=$state(''),busy=$state(false);
 async function refresh(){try{cohorts=(await request('research/screen-cohorts?limit=100')).cohorts;error='';}catch(e){error=String(e);}}
 onMount(refresh);
 async function compare(event:SubmitEvent){event.preventDefault();busy=true;try{report=await request('research/screen-comparability','POST',{cohort_ids:selected,authorized_by:actor,attestation:ATTESTATION});error='';}catch(e){error=String(e);}finally{busy=false;}}
</script>
<section class="comparability" aria-label="Screening cohort comparability">
 <header><h2>Screening cohort comparability</h2><button onclick={refresh} disabled={busy}>Refresh cohorts</button></header>
 <p>States whether frozen cohorts share evaluation semantics. Comparability never authorizes pooling screening observations into a qualification, ranking or strategy claim.</p>
 {#if error}<p role="alert">{error}</p>{/if}
 <form onsubmit={compare}>
  <fieldset><legend>Frozen cohorts</legend>{#each cohorts as cohort}<label class="choice"><input type="checkbox" bind:group={selected} value={cohort.cohort_id}/><span><small>{cohort.cohort_id}</small></span></label>{/each}{#if cohorts.length===0}<p>No frozen cohorts.</p>{/if}</fieldset>
  <div class="fields"><label>Cohort authorized by <input bind:value={actor} maxlength="200" required/></label></div>
  <label class="choice"><input type="checkbox" bind:checked={attest}/><span>{ATTESTATION}</span></label>
  <button disabled={busy||!attest||selected.length<2}>Compare cohorts</button>
 </form>
 {#if report}<article>
  <h3>Comparability report</h3>
  <p>All selected cohorts share evaluation semantics: {report.all_comparable?'yes':'no'}.</p>
  <ul>{#each report.pairwise as pair}<li>{pair.left.slice(0,12)} vs {pair.right.slice(0,12)}: {pair.comparable?'comparable':'not comparable'}{pair.differences.length?' · '+pair.differences.join(', '):''}</li>{/each}</ul>
  <h4>Selection bias</h4>
  <div class="metrics"><p><strong>{report.selection_bias.distinct_effective_experiments}</strong> distinct effective experiments</p><p><strong>{report.selection_bias.selected_for_native_audit}</strong> selected for native audit</p><p><strong>{report.selection_bias.selected_and_observed}</strong> selected and observed</p><p><strong>{report.selection_bias.selected_but_unobserved}</strong> selected but unobserved</p><p><strong>{report.selection_bias.unselected_frame_members}</strong> unselected frame members</p></div>
  <p>Pooled claim authorized: {report.pooled_claim_authorized?'yes':'no'}. Approximate pruning: {report.approximate_pruning_authorized?'authorized':'disabled'}.</p>
  <ul>{#each report.limitations as limitation}<li>{limitation}</li>{/each}</ul>
 </article>{/if}
</section>
<style>
 .comparability{margin:1.2rem 0;padding:1rem;background:#151e29;border:1px solid #304158;border-radius:12px;overflow-wrap:anywhere}header,.fields{display:flex;flex-wrap:wrap;gap:.8rem;align-items:center;justify-content:space-between}fieldset{min-width:0;margin:1rem 0;border:1px solid #40516a;border-radius:8px}.choice{display:flex;align-items:flex-start;gap:.6rem;margin:.6rem 0}.choice input{width:auto;flex:none}small{display:block;color:#b5c2d3;overflow-wrap:anywhere}.fields label{flex:1;min-width:180px}input{display:block;max-width:100%;box-sizing:border-box;padding:.6rem}article{margin-top:1rem}.metrics{display:flex;flex-wrap:wrap;gap:1rem}button{padding:.6rem;margin:.2rem;max-width:100%}
</style>
