# Contributing to MeshML

Thank you for your interest in contributing to MeshML! This document provides guidelines and instructions for contributing.

## 🎯 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/meshml.git
   cd meshml
   ```
3. **Set up the development environment** (see [local-setup.md](docs/development/local-setup.md))
4. **Create a feature branch**:
   ```bash
   git checkout -b feature/TASK-X.Y-description
   ```

## 📋 Finding Work

- Check [TASKS.md](TASKS.md) for the project roadmap
- Look for issues labeled `🎓 Good First Issue`
- Ask in GitHub Discussions if you need guidance

## 💻 Development Workflow

### 1. Code Standards

#### Python
- **Formatter**: Black (line length: 100)
- **Linter**: Ruff
- **Type Checking**: mypy
- **Docstrings**: Google style

```bash
# Format code
black services/api-gateway/app/

# Run linter
ruff check services/api-gateway/

# Type check
mypy services/api-gateway/app/
```

#### C++
- **Standard**: C++17
- **Formatter**: clang-format
- **Style Guide**: Google C++ Style Guide

```bash
# Format code
clang-format -i workers/cpp-worker/src/*.cpp
```

#### JavaScript/TypeScript
- **Formatter**: Prettier
- **Linter**: ESLint
- **Style**: Airbnb

```bash
# Format and lint
npm run format
npm run lint
```

### 2. Testing Requirements

- **Minimum Coverage**: 80%
- **Test Types**: Unit, Integration, E2E
- **Frameworks**: pytest (Python), Google Test (C++), Jest (JS)

```bash
# Python tests
pytest tests/ --cov=app --cov-report=html

# C++ tests
cd build && ctest

# JavaScript tests
npm test -- --coverage
```

### 3. Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, no logic change)
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(api-gateway): add job submission endpoint

Implements POST /api/v1/jobs with Pydantic validation
and database persistence.

Closes #123
```

```
fix(parameter-server): correct gradient averaging bug

The staleness weight was not applied correctly in edge cases
where version_id > threshold.
```

### 4. Pull Request Process

1. **Update your branch** with latest main:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all checks**:
   ```bash
   # Format
   black . && ruff check .
   
   # Tests
   pytest
   
   # Build (if applicable)
   docker build -t meshml/api-gateway .
   ```

3. **Push to your fork**:
   ```bash
   git push origin feature/TASK-X.Y-description
   ```

4. **Create Pull Request** with:
   - Clear title: `feat: Add gradient aggregation logic`
   - Description referencing task: `Implements TASK-6.2`
   - Screenshots/logs if UI/behavior change
   - Checklist:
     ```markdown
     - [ ] Tests pass
     - [ ] Code formatted
     - [ ] Documentation updated
     - [ ] No breaking changes (or documented)
     ```

5. **Address review feedback**
6. **Squash commits** if requested
7. **Wait for approval** from 2 maintainers

## 🏗️ Architecture Guidelines

### Adding a New Microservice

1. Create directory structure:
   ```
   services/your-service/
   ├── app/
   │   ├── __init__.py
   │   ├── main.py
   │   └── ...
   ├── tests/
   ├── Dockerfile
   └── requirements.txt
   ```

2. Follow existing patterns (see `api-gateway` as reference)

3. Add to `docker-compose.yml`

4. Update documentation

### Database Migrations

Use Alembic for schema changes:

```bash
cd database/migrations
alembic revision -m "Add worker_capacity column"
# Edit the generated file
alembic upgrade head
```

### Protocol Changes

When modifying `.proto` files:

1. Update the proto definition
2. Regenerate code:
   ```bash
   ./scripts/generate/proto_compile.sh
   ```
3. Update all affected services
4. Ensure backward compatibility

## 🐛 Reporting Bugs

Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md):

- **Clear title**: "Parameter server crashes on empty gradient"
- **Reproduction steps**
- **Expected vs actual behavior**
- **Environment details** (OS, versions)
- **Logs and stack traces**

## ✨ Requesting Features

Use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md):

- **Use case**: Why is this needed?
- **Proposed solution**
- **Alternatives considered**

## 🔒 Security Issues

**Do NOT open public issues for security vulnerabilities.**

Email: security@meshml.example.com

We'll respond within 48 hours.

## 📚 Documentation

- Update docs for any user-facing changes
- Use Markdown for documentation
- Include code examples
- Add diagrams (use Mermaid or PlantUML)

## 🎓 Learning Resources

New to distributed systems or ML?

- [Distributed Systems Course](https://example.com/dist-sys)
- [PyTorch Distributed Tutorial](https://pytorch.org/tutorials/beginner/dist_overview.html)
- [gRPC Basics](https://grpc.io/docs/what-is-grpc/introduction/)

## ❓ Questions?

- **GitHub Discussions**: For general questions
- **Discord**: [Join our server](https://discord.gg/meshml)
- **Office Hours**: Wednesdays 3-5 PM UTC

## 🙏 Code of Conduct

Be respectful, inclusive, and professional. We follow the [Contributor Covenant](https://www.contributor-covenant.org/).

## 📝 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for making MeshML better! 🚀
