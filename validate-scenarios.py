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

errors = []
coverage_union = {k: False for k in ['persistent_state','variants','mission_gamification','misconception_feedback','verification','retrieval_interleaving','fail_forward']}
coverage_rows = []
catalog_rows = []
scenario_files = set()

catalog_index_path = SCENARIOS / 'catalogs.json'
if not catalog_index_path.exists():
    errors.append('catalogs.json: catalog index is missing')
    catalogs = []
else:
    catalog_index = json.loads(catalog_index_path.read_text())
    catalogs = catalog_index.get('catalogs', [])
    if not isinstance(catalogs, list) or not catalogs:
        errors.append('catalogs.json: no catalogs configured')
        catalogs = []

catalog_ids = set()
catalog_names = set()
for catalog_entry in catalogs:
    catalog_id = catalog_entry.get('id')
    catalog_name = catalog_entry.get('file')
    label = catalog_id or catalog_name or '<missing catalog>'
    if not catalog_id:
        errors.append(f'catalogs.json: catalog {label} is missing an id')
    elif catalog_id in catalog_ids:
        errors.append(f'catalogs.json: duplicate catalog id {catalog_id}')
    else:
        catalog_ids.add(catalog_id)
    if not catalog_name:
        errors.append(f'catalogs.json: catalog {label} is missing a file')
        continue
    if catalog_name in catalog_names:
        errors.append(f'catalogs.json: duplicate catalog file {catalog_name}')
        continue
    catalog_names.add(catalog_name)

    catalog_path = SCENARIOS / catalog_name
    if not catalog_path.exists():
        errors.append(f'catalogs.json: missing catalog file {catalog_name}')
        continue
    catalog = json.loads(catalog_path.read_text())
    scenarios = catalog.get('scenarios', [])
    if not isinstance(scenarios, list) or not scenarios:
        errors.append(f'{catalog_name}: no scenarios configured')
        continue
    catalog_rows.append((catalog_name, len(scenarios)))

    for item in scenarios:
        scenario_name = item.get('file')
        if not scenario_name:
            errors.append(f'{catalog_name}: scenario entry is missing a file')
            continue
        path = SCENARIOS / scenario_name
        if path in scenario_files:
            errors.append(f'{catalog_name}: scenario file {scenario_name} is registered more than once')
            continue
        scenario_files.add(path)
        if not path.exists():
            errors.append(f'{catalog_name}: missing scenario file {scenario_name}')
            continue
        data = json.loads(path.read_text())
        variants = data.get('variants') or [None]
        for variant in variants:
            prepared = apply_variant(data, variant) if variant else data
            errors.extend(validate_scenario(path, prepared, variant['id'] if variant else 'base'))
        cov = feature_coverage(data)
        coverage_rows.append((catalog_name, path.name, cov))
        for key, value in cov.items():
            coverage_union[key] |= value

print('Scenario validation')
print('===================')
print(f'Catalogs: {len(catalog_rows)}')
for name, count in catalog_rows:
    print(f'- {name}: {count} scenarios')
print(f'Total scenarios: {len(scenario_files)}')
for catalog_name, name, cov in coverage_rows:
    present = ', '.join(k for k,v in cov.items() if v)
    print(f'- {catalog_name} / {name}: {present}')
print('\nTop-seven feature coverage')
for key, value in coverage_union.items():
    print(f'- {key}: {"YES" if value else "NO"}')

if errors:
    print('\nERRORS')
    for error in errors:
        print('-', error)
    raise SystemExit(1)
print('\nAll configured references and answer keys passed validation.')
