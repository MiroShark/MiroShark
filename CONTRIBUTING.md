# Contributing

<sup>English · [中文](CONTRIBUTING.zh-CN.md)</sup>

## Testing

A pytest suite lives at `backend/tests/`.

### Fast offline unit suite

```bash
cd backend && pytest -m "not integration"
```

### Integration tests

Integration tests hit a live backend at `MIROSHARK_API_URL` (default `http://localhost:5001`). Legacy E2E scripts wrap as `slow` tests:

```bash
pytest -m integration                # endpoint contracts (seconds)
pytest -m "integration and slow"     # full pipeline smoke tests (minutes)
```

Some integration tests need a pre-existing simulation — set `MIROSHARK_TEST_SIM_ID=sim_xxx`.

The hand-run scripts in `backend/scripts/test_*.py` still work as stand-alone programs; the pytest layer just registers them for discovery.

### CI

The `.github/workflows/tests.yml` workflow runs the unit suite on every push and PR.
