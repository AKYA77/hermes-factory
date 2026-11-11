<script lang="ts">
 import {onMount} from 'svelte';
 type Provenance={provider:string;source:string;license:string;synthetic:boolean;parser_version:string;source_timezone:string;limitations:string[];[key:string]:unknown};
 type Source={dataset_hash:string;instrument:string;rows:number;first_ns:number;latest_verified_ns:number;fidelity:string;provenance:Provenance;[key:string]:unknown};
 let {request}:{request:(path:string,method?:string,body?:unknown)=>Promise<any>}=$props();
 let sources=$state<Source[]>([]),error=$state(''),busy=$state(false);
 const fmt=(ns:number)=>new Date(ns/10**6).toISOString().slice(0,10);
 // Classify from the declared provenance, not from the synthetic flag alone.
 // A rehearsal dataset carries real ticks but is a test artifact, so bucketing
 // it as provider-sourced would misdescribe it.
 function kind(s:Source):string{
  const p=s.provenance;
  if(p.synthetic)return 'synthetic';
  const source=String(p.source??'');
  if(/TEST ONLY/i.test(source))return 'test fixture';
  if(!p.provider)return 'unattributed';
  return 'provider';
 }
 function counts(){const c:Record<string,number>={};for(const s of sources){const k=kind(s);c[k]=(c[k]??0)+1;}return c;}
 async function refresh(){busy=true;error='';
  try{sources=(await request('sources')).sources;}
  catch(e){error=String(e);}finally{busy=false;}}
 onMount(refresh);
</script>
<section class="sources" aria-label="Source registry">
 <header><h2>Source registry</h2><button onclick={refresh} disabled={busy}>Refresh sources</button></header>
 <p>Every acquired dataset with its declared provenance. Provider quotes are not brokerage fills, and the provider's fourth volume column is not used. Synthetic datasets are labelled.</p>
 {#if error}<p role="alert">{error}</p>{/if}
 {#if sources.length}
 <div class="metrics">
  <p><strong>{sources.length}</strong> datasets</p>
  {#each Object.entries(counts()) as [k,n]}<p><strong>{n}</strong> {k}</p>{/each}
  <p><strong>{new Set(sources.map(s=>s.provenance.provider).filter(Boolean)).size}</strong> providers</p>
 </div>
 <table><thead><tr><th>Instrument</th><th>Kind</th><th>Rows</th><th>First</th><th>Last</th><th>Fidelity</th><th>Provider</th><th>Parser</th></tr></thead>
 <tbody>{#each sources as s}
  <tr><td>{s.instrument}</td><td>{kind(s)}</td><td>{s.rows.toLocaleString()}</td>
   <td>{fmt(s.first_ns)}</td><td>{fmt(s.latest_verified_ns)}</td>
   <td>{s.fidelity}</td><td>{s.provenance.provider}</td><td>{s.provenance.parser_version}</td></tr>
 {/each}</tbody></table>
 <details>
  <summary>Declared limitations and licence</summary>
  {#each sources as s}
   <article>
    <h3>{s.instrument} · {s.dataset_hash.slice(0,12)}</h3>
    <p>Licence: {s.provenance.license}</p>
    <p>Source timezone: {s.provenance.source_timezone}</p>
    <ul>{#each s.provenance.limitations as l}<li>{l}</li>{/each}</ul>
   </article>
  {/each}
 </details>
 {/if}
</section>
<style>
 .sources{margin:1.2rem 0;padding:1rem;background:#151e29;border:1px solid #304158;border-radius:12px;overflow-wrap:anywhere}
 header{display:flex;flex-wrap:wrap;gap:.8rem;align-items:center;justify-content:space-between}
 table{width:100%;border-collapse:collapse;margin-top:1rem;font-size:.9rem}
 th,td{text-align:left;padding:.5rem .4rem;border-bottom:1px solid #304158}
 th{color:#b5c2d3;font-weight:600}
 .metrics{display:flex;flex-wrap:wrap;gap:1rem;margin-top:.6rem}
 article{margin-top:1rem}
 button{padding:.6rem;margin:.2rem;max-width:100%}
</style>
