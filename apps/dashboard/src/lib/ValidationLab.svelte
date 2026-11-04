<script lang="ts">
 import {onMount} from 'svelte';
 type Request = (path:string,method?:string,body?:unknown)=>Promise<unknown>;
 type Profile = {instrument:string;synthetic:boolean;[key:string]:unknown};
 type Region = {protocol_hash:string;protocol_json:string;enabled:number};
 type Protocol = {protocol_id:string;spec_json:string;enabled:number;status:string|null;artifact_hash:string|null};
 type Holdout = {holdout_id:string;status:string;spec_json:string;[key:string]:unknown};
 type Stage = {stage_id:string;stage_name:string;state:string|null;error:string|null;training_run_id:string};
 type Summary = {completed_trades:number;win_rate:number|null;ending_balance:string;max_losing_streak:number;wilson_95:[number,number]|null};
 type WindowResult = {metrics:Summary|null;replay?:{equity:{curve:{ts:number;equity:string}[];max_mark_to_market_drawdown:string}}};
 type FoldResult = {fold:{oos_start:number;oos_end:number;partial:boolean};training_run_id:string;result:{windows:WindowResult[]}};
 type Report = {status:string;synthetic:boolean;independently_validated:boolean;eligible_for_historical_validated_board:boolean;reason?:string;folds?:FoldResult[];annual?:{year:{year:number;partial:boolean};result:{windows:WindowResult[]}}[];pooled_retrospective?:{result:{windows:WindowResult[]}};holdout?:{evaluation_id:string;metrics:Summary};neighborhood?:{neighbor_count:number;neighbors_with_trades:number;isolated_peak:boolean}};
 type Detail = {protocol:{holdout:{profile:Profile};criteria:Record<string,unknown>};stages:Stage[];training_regions:unknown[];report:Report|null;artifact_hash:string|null};
 let {request,download}:{request:Request;download:(path:string,name:string)=>Promise<void>}=$props();
 let protocols=$state<Protocol[]>([]), holdouts=$state<Holdout[]>([]), regions=$state<Region[]>([]);
 let detail=$state<Detail|null>(null), selected=$state(''), region=$state(''), busy=$state(false), error=$state(''), notice=$state('');
 let trainingStart=$state(''), finalStart=$state(''), finalEnd=$state('');
 let trials=$state(8), cpu=$state(600), seed=$state(42), purge=$state(86400), embargo=$state(0);
 let minTrades=$state(50), minFolds=$state(2), minAnnual=$state(50), wilson=$state(.5), minProfit=$state(0), maxStreak=$state(5), alpha=$state(.05), neighbors=$state(1), targets=$state(true);
 let declaration=$state(false), declarationNotes=$state('');
 let chartIndex=$state(0), confirmation=$state('none');
 const frames=['M1','M5','M15','M30','H1','H4','D1'];
 function higherFrames(){const source=regions.find(r=>r.protocol_hash===region);return source?frames.slice(frames.indexOf(params(source).timeframe)+1):[];}
 function curve(){return detail?.report?.folds?.[chartIndex]?.result.windows[0]?.replay?.equity.curve??[];}
 function curvePoints(){const data=curve();if(!data.length)return '';const values=data.map(p=>Number(p.equity)),low=Math.min(...values),high=Math.max(...values);const first=data[0].ts,last=data[data.length-1].ts;return data.map((p,i)=>`${80+(p.ts-first)/Math.max(1,last-first)*500},${150-(values[i]-low)/(high-low||1)*130}`).join(' ');}
 function params(row:{protocol_json?:string;spec_json?:string}){return JSON.parse(row.protocol_json??row.spec_json??'{}');}
 function date(ns:number){return new Date(ns/1e6).toISOString().replace('T',' ').slice(0,19)+' UTC';}
 function percent(value:number|null|undefined){return value==null?'—':(value*100).toFixed(1)+'%';}
 function ns(text:string){const value=Date.parse(text+'Z');if(!Number.isFinite(value))throw Error('Enter a valid UTC date.');return (BigInt(value)*1000000n).toString();}
 async function refresh(){
  busy=true;error='';
  try{[protocols,holdouts,regions]=await Promise.all([request('validation/protocols'),request('validation/holdouts'),request('research/protocols')]) as [Protocol[],Holdout[],Region[]];
   if(selected)detail=await request('validation/protocols/'+selected) as Detail;
  }catch(e){error=String(e);}finally{busy=false;}
 }
 async function inspect(id:string){selected=id;chartIndex=0;busy=true;error='';try{detail=await request('validation/protocols/'+id) as Detail;}catch(e){error=String(e);}finally{busy=false;}}
 async function disable(id:string){busy=true;error='';try{await request('validation/protocols/'+id+'/disable','POST');await refresh();notice='New protocol stages disabled. An active worker may finish.';}catch(e){error=String(e);}finally{busy=false;}}
 async function register(event:SubmitEvent){
  event.preventDefault();busy=true;error='';notice='';
  try{
   const source=regions.find(r=>r.protocol_hash===region);if(!source||!declaration)throw Error('Choose a research region and provide the independence declaration.');
   const p=params(source);
   // New user-entered boundaries are strings of exact UTC nanoseconds. Never
   // round-trip an existing API nanosecond Number through JSON.stringify.
   const holdout={dataset_hash:p.dataset_hash,profile:p.profile,code_revision:p.code_revision,
    window:{start_ns:ns(finalStart),end_ns:ns(finalEnd),role:'final_holdout_unseen'},
    external_use_declaration:'NO_PRIOR_USE_DECLARED',declaration_notes:declarationNotes};
   const result=await request('validation/protocols','POST',{holdout,start_ns:ns(trainingStart),family:p.family,timeframe:p.timeframe,
    confirmations:confirmation==='none'?[]:[confirmation],seed,trials_per_refit:trials,cpu_seconds_per_refit:cpu,purge_seconds:purge,embargo_seconds:embargo,
    criteria:{min_oos_closed_trades:minTrades,min_full_folds:minFolds,min_annual_closed_trades:minAnnual,min_wilson_lower:wilson,
    min_net_profit:String(minProfit),max_losing_streak:maxStreak,familywise_alpha:alpha,min_neighborhoods_with_trades:neighbors,require_research_targets:targets}}) as {protocol_id:string;paused:boolean};
   notice='Protocol registered. '+(result.paused?'Research remains paused.':'The autonomous coordinator may admit stages.');
   await refresh();await inspect(result.protocol_id);
  }catch(e){error=String(e);}finally{busy=false;}
 }
 onMount(()=>{void refresh();});
</script>
<section class="lab" aria-label="Validation laboratory">
 <header><div><h2>Validation laboratory</h2><p>Chronological refits, forward evaluation and one frozen final confirmation. Annual and pooled reports are separate simulations.</p></div><button onclick={refresh} disabled={busy}>Refresh validation</button></header>
 <p class="warning">Current protocols use synthetic software reference data. They cannot qualify for a historical validated leaderboard. Historical profile and source gates remain closed.</p>
 {#if error}<p role="alert" class="error">{error}</p>{/if}
 {#if notice}<p role="status">{notice}</p>{/if}
 {#if busy}<p role="status">Loading validation evidence…</p>{/if}
 <section><h3>Prospective protocols</h3>{#if !protocols.length}<p>No validation protocols registered.</p>{/if}
  {#each protocols as row}<article><div><strong>{params(row).holdout.profile.instrument} · {params(row).family} · {params(row).timeframe}</strong><p>{row.status??'Awaiting staged execution'} · {row.enabled?'enabled':'disabled'}</p><code>{row.protocol_id}</code></div><div class="actions"><button disabled={busy} onclick={()=>inspect(row.protocol_id)}>Inspect validation {row.protocol_id.slice(0,8)}</button>{#if row.enabled}<button disabled={busy} onclick={()=>disable(row.protocol_id)}>Stop new stages</button>{/if}</div></article>{/each}
 </section>
 {#if detail}
 <section><header><h3>Protocol evidence</h3><button disabled={busy} onclick={()=>download('validation/protocols/'+selected,'validation-'+selected+'.json')}>Download exact API evidence</button></header>
  <p><strong>{detail.report?.status??'In progress'}</strong> · {detail.protocol.holdout.profile.synthetic?'Synthetic reference':'Historical input'} · {detail.training_regions.length} training regions</p>
  {#if detail.report?.reason}<p class="error">{detail.report.reason}</p>{/if}
  {#if detail.report}<p>Historical validated board: <strong>{detail.report.eligible_for_historical_validated_board?'eligible':'ineligible'}</strong>. Independent synthetic-reference decision: {detail.report.independently_validated?'passed':'not passed'}.</p>{/if}
  {#if detail.artifact_hash}<p class="hash">Immutable report hash <code>{detail.artifact_hash}</code></p>{/if}
  <div class="scroll"><table><caption>Actual stage jobs</caption><thead><tr><th>Stage</th><th>Job state</th><th>Frozen training run</th><th>Error</th></tr></thead><tbody>{#each detail.stages as stage}<tr><td>{stage.stage_name}</td><td>{stage.state??'Not queued'}</td><td><code title={stage.training_run_id}>{stage.training_run_id.slice(0,12)}</code></td><td>{stage.error??'—'}</td></tr>{/each}</tbody></table></div>
  {#if detail.report?.folds?.length}<div class="scroll"><table><caption>Forward folds · each resets $20</caption><thead><tr><th>UTC period</th><th>Closed trades</th><th>Win rate / 95% interval</th><th>Final balance</th><th>Worst loss run</th></tr></thead><tbody>{#each detail.report.folds as fold}<tr><td>{date(fold.fold.oos_start)}<br/>{date(fold.fold.oos_end)}{fold.fold.partial?' (partial)':''}</td><td>{fold.result.windows[0]?.metrics?.completed_trades??'—'}</td><td>{percent(fold.result.windows[0]?.metrics?.win_rate)}<br/>{fold.result.windows[0]?.metrics?.wilson_95?.map(v=>percent(v)).join(' – ')??'—'}</td><td>{fold.result.windows[0]?.metrics?.ending_balance??'—'}</td><td>{fold.result.windows[0]?.metrics?.max_losing_streak??'—'}</td></tr>{/each}</tbody></table></div>{/if}
  {#if detail.report?.folds?.length}
   <label>Forward equity curve <select aria-label="Forward equity curve" bind:value={chartIndex}>{#each detail.report.folds as fold,index}<option value={index}>Forward fold {index+1}</option>{/each}</select></label>
   {#if curve().length}<svg viewBox="0 0 600 180" role="img" aria-label="Observed forward mark-to-market equity display envelope"><path d="M80 15V150H580" fill="none" stroke="#66758c"/><text x="3" y="24">${Math.max(...curve().map(p=>Number(p.equity))).toFixed(2)}</text><text x="3" y="150">${Math.min(...curve().map(p=>Number(p.equity))).toFixed(2)}</text><polyline points={curvePoints()} fill="none" stroke="#65d9bf" stroke-width="2"/></svg><p>USD · {date(curve()[0].ts)} to {date(curve()[curve().length-1].ts)}.<br/>Actual native replay valuation · {curve().length} display-envelope observations. Full-stream statistics use every quote and fill. Chart numbers are for display; downloads preserve exact API response bytes.</p>{:else}<p>No completed replay curve for this fold.</p>{/if}
  {/if}
  {#if detail.report?.annual?.length}<div class="scroll"><table><caption>Annual reset and pooled retrospective reports · not additional OOS</caption><thead><tr><th>Scenario</th><th>Closed trades</th><th>Win rate</th><th>Final balance</th></tr></thead><tbody>{#each detail.report.annual as year}<tr><td>{year.year.year}{year.year.partial?' (partial)':''} · reset $20</td><td>{year.result.windows[0]?.metrics?.completed_trades??'—'}</td><td>{percent(year.result.windows[0]?.metrics?.win_rate)}</td><td>{year.result.windows[0]?.metrics?.ending_balance??'—'}</td></tr>{/each}{#if detail.report.pooled_retrospective}<tr><td>Pooled · one $20 start</td><td>{detail.report.pooled_retrospective.result.windows[0]?.metrics?.completed_trades??'—'}</td><td>{percent(detail.report.pooled_retrospective.result.windows[0]?.metrics?.win_rate)}</td><td>{detail.report.pooled_retrospective.result.windows[0]?.metrics?.ending_balance??'—'}</td></tr>{/if}</tbody></table></div>{/if}
  {#if detail.report?.holdout}<h4>Final independent observation</h4><p>{detail.report.holdout.metrics.completed_trades} closed trades · {percent(detail.report.holdout.metrics.win_rate)} win rate · final balance {detail.report.holdout.metrics.ending_balance} USD.</p><code>{detail.report.holdout.evaluation_id}</code>{/if}
  <details><summary>Declared decision criteria</summary><dl>{#each Object.entries(detail.protocol.criteria) as [name,value]}<dt>{name.replaceAll('_',' ')}</dt><dd>{String(value)}</dd>{/each}</dl></details>
 </section>
 {/if}
 <section><h3>Protected final windows</h3><p>A consumed window stays consumed after failures and retries. Recorded managed use cannot prove that nobody inspected data outside Factory.</p>{#if !holdouts.length}<p>No protected final windows.</p>{/if}{#each holdouts as held}<article><div><strong>{JSON.parse(held.spec_json).profile.instrument} · {held.status}</strong><p class="hash"><code>{held.holdout_id}</code></p></div></article>{/each}</section>
 <section><details><summary>Register prospective validation</summary><p>Choose an existing research source. Boundaries below are UTC with millisecond input precision. The backend verifies source bounds, training influence, chronology and protected-window independence. This does not reserve data retroactively.</p>
  <form onsubmit={register}>
   <label>Validation research source <select aria-label="Validation research source" bind:value={region} onchange={()=>{confirmation='none';}} required><option value="">Select a registered source and family</option>{#each regions as row}<option value={row.protocol_hash}>{params(row).profile.instrument} · {params(row).family} · {params(row).timeframe} · {row.protocol_hash.slice(0,8)}</option>{/each}</select></label>
   <label>Higher-timeframe confirmation <select aria-label="Higher-timeframe confirmation" bind:value={confirmation}><option value="none">None</option>{#each higherFrames() as frame}<option>{frame}</option>{/each}</select></label>
   <div class="fields"><label>Development start (UTC)<input type="datetime-local" step=".001" bind:value={trainingStart} required/></label><label>Final window start (UTC)<input type="datetime-local" step=".001" bind:value={finalStart} required/></label><label>Final window end, exclusive (UTC)<input type="datetime-local" step=".001" bind:value={finalEnd} required/></label></div>
   <fieldset><legend>Compute and chronology</legend><div class="fields"><label>Trials per refit<input type="number" min="1" max="32" bind:value={trials} required/></label><label>CPU seconds per refit<input type="number" min="1" max="3600" bind:value={cpu} required/></label><label>Seed<input type="number" min="0" max="4294967295" bind:value={seed} required/></label><label>Purge seconds<input type="number" min="0" max="86400" bind:value={purge} required/></label><label>Embargo seconds<input type="number" min="0" max="86400" bind:value={embargo} required/></label></div></fieldset>
   <fieldset><legend>Required decision criteria</legend><div class="fields"><label>Minimum OOS closed trades<input type="number" min="50" max="10000" bind:value={minTrades} required/></label><label>Minimum full forward folds<input type="number" min="1" max="8" bind:value={minFolds} required/></label><label>Minimum annual closed trades<input type="number" min="50" max="10000" bind:value={minAnnual} required/></label><label>Minimum Wilson lower bound<input type="number" min="0" max="1" step=".01" bind:value={wilson} required/></label><label>Minimum net profit (USD)<input type="number" min="0" step=".01" bind:value={minProfit} required/></label><label>Maximum losing streak<input type="number" min="1" max="10000" bind:value={maxStreak} required/></label><label>Familywise alpha<input type="number" min=".001" max=".999" step=".001" bind:value={alpha} required/></label><label>Minimum neighbors with trades<input type="number" min="1" max="10" bind:value={neighbors} required/></label></div><label class="check"><input type="checkbox" bind:checked={targets}/> Require 70% win rate, $500 ending balance and at most five consecutive losses</label></fieldset>
   <label>External-use declaration notes<textarea bind:value={declarationNotes} minlength="1" required placeholder="Identify the fresh window and record any prior external use honestly."></textarea></label>
   <label class="check"><input type="checkbox" bind:checked={declaration} required/> I declare no prior use of this instrument's final window outside the managed research history.</label>
   <p>Registration enables staged work under the coordinator's existing pause and resource controls. The family and entry timeframe come from the selected source. A chosen higher confirmation must be closed and observable at the decision time.</p>
   <button type="submit" disabled={busy||!region||!declaration}>Register validation protocol</button>
  </form></details>
 </section>
</section>
<style>
 .lab{background:#151d29;border:1px solid #293447;border-radius:12px;padding:22px;margin-bottom:22px;min-width:0}.lab header{display:flex;align-items:start;justify-content:space-between;gap:16px}h2{font-size:19px;margin-top:0}h3{font-size:17px}p{line-height:1.6;color:#b6c2d2}.warning{color:#e5c37c;border-left:3px solid;padding-left:14px}.error{color:#ffa69e}section{border-top:1px solid #293447;margin-top:24px;padding-top:12px}article{display:flex;align-items:center;justify-content:space-between;gap:14px;border-bottom:1px solid #293447;padding:16px 0}.actions{display:flex;flex-wrap:wrap;gap:8px}button,input,select,textarea{font:inherit;border:1px solid #3a4b61;border-radius:7px;padding:10px;background:#1c293b;color:#e3e8f0;max-width:100%}button{cursor:pointer}button:disabled{opacity:.5}text{fill:#9eacbf;font:12px system-ui}svg{width:100%;max-height:260px;background:#10151e;border-radius:8px}code{overflow-wrap:anywhere;font-size:12px}.fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr));gap:16px}label{display:grid;gap:8px;margin:16px 0}input,select,textarea{width:100%;min-width:0}.check{display:flex;align-items:start;gap:12px}.check input{width:auto;margin-top:4px}fieldset{border:1px solid #3a4b61;margin:20px 0;padding:16px;min-width:0}legend{padding:0 8px}textarea{min-height:80px}.scroll{overflow:auto;max-width:100%;margin:20px 0}table{border-collapse:collapse;min-width:580px;width:100%;font-size:13px}th,td{padding:12px;text-align:left;border-bottom:1px solid #293447}caption{text-align:left;padding:10px 0;color:#65d9bf}dl{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px}dt{overflow-wrap:anywhere}dd{margin:0}summary{cursor:pointer}.hash{overflow-wrap:anywhere}@media(max-width:760px){.lab header,article{display:block}.actions{margin-top:12px}.lab{padding:16px}}
</style>
