# Scenario Configuration Guide — V2

The simulator engine is shared by every mission. New challenges are created in JSON rather than by changing `simulator.html`.

## Package structure

```text
coding-exercise-simulator/
├── index.html
├── simulator.html
├── validate-scenarios.py
└── scenarios/
    ├── catalog.json
    ├── 01-release-gate.json
    ├── 02-pipeline-containment.json
    ├── 03-terraform-boundary.json
    ├── 04-exposure-response.json
    └── 05-ai-context-control.json
```

## Add a mission

1. Copy the scenario that most closely matches the interaction you need.
2. Give the scenario a unique `meta.id`.
3. Replace the briefing, files, stages, feedback and completion content.
4. Add the file to `scenarios/catalog.json`.
5. Run `python3 validate-scenarios.py`.
6. Test the hosted scenario with keyboard controls, narrow-screen layout, retry behaviour, hints and Reveal solution.

## Core JSON sections

### `meta`

Defines the mission title and learner-facing metadata.

```json
{
  "meta": {
    "id": "example-mission",
    "title": "Example Mission",
    "subtitle": "Short learner-facing description.",
    "role": "Merge request reviewer",
    "estimatedMinutes": 6,
    "difficulty": "Applied"
  }
}
```

### `mission`

Controls the game layer.

```json
{
  "mission": {
    "eyebrow": "Mission 06 · Example",
    "objective": "Resolve the exposure before approving the change.",
    "activeLabel": "Blocked",
    "clearLabel": "Cleared",
    "riskSignals": [
      {"id": "source", "label": "Credential in source", "initial": "open"},
      {"id": "artifact", "label": "Credential in artifact", "initial": "dormant"}
    ],
    "achievements": []
  }
}
```

Risk signal states are:

- `open` — currently contributes to the open-risk count;
- `resolved` — already closed;
- `dormant` — potential risk that can be opened by a consequence.

### `initialState`

Stores scenario variables used by conditional stages and verification checks.

```json
{
  "initialState": {
    "patchApplied": false,
    "pipelineLeak": false
  }
}
```

### `files`

A file can use one static `content` value or several named `versions`.

```json
{
  "id": "service",
  "path": "src/service.ts",
  "language": "TypeScript",
  "badge": "changed",
  "initialVersion": "unsafe",
  "versions": {
    "unsafe": "const token = \"FAKE_NOT_A_REAL_SECRET\";",
    "safe": "const token = process.env.SERVICE_TOKEN;"
  }
}
```

Set `"hidden": true` when an artefact should appear only after an effect unlocks it.

## Stateful effects

Stages and fail-forward outcomes can change the mission state.

```json
{
  "onCorrect": {
    "resolveSignals": ["source"],
    "openSignals": ["artifact"],
    "setState": {"patchApplied": true},
    "fileVersions": {"service": "safe"},
    "unlockFiles": ["scan-log"],
    "workspaceStatus": "Patch applied · verification required"
  }
}
```

Supported effect fields:

- `resolveSignals`
- `openSignals`
- `dormantSignals`
- `setState`
- `fileVersions`
- `unlockFiles`
- `lockFiles`
- `workspaceStatus`
- `awardAchievements`

## Random variants

Use `variants` to change evidence or the required response while keeping the same engine.

```json
{
  "variants": [
    {
      "id": "active",
      "initialState": {"credentialStatus": "active"},
      "fileVersions": {"finding": "active"},
      "stageOverrides": {
        "first-action": {
          "correctIds": ["contain"]
        }
      }
    },
    {
      "id": "inactive",
      "initialState": {"credentialStatus": "inactive"},
      "fileVersions": {"finding": "inactive"},
      "stageOverrides": {
        "first-action": {
          "correctIds": ["verify"]
        }
      }
    }
  ]
}
```

The engine selects a variant at random. For QA, force one with:

```text
simulator.html?scenario=scenarios/04-exposure-response.json&variant=active
```

Variant overrides can use:

- `metaOverride`
- `briefOverride`
- `missionOverride`
- `workspaceOverride`
- `completionOverride`
- `initialState`
- `fileVersions`
- `stageOverrides`

## Supported stage types

### `select-lines`

Learners mark risky lines in one or more files.

```json
{
  "type": "select-lines",
  "correctSelections": ["service:1", "logger:4"]
}
```

Optional misconception feedback:

```json
{
  "feedbackByMissing": {
    "service:1": "The credential is stored directly in source."
  },
  "feedbackBySelection": {
    "service:6": "This line does not expose the credential."
  }
}
```

### `single-choice`

```json
{
  "type": "single-choice",
  "correctIds": ["runtime"],
  "choices": [
    {
      "id": "private-repo",
      "label": "Move the value to another repository file",
      "feedback": "Repository visibility does not make source control a secrets manager."
    },
    {
      "id": "runtime",
      "label": "Use the current approved runtime retrieval pattern"
    }
  ]
}
```

### `multi-choice`

Use `feedbackIfSelected` for an unsafe distractor and `feedbackIfMissed` for a required action.

```json
{
  "type": "multi-choice",
  "correctIds": ["remove", "verify"],
  "choices": [
    {
      "id": "remove",
      "label": "Remove the secret-bearing output",
      "feedbackIfMissed": "The current output still exposes the credential."
    },
    {
      "id": "publish",
      "label": "Publish the debug file as an artifact",
      "feedbackIfSelected": "The artifact creates another durable copy."
    }
  ]
}
```

### `sequence`

```json
{
  "type": "sequence",
  "items": [
    {"id": "contain", "text": "Make the active credential unusable"},
    {"id": "verify", "text": "Verify the replacement"},
    {"id": "cleanup", "text": "Clean repository history"}
  ],
  "correctOrder": ["contain", "verify", "cleanup"]
}
```

The engine uses accessible Up and Down buttons rather than requiring drag-and-drop.

### `verification`

Verification stages simulate scans, tests, pipeline checks or policy checks. No real code is executed.

```json
{
  "type": "verification",
  "checks": [
    {
      "label": "Secret scan",
      "results": [
        {
          "when": {"key": "patchApplied", "equals": true},
          "status": "pass",
          "message": "No simulated credential literal found."
        },
        {
          "default": true,
          "status": "fail",
          "message": "Credential-like content remains."
        }
      ]
    }
  ]
}
```

Statuses are `pass`, `fail` or `warn`.

## Conditional stages

A stage can appear only when a state condition is true.

```json
{
  "when": {"key": "pipelineLeak", "equals": true}
}
```

Conditions support:

- `key` with `equals`, `notEquals` or `in`;
- `signal` with a risk status;
- `achievement`;
- nested `all`, `any` and `not`.

## Fail-forward consequences

A wrong single-choice decision can be intentionally applied instead of immediately rejected.

```json
{
  "outcomes": {
    "mask-only": {
      "kind": "consequence",
      "advance": true,
      "feedback": "The job finishes, but the debug artifact contains the credential.",
      "effects": {
        "openSignals": ["artifact"],
        "setState": {"pipelineLeak": true},
        "unlockFiles": ["job-log"]
      }
    }
  }
}
```

Use this selectively. It is strongest when the learner benefits from seeing the consequence before diagnosing it.

## Retrieval and interleaving

Tag an early stage with a concept:

```json
{
  "concept": {
    "id": "secret-output",
    "label": "Keep secret values out of output"
  }
}
```

Reuse the same concept later and add `retrieval: true`:

```json
{
  "concept": {
    "id": "secret-output",
    "label": "Keep secret values out of output",
    "retrieval": true
  }
}
```

When the learner recognizes the concept again, the engine records a Pattern recall and can unlock an achievement.

## Achievements

Achievements are configured in `mission.achievements`.

Supported completion conditions:

- `no-hints`
- `no-reveals`
- `all-risk-resolved`
- `best-streak-at-least`
- `retrieval-wins-at-least`
- `state-equals`
- `all-first-try`

Example:

```json
{
  "id": "pattern-spotter",
  "icon": "↺",
  "title": "Pattern spotter",
  "description": "Recognized a familiar risk in a new artefact.",
  "condition": {
    "type": "retrieval-wins-at-least",
    "value": 1
  }
}
```

Achievements should reinforce useful engineering behaviour. Avoid decorative badges that do not map to the learning goal.

## Hints and Reveal solution

Add hints from general to specific:

```json
{
  "hints": [
    "Review every place the credential can travel.",
    "Check the diagnostic output and artifact configuration."
  ]
}
```

The engine automatically adds Reveal solution for assessed stages. It reads the configured `correctSelections`, `correctIds` or `correctOrder`, applies `onReveal` when provided, and otherwise applies `onCorrect` so the learner can continue in a valid state.

Set `"allowReveal": false` only when a stage genuinely should not expose an answer.

## Authoring rules for Secrets Management missions

- Test secure engineering judgement, not syntax recall.
- Use fictional credentials such as `FAKE_NOT_A_REAL_SECRET`.
- Do not reproduce real production logs, secret values, internal sensitive data or service-specific secrets-manager paths.
- Do not invent organizational requirements, approvals, owners or exception processes.
- Do not teach a universal numeric rotation interval unless the current owning standard establishes one.
- Do not infer a blanket GitLab CI-variable rule from conflicting source material.
- Treat exposed active credentials as a credential problem first; repository cleanup follows containment and verification.
- Treat AI files, logs, screenshots, terminal output, tools and connected systems as possible context paths.
- Keep feedback focused on why risk remains and what the learner should inspect or decide next.

## QA checklist

Before publishing a new mission, confirm that:

- `python3 validate-scenarios.py` passes;
- every JSON file parses;
- every referenced file and file version exists;
- every line-selection answer points to the intended line in every variant;
- every choice and sequence answer exists;
- every risk signal opened or resolved by an effect exists;
- every branch reaches a valid completion path;
- misconception feedback explains the learner's actual error;
- a learner can always recover using hints or Reveal solution;
- keyboard navigation works;
- meaning does not depend on colour alone;
- the layout works at desktop and narrow widths;
- all values and systems shown to learners are fictional or deliberately generic;
- no unconfirmed organizational policy has been introduced.
