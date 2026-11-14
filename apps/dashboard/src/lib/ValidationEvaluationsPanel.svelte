<script lang="ts">
 import {onMount} from 'svelte';
 type EvalRow={evaluation_id:string;artifact_hash:string|null;holdout_id:string|null;created_at:number;contract:Record<string,unknown>};
 type EvalDetail={evaluation_id:string;artifact_hash:string|null;holdout_id:string|null;created_at:number;contract:Record<string,unknown>;result:Record<string,unknown>};
 let {request}:{request:(path:string,method?:string,body?:unknown)=>Promise<any>}=$props();
 let rows=$state<EvalRow[]>([]),detail=$state<EvalDetail|null>(null),error=$state(''),busy=$state(false);
 async function refresh(){busy=true;error='';detail=null;
  try{rows=await request('validation/evaluations?limit=100&offset=0');}
  catch(e){error=String(e);}finally{busy=false;}}
 async function inspect(id:string){busy=true;error='';
  try{detail=await request('validation/evaluations/'+id);}
  catch(e){error=String(e);}finally{busy=false;}}
 onMount(refresh);
</script>
<section class="evals" aria-label="Validation evaluations">
 <header><h2>Validation evaluations</h2><button onclick={refresh} disabled={busy}>Refresh evaluations</button></header>
 <p>Retained independent evaluation records with their holdout identity and result. An evaluation record is evidence about the sampled period; it is not a qualification of the strategy.</p>
 {#if error}<p role="alert">{error}</p>{/if}
 {#if detail}
  <article>
   <h3>Evaluation {detail.evaluation_id.slice(0,12)}</h3>
   <p>Holdout: {detail.holdout_id??'none recorded'}. Artifact: {detail.artifact_hash??'none recorded'}.</p>
   <pre>{JSON.stringify(detail.result,null,2)}</pre>
  </article>
 {/if}
 {#if rows.length}
 <div class="tablewrap"><table><thead><tr><th>Evaluation</th><th>Holdout</th><th>Artifact</th><th></th></tr></thead>
  <tbody>{#each rows as r}
   <tr><td>{r.evaluation_id.slice(0,12)}</td><td>{r.holdout_id?r.holdout_id.slice(0,12):'—'}</td><td>{r.artifact_hash?r.artifact_hash.slice(0,12):'—'}</td>
    <td><button onclick={()=>inspect(r.evaluation_id)} disabled={busy}>Inspect</button></td></tr>
  {/each}</tbody></table></div>
 {:else}<p>No evaluation records are retained. An empty list is a valid result, not a missing feature.</p>{/if}
</section>
<style>
 .evals{margin:1.2rem 0;padding:1rem;background:#151e29;border:1px solid #304158;border-radius:12px;overflow-wrap:anywhere}
 header{display:flex;flex-wrap:wrap;gap:.8rem;align-items:center;justify-content:space-between}
 .tablewrap{overflow-x:auto;margin-top:1rem}
 table{width:100%;border-collapse:collapse;font-size:.9rem}
 th,td{text-align:left;padding:.5rem .4rem;border-bottom:1px solid #304158}
 th{color:#b5c2d3;font-weight:600}
 pre{font-size:.8rem;overflow:auto;max-height:50vh}
 article{margin-top:1rem}
 button{padding:.6rem;margin:.2rem;max-width:100%}
</style>
