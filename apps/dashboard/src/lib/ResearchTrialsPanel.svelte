<script lang="ts">
 import {onMount} from 'svelte';
 type Trial={trial_id:string;created_at:number;outcome:string|null;objective:number|null;run_id:string|null;cpu_seconds:number|null;reason:string|null;[key:string]:unknown};
 let {request}:{request:(path:string,method?:string,body?:unknown)=>Promise<any>}=$props();
 let rows=$state<Trial[]>([]),error=$state(''),busy=$state(false);
 async function refresh(){busy=true;error='';
  try{rows=await request('research/trials?limit=200&offset=0');}
  catch(e){error=String(e);}finally{busy=false;}}
 onMount(refresh);
</script>
<section class="trials" aria-label="Research trials">
 <header><h2>Research trials</h2><button onclick={refresh} disabled={busy}>Refresh trials</button></header>
 <p>Every retained hypothesis with its outcome and measured cost. An outcome is a reported observation, not a qualified result, and a rejected trial is evidence rather than a failure.</p>
 {#if error}<p role="alert">{error}</p>{/if}
 {#if rows.length}
 <div class="metrics">
  <p><strong>{rows.length}</strong> trials</p>
  <p><strong>{rows.filter(r=>r.outcome==='PRUNED').length}</strong> pruned</p>
  <p><strong>{rows.filter(r=>r.run_id).length}</strong> with a native run</p>
  <p><strong>{rows.reduce((n,r)=>n+(r.cpu_seconds||0),0).toFixed(1)}</strong> measured CPU seconds</p>
 </div>
 <div class="tablewrap"><table><thead><tr><th>Trial</th><th>Outcome</th><th>Objective</th><th>CPU s</th><th>Reason</th></tr></thead>
  <tbody>{#each rows as r}
   <tr><td>{r.trial_id.slice(0,12)}</td><td>{r.outcome??'—'}</td><td>{r.objective??'—'}</td><td>{r.cpu_seconds??'—'}</td><td>{r.reason??'—'}</td></tr>
  {/each}</tbody></table></div>
 {:else}<p>No trials are retained. An empty list is a valid result, not a missing feature.</p>{/if}
</section>
<style>
 .trials{margin:1.2rem 0;padding:1rem;background:#151e29;border:1px solid #304158;border-radius:12px;overflow-wrap:anywhere}
 header{display:flex;flex-wrap:wrap;gap:.8rem;align-items:center;justify-content:space-between}
 .tablewrap{overflow-x:auto;margin-top:1rem}
 table{width:100%;border-collapse:collapse;font-size:.9rem}
 th,td{text-align:left;padding:.5rem .4rem;border-bottom:1px solid #304158}
 th{color:#b5c2d3;font-weight:600}
 .metrics{display:flex;flex-wrap:wrap;gap:1rem;margin-top:.6rem}
 button{padding:.6rem;margin:.2rem;max-width:100%}
</style>
