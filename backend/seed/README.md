# Canonical Registry Seed Files

These JSON files are the source of truth for the car/track normalization
registry. They live in the backend repo and are imported into Postgres
via `scripts/import_canonicals.py`.

## Adding a new car or track

1. Add an entry to `canonical_cars.json` or `canonical_tracks.json`.
2. Generate a canonical_id: `python -c "import uuid; print(uuid.uuid4())"`.
3. Add one alias per sim under `aliases[]`.
4. Run the import: `python -m scripts.import_canonicals`.
5. Run the backfill: `python -m scripts.backfill_resolver`.
6. Commit the updated JSON + verify the CI test `test_no_duplicate_aliases` passes.

## Rules

- **No duplicate `(sim_id, raw_id)` pairs.** One raw string maps to exactly one canonical. CI enforces this.
- **`car_class`** must be one of: GT3, GT4, GTE, LMP2, Hypercar, Formula, Cup, Touring, or null.
- **`canonical_layout`** should be a short, human-readable label: GP, Full, Junior, National, Indy, Oval, Road Course, Nordschleife, etc.
- **`raw_layout`** must match what the sim API returns (lowercase for ACC/AC, mixed case for iRacing/LMU). Empty string `""` when the sim doesn't report a layout.

## Distribution to desktop

At desktop release time, `scripts/sync_lut_from_backend.py` copies these
files into `src/lap_coach_logger/normalization/lut/` and generates a
`lut_version.txt` from the file SHA.
