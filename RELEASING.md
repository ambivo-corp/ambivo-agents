# Releasing ambivo-agents

How to version, tag, and publish this package to PyPI.

---

## Why version appears in 3 files

The version is declared in three places because each serves a different consumer:

| File | Why it exists | Who reads it |
|------|--------------|--------------|
| `ambivo_agents/__init__.py` (`__version__`) | Runtime access -- `import ambivo_agents; print(ambivo_agents.__version__)`. Also used by tools like `importlib.metadata` as a fallback. | Your code, pip, debugging |
| `pyproject.toml` (`version`) | PEP 621 standard. Modern build tools (`python -m build`) read this to stamp the wheel/sdist filename and package metadata. | `build`, `pip`, PyPI |
| `setup.py` (`version`) | Legacy setuptools entry point. Still needed because some downstream tools and editable installs (`pip install -e .`) fall back to `setup.py`. Will eventually be removed when full PEP 621 migration is complete. | `pip install -e .`, older tooling |

**Rule:** All three must match. The publish script (`manual_pypi_publish.sh`) validates this and syncs them automatically.

---

## Release workflow

### Standard release (CI-driven)

```bash
# 1. Make your changes, bump version in all 3 files
#    __init__.py, setup.py, pyproject.toml

# 2. Commit
git add ambivo_agents/__init__.py setup.py pyproject.toml [other files]
git commit -m "Release v1.4.2 - brief description of changes"

# 3. Tag AFTER commit, BEFORE push
git tag v1.4.2

# 4. Push commit AND tag together
git push origin main --tags

# 5. Done -- GitHub Actions (pypi-publish.yml) auto-publishes to PyPI
```

### What triggers publishing

| Action | CI workflow triggered | Publishes? |
|--------|---------------------|------------|
| `git push origin main` | `python-package.yml` (tests only) | No |
| `git push origin v1.4.2` | `pypi-publish.yml` | Yes (production PyPI) |
| `git push origin v1.4.2-beta.1` | `pypi-publish.yml` | Yes (Test PyPI only) |
| Manual workflow dispatch | `pypi-publish.yml` | Yes (whichever target) |

### Pre-release testing

```bash
# Tag as beta -- publishes to Test PyPI only
git tag v1.4.2-beta.1
git push origin v1.4.2-beta.1

# Install from Test PyPI to verify
pip install -i https://test.pypi.org/simple/ --no-deps ambivo-agents==1.4.2b1

# If good, tag the SAME commit for production
git tag v1.4.2
git push origin v1.4.2
```

**Tip:** Test PyPI has unreliable mirrors for dependencies. Install deps from real PyPI first, then install only your package with `--no-deps`:

```bash
pip install -r requirements.txt
pip install -i https://test.pypi.org/simple/ --no-deps ambivo-agents==1.4.2b1
```

---

## Manual publishing (fallback)

Use `manual_pypi_publish.sh` only when GitHub Actions runners are unavailable.

```bash
# Make executable (first time)
chmod +x manual_pypi_publish.sh

# Publish current version
./manual_pypi_publish.sh

# Test on Test PyPI first
./manual_pypi_publish.sh --test

# Specific version
./manual_pypi_publish.sh --version 1.4.2

# Dry run (see what would happen)
./manual_pypi_publish.sh --dry-run

# Force (skip confirmations)
./manual_pypi_publish.sh --force
```

### What the script does

1. Validates prerequisites (.pypirc, git repo, Python tools)
2. Determines version from git tag / pyproject.toml / manual flag
3. Syncs version across all 3 files if they differ
4. Installs/upgrades build tools (pip, build, twine, wheel)
5. Cleans old `dist/`, `build/`, `*.egg-info/`
6. Builds wheel + sdist via `python -m build`
7. Verifies with `twine check dist/*`
8. Checks PyPI for duplicate version
9. Asks for confirmation
10. Uploads via `twine upload dist/* --config-file .pypirc`

### If the script fails

```bash
rm -rf dist/ build/ *.egg-info/
python -m build
twine check dist/*
twine upload dist/* --config-file .pypirc --verbose
```

---

## Prerequisites

- `.pypirc` with PyPI API tokens (never commit this -- already in .gitignore)
- Python 3.11+ with pip
- Git

### PyPI environments (for GitHub Actions)

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
| 1.4.1 | `v1.4.1` | Security hardening, SSE streaming, emoji removal, defensive coding |
| 1.4.0 | `v1.4.0` | Pre-hardening baseline |
| 1.3.9 | `v1.3.9` | Knowledge synthesis, response quality assessor |
| 1.3.5 | `v1.3.5` | NLP gather agent, natural language parsing |
| 1.3.3 | `v1.3.3` | Web scraping proxy support |
