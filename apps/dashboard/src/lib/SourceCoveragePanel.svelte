<script lang="ts">
 import {onMount} from 'svelte';
 type Period={observation_id:string;dataset_hash:string;start_ns:number;end_ns:number;selected:boolean;unresolved_quarantined:boolean};
 type Instrument={observed:number;selected:number;unresolved_quarantined:number;periods:Period[]};
 type Coverage={schema_version:string;instruments:Record<string,Instrument>};
 type Storage={partitions?:number;rows?:number;bytes?:number;[key:string]:unknown};
 let {request}:{request:(path:string,method?:string,body?:unknown)=>Promise<any>}=$props();
 let coverage=$state<Coverage|null>(null),storage=$state<Storage|null>(null),error=$state(''),busy=$state(false);
 const MONTH=86400*30*10**6; // ns per ~month, for a coarse gap estimate
 function months(ns:number){return new Date(ns/10**6).toISOString().slice(0,7);}
 function gaps(periods:Period[]):number{
  const sorted=[...periods].sort((a,b)=>a.start_ns-b.start_ns);
  let n=0;
  for(let i=1;i<sorted.length;i++){
   // A gap is a start later than the previous end, beyond one millisecond.
   if(sorted[i].start_ns>sorted[i-1].end_ns+1000000)n++;
  }
  return n;
 }
 async function refresh(){busy=true;error='';
  try{[coverage,storage]=await Promise.all([request('source-coverage'),request('storage')]);}
  catch(e){error=String(e);}finally{busy=false;}}
 onMount(refresh);
</script>
<section class="coverage" aria-label="Source coverage and storage">
 <header><h2>Source coverage and storage</h2><button onclick={refresh} disabled={busy}>Refresh coverage</button></header>
 <p>Observed acquired partitions per instrument. <strong>Selected</strong> counts are admission decisions, not a property of the data: an unselected period is not a defect. Nothing here authorizes historical validation.</p>
 {#if error}<p role="alert">{error}</p>{/if}
 {#if storage}<div class="metrics">
  <p><strong>{storage.partitions??'—'}</strong> catalog partitions</p>
  <p><strong>{storage.rows??'—'}</strong> canonical rows</p>
  <p><strong>{storage.bytes!=null?(Number(storage.bytes)/1073741824).toFixed(2)+' GiB':'—'}</strong> canonical bytes</p>
 </div>{/if}
 {#if coverage}<p>{Object.keys(coverage.instruments).length} instruments reported.</p>
 <table><thead><tr><th>Instrument</th><th>Observed</th><th>Selected</th><th>Quarantined</th><th>First</th><th>Last</th><th>Gaps</th></tr></thead>
 <tbody>{#each Object.entries(coverage.instruments) as [name,row](name)}
  <tr><td>{name}</td><td>{row.observed}</td><td>{row.selected}</td><td>{row.unresolved_quarantined}</td>
   <td>{row.periods.length?months(Math.min(...row.periods.map(p=>p.start_ns))):'—'}</td>
   <td>{row.periods.length?months(Math.max(...row.periods.map(p=>p.end_ns))):'—'}</td>
   <td>{gaps(row.periods)}</td></tr>
 {/each}</tbody></table>
  {#if Object.values(coverage.instruments).some(r=>r.selected>0)}<p role="alert">Some periods are selected. Selection is a reviewed admission decision and is reported, not implied by this panel.</p>
  {:else}<p>No period is selected. Coverage is reported for review; admission is a separate decision.</p>{/if}
 {/if}
</section>
<style>
 .coverage{margin:1.2rem 0;padding:1rem;background:#151e29;border:1px solid #304158;border-radius:12px;overflow-wrap:anywhere}
 header{display:flex;flex-wrap:wrap;gap:.8rem;align-items:center;justify-content:space-between}
 table{width:100%;border-collapse:collapse;margin-top:1rem;font-size:.9rem}
 th,td{text-align:left;padding:.5rem .4rem;border-bottom:1px solid #304158}
 th{color:#b5c2d3;font-weight:600}
 .metrics{display:flex;flex-wrap:wrap;gap:1rem;margin-top:.6rem}
 button{padding:.6rem;margin:.2rem;max-width:100%}
</style>
