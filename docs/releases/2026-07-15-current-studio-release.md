# Studio Update: 2026-07-15

## Scope

This release publishes the current trajectory annotation Studio as a complete,
standalone GitHub codebase. It preserves the existing repository history while
adding the application, adapters, CLI, deployment templates, documentation,
and test suite required for normal development and review workflows.

Notable capabilities included in this release:

- review server, browser UI, reviewer namespaces, timeline annotations, and
  aggregate export surfaces;
- agent-native CLI commands for batch, sample, reviewer, review, timeline,
  aggregate, bundle, and mode-labeling workflows;
- adapters for Arena task02/task03, signal-to-GPS comparison, and the
  Dalian/Chania transfer-recovery truth-layer visualization batch;
- trajectory recovery timeline rendering improvements for layered signal and
  truth inspection;
- Docker, nginx, and systemd example deployment assets.

## Data Boundary

This is a zero-data release. Real review batches, reviewer outputs, raw
signals, runtime caches, local configuration, logs, backups, and generated
bundles are excluded by `.gitignore`. Runtime data should be supplied through
`--batches-root`, `--result-root`, or the documented environment variables.

## Verification

The release candidate was verified on 2026-07-15 with:

```bash
PYTHONPATH=/tmp PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  python3 -m pytest web/test_review_lib.py web/test_review_server.py scripts/tests
python3 scripts/check_docs_entrypoints.py
python3 scripts/check_index_html_inline_js.py
```

Results: `138 passed, 1 skipped`; documentation entrypoints and JavaScript
syntax checks passed.

## Upgrade

Existing deployments should update the code separately from runtime batches.
Keep each existing batch root outside the repository, then restart the review
server with its current `--batches-root` value. The release does not migrate or
replace existing reviewer data.
