"""Fresh generated state with an actual native audit of an injected broken screen."""

import argparse
from pathlib import Path
import subprocess
import sys

from apps.coordinator import worker
from factory.contracts import ExperimentContract
from factory.operations.fixtures import seed
from factory.screening import SCREEN_POLICY, screen, selected_for_audit

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state',type=Path,required=True)
args=parser.parse_args()
if args.state.exists() and any(args.state.iterdir()):
    parser.error('use a fresh isolated state')
payload=seed(args.state,240)
original=ExperimentContract.model_validate(payload['contract'])
for value in range(1024):
    contract=original.model_copy(update={'seed':value})
    if selected_for_audit(contract):break
else:raise AssertionError('no deterministic audit fixture')
payload['contract']=contract.model_dump(mode='json');payload['screening']=SCREEN_POLICY
saved=worker.screen
try:
    worker.screen=lambda signals,contract:screen([],contract)
    try:worker.run(payload,args.state)
    except ValueError as exc:
        if 'TIER0_FALSE_NEGATIVE' not in str(exc):raise
    else:raise AssertionError('native disagreement was not detected')
finally:worker.screen=saved
subprocess.run([sys.executable,'-m','factory.cli','--state',str(args.state),'create-admin'],check=True)
print('GENERATED fault-injection fixture: native disagreement retained, screen disabled, research paused')
