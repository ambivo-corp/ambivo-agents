# Manual PyPI Publishing Script

This script automates the manual publishing process when GitHub Actions runners are unavailable.

## Quick Start

```bash
# Make executable (first time only)
chmod +x manual_pypi_publish.sh

# Publish current version to production PyPI
./manual_pypi_publish.sh

# Test on Test PyPI first
./manual_pypi_publish.sh --test

# Publish specific version
./manual_pypi_publish.sh --version 1.1.9

# Force publish (skip version checks)
./manual_pypi_publish.sh --force

# See what would happen without actually publishing
./manual_pypi_publish.sh --dry-run
```

## Common Workflows

### 1. Normal Release Process
```bash
# 1. First test on Test PyPI
./manual_pypi_publish.sh --test --version 1.1.9

# 2. If test is successful, publish to production
./manual_pypi_publish.sh --version 1.1.9
```

### 2. Emergency Hotfix
```bash
# Skip confirmations for urgent releases
./manual_pypi_publish.sh --force --version 1.1.8-hotfix
```

### 3. Version Already Tagged
```bash
# Script will automatically use git tag version
git tag v1.1.9
./manual_pypi_publish.sh
```

## Options

| Option | Description |
|--------|-------------|
| `--test` | Publish to Test PyPI instead of production |
| `--force` | Skip version checks and confirmations |
| `--version X.Y.Z` | Specify version manually |
| `--dry-run` | Show what would be done without publishing |
| `--help` | Show help message |

## Prerequisites

1. **PyPI Credentials**: `.pypirc` file configured with your PyPI tokens
2. **Git Repository**: Must be in the ambivo-agents git repository
3. **Python Environment**: Python 3.11+ with pip

## What the Script Does

1. ✅ **Validates environment** - Checks for required files and tools
2. ✅ **Determines version** - Uses git tag, manual version, or pyproject.toml
3. ✅ **Syncs version files** - Updates pyproject.toml and setup.py if needed
4. ✅ **Installs dependencies** - Updates pip, build, twine, setuptools, wheel
5. ✅ **Cleans previous builds** - Removes old dist/, build/, *.egg-info/
6. ✅ **Builds package** - Creates wheel and source distributions
7. ✅ **Verifies package** - Runs twine check for integrity
8. ✅ **Checks existing versions** - Prevents duplicate uploads
9. ✅ **Confirms publication** - Shows summary and asks for confirmation
10. ✅ **Publishes to PyPI** - Uploads using configured credentials
11. ✅ **Shows final summary** - Provides links and install commands

## Error Handling

The script includes comprehensive error handling:
- Validates all prerequisites before starting
- Checks version format and consistency
- Prevents publishing existing versions (unless --force)
- Verifies package integrity before upload
- Provides clear error messages and suggestions

## Examples

### Successful Run
```bash
$ ./manual_pypi_publish.sh --version 1.1.9

=================================================================
 MANUAL PYPI PUBLISH - ambivo-agents
=================================================================

🔧 Checking prerequisites...
✅ All prerequisites met

🔧 Determining target version...
ℹ️  Using manually specified version: 1.1.9
✅ Target version: 1.1.9

🔧 Building package...
✅ Package built successfully

🔧 Publishing to PyPI...
✅ Package published successfully!
ℹ️  View at: https://pypi.org/project/ambivo-agents/1.1.9/

🎉 Successfully published ambivo-agents v1.1.9 to Production PyPI!
```

### Testing First
```bash
# Test on Test PyPI
$ ./manual_pypi_publish.sh --test --version 1.1.9

# Then publish to production if test successful
$ ./manual_pypi_publish.sh --version 1.1.9
```

## Troubleshooting

### Common Issues

1. **"pyproject.toml not found"**
   - Make sure you're in the ambivo-agents repository root

2. **".pypirc file not found"**
   - Configure PyPI credentials first
   - Copy from existing .pypirc or create new one

3. **"Version already exists"**
   - Use `--force` to override
   - Or increment the version number

4. **Build failures**
   - Check Python environment
   - Ensure all dependencies are installed

### Manual Steps if Script Fails

If the script fails, you can run the manual commands:

```bash
# Clean and build
rm -rf dist/ build/ *.egg-info/
python -m build

# Verify
twine check dist/*

# Upload
twine upload dist/* --config-file .pypirc --verbose
```

## Security Notes

- The script uses your existing `.pypirc` credentials
- Never commit `.pypirc` to git (already in .gitignore)
- Use environment variables for CI/CD instead of .pypirc files
- Test PyPI tokens are separate from production tokens

## Support

If you encounter issues:
1. Run with `--dry-run` first to see what would happen
2. Check that all prerequisites are met
3. Verify your `.pypirc` configuration
4. Try publishing to Test PyPI first with `--test`