<script lang="ts">
 import {onMount} from 'svelte';
 type Policy={policy_id:string;policy_json:string;enabled:number;reason:string|null};
 type Region={region_id:string;protocol_json:string;state:string;reason:string|null};
 type Status={current_source_revision:string;counts:{state:string;count:number}[];policies:Policy[];regions:Region[];source_rejections:{body_json:string}[]};
 let {request,download}:{request:(path:string,method?:string,body?:unknown)=>Promise<any>;download:(path:string,name:string)=>Promise<void>}=$props();
 let snapshot=$state<Status|null>(null),error=$state(''),busy=$state(false);
 let profiles=$state<Record<string,unknown>[]>([]),start=$state(''),end=$state(''),actor=$state(''),attest=$state(false);
 let maxRegions=$state(256),active=$state(8),trials=$state(16),regionCpu=$state(120),totalCpu=$state(3600);
 const frames=['M1','M5','M15','M30','H1','H4','D1'];
 let timeframes=$state([...frames]),confirmations=$state(true);
 async function refresh(){try{snapshot=await request('research/discovery');error='';}catch(e){error=String(e);}}
 onMount(refresh);
 async function files(event:Event){
  try{
   const selected=Array.from((event.currentTarget as HTMLInputElement).files??[]);
   if(selected.length<1||selected.length>8)throw Error('Choose one to eight profile files.');
   const values=[];
   for(const file of selected){if(file.size>16384)throw Error('Profile file exceeds 16 KiB.');values.push(JSON.parse(await file.text()));}
   profiles=values;error='';
  }catch(e){profiles=[];error=String(e);}
 }
 function ns(value:string){const milliseconds=Date.parse(value+'Z');if(!Number.isFinite(milliseconds))throw Error('Enter valid UTC bounds.');return (BigInt(milliseconds)*1000000n).toString();}
 async function register(event:SubmitEvent){
  event.preventDefault();if(!snapshot)return;busy=true;error='';
  try{
   await request('research/discovery','POST',{
    profiles,training_windows:[{start_ns:ns(start),end_ns:ns(end),role:'train_only'}],
    timeframes,higher_confirmations:confirmations,code_revision:snapshot.current_source_revision,
    seed:42,max_regions:maxRegions,max_active_regions:active,trials_per_region:trials,
    cpu_seconds_per_region:regionCpu,total_cpu_seconds:totalCpu,authorized_by:actor,
    attestation:attest?'I authorize training-only discovery within these bounds, never evaluation or holdout reuse':'',
   });
   await refresh();
  }catch(e){error=String(e);}finally{busy=false;}
 }
 async function disable(id:string){busy=true;try{await request('research/discovery/'+id+'/disable','POST',{});await refresh();}catch(e){error=String(e);}finally{busy=false;}}
 function spec(row:Region){return JSON.parse(row.protocol_json);}
</script>

<section class="discovery" aria-label="Automatic research discovery">
 <header><h2>Automatic research discovery</h2><button disabled={busy} onclick={refresh}>Refresh discovery</button></header>
 <p>Authorize a bounded training scope once. New eligible datasets can then generate research regions without manual registration of each region. Historical inputs still require reviewed admission; evaluation and holdout periods stay protected.</p>
 {#if error}<p class="error" role="alert">{error}</p>{/if}
 {#if snapshot}
  <div class="counts">{#each snapshot.counts as item}<p><strong>{item.count}</strong> {item.state.toLowerCase()}</p>{/each}{#if snapshot.counts.length===0}<p>No discovery regions yet.</p>{/if}</div>
  <form onsubmit={register}>
   <h3>Authorize automatic training research</h3>
   <label>Instrument profile files <input type="file" accept=".json,application/json" multiple onchange={files} required/></label>
   {#each profiles as profile}<p>{String(profile.instrument??'Unknown instrument')} · {profile.synthetic?'Generated profile':'Historical research profile'} · {String(profile.source??'No reference declared')}</p>{/each}
   <div class="fields"><label>Training starts (UTC) <input type="datetime-local" step="1" bind:value={start} required/></label><label>Training ends (UTC) <input type="datetime-local" step="1" bind:value={end} required/></label><label>Authorized by <input bind:value={actor} required maxlength="256"/></label></div>
   <fieldset><legend>Entry timeframes</legend>{#each frames as tf}<label class="choice"><input type="checkbox" bind:group={timeframes} value={tf}/>{tf}</label>{/each}</fieldset>
   <label class="choice"><input type="checkbox" bind:checked={confirmations}/>Explore strictly closed higher-timeframe confirmations</label>
   <p>Includes all nine family categories. The initial session hypothesis uses 08:00–16:00 UTC as an explicit research choice.</p>
   <div class="fields"><label>Region limit <input type="number" min="1" max="4096" bind:value={maxRegions} required/></label><label>Active regions <input type="number" min="1" max="64" bind:value={active} required/></label><label>Trials per region <input type="number" min="1" max="256" bind:value={trials} required/></label><label>CPU seconds per region <input type="number" min="1" max="86400" bind:value={regionCpu} required/></label><label>Total measured CPU admission budget <input type="number" min="1" max="2592000" bind:value={totalCpu} required/></label></div>
   <p>Budgets stop new admission after measured use; an in-flight bounded worker may finish. Registration preserves the current research pause state.</p>
   <label class="choice"><input type="checkbox" bind:checked={attest} required/>I authorize only this training scope, never evaluation or holdout reuse.</label>
   <button type="submit" disabled={busy||!profiles.length||!timeframes.length||!attest}>Authorize discovery</button>
  </form>
  <h3>Authorizations</h3>
  {#if snapshot.policies.length===0}<p>No automatic discovery authorizations registered.</p>{/if}
  {#each snapshot.policies as policy}<article><p><strong>{policy.enabled?'Enabled':'Stopped'}</strong> · {JSON.parse(policy.policy_json).profiles.map((p:{instrument:string})=>p.instrument).join(', ')} · {JSON.parse(policy.policy_json).max_regions} regions maximum</p>{#if policy.reason}<p>{policy.reason}</p>{/if}{#if policy.enabled}<button disabled={busy} onclick={()=>disable(policy.policy_id)}>Stop discovery</button>{/if}</article>{/each}
  <p>Stopping discovery stops new regions and proposals. Existing queued jobs can be cancelled in Queue.</p>
  <h3>Discovered regions</h3>
  {#if snapshot.regions.length===0}<p>No regions admitted. Resume research to permit the scheduler to expand eligible training inputs.</p>{/if}
  {#each snapshot.regions as region}<article><p>{spec(region).profile.instrument} · {spec(region).family} · {spec(region).timeframe} · <strong>{region.state}</strong></p>{#if region.reason}<p>{region.reason}</p>{/if}</article>{/each}
  {#if snapshot.source_rejections.length}<h3>Sources requiring attention</h3>{#each snapshot.source_rejections as item}<p>{JSON.parse(item.body_json).reason}</p>{/each}{/if}
  <button onclick={()=>download('research/discovery','hermes-discovery.json')}>Export discovery evidence</button>
 {/if}
</section>

<style>
 .discovery{background:#151d29;border:1px solid #293447;border-radius:12px;padding:22px;margin-bottom:22px;overflow-wrap:anywhere}header,.fields,.counts{display:flex;flex-wrap:wrap;gap:16px;align-items:center}header{justify-content:space-between}h2{font-size:18px}h3{font-size:16px}label{display:grid;gap:8px;margin:12px 0}input{min-width:0;max-width:100%}.fields input{width:180px}.choice{display:inline-flex;align-items:center;gap:8px;margin-right:15px}fieldset{border:1px solid #3a4b61;border-radius:7px;margin:16px 0}article{border-top:1px solid #293447;padding:10px 0}.counts strong{font-size:23px;color:#65d9bf}form{border:1px solid #3a4b61;padding:16px;border-radius:8px}.error{color:#ffa69e}button,input{font:inherit;border:1px solid #3a4b61;border-radius:7px;padding:10px;background:#1c293b;color:#e3e8f0}button{cursor:pointer}button:disabled{opacity:.5}p{line-height:1.5}@media(max-width:760px){.discovery{padding:16px}.fields,label{width:100%}.fields input{width:100%}.choice{width:auto}header{align-items:start}}
</style>
