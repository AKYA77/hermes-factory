"""GENERATED exact feature-only comparison; no native throughput/P&L claim."""

import argparse
from decimal import Decimal
import json
from pathlib import Path
import resource
import time

from factory.contracts import Signal, StrategySpec
from factory.data import Catalog, Quote
from factory.features.disk import BarCache
from factory.features.indicators import IndicatorCache
from factory.operations.feature_cache_probe import digest
from factory.provenance import execution_revision, source_identity
from factory.strategies import iter_bar_signals

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.state.exists() and any(args.state.iterdir()):
    parser.error('use an empty dedicated directory')
args.state.mkdir(parents=True, exist_ok=True)
cat = Catalog(args.state/'catalog')
manifest = cat.commit((Quote('EURUSD',1735689600*10**9+i*30*10**9,110000+(i*37%113)*10,110012+(i*37%113)*10,100000,'synthetic','indicator-benchmark',i) for i in range(20000)), b'GENERATED indicator benchmark', {'synthetic':True,'source':'deterministic generated benchmark','license':'test only'})
dataset = manifest['dataset_hash']
context, revision = source_identity(), execution_revision()
bars,cache = BarCache(args.state/'bars'), IndicatorCache(args.state/'indicators')
with bars.events(cat,dataset,'profile',revision,('M1',)) as events:
    sum(1 for _ in events)
results=[]
for operator in ('momentum','mean_reversion','trend'):
    for lookback in (8,64):
        row={'operator':operator,'lookback':lookback,'results':{}}
        for mode in ('bar_only','indicator_build','indicator_reuse'):
            wall,cpu=time.perf_counter(),time.process_time()
            hashes=[]
            for threshold in ('.5','1','2'):
                spec=StrategySpec(instrument='EURUSD',timeframe='M1',stop_ticks=100,signal=Signal(version='2',operator=operator,lookback=lookback,threshold=Decimal(threshold)))
                if mode=='bar_only':
                    with bars.events(cat,dataset,'profile',revision,('M1',)) as events:
                        hashes.append(digest(iter_bar_signals(events,spec)))
                else:
                    with cache.events(cat,dataset,'profile',revision,spec,bars) as (events,lookup):
                        hashes.append(digest(iter_bar_signals(events,spec,transform_lookup=lookup)))
            row['results'][mode]={'wall_seconds':time.perf_counter()-wall,'cpu_seconds':time.process_time()-cpu,'signal_digests':hashes,'indicator_stats_cumulative':dict(cache.stats)}
        row['exact_parity']=all(r['signal_digests']==row['results']['bar_only']['signal_digests'] for r in row['results'].values())
        assert row['exact_parity']
        results.append(row)
report={'fixture':'GENERATED, not market data','rows':20000,'source':context,'source_unchanged':context==source_identity(),'operation':'three threshold variants per mode, feature-only; existing bar cache prewarmed; no cold OS page-cache or native throughput claim','results':results,'cache_bytes':sum(p.stat().st_size for p in cache.root.rglob('*') if p.is_file()),'cumulative_process_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
assert report['source_unchanged']
args.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'parity':all(r['exact_parity'] for r in results),'results':[{'operator':r['operator'],'lookback':r['lookback'],**{k:round(v['wall_seconds'],4) for k,v in r['results'].items()}} for r in results]},indent=2))
