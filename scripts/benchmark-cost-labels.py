"""Generated multi-quarter feature-only cost-label benchmark; no tick backtests."""
import argparse
from decimal import Decimal as D
import json
from pathlib import Path
import resource
import time

from factory.contracts import ExperimentContract, Signal, StrategySpec, Window, fingerprint
from factory.features import Bar
from factory.instruments import synthetic_profile
from factory.provenance import execution_revision, source_identity
from factory.screening import screen
from factory.screening.labels import CostHorizonPolicy, estimate_labels
from factory.strategies import iter_bar_signals

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bars', type=int, default=200000)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if not 1000 <= args.bars <= 1000000:
    parser.error('bounded synthetic bar count is 1,000..1,000,000')
context = source_identity()
start = 1735689600 * 10**9
profile = synthetic_profile('EURUSD')
results = []

def events():
    for index in range(args.bars):
        phase = index % 800
        ticks = phase if phase <= 400 else 800 - phase
        close = D(110000 + ticks) / 100000
        end = start + (index + 1) * 60 * 10**9
        yield {'M1': Bar(end, end + 1, close, close, close)}

for operator in ('momentum', 'mean_reversion', 'breakout'):
    spec = StrategySpec(instrument='EURUSD', timeframe='M1',
                        signal=Signal(operator=operator, lookback=16, threshold='1'), stop_ticks=60)
    contract = ExperimentContract(strategy_hash=spec.strategy_hash,
        dataset_hash=fingerprint({'generator':'synthetic-triangle-bars/v1','bars':args.bars}),
        instrument_hash=fingerprint(profile), code_revision=execution_revision(),
        engine_version='NO_NATIVE_ENGINE_FEATURE_ONLY_BENCHMARK',
        fill_version='NO_FILLS_FEATURE_LABELS_ONLY', evaluation_policy='synthetic-training/v1',
        windows=(Window(start_ns=start, end_ns=start+(args.bars+1)*60*10**9, role='train_only'),),
        scenario='historical-pessimistic/v1', seed=0)
    wall, cpu = time.perf_counter(), time.process_time()
    baseline = screen(iter_bar_signals(events(), spec), contract)
    baseline_metrics = {'wall_seconds':time.perf_counter()-wall,'cpu_seconds':time.process_time()-cpu}
    wall, cpu = time.perf_counter(), time.process_time()
    labels = estimate_labels(events(), spec, profile, contract, CostHorizonPolicy())
    measured = {'wall_seconds':time.perf_counter()-wall,'cpu_seconds':time.process_time()-cpu}
    assert (baseline.signal_count,baseline.signal_sha256)==(labels['signal_count'],labels['signal_sha256'])
    assert labels['max_pending_labels'] <= 5 and labels['pruning_authorized'] is False
    results.append({'operator':operator,'entry_bars':args.bars,'signals':labels['signal_count'],
                    'feature_labels':labels['label_count'],'max_pending_labels':labels['max_pending_labels'],
                    'signal_sha256':labels['signal_sha256'],'label_sha256':labels['label_sha256'],
                    'legacy_exact_screen':baseline_metrics,'cost_labels':measured,
                    'wall_ratio_cost_to_legacy':measured['wall_seconds']/baseline_metrics['wall_seconds']})
report={'status':'PASS_FEATURE_LABEL_SIGNAL_PARITY','scope':'generated multi-quarter feature-only benchmark; NOT native strategy/tick throughput, market validation, compiled screening acceptance or Contabo verification',
        'source_context':context,'source_context_unchanged':source_identity()==context,
        'results':results,'process_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        'cgroup_cpu_max':Path('/sys/fs/cgroup/cpu.max').read_text().strip(),
        'cgroup_memory_max':Path('/sys/fs/cgroup/memory.max').read_text().strip(),
        'approximate_pruning_enabled':False,'native_replays':0}
assert report['source_context_unchanged']
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':report['status'],'bars_per_operator':args.bars,'native_replays':0,'process_peak_rss_bytes':report['process_peak_rss_bytes']}))
