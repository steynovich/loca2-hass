# GitHub Actions CI/CD Pipeline

This document describes the GitHub Actions workflows implemented for the Loca2 Home Assistant integration.

## Workflows Overview

### 1. CI Workflow (`.github/workflows/ci.yml`)

**Triggers:** Push to `main`/`develop`, Pull Requests
**Purpose:** Main continuous integration pipeline

**Jobs:**
- **Test**: Runs on Python 3.11 and 3.12
  - Install uv package manager
  - Install dependencies with uv
  - Lint with Ruff (via uv run)
  - Format check with Black (via uv run)
  - Type check with MyPy (via uv run)
  - Run pytest with coverage (via uv run)
  - Upload coverage to Codecov

- **Validate**: Home Assistant integration validation
  - Run comprehensive validation tests
  - Run HACS validation tests
  - Validate manifest.json structure

- **HACS Validation**: Official HACS validation
  - Uses `hacs/action@main`
  - Validates integration category compliance

- **Hassfest**: Home Assistant official validation
  - Uses `home-assistant/actions/hassfest@master`
  - Validates Home Assistant integration standards

- **Integration Test**: End-to-end testing
  - Run integration tests
  - Run comprehensive validation
  - Run final validation tests

### 2. Release Workflow (`.github/workflows/release.yml`)

**Triggers:** Git tags matching `v*` pattern
**Purpose:** Automated release creation and asset publishing

**Jobs:**
- **Validate**: Pre-release validation
  - Run all tests with coverage
  - Run comprehensive validation
  - HACS validation
  - Home Assistant hassfest validation

- **Release**: Create GitHub release
  - Extract version from git tag
  - Update manifest.json version
  - Create release archive (ZIP)
  - Create GitHub release with changelog
  - Upload release assets

### 3. HACS Validation Workflow (`.github/workflows/hacs.yml`)

**Triggers:** Push to `main`, Pull Requests, Weekly schedule
**Purpose:** Dedicated HACS compatibility validation

**Jobs:**
- **HACS Validation**: Official HACS validation
- **Manifest Validation**: Detailed manifest.json validation
- **Strings Validation**: Validate strings.json structure
- **Integration Structure**: Validate file structure and required components

### 4. Home Assistant Validation (`.github/workflows/hassfest.yml`)

**Triggers:** Push to `main`/`develop`, Pull Requests
**Purpose:** Home Assistant official validation and integration testing

**Jobs:**
- **Hassfest**: Official Home Assistant validation
- **Integration Test**: Test integration loading and imports
- **Manifest Validation**: Home Assistant specific manifest validation
- **Async Validation**: Validate async implementation compliance

### 5. Code Quality Workflow (`.github/workflows/code-quality.yml`)

**Triggers:** Push to `main`/`develop`, Pull Requests
**Purpose:** Comprehensive code quality analysis

**Jobs:**
- **Lint**: Code linting and formatting
  - Ruff linting with GitHub annotations
  - Black formatting check
  - MyPy type checking

- **Security**: Security analysis
  - Bandit security scanning
  - Upload security reports as artifacts

- **Complexity**: Code complexity analysis
  - Radon cyclomatic complexity
  - Maintainability index
  - Xenon complexity validation

- **Documentation**: Documentation quality
  - Pydocstyle docstring validation

- **Dependency Check**: Security vulnerability scanning
  - Safety dependency vulnerability check
  - Upload safety reports as artifacts

## Configuration Files

### Development Dependencies (`pyproject.toml`)
- Testing: pytest, pytest-asyncio, pytest-cov
- Home Assistant: homeassistant, pytest-homeassistant-custom-component
- Code Quality: black, ruff, mypy, bandit
- Documentation: sphinx, sphinx-rtd-theme
- Package Management: uv for fast dependency resolution and installation

### Pre-commit Configuration (`.pre-commit-config.yaml`)
- Trailing whitespace removal
- End-of-file fixing
- YAML/JSON validation
- Black formatting
- Ruff linting
- MyPy type checking
- Custom manifest and strings validation

### Project Configuration (`pyproject.toml`)
- Build system configuration
- Black formatting settings
- Ruff linting configuration
- MyPy type checking settings
- Pytest configuration
- Coverage settings
- Bandit security settings
- Pydocstyle documentation settings

## Badges and Status

The following badges are available for the README:

```markdown
[![CI](https://github.com/username/loca2-hass/workflows/CI/badge.svg)](https://github.com/username/loca2-hass/actions/workflows/ci.yml)
[![HACS Validation](https://github.com/username/loca2-hass/workflows/HACS%20Validation/badge.svg)](https://github.com/username/loca2-hass/actions/workflows/hacs.yml)
[![Home Assistant Validation](https://github.com/username/loca2-hass/workflows/Home%20Assistant%20Validation/badge.svg)](https://github.com/username/loca2-hass/actions/workflows/hassfest.yml)
[![Code Quality](https://github.com/username/loca2-hass/workflows/Code%20Quality/badge.svg)](https://github.com/username/loca2-hass/actions/workflows/code-quality.yml)
[![codecov](https://codecov.io/gh/username/loca2-hass/branch/main/graph/badge.svg)](https://codecov.io/gh/username/loca2-hass)
```

## Automated Features

### Dependabot (`.github/dependabot.yml`)
- Weekly Python dependency updates
- Weekly GitHub Actions updates
- Automatic PR creation for security updates
- Configured reviewers and assignees

### Issue Templates
- **Bug Report**: Structured bug reporting with environment details
- **Feature Request**: Feature request template with use cases

### Pull Request Template
- Checklist for code quality and testing
- Type of change classification
- Testing verification requirements

## Security and Quality Gates

### Required Checks
All pull requests must pass:
- ✅ All test suites (Python 3.11 and 3.12)
- ✅ Code formatting (Black)
- ✅ Linting (Ruff)
- ✅ Type checking (MyPy)
- ✅ HACS validation
- ✅ Home Assistant hassfest validation
- ✅ Security scanning (Bandit)
- ✅ Integration validation tests

### Coverage Requirements
- Minimum test coverage maintained
- Coverage reports uploaded to Codecov
- Coverage trends tracked over time

### Security Scanning
- Bandit security analysis on every PR
- Safety dependency vulnerability scanning
- Automated security reports as artifacts

## Release Process

### Automated Release Creation
1. Create and push a git tag: `git tag v1.0.0 && git push origin v1.0.0`
2. GitHub Actions automatically:
   - Runs full validation suite
   - Updates manifest.json version
   - Creates release archive
   - Publishes GitHub release
   - Uploads release assets

### Version Management
- Semantic versioning (MAJOR.MINOR.PATCH)
- Automatic manifest.json version updates
- Release notes generation
- Asset packaging and distribution

## Monitoring and Maintenance

### Scheduled Workflows
- Weekly HACS validation to catch requirement changes
- Weekly dependency updates via Dependabot
- Automated security scanning

### Artifact Management
- Test coverage reports
- Security scan results
- Code quality metrics
- Release archives

### Notifications
- Failed workflow notifications
- Security vulnerability alerts
- Dependency update notifications

This comprehensive CI/CD pipeline ensures code quality, security, and compatibility while automating the release process for the Loca2 Home Assistant integration.