<script lang="ts">
 import {onMount} from 'svelte';
 type Status={instrument:string;status:string;profile:string};
 type Profile={instrument:string;version:string;synthetic:boolean;profile_hash:string;tick_size:string;pip_size:string};
 let {request}:{request:(path:string,method?:string,body?:unknown)=>Promise<any>}=$props();
 let rows=$state<Status[]>([]),profiles=$state<Record<string,Profile>>({}),error=$state(''),busy=$state(false);
 async function refresh(){busy=true;error='';
  try{
   const [status,listing]=await Promise.all([request('instruments'),request('profiles')]);
   rows=status;
   profiles=Object.fromEntries(listing.profiles.map((p:Profile)=>[p.instrument,p]));
  }catch(e){error=String(e);}finally{busy=false;}}
 onMount(refresh);
</script>
<section class="status" aria-label="Instrument data and profile status">
 <header><h2>Instrument data and profile status</h2><button onclick={refresh} disabled={busy}>Refresh status</button></header>
 <p>Per-instrument admission status and declared profile version. A declared geometry is not verified broker metadata, and an unavailable status is not a defect in the data.</p>
 {#if error}<p role="alert">{error}</p>{/if}
 {#if rows.length}
 <table><thead><tr><th>Instrument</th><th>Data status</th><th>Profile spec</th><th>Profile version</th><th>Synthetic</th><th>Tick</th><th>Pip</th></tr></thead>
 <tbody>{#each rows as r}
  <tr><td>{r.instrument}</td><td>{r.status}</td><td>{r.profile}</td>
   <td>{profiles[r.instrument]?.version??'—'}</td>
   <td>{profiles[r.instrument]?(profiles[r.instrument].synthetic?'yes':'no'):'—'}</td>
   <td>{profiles[r.instrument]?.tick_size??'—'}</td>
   <td>{profiles[r.instrument]?.pip_size??'—'}</td></tr>
 {/each}</tbody></table>
  {#if rows.every(r=>r.status==='DATA_UNAVAILABLE')}<p role="alert">No instrument has verified data admission. This panel reports declared status; it does not grant admission.</p>{/if}
 {/if}
</section>
<style>
 .status{margin:1.2rem 0;padding:1rem;background:#151e29;border:1px solid #304158;border-radius:12px;overflow-wrap:anywhere}
 header{display:flex;flex-wrap:wrap;gap:.8rem;align-items:center;justify-content:space-between}
 table{width:100%;border-collapse:collapse;margin-top:1rem;font-size:.9rem}
 th,td{text-align:left;padding:.5rem .4rem;border-bottom:1px solid #304158}
 th{color:#b5c2d3;font-weight:600}
 button{padding:.6rem;margin:.2rem;max-width:100%}
</style>
