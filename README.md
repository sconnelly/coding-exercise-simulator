# Secure Engineering Mission Library

This package uses one shared simulation engine and multiple JSON-configured course mission boards.

Open `index.html` through a local or hosted web server. The launcher reads `scenarios/catalogs.json`, loads the selected course catalog, then opens each mission in `simulator.html`.

## Catalog structure

```text
scenarios/
├── catalogs.json
├── 01-catalog.json
├── 01-01-input-validation-query.json
├── 01-02-contextual-output-encoding.json
├── ...
├── 02-catalog.json
├── 02-01-next-course-mission.json
└── ...
```

- `catalogs.json` is the library index. Add one entry per course mission board.
- Each numbered catalog lists only the scenarios for that course.
- Scenario file prefixes follow `<course>-<mission>-<slug>.json`, such as `02-03-api-review.json`.

The current catalog is carried in the URL, so **All scenarios** returns the learner to the same course board.

## Add a course board

1. Add the course's scenario JSON files in `scenarios/`, using the next course prefix.
2. Create a matching numbered catalog, such as `02-catalog.json`.
3. Add its metadata and filename to `scenarios/catalogs.json`.
4. Run:

   ```bash
   python3 validate-scenarios.py
   ```

No launcher or engine changes are required when adding another catalog.

## Current board

`01-catalog.json` contains the five **Secure Coding Techniques** scenarios. `02-catalog.json` preserves the five original **Secrets Management** scenarios from the supplied simulator package.
