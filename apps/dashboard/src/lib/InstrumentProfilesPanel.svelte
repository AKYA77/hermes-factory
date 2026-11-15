<script lang="ts">
 import {onMount} from 'svelte';
 type Profile={instrument:string;version:string;synthetic:boolean;source:string;tick_size:string;pip_size:string;price_scale:number;base_currency:string;quote_currency:string;contract_multiplier:string;volume_step:string;min_volume:string;max_volume:string;margin_rate:string;min_stop_ticks:number;profile_hash:string};
 type Listing={profiles:Profile[]};
 type Integrity={model_version:string;profiles:number;synthetic:number;non_synthetic:number;hashes:Record<string,string>};
 let {request}:{request:(path:string,method?:string,body?:unknown)=>Promise<any>}=$props();
 let profiles=$state<Profile[]>([]),integrity=$state<Integrity|null>(null),error=$state(''),busy=$state(false);
 async function refresh(){busy=true;error='';
  try{const [listing,check]=await Promise.all([request('profiles'),request('profile-integrity')]);
   profiles=listing.profiles;integrity=check;}
  catch(e){error=String(e);}finally{busy=false;}}
 onMount(refresh);
 // Declared geometry is fetched per instrument rather than inferred from the listing,
 // so what the operator sees is exactly what the backend declares.
 let detailFor=$state('');
 let detail=$state<Profile|null>(null);
 async function showDetail(instrument:string){detailFor=instrument;detail=null;
  try{detail=await request(`profiles/${instrument}`);}catch(e){error=String(e);}}
</script>
<section class="profiles" aria-label="Instrument profiles">
 <header><h2>Instrument profiles</h2><button onclick={refresh} disabled={busy}>Refresh profiles</button></header>
 <p>Declared instrument geometry only. <strong>Synthetic profiles are fixtures, not broker metadata</strong>, and Gold units in particular remain unverified. Nothing here admits a profile for live use.</p>
 {#if error}<p role="alert">{error}</p>{/if}
 {#if integrity}
  <div class="metrics">
   <p><strong>{integrity.profiles}</strong> profiles</p>
   <p><strong>{integrity.synthetic}</strong> synthetic</p>
   <p><strong>{integrity.non_synthetic}</strong> verified non-synthetic</p>
  </div>
  {#if integrity.non_synthetic===0}
   <p role="alert">No profile is verified against broker metadata. Every declared unit below is a synthetic fixture convention.</p>
  {/if}
 {/if}
 {#if profiles.length}
 <table><thead><tr><th>Instrument</th><th>Kind</th><th>Tick</th><th>Pip</th><th>Base</th><th>Quote</th><th>Multiplier</th><th>Min stop</th></tr></thead>
 <tbody>{#each profiles as p}
  <tr><td>{p.instrument}</td>
   <td>{p.synthetic?'synthetic':'verified'}</td>
   <td>{p.tick_size}</td><td>{p.pip_size}</td>
   <td>{p.base_currency}</td><td>{p.quote_currency}</td>
   <td>{p.contract_multiplier}</td><td>{p.min_stop_ticks}</td></tr>
 {/each}</tbody></table>
 <p>Full declared geometry is fetched per instrument from its own profile endpoint; the tables above are only the summary.</p>
 <table><thead><tr><th>Instrument</th><th>Profile hash</th><th aria-label="declared geometry">Declared geometry</th></tr></thead>
 <tbody>{#each profiles as p}
  <tr><td>{p.instrument}</td><td><small>{p.profile_hash}</small></td>
   <td>{#if detailFor===p.instrument && detail}<small>{JSON.stringify(detail)}</small>{:else if detailFor===p.instrument}<small>loading…</small>{:else}<button onclick={()=>showDetail(p.instrument)}>Show declared geometry</button>{/if}</td></tr>
 {/each}</tbody></table>
 {/if}
</section>
<style>
 .profiles{margin:1.2rem 0;padding:1rem;background:#151e29;border:1px solid #304158;border-radius:12px;overflow-wrap:anywhere}
 header{display:flex;flex-wrap:wrap;gap:.8rem;align-items:center;justify-content:space-between}
 table{width:100%;border-collapse:collapse;margin-top:1rem;font-size:.9rem}
 th,td{text-align:left;padding:.5rem .4rem;border-bottom:1px solid #304158}
 th{color:#b5c2d3;font-weight:600}
 small{color:#b5c2d3;overflow-wrap:anywhere}
 .metrics{display:flex;flex-wrap:wrap;gap:1rem;margin-top:.6rem}
 button{padding:.6rem;margin:.2rem;max-width:100%}
</style>
