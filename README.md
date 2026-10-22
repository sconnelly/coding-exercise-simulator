# Secrets Management Mission Simulator — V2

This package contains one reusable HTML5 simulation engine and five Secrets Management missions configured in JSON.

## Open the simulator

Host this folder on a web server and open `index.html`.

The scenario board reads `scenarios/catalog.json`. Each mission launches the shared `simulator.html` engine with a scenario JSON file.

## Included missions

1. `01-release-gate.json` — code review, runtime retrieval and regression verification
2. `02-pipeline-containment.json` — GitLab CI/CD, fail-forward consequences, artifacts and external-secret retrieval review
3. `03-terraform-boundary.json` — Terraform `sensitive`, plan/state persistence and support-sharing risk
4. `04-exposure-response.json` — active versus already-inactive credential response and repository cleanup priority
5. `05-ai-context-control.json` — AI context control, generated-code review and later context re-exposure

## V2 capabilities

The engine supports JSON-configured:

- persistent mission state and file versions;
- random scenario variants;
- risk signals, review streaks, retrieval wins and achievements;
- misconception-specific feedback;
- simulated verification checks;
- retrieval and interleaving tags;
- fail-forward consequences and conditional stages;
- line selection, single choice, multiple choice and sequencing;
- progressive hints and Reveal solution;
- responsive and keyboard-accessible interactions.

No learner score is sent to an LMS.

## Create or modify a mission

See `SCENARIO-CONFIG-GUIDE.md`.

Run the configuration validator after edits:

```bash
python3 validate-scenarios.py
```

## Important content guardrail

Use fictional placeholders only. Do not place real credentials, production logs, secret-bearing screenshots, sensitive internal data or real `.env` values in a scenario.
