# MeshML Code Quality Standards

## Overview

This document outlines the code quality standards and tooling used in the MeshML project.

## Automated Code Quality

### Pre-commit Hooks

All code is automatically checked before commits using [pre-commit](https://pre-commit.com/).

**Setup:**
```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Python Standards

### Formatting: Black

- **Line length**: 100 characters
- **Target**: Python 3.11+
- **Style**: PEP 8 compliant

**Usage:**
```bash
black services/api-gateway/app/
```

### Linting: Ruff

Fast Python linter (10-100x faster than Flake8).

**Rules enabled:**
- E/W: pycodestyle errors and warnings
- F: pyflakes
- I: isort (import sorting)
- C: flake8-comprehensions
- B: flake8-bugbear
- UP: pyupgrade

**Usage:**
```bash
ruff check services/api-gateway/
ruff check --fix services/api-gateway/  # Auto-fix
```

### Type Checking: mypy

Static type checker for Python.

**Configuration:**
- `python_version = "3.11"`
- `check_untyped_defs = true`
- `warn_return_any = true`

**Usage:**
```bash
mypy services/api-gateway/app/
```

### Import Sorting: isort

Automatically sort imports.

**Profile**: Black-compatible

**Usage:**
```bash
isort services/api-gateway/app/
```

### Testing: pytest

**Minimum coverage**: 80%

**Configuration:**
```bash
pytest tests/ -v --cov=app --cov-report=html
```

Coverage reports are generated in `htmlcov/`.

## JavaScript/TypeScript Standards

### Formatting: Prettier

- **Print width**: 100 characters
- **Semi-colons**: Always
- **Quotes**: Single
- **Trailing commas**: ES5

**Usage:**
```bash
npm run format          # Auto-format
npm run format:check    # Check only
```

### Linting: ESLint

- **Config**: Airbnb base + TypeScript
- **Parser**: @typescript-eslint

**Usage:**
```bash
npm run lint
npm run lint:fix
```

### Type Checking: TypeScript

- **Target**: ES2020
- **Strict mode**: Enabled
- **Module**: ESNext

**Usage:**
```bash
npm run type-check
```

### Testing: Jest

**Minimum coverage**: 80% (dashboard), 75% (worker)

**Usage:**
```bash
npm test
npm test -- --coverage
```

## C++ Standards

### Formatting: clang-format

- **Style**: Google C++ Style Guide
- **Indent**: 4 spaces
- **Line length**: 100 characters
- **Standard**: C++17

**Usage:**
```bash
clang-format -i workers/cpp-worker/src/*.cpp
```

### Build: CMake

**Minimum version**: 3.20

**Configuration:**
```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

### Testing: Google Test

**Usage:**
```bash
cd workers/cpp-worker/build
ctest --verbose
```

## Configuration Files

### Python
- `pyproject.toml` - Black, isort, Ruff, mypy, pytest configs
- `.flake8` - (Deprecated, using Ruff)

### JavaScript/TypeScript
- `.eslintrc.js` - ESLint configuration
- `.prettierrc.json` - Prettier formatting
- `tsconfig.json` - TypeScript compiler options
- `jest.config.js` - Jest testing configuration

### C++
- `.clang-format` - Formatting rules
- `CMakeLists.txt` - Build configuration

### General
- `.editorconfig` - Editor-agnostic settings
- `.pre-commit-config.yaml` - Pre-commit hooks

## CI/CD Integration

All checks run automatically in GitHub Actions:

- **Python CI**: Black, Ruff, mypy, pytest
- **C++ CI**: clang-format, CMake build, Google Test
- **JavaScript CI**: ESLint, Prettier, TypeScript, Jest

**Branches**: `main`, `develop`

**Required checks**: All must pass before merge

## Code Review Checklist

Before submitting a PR:

- [ ] All pre-commit hooks pass
- [ ] Code is formatted (Black/Prettier/clang-format)
- [ ] No linting errors (Ruff/ESLint)
- [ ] Type checking passes (mypy/TypeScript)
- [ ] Tests pass with >80% coverage
- [ ] No security vulnerabilities (detect-secrets)
- [ ] Documentation updated
- [ ] Commit messages follow Conventional Commits

## Coverage Requirements

| Component | Minimum Coverage |
|-----------|------------------|
| Python services | 80% |
| Dashboard (React) | 80% |
| JS Worker | 75% |
| C++ Worker | 70% |

## Ignoring Checks

**Use sparingly!**

### Python
```python
# type: ignore  # mypy
# noqa: E501   # ruff/flake8
# pragma: no cover  # coverage
```

### TypeScript
```typescript
// eslint-disable-next-line @typescript-eslint/no-explicit-any
// @ts-ignore
```

### C++
```cpp
// clang-format off
// ... code ...
// clang-format on
```

## Local Development

### Run all checks locally:

```bash
# Python
black . && ruff check . && mypy services/*/app && pytest

# JavaScript (dashboard)
cd dashboard
npm run lint && npm run format:check && npm run type-check && npm test

# C++
cd workers/cpp-worker
clang-format -i src/**/*.{cpp,h}
cmake --build build && cd build && ctest
```

### Quick fix:

```bash
# Python
black . && ruff check --fix . && isort .

# JavaScript
npm run lint:fix && npm run format
```

## Resources

- [Black documentation](https://black.readthedocs.io/)
- [Ruff documentation](https://docs.astral.sh/ruff/)
- [mypy documentation](https://mypy.readthedocs.io/)
- [ESLint rules](https://eslint.org/docs/rules/)
- [Prettier options](https://prettier.io/docs/en/options.html)
- [Google C++ Style Guide](https://google.github.io/styleguide/cppguide.html)
