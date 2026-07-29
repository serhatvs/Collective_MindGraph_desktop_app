# Quality Ratchets

The production-v1 program starts from measured, reviewable quality debt and
allows that debt to move in only one direction.

- `mypy-baseline.json` records strict-mypy errors by module and error code.
  New categories and count increases fail CI. Run
  `python scripts/quality/check_mypy_baseline.py --update` only after errors
  have been removed.
- `coverage-baseline.json` records the initial 79% statement coverage and 75%
  branch-inclusive coverage. CI requires at least 75% branch-inclusive total
  coverage and 90% coverage on changed production lines. The public-v1 release
  gate is 85% total and 95% for domain, application, migration, sync, and
  cryptography code.
- Production modules are limited to 400 physical lines. Existing exceptions
  are exact, documented in `pyproject.toml`, and may not expand.
- McCabe complexity is limited to 12. Existing focused exceptions are named in
  `pyproject.toml`; new exceptions require an explicit architecture review.
