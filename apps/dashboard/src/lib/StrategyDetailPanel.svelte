<script lang="ts">
 import {onMount} from 'svelte';
 type Spec={strategy_id:string;parent_id:string|null;hypothesis:string|null;changed_fields:unknown;spec_json:string};
 type LineageRow={strategy_id:string;parent_id:string|null;hypothesis:string|null;changed_fields:unknown};
 let {request}:{request:(path:string,method?:string,body?:unknown)=>Promise<any>}=$props();
 let strategyId=$state(''),spec=$state<Spec|null>(null),lineage=$state<LineageRow[]>([]),error=$state(''),busy=$state(false);
 async function load(id:string){busy=true;error='';spec=null;lineage=[];
  try{
   spec=await request('strategies/'+id);
   lineage=await request('strategies/'+id+'/lineage');
  }catch(e){error=String(e);}finally{busy=false;}}
 function submit(event:SubmitEvent){event.preventDefault();if(strategyId.trim())load(strategyId.trim());}
 onMount(()=>{});
</script>
<section class="strategy" aria-label="Strategy detail and lineage">
 <header><h2>Strategy detail and lineage</h2></header>
 <p>A strategy spec with its recorded parent, hypothesis and changed fields. Lineage records provenance only; a child is not evidence that the parent improved.</p>
 {#if error}<p role="alert">{error}</p>{/if}
 <form onsubmit={submit}>
  <label>Strategy id <input aria-label="Strategy id" bind:value={strategyId} required maxlength="200"/></label>
  <button disabled={busy||!strategyId.trim()}>Load strategy</button>
 </form>
 {#if spec}
 <article>
  <h3>Strategy {spec.strategy_id.slice(0,12)}</h3>
  <p>Parent: {spec.parent_id?spec.parent_id.slice(0,12):'none (root strategy)'}.</p>
  <p>Hypothesis: {spec.hypothesis??'none recorded'}.</p>
  <p>Changed fields: {spec.changed_fields?JSON.stringify(spec.changed_fields):'none recorded'}.</p>
  <pre>{spec.spec_json}</pre>
 </article>
 {/if}
 {#if lineage.length}
 <article>
  <h3>Lineage · {lineage.length} record(s)</h3>
  <div class="tablewrap"><table><thead><tr><th>Strategy</th><th>Parent</th><th>Hypothesis</th></tr></thead>
   <tbody>{#each lineage as row}
    <tr><td>{row.strategy_id.slice(0,12)}</td><td>{row.parent_id?row.parent_id.slice(0,12):'—'}</td><td>{row.hypothesis??'—'}</td></tr>
   {/each}</tbody></table></div>
 </article>
 {/if}
</section>
<style>
 .strategy{margin:1.2rem 0;padding:1rem;background:#151e29;border:1px solid #304158;border-radius:12px;overflow-wrap:anywhere}
 header{display:flex;flex-wrap:wrap;gap:.8rem;align-items:center;justify-content:space-between}
 form{display:flex;flex-wrap:wrap;gap:1rem;align-items:end;margin-top:1rem}
 form label{display:grid;gap:.4rem;flex:1;min-width:220px}
 input{display:block;max-width:100%;box-sizing:border-box;padding:.6rem}
 article{margin-top:1rem}
 .tablewrap{overflow-x:auto;margin-top:.6rem}
 table{width:100%;border-collapse:collapse;font-size:.85rem}
 th,td{text-align:left;padding:.5rem .4rem;border-bottom:1px solid #304158}
 th{color:#b5c2d3;font-weight:600}
 pre{font-size:.8rem;overflow:auto;max-height:45vh}
 button{padding:.6rem;margin:.2rem;max-width:100%}
</style>
