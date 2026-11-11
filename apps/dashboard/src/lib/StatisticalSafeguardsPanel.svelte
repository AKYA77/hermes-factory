<script lang="ts">
 import {onMount} from 'svelte';
 type Funnel={schema_version:string;[key:string]:unknown};
 type Retained={schema_version:string;instrument:string;[key:string]:unknown};
 type Testing={schema_version:string;candidates:number;uncorrected_passes:number;bonferroni_passes:number;benjamini_hochberg_passes:number;descriptive_only:boolean;qualification_authorized:boolean;[key:string]:unknown};
 let {request}:{request:(path:string,method?:string,body?:unknown)=>Promise<any>}=$props();
 const FUNNEL_ATTEST='Report a descriptive global candidate-selection funnel only; no qualification, ranking or promotion';
 const RETAINED_ATTEST='Retain and report every candidate with its exclusion reason; no silent discard and no validation of failed out-of-sample runs';
 const TESTING_ATTEST='Report descriptive multiple-testing corrections for retained candidate evidence only; no qualification, ranking or promotion';
 let instruments=$state<string[]>([]),instrument=$state('EURUSD'),actor=$state(''),agree=$state(false);
 let funnel=$state<Funnel|null>(null),retained=$state<Retained|null>(null),testing=$state<Testing|null>(null);
 let pvalues=$state('0.01,0.04,0.03,0.20'),error=$state(''),busy=$state(false);
 async function refresh(){busy=true;error='';
  try{
   const listing=await request('profiles');
   instruments=listing.profiles.map((p:{instrument:string})=>p.instrument).sort();
   if(!instruments.includes(instrument))instrument=instruments[0]??'EURUSD';
  }catch(e){error=String(e);}finally{busy=false;}}
 onMount(refresh);
 async function run(path:string,body:unknown){busy=true;error='';
  try{const r=await request(path,'POST',body);
   if(path==='research/selection-funnel')funnel=r;
   else if(path==='research/retained-candidates')retained=r;
   else testing=r;
  }catch(e){error=String(e);}finally{busy=false;}}
</script>
<section class="safeguards" aria-label="Statistical selection safeguards">
 <header><h2>Statistical selection safeguards</h2><button onclick={refresh} disabled={busy}>Refresh instruments</button></header>
 <p>These reports describe how many candidates survive each selection stage and each correction. They never qualify, rank or promote a strategy, and a corrected pass is still only evidence about the sampled period.</p>
 {#if error}<p role="alert">{error}</p>{/if}
 <div class="fields">
  <label>Authorized by <input aria-label="Authorized by" bind:value={actor} maxlength="200" required/></label>
  <label>Instrument <select aria-label="Instrument" bind:value={instrument}>{#each instruments as i}<option>{i}</option>{/each}</select></label>
  <label>p-values (comma separated) <input aria-label="p-values (comma separated)" bind:value={pvalues} required/></label>
 </div>
 <label class="choice"><input type="checkbox" aria-label="Descriptive reporting declaration" bind:checked={agree}/><span>I authorize descriptive reporting only, with no qualification, ranking or promotion.</span></label>
 <div class="actions">
  <button disabled={busy||!agree||!actor} onclick={()=>run('research/selection-funnel',{authorized_by:actor,attestation:FUNNEL_ATTEST})}>Report selection funnel</button>
  <button disabled={busy||!agree||!actor} onclick={()=>run('research/retained-candidates',{instrument,authorized_by:actor,attestation:RETAINED_ATTEST})}>Report retained candidates</button>
  <button disabled={busy||!agree||!actor} onclick={()=>{const values=pvalues.split(',').map((v:string)=>Number(v.trim())).filter((n:number)=>Number.isFinite(n));return run('research/multiple-testing',{candidate_ids:values.map((_v:number,i:number)=>i.toString(16).padStart(64,'0')),p_values:values,authorized_by:actor,attestation:TESTING_ATTEST});}}>Report multiple-testing correction</button>
 </div>
 {#if funnel}<article><h3>Selection funnel</h3><pre>{JSON.stringify(funnel,null,2)}</pre></article>{/if}
 {#if retained}<article><h3>Retained candidates · {retained.instrument}</h3><pre>{JSON.stringify(retained,null,2)}</pre></article>{/if}
 {#if testing}<article>
  <h3>Multiple-testing correction</h3>
  <div class="metrics">
   <p><strong>{testing.candidates}</strong> candidates</p>
   <p><strong>{testing.uncorrected_passes}</strong> uncorrected</p>
   <p><strong>{testing.bonferroni_passes}</strong> Bonferroni</p>
   <p><strong>{testing.benjamini_hochberg_passes}</strong> Benjamini-Hochberg</p>
  </div>
  <p>Descriptive only: {testing.descriptive_only?'yes':'no'}. Qualification authorized: {testing.qualification_authorized?'yes':'no'}.</p>
 </article>{/if}
</section>
<style>
 .safeguards{margin:1.2rem 0;padding:1rem;background:#151e29;border:1px solid #304158;border-radius:12px;overflow-wrap:anywhere}
 header{display:flex;flex-wrap:wrap;gap:.8rem;align-items:center;justify-content:space-between}
 .fields{display:flex;flex-wrap:wrap;gap:1rem;margin-top:1rem}
 .fields label{display:grid;gap:.4rem;flex:1;min-width:180px}
 .choice{display:flex;align-items:flex-start;gap:.6rem;margin:.8rem 0}
 .actions{display:flex;flex-wrap:wrap;gap:.6rem}
 input{display:block;max-width:100%;box-sizing:border-box;padding:.6rem}
 article{margin-top:1rem}
 pre{font-size:.8rem;overflow:auto;max-height:50vh}
 .metrics{display:flex;flex-wrap:wrap;gap:1rem}
 button{padding:.6rem;margin:.2rem;max-width:100%}
</style>
