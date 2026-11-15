"""Read-only legacy/current Decimal encoding comparison of persisted typed specs.

This verifies the values retained in SQLite, not unrecoverable pre-normalization
inputs from older software. No database, result or identity is rewritten.
"""
import argparse
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import sqlite3

from pydantic import BaseModel
from factory.contracts import ExperimentContract, InstrumentSpec, StrategySpec, canonical

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--states', type=Path, default=Path('.local'))
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()


def legacy(value):
    if isinstance(value, BaseModel):
        value = value.model_dump(mode='python')
    if isinstance(value, Decimal):
        with localcontext() as context:
            context.prec = 28
            return format(value.normalize(), 'f')
    if isinstance(value, dict):
        return {k: legacy(v) for k, v in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [legacy(v) for v in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


counts = {'databases': 0, 'strategy_specs': 0, 'experiment_contracts': 0, 'instrument_profiles': 0}
changes, errors = [], []


def compare(value, category, location):
    counts[category] += 1
    if digest(legacy(value)) != digest(canonical(value)):
        changes.append(location)


for database in sorted(args.states.rglob('factory.sqlite')):
    counts['databases'] += 1
    connection = sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table, column, model, category in (
            ('strategy_specs', 'spec_json', StrategySpec, 'strategy_specs'),
            ('experiments', 'contract_json', ExperimentContract, 'experiment_contracts'),
            ('search_trials', 'contract_json', ExperimentContract, 'experiment_contracts'),
            ('evaluation_results', 'contract_json', ExperimentContract, 'experiment_contracts'),
        ):
            if table not in tables:
                continue
            for index, row in enumerate(connection.execute(f'SELECT {column} FROM {table}')):
                location = f'{database.parent.name}:{table}:{index}'
                try:
                    compare(model.model_validate_json(row[0]), category, location)
                except Exception as exc:
                    errors.append({'location': location, 'error_type': type(exc).__name__})
        for table, column in (('search_protocols', 'protocol_json'), ('protected_holdouts', 'spec_json')):
            if table not in tables:
                continue
            for index, row in enumerate(connection.execute(f'SELECT {column} FROM {table}')):
                location = f'{database.parent.name}:{table}:{index}:profile'
                try:
                    compare(InstrumentSpec.model_validate(json.loads(row[0])['profile']),
                            'instrument_profiles', location)
                except Exception as exc:
                    errors.append({'location': location, 'error_type': type(exc).__name__})
    finally:
        connection.close()
report = {'status': 'PASS_RETAINED_TYPED_VALUES_UNCHANGED' if not changes and not errors else 'REVIEW_REQUIRED',
          'counts': counts, 'changed_encoding_locations': changes, 'unparsed_records': errors,
          'scope': 'read-only persisted typed values under requested states; not proof of pre-normalization inputs, all Git history, or fields not enumerated',
          'databases_modified': False}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
raise SystemExit(bool(changes or errors))
