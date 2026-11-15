"""One supervised generated regression case; NOT historical market evidence."""
import argparse
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'tests' / 'integration'))
from test_cost_label_native_audit import counterexample  # noqa: E402
from apps.coordinator.service import cycle  # noqa: E402
from factory.contracts import ExperimentContract  # noqa: E402
from factory.experiments import Store  # noqa: E402
from factory.provenance import source_identity  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.state.exists():
    raise SystemExit('Choose a new isolated state; never overwrite earlier evidence')
args.state.mkdir(parents=True)
context = source_identity()
payload, data = counterexample(args.state)
contract = ExperimentContract.model_validate(payload['contract'])
store = Store(args.state / 'factory.sqlite')
job_id = store.enqueue('research', payload, contract.experiment_hash, actor='synthetic-regression-verifier')
store.pause(False, 'synthetic-regression-verifier')
assert cycle(store, args.state)
job = store.rows('SELECT * FROM jobs WHERE job_id=?', (job_id,))[0]
assert job['state'] == 'COMPLETED', job.get('error')
experiment = store.rows('SELECT * FROM experiments WHERE experiment_hash=?', (contract.experiment_hash,))[0]
result = json.loads(experiment['result_json'])
audit = json.loads(store.rows('SELECT body_json FROM cost_label_audits')[0]['body_json'])
assert result['cost_horizon_labels']['rejection_suggested']
assert not result['cost_horizon_labels']['pruning_authorized']
assert audit['observed_false_negative'] and not result['integrity_errors']
assert result['trades'] and D(result['equity']['ending_marked_equity']) > 20
assert any(t['exit_reason'] == 'TAKE_PROFIT' for t in result['trades'])
store.pause(True, 'synthetic-regression-verifier')
report = {
    'status':'PASS_SUPERVISED_NATIVE_SHADOW_COUNTEREXAMPLE',
    'scope':'one generated 400-quote Native regression, NOT historical market evaluation or throughput benchmark',
    'source_context':context,'source_context_unchanged':source_identity()==context,
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'synthetic':True,'source_quotes':len(data),'experiment_hash':contract.experiment_hash,
    'native_artifact_sha256':experiment['artifact_hash'],
    'signals':result['cost_horizon_labels']['signal_count'],
    'feature_labels':result['cost_horizon_labels']['label_count'],
    'mean_net_feature_label_pips':result['cost_horizon_labels']['mean_net_label_pips'],
    'native_closed_trades':len(result['trades']),
    'native_exit_reasons':[t['exit_reason'] for t in result['trades']],
    'native_ending_marked_equity':result['equity']['ending_marked_equity'],
    'native_reference_status':result['reconciliation']['native_reference_status'],
    'prospective_rejection_disagreement':audit['observed_false_negative'],
    'approximate_pruning_enabled':False,'job_state':job['state'],
    'measured_worker_resources':json.loads(job['result'])['resources'],
    'SOFTWARE_VERIFIED':False,'DATA_READY':False,'OPERATION_READY':False,
}
assert report['source_context_unchanged']
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
