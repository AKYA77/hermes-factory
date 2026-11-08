<script lang="ts">
 import {onMount} from 'svelte';
 type Profile={instrument:string;version:string;synthetic:boolean;profile_hash:string};
 type Source={dataset_hash:string;instrument:string;rows:number;bytes:number;fidelity:string};
 type Funnel={search_trials:number;distinct_effective_cohort_candidates:number;selected_for_native_audit:number;selected_and_observed:number;training_promotions:number;funnel_complete:boolean};
 type Annual={evaluations:number;by_year:Record<string,{trades:number;win_rate:string|null}>;pooled:{trades:number;win_rate:string|null}};
 type Ranking={evaluations_considered:number;selected:{strategy_id:string;ending_equity:string}[];descriptive_only:boolean};
 type Storage={partitions:number;rows:number;bytes:number;by_instrument:Record<string,{partitions:number;rows:number;bytes:number}>};
 let {request}:{request:(path:string,method?:string,body?:unknown)=>Promise<any>}=$props();
 const ATTESTATION='Report descriptive research aggregates only; no qualification, ranking or promotion';
 let actor=$state(''),attest=$state(false),error=$state(''),busy=$state(false);
 let profiles=$state<Profile[]>([]),sources=$state<Source[]>([]),storage=$state<Storage|null>(null);
 let funnel=$state<Funnel|null>(null),annual=$state<Annual|null>(null),ranking=$state<Ranking|null>(null);
 async function get(path:string){busy=true;try{return await request(path);}catch(e){error=String(e);return null;}finally{busy=false;}}
 async function post(path:string){busy=true;try{return await request(path,'POST',{authorized_by:actor,attestation:ATTESTATION});}catch(e){error=String(e);return null;}finally{busy=false;}}
 onMount(async()=>{const [p,s]=await Promise.all([get('profiles'),get('sources')]);if(p)profiles=p.profiles;if(s)sources=s.sources;storage=await get('storage');});
</script>
<section class="reports" aria-label="Research reports">
 <header><h2>Research reports</h2></header>
 <p>Descriptive aggregates over retained evidence. None of these reports qualifies, ranks or promotes a strategy.</p>
 {#if error}<p role="alert">{error}</p>{/if}
 <div class="fields"><label>Authorized by <input bind:value={actor} maxlength="200" required/></label>
  <label class="choice"><input type="checkbox" bind:checked={attest}/><span>{ATTESTATION}</span></label></div>
 <div class="actions">
  <button disabled={busy||!attest} onclick={async()=>{funnel=await post('research/selection-funnel');}}>Selection funnel</button>
  <button disabled={busy||!attest} onclick={async()=>{annual=await post('research/annual-reporting');}}>Annual reporting</button>
  <button disabled={busy||!attest} onclick={async()=>{ranking=await post('research/independent-ranking');}}>Independent ranking</button>
 </div>
 {#if funnel}<article><h3>Selection funnel</h3>
  <div class="metrics"><p><strong>{funnel.distinct_effective_cohort_candidates}</strong> distinct effective candidates</p><p><strong>{funnel.selected_for_native_audit}</strong> selected for audit</p><p><strong>{funnel.selected_and_observed}</strong> selected and observed</p><p><strong>{funnel.training_promotions}</strong> training promotions</p></div>
  <p>Funnel complete: {funnel.funnel_complete?'yes':'no'}.</p></article>{/if}
 {#if annual}<article><h3>Annual and pooled reporting</h3>
  <p>{annual.evaluations} evaluations. Pooled trades: {annual.pooled.trades}.</p>
  <ul>{#each Object.entries(annual.by_year) as [year,row]}<li>{year}: {row.trades} trades{row.win_rate?` · win rate ${row.win_rate}`:''}</li>{/each}</ul></article>{/if}
 {#if ranking}<article><h3>Independent qualified ranking</h3>
  <p>{ranking.evaluations_considered} evaluations considered. Descriptive only: {ranking.descriptive_only?'yes':'no'}.</p>
  <ul>{#each ranking.selected as entry}<li>{entry.strategy_id} · {entry.ending_equity}</li>{/each}</ul></article>{/if}
 {#if storage}<article><h3>Storage</h3>
  <p>{storage.partitions} partitions · {storage.rows} rows · {storage.bytes} bytes.</p>
  <ul>{#each Object.entries(storage.by_instrument) as [instrument,row]}<li>{instrument}: {row.partitions} partitions, {row.rows} rows</li>{/each}</ul></article>{/if}
 {#if profiles.length}<article><h3>Instrument profiles</h3>
  <ul>{#each profiles as profile}<li>{profile.instrument} · {profile.version} · synthetic: {profile.synthetic?'yes':'no'} · {profile.profile_hash.slice(0,12)}</li>{/each}</ul></article>{/if}
 {#if sources.length}<article><h3>Data sources</h3>
  <ul>{#each sources.slice(0,20) as source}<li>{source.instrument} · {source.rows} rows · {source.fidelity} · {source.dataset_hash.slice(0,12)}</li>{/each}</ul></article>{/if}
</section>
<style>
 .reports{margin:1.2rem 0;padding:1rem;background:#151e29;border:1px solid #304158;border-radius:12px;overflow-wrap:anywhere}header,.fields,.actions{display:flex;flex-wrap:wrap;gap:.8rem;align-items:center;justify-content:space-between}.choice{display:flex;align-items:flex-start;gap:.6rem;margin:.6rem 0}.choice input{width:auto;flex:none}.fields label{flex:1;min-width:180px}input{display:block;max-width:100%;box-sizing:border-box;padding:.6rem}article{margin-top:1rem}.metrics{display:flex;flex-wrap:wrap;gap:1rem}button{padding:.6rem;margin:.2rem;max-width:100%}ul{margin:.4rem 0}
</style>
