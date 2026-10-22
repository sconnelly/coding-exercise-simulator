#!/usr/bin/env python3
import json
from pathlib import Path
from copy import deepcopy

ROOT = Path(__file__).resolve().parent
SCENARIOS = ROOT / 'scenarios'


def deep_merge(target, patch):
    if not isinstance(patch, dict):
        return deepcopy(patch)
    result = deepcopy(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if isinstance(value, dict):
            result[key] = deep_merge(result.get(key), value)
        else:
            result[key] = deepcopy(value)
    return result


def apply_variant(data, variant):
    d = deepcopy(data)
    for field in ['meta', 'brief', 'mission', 'workspace', 'completion']:
        override = variant.get(field + 'Override')
        if override:
            d[field] = deep_merge(d.get(field, {}), override)
    if variant.get('initialState'):
        d['initialState'] = deep_merge(d.get('initialState', {}), variant['initialState'])
    for file_id, version in variant.get('fileVersions', {}).items():
        f = next((x for x in d['files'] if x['id'] == file_id), None)
        if f:
            f['initialVersion'] = version
    for stage_id, patch in variant.get('stageOverrides', {}).items():
        for i, stage in enumerate(d['stages']):
            if stage['id'] == stage_id:
                d['stages'][i] = deep_merge(stage, patch)
                break
    return d


def validate_scenario(path, data, label='base'):
    errors = []
    prefix = f'{path.name} [{label}]'
    files = {f['id']: f for f in data.get('files', [])}
    stages = data.get('stages', [])
    stage_ids = [s.get('id') for s in stages]
    if len(stage_ids) != len(set(stage_ids)):
        errors.append(f'{prefix}: duplicate stage IDs')
    risk_ids = {r['id'] for r in data.get('mission', {}).get('riskSignals', [])}

    def check_effects(effects, where):
        if not effects:
            return
        for key in ['resolveSignals', 'openSignals', 'dormantSignals']:
            for rid in effects.get(key, []):
                if rid not in risk_ids:
                    errors.append(f'{prefix}: {where} references missing risk signal {rid}')
        for file_id, version in effects.get('fileVersions', {}).items():
            f = files.get(file_id)
            if not f:
                errors.append(f'{prefix}: {where} references missing file {file_id}')
            elif 'versions' not in f or version not in f['versions']:
                errors.append(f'{prefix}: {where} references missing version {file_id}:{version}')
        for key in ['unlockFiles', 'lockFiles']:
            for file_id in effects.get(key, []):
                if file_id not in files:
                    errors.append(f'{prefix}: {where} references missing file {file_id}')

    for f in files.values():
        if 'versions' in f:
            initial = f.get('initialVersion')
            if initial not in f['versions']:
                errors.append(f'{prefix}: file {f["id"]} has invalid initialVersion {initial}')

    for stage in stages:
        sid = stage.get('id', '<missing>')
        stype = stage.get('type')
        for file_id in stage.get('visibleFiles', []):
            if file_id not in files:
                errors.append(f'{prefix}: stage {sid} references missing visible file {file_id}')
        if stage.get('focusFile') and stage['focusFile'] not in files:
            errors.append(f'{prefix}: stage {sid} references missing focusFile {stage["focusFile"]}')
        if stype == 'select-lines':
            for key in stage.get('correctSelections', []):
                try:
                    file_id, line = key.rsplit(':', 1)
                    line = int(line)
                except Exception:
                    errors.append(f'{prefix}: stage {sid} has invalid line key {key}')
                    continue
                f = files.get(file_id)
                if not f:
                    errors.append(f'{prefix}: stage {sid} line key references missing file {file_id}')
                    continue
                versions = list(f.get('versions', {}).values()) or [f.get('content', '')]
                if any(line > len(content.split('\n')) for content in versions):
                    errors.append(f'{prefix}: stage {sid} line {key} is outside at least one file version')
        if stype in ('single-choice', 'multi-choice'):
            choice_ids = {c['id'] for c in stage.get('choices', [])}
            for cid in stage.get('correctIds', []):
                if cid not in choice_ids:
                    errors.append(f'{prefix}: stage {sid} correctIds references missing choice {cid}')
            for cid in stage.get('outcomes', {}):
                if cid not in choice_ids:
                    errors.append(f'{prefix}: stage {sid} outcome references missing choice {cid}')
            for cid, outcome in stage.get('outcomes', {}).items():
                check_effects(outcome.get('effects'), f'stage {sid} outcome {cid}')
        if stype == 'sequence':
            item_ids = {i['id'] for i in stage.get('items', [])}
            if set(stage.get('correctOrder', [])) != item_ids:
                errors.append(f'{prefix}: stage {sid} correctOrder does not match sequence item IDs')
        check_effects(stage.get('onCorrect'), f'stage {sid} onCorrect')
        check_effects(stage.get('onReveal'), f'stage {sid} onReveal')
        check_effects(stage.get('onRun'), f'stage {sid} onRun')

    return errors


def feature_coverage(data):
    stages = data.get('stages', [])
    text = json.dumps(data)
    return {
        'persistent_state': any(s.get('onCorrect') or s.get('outcomes') or s.get('onRun') for s in stages),
        'variants': bool(data.get('variants')),
        'mission_gamification': bool(data.get('mission', {}).get('riskSignals')) and bool(data.get('mission', {}).get('achievements')),
        'misconception_feedback': any(any(k in json.dumps(s) for k in ['feedbackIfSelected','feedbackIfMissed','feedbackByMissing','feedbackBySelection']) or any(c.get('feedback') for c in s.get('choices', [])) for s in stages),
        'verification': any(s.get('type') == 'verification' for s in stages),
        'retrieval_interleaving': any(s.get('concept', {}).get('retrieval') for s in stages),
        'fail_forward': any(any(o.get('kind') == 'consequence' and o.get('advance') for o in s.get('outcomes', {}).values()) for s in stages),
    }

catalog = json.loads((SCENARIOS / 'catalog.json').read_text())
scenario_files = [SCENARIOS / item['file'] for item in catalog['scenarios']]
errors = []
coverage_union = {k: False for k in ['persistent_state','variants','mission_gamification','misconception_feedback','verification','retrieval_interleaving','fail_forward']}
coverage_rows = []

if len(scenario_files) != 5:
    errors.append(f'catalog.json: expected 5 scenarios, found {len(scenario_files)}')

for path in scenario_files:
    if not path.exists():
        errors.append(f'catalog.json: missing scenario file {path.name}')
        continue
    data = json.loads(path.read_text())
    variants = data.get('variants') or [None]
    if not variants:
        variants = [None]
    for variant in variants:
        prepared = apply_variant(data, variant) if variant else data
        errors.extend(validate_scenario(path, prepared, variant['id'] if variant else 'base'))
    cov = feature_coverage(data)
    coverage_rows.append((path.name, cov))
    for key, value in cov.items():
        coverage_union[key] |= value

print('Scenario validation')
print('===================')
print(f'Catalog scenarios: {len(scenario_files)}')
for name, cov in coverage_rows:
    present = ', '.join(k for k,v in cov.items() if v)
    print(f'- {name}: {present}')
print('\nTop-seven feature coverage')
for key, value in coverage_union.items():
    print(f'- {key}: {"YES" if value else "NO"}')

if errors:
    print('\nERRORS')
    for error in errors:
        print('-', error)
    raise SystemExit(1)
print('\nAll configured references and answer keys passed validation.')
