<script lang="ts">
 import {onMount} from 'svelte';
 type Row={review_id:string;kind:string;reviewer:string;start_ns:string;end_ns:string;revoked_dependencies:string[];reference_count:number;assumption_fields:string[];status:string};
 let {request,download}:{request:(path:string,method?:string,body?:unknown)=>Promise<unknown>;download:(path:string,name:string)=>Promise<void>}=$props();
 let rows=$state<Row[]>([]),offset=$state(0),busy=$state(false),error=$state('');
 async function load(next=offset){busy=true;error='';try{rows=await request('input-reviews?limit=25&offset='+next) as Row[];offset=next;}catch(e){error=String(e);}finally{busy=false;}}
 onMount(()=>{void load();});
</script>
<section aria-label="Reviewed research inputs">
 <header><h2>Reviewed research inputs</h2><button disabled={busy} onclick={()=>load()}>Refresh input reviews</button></header>
 <p>Captured references, declared research assumptions and dated source acceptance are separate from a structural QA pass. Reviewers attest reference meaning; execution rechecks exact bytes, scope and revocations. A review never validates a strategy.</p>
 {#if error}<p class="error" role="alert">{error}</p>{/if}
 {#if busy}<p role="status">Checking review registry…</p>{/if}
 {#if !rows.length}<p>No recorded input reviews on this page. Unknown specifications remain blocked. Register reviews through the documented trusted local operator workflow.</p>{/if}
 {#each rows as row}<article>
 <h3>{row.kind} · {row.status==='REVOKED'?'Revoked':'Recorded; execution recheck required'}</h3>
 <p>Reviewer: {row.reviewer}<br/>UTC nanosecond scope: <code>{row.start_ns}</code> through <code>{row.end_ns}</code> (exclusive)</p>
 <p>{row.reference_count} captured reference documents{#if row.assumption_fields.length} · Research assumptions: {row.assumption_fields.join(', ')}{/if}</p>
 <code>{row.review_id}</code>
 {#if row.revoked_dependencies.length}<p class="error">This review or a required reference was revoked. Execution is blocked; previous evidence remains preserved.</p>{:else}<p><button disabled={busy} onclick={()=>download('input-reviews/'+row.review_id,'input-review-'+row.review_id+'.json')}>Verify and export review {row.review_id.slice(0,8)}</button></p>{/if}
 </article>{/each}
 <nav aria-label="Input review pagination"><button disabled={busy||offset===0} onclick={()=>load(Math.max(0,offset-25))}>Previous reviews</button><span>Records {offset+1}–{offset+rows.length}</span><button disabled={busy||rows.length<25} onclick={()=>load(offset+25)}>Next reviews</button></nav>
</section>
<style>
 section{padding:22px;background:#151d29;border:1px solid #293447;border-radius:12px;margin-bottom:22px;min-width:0}header,nav{display:flex;gap:14px;align-items:center;justify-content:space-between;flex-wrap:wrap}article{border-top:1px solid #293447;padding:16px 0}h2{font-size:19px}h3{font-size:16px}p{line-height:1.6;color:#b6c2d2}.error{color:#ffa69e}code{font-size:12px;overflow-wrap:anywhere}button{font:inherit;border:1px solid #3a4b61;border-radius:7px;padding:10px;background:#1c293b;color:#e3e8f0;cursor:pointer;max-width:100%}button:disabled{opacity:.5}@media(max-width:760px){section{padding:16px}}
</style>
