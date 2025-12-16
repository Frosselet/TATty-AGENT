# TATty Agent Distribution Guide

This document provides comprehensive instructions for building, testing, and distributing the TATty Agent package on the JFrog platform.

## 📋 Pre-Distribution Checklist

### ✅ Code Quality
- [ ] All tests passing (`pytest tests/ -v`)
- [ ] Package imports work correctly
- [ ] CLI commands functional (`tatty-agent --help`, `tatty-init`, `tatty-tui`)
- [ ] Jupyter integration tested
- [ ] Library API validated
- [ ] Documentation updated

### ✅ Version Management
- [ ] Version number updated in `pyproject.toml`
- [ ] Version matches across all files
- [ ] CHANGELOG.md updated with new features
- [ ] Git tags created for release

### ✅ Dependencies
- [ ] All dependencies tested and locked
- [ ] Optional dependencies properly configured
- [ ] No circular dependencies
- [ ] Requirements compatible with target Python versions

### ✅ Documentation
- [ ] README_PACKAGE.md comprehensive and up-to-date
- [ ] Installation instructions tested
- [ ] Examples and usage patterns verified
- [ ] API documentation complete

## 🔧 Building the Package

### 1. Environment Setup
```bash
# Ensure clean environment
python -m venv dist_env
source dist_env/bin/activate  # On Windows: dist_env\Scripts\activate

# Install build dependencies
pip install --upgrade pip setuptools wheel build twine
```

### 2. Package Configuration Validation
```bash
# Verify pyproject.toml configuration
python -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    config = tomllib.load(f)
print('Package Name:', config['project']['name'])
print('Version:', config['project']['version'])
print('Dependencies:', len(config['project']['dependencies']))
print('Optional Dependencies:', list(config['project']['optional-dependencies'].keys()))
"
```

### 3. Build Package
```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info/

# Build source distribution and wheel
python -m build

# Verify build outputs
ls -la dist/
```

### 4. Local Installation Test
```bash
# Test installation from wheel
pip install dist/TATty_agent-*.whl

# Test basic functionality
python -c "
from tatty_agent import TattyAgent
agent = TattyAgent()
print('✅ Package installation successful')
"

# Test CLI commands
tatty-agent --help
tatty-init --help
```

## 🧪 Pre-Distribution Testing

### 1. Comprehensive Test Suite
```bash
# Run all tests with coverage
pytest tests/ -v --cov=tatty_agent --cov-report=html

# Integration tests
pytest tests/test_integration.py -v

# Jupyter integration tests (if jupyter installed)
pytest tests/test_jupyter_integration.py -v

# Library API tests
pytest tests/test_library_api.py -v

# Configuration tests
pytest tests/test_config.py -v

# Core runtime tests
pytest tests/test_core_runtime.py -v
```

### 2. Installation Testing Matrix
```bash
# Test different installation modes
pip install dist/TATty_agent-*.whl                    # Base installation
pip install "dist/TATty_agent-*.whl[tui]"             # With TUI
pip install "dist/TATty_agent-*.whl[jupyter]"         # With Jupyter
pip install "dist/TATty_agent-*.whl[full]"            # Full installation

# Test each installation mode
python -c "from tatty_agent import TattyAgent; print('✅ Base')"
python -c "from tatty_agent.tui import TattyApp; print('✅ TUI')" || echo "❌ TUI dependencies missing"
python -c "from tatty_agent.jupyter import create_quick_chat; print('✅ Jupyter')" || echo "❌ Jupyter dependencies missing"
```

### 3. Example Usage Testing
```bash
# Test project initialization
mkdir test_project && cd test_project
tatty-init
ls -la  # Verify folders created

# Test basic agent functionality
tatty-agent "List Python files in this directory"

# Test library usage
python -c "
from tatty_agent import TattyAgent, initialize_project
result = initialize_project('.', force=True)
print('✅ Library functions work')
"
```

## 📦 JFrog Platform Distribution

### 1. JFrog Configuration
```bash
# Configure JFrog CLI (if not already done)
jf config add

# Set up repository configuration
# Repository URL: your-domain.jfrog.io/artifactory/pypi-local/
# Authentication: API key or username/password
```

### 2. Package Metadata Validation
```bash
# Verify package metadata
python -c "
import pkg_resources
import tomllib

# Check pyproject.toml
with open('pyproject.toml', 'rb') as f:
    config = tomllib.load(f)

required_fields = ['name', 'version', 'description', 'authors', 'dependencies']
missing = [field for field in required_fields if field not in config['project']]

if missing:
    print('❌ Missing required fields:', missing)
else:
    print('✅ All required metadata present')

print('Package:', config['project']['name'])
print('Version:', config['project']['version'])
print('Description:', config['project']['description'])
"
```

### 3. Upload to JFrog
```bash
# Option 1: Using JFrog CLI
jf rt upload "dist/*" pypi-local/TATty-agent/ \
    --build-name=TATty-agent \
    --build-number=${BUILD_NUMBER:-1}

# Option 2: Using twine (if JFrog supports PyPI protocol)
twine upload --repository-url https://your-domain.jfrog.io/artifactory/api/pypi/pypi-local dist/*

# Option 3: Direct upload via REST API
for file in dist/*; do
    curl -X PUT \
        -T "$file" \
        -H "Authorization: Bearer $JFROG_API_KEY" \
        "https://your-domain.jfrog.io/artifactory/pypi-local/TATty-agent/$(basename $file)"
done
```

### 4. Installation Testing from JFrog
```bash
# Test installation from JFrog repository
pip install --index-url https://your-domain.jfrog.io/artifactory/api/pypi/pypi-local/simple/ \
    --trusted-host your-domain.jfrog.io \
    TATty-agent[full]

# Verify installation
python -c "
from tatty_agent import TattyAgent
print('✅ JFrog installation successful')
print('Version:', TattyAgent.__version__ if hasattr(TattyAgent, '__version__') else 'N/A')
"
```

## 🔄 Continuous Integration Setup

### GitHub Actions Workflow
```yaml
# .github/workflows/build-and-distribute.yml
name: Build and Distribute TATty Agent

on:
  push:
    tags:
      - 'v*'
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11, 3.12]

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pytest pytest-cov
        pip install -e .[full]

    - name: Run tests
      run: |
        pytest tests/ -v --cov=tatty_agent

  build-and-distribute:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install build dependencies
      run: |
        python -m pip install --upgrade pip build twine

    - name: Build package
      run: |
        python -m build

    - name: Upload to JFrog
      env:
        JFROG_API_KEY: ${{ secrets.JFROG_API_KEY }}
        JFROG_URL: ${{ secrets.JFROG_URL }}
      run: |
        # Upload using your preferred method
        twine upload --repository-url $JFROG_URL/api/pypi/pypi-local dist/*
```

## 📝 Release Process

### 1. Pre-Release
```bash
# Update version in pyproject.toml
# Update CHANGELOG.md
# Commit changes
git add .
git commit -m "Prepare release v1.0.0"

# Create and push tag
git tag v1.0.0
git push origin v1.0.0
```

### 2. Build and Test
```bash
# Clean build
rm -rf dist/ build/
python -m build

# Test build
pip install dist/TATty_agent-*.whl
python -c "from tatty_agent import TattyAgent; print('✅ Release build works')"
```

### 3. Distribution
```bash
# Upload to JFrog
# (Use your configured method from above)

# Verify installation from repository
pip uninstall TATty-agent -y
pip install --index-url https://your-domain.jfrog.io/... TATty-agent[full]
```

### 4. Post-Release
```bash
# Create GitHub release with changelog
# Update documentation
# Notify users of new version
# Update downstream dependencies if needed
```

## 🐛 Troubleshooting

### Common Build Issues

**Issue: Import errors during testing**
```bash
# Solution: Ensure proper package structure
find tatty_agent -name "__init__.py" -exec cat {} \;
```

**Issue: Missing dependencies**
```bash
# Solution: Verify all dependencies in pyproject.toml
pip install -e .[full]
pip check  # Verify no dependency conflicts
```

**Issue: CLI commands not working**
```bash
# Solution: Check entry points in pyproject.toml
python -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    config = tomllib.load(f)
print(config['project']['scripts'])
"
```

### JFrog Upload Issues

**Issue: Authentication failures**
```bash
# Verify credentials
jf rt ping
curl -H "Authorization: Bearer $JFROG_API_KEY" https://your-domain.jfrog.io/artifactory/api/system/ping
```

**Issue: Upload timeouts**
```bash
# Upload files individually
for file in dist/*; do
    echo "Uploading $file..."
    # Your upload command here
done
```

## 📊 Release Metrics

### Track These Metrics
- **Download counts** from JFrog repository
- **Installation success rates** across Python versions
- **Test coverage** percentage
- **Documentation completeness**
- **User feedback** and issue reports

### Post-Release Monitoring
```bash
# Check package availability
pip search TATty-agent || echo "Search may not be available"

# Verify latest version
pip index versions TATty-agent

# Test installation on clean environment
docker run --rm -it python:3.11 bash -c "
pip install TATty-agent[full] && python -c 'from tatty_agent import TattyAgent; print(\"✅ Docker test passed\")'
"
```

## 🔐 Security Considerations

### Before Distribution
- [ ] No hardcoded secrets or API keys
- [ ] Dependencies scanned for vulnerabilities
- [ ] Code signing if required by organization
- [ ] Security review for sensitive operations

### During Distribution
- [ ] HTTPS/TLS for all uploads
- [ ] API key management best practices
- [ ] Access logging enabled
- [ ] Repository permissions properly configured

---

This distribution guide ensures reliable, secure, and repeatable deployment of TATty Agent to the JFrog platform.