# Releasing ambivo-agents

How to version, tag, and publish this package to PyPI.

---

## Why version appears in 3 files

| File | Why it exists | Who reads it |
|------|--------------|--------------|
| `ambivo_agents/__init__.py` (`__version__`) | Runtime access -- `import ambivo_agents; print(ambivo_agents.__version__)` | Your code, pip, debugging |
| `pyproject.toml` (`version`) | PEP 621 standard. `python -m build` reads this to stamp the wheel filename. | `build`, `pip`, PyPI |
| `setup.py` (`version`) | Legacy setuptools. Still needed for `pip install -e .` and older tooling. | Editable installs, older pip |

**Rule:** All three must match. The publish script (`manual_pypi_publish.sh`) validates and syncs them.

---

## Release workflow (primary)

Build and publish locally, then tag and push. This is the fastest and most reliable path.

```bash
# 1. Bump version in all 3 files
#    ambivo_agents/__init__.py, setup.py, pyproject.toml

# 2. Commit everything
git add ambivo_agents/__init__.py setup.py pyproject.toml [other changed files]
git commit -m "Release v1.4.3 - brief description of changes"

# 3. Build and publish to PyPI
rm -rf dist/ build/ *.egg-info/
python -m build
twine upload dist/*

# 4. Tag AFTER successful publish
git tag v1.4.3

# 5. Push commit and tag
git push origin main --tags
```

**Why publish before tagging:** If the build or upload fails, you don't have a tag pointing to an unpublished version. Tag only after PyPI confirms the upload.

### Using the publish script (alternative to steps 3-4)

```bash
# After committing (step 2), use the script instead of manual commands:
./manual_pypi_publish.sh

# Or for a specific version:
./manual_pypi_publish.sh --version 1.4.3
```

The script validates prerequisites, syncs version files, builds, verifies, and uploads.

---

## What happens on push

| Action | What triggers | Result |
|--------|--------------|--------|
| `git push origin main` | `python-package.yml` | Runs integration tests only. No publishing. |
| `git push origin v1.4.3` (stable tag) | `pypi-publish.yml` | Attempts PyPI publish. Requires `pypi` environment approval. Harmless "version exists" if already published locally. |
| `git push origin v1.4.3-beta.1` (pre-release tag) | `pypi-publish.yml` | Publishes to Test PyPI only. Requires `testpypi` environment approval. |

The CI publish workflow (`pypi-publish.yml`) serves as a **backup path**. It requires GitHub environment approval and uses the `PYPI_API_TOKEN` secret. The primary path is local publishing with `.pypirc`.

---

## Pre-release testing

```bash
# 1. Publish to Test PyPI first
./manual_pypi_publish.sh --test --version 1.4.3

# 2. Install from Test PyPI to verify (deps from real PyPI, package from test)
pip install -r requirements.txt
pip install -i https://test.pypi.org/simple/ --no-deps ambivo-agents==1.4.3

# 3. If good, publish to production
./manual_pypi_publish.sh --version 1.4.3

# 4. Tag and push
git tag v1.4.3
git push origin main --tags
```

---

## Quick reference: manual commands

If the publish script isn't available:

```bash
rm -rf dist/ build/ *.egg-info/
python -m build
twine check dist/*
twine upload dist/* --config-file .pypirc --verbose
```

---

## Prerequisites

- `.pypirc` with PyPI API tokens in the repo root (never committed -- in .gitignore)
- Python 3.11+ with `build` and `twine` installed (`pip install build twine`)
- Git

### PyPI environments (for GitHub Actions CI backup)

| Environment | Secret | Repository URL |
|-------------|--------|---------------|
| `testpypi` | `TEST_PYPI_API_TOKEN` | `https://test.pypi.org/legacy/` |
| `pypi` | `PYPI_API_TOKEN` | `https://upload.pypi.org/legacy/` |

---

## Tag management

```bash
# List tags
git tag -l

# Tag a specific commit retroactively
git tag v1.3.9 c776f2b
git push origin v1.3.9

# Delete a tag (local + remote)
git tag -d v1.0.0-beta
git push origin --delete v1.0.0-beta

# Re-tag (delete then recreate)
git tag -d v1.1.8
git push origin --delete v1.1.8
git tag v1.1.8
git push origin v1.1.8
```

---

## Version history

| Version | Tag | Key changes |
|---------|-----|-------------|
| 1.4.2 | `v1.4.2` | Doc consolidation, CI lint removal, workflow pattern docs |
| 1.4.1 | `v1.4.1` | Security hardening, SSE streaming, emoji removal, defensive coding |
| 1.4.0 | `v1.4.0` | Pre-hardening baseline |
| 1.3.9 | `v1.3.9` | Knowledge synthesis, response quality assessor |
| 1.3.5 | `v1.3.5` | NLP gather agent, natural language parsing |
| 1.3.3 | `v1.3.3` | Web scraping proxy support |
