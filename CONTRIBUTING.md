# Contributing to Ambivo Agents

We welcome contributions to the Ambivo Agents multi-agent AI system. This document provides guidelines for contributing to the project.

## ⚠️ Alpha Release Notice

**Ambivo Agents is currently in alpha stage.** Contributions are welcome as we work toward production readiness. Contributors should be aware that:

- APIs and interfaces may change significantly
- Breaking changes may occur between releases
- Documentation may be incomplete or outdated
- Testing coverage is still being expanded

Your contributions help move the project toward a stable release!

## About Ambivo Agents

Ambivo Agents is developed by Ambivo, Inc., a Nashville-based company specializing in AI and automation solutions. The project is maintained by Hemant Gosain 'Sunny' and the Ambivo team.

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- Python 3.11+
- Docker
- Redis access (Cloud Redis recommended, local Docker acceptable for development)
- Git

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/ambivo-agents.git
   cd ambivo-agents
   ```

2. **Install Dependencies**
   ```bash
   pip install -e .
   pip install -r requirements.txt
   ```

3. **Setup Configuration**
   - Copy `agent_config.yaml.example` to `agent_config.yaml`
   - Add your API keys and configuration settings
   - **Recommended**: Use cloud Redis and Qdrant for development
   - **Alternative**: Local services: `docker run -d -p 6379:6379 redis` and Qdrant locally

4. **Run Tests**
   ```bash
   python -m pytest tests/
   ```

5. **Verify Installation**
   ```bash
   python examples/basic_chat.py
   ```

## Contribution Guidelines

### Code Standards

- Follow PEP 8 Python style guidelines
- Use type hints where applicable
- Write clear, descriptive docstrings
- Keep functions focused and concise
- Add appropriate error handling
- **Alpha Considerations**: Be prepared for API changes and maintain flexibility in implementations

### Testing

- Write tests for new functionality
- Ensure existing tests pass
- Test with multiple LLM providers when applicable
- Include integration tests for new agents
- **Alpha Testing**: Given the alpha status, thorough testing is especially important. Test edge cases and error conditions extensively.

### Documentation

- Update README.md for new features
- Add docstrings to new classes and methods
- Include example usage in `/examples` directory
- Update configuration documentation as needed

## Types of Contributions

### Bug Reports

When reporting bugs, include:

- Python version and operating system
- Ambivo Agents version
- Steps to reproduce the issue
- Expected vs actual behavior
- Relevant logs or error messages
- Configuration details (with sensitive info redacted)

**Alpha-Specific Issues**: Please report any stability issues, unexpected behaviors, or performance problems you encounter. These reports are especially valuable during the alpha phase.

### Feature Requests

For new features:

- Describe the use case clearly
- Explain how it fits with existing functionality
- Provide examples of expected usage
- Consider backward compatibility

### Code Contributions

#### Agent Development

When creating new agents:

- Inherit from `BaseAgent` in `core/base.py`
- Implement required abstract methods
- Add comprehensive error handling
- Include example usage
- Update agent factory registration in `services/`
- Support both `.create()` and service-based instantiation

**Agent Creation Patterns:**
- `.create()` method: Returns `(agent, context)` for direct control
- Service method: Automatic routing and lifecycle management
- Both patterns should be supported for maximum flexibility

#### Core Components

When modifying `core/` components:

- `base.py`: Core agent classes and interfaces
- `llm.py`: Multi-provider LLM service
- `memory.py`: Redis-based memory management
- Maintain backward compatibility
- Add comprehensive tests

#### CLI Development

When updating `cli.py`:

- Follow Click framework patterns
- Add help text for new commands
- Include examples in docstrings
- Test with various input scenarios

#### Executor Development

For new executors in `executors/`:

- Follow existing executor patterns
- Ensure Docker compatibility where applicable
- Add appropriate timeouts and resource limits
- Test with various input types

#### Tool Development

When adding new tools to agents:

- Implement clear input/output schemas
- Add proper validation
- Include usage examples
- Consider security implications

## Submission Process

### Pull Request Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Write code following our standards
   - Add tests for new functionality
   - Update documentation

3. **Test Thoroughly**
   ```bash
   python -m pytest tests/
   python examples/your-example.py
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "Add: brief description of changes"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   - Open pull request on GitHub
   - Fill out PR template completely
   - Link any related issues

### Review Process

- All submissions require review
- Address reviewer feedback promptly
- Maintain clean commit history
- Ensure CI/CD passes
- **Alpha Flexibility**: During alpha, backward compatibility may be broken if necessary for stability or performance improvements

## Code of Conduct

### Our Standards

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Keep discussions professional

### Not Acceptable

- Harassment or discrimination
- Trolling or insulting comments
- Publishing private information
- Unethical or illegal activities

## Development Environment

### Recommended Tools

- **IDE**: VS Code with Python extension
- **Version Control**: Git
- **Testing**: pytest
- **Code Formatting**: black, isort
- **Linting**: flake8, mypy

### Configuration

All configuration is managed through `agent_config.yaml` in your project root. The system automatically loads:

- **LLM Provider Settings**: API keys, models, temperature
- **Redis Configuration**: Host, port, database settings  
- **Agent Capabilities**: Enable/disable specific features
- **Service Settings**: Timeouts, memory limits, Docker images

Example minimal configuration:
```yaml
# Redis Configuration (Cloud recommended)
redis:
  host: "your-redis-cloud-endpoint.redis.cloud"
  port: 6379
  password: "your-redis-password"

# LLM Configuration (Required)  
llm:
  preferred_provider: "openai"
  openai_api_key: "your-openai-key"

# Knowledge Base (Cloud Qdrant recommended)
knowledge_base:
  qdrant_url: "https://your-cluster.qdrant.tech"
  qdrant_api_key: "your-qdrant-api-key"

# Agent Capabilities
agent_capabilities:
  enable_knowledge_base: true
  enable_web_search: true
```

The system automatically sets environment variables internally from your YAML configuration.

## Project Structure

```
ambivo_agents/
├── agents/          # Agent implementations
│   ├── assistant.py
│   ├── code_executor.py
│   ├── knowledge_base.py
│   ├── media_editor.py
│   ├── simple_web_search.py
│   ├── web_scraper.py
│   ├── web_search.py
│   └── youtube_download.py
├── config/          # Configuration management
├── core/            # Core functionality (base classes, LLM, memory)
│   ├── base.py
│   ├── llm.py
│   └── memory.py
├── executors/       # Execution environments
├── services/        # Service layer
├── __init__.py      # Package initialization
├── cli.py          # Command line interface
├── examples/        # Usage examples
└── tests/           # Test suite
```

## Release Process

Releases are managed by the Ambivo team:

1. Version bump in `setup.py`
2. Update changelog
3. Create release tag
4. Publish to PyPI
5. Update documentation

## Getting Help

### Support Channels

- **Email**: dev-contributions@ambivo.com
- **Issues**: GitHub Issues for bugs and features
- **Documentation**: README.md and code examples

### Before Asking for Help

1. Check existing documentation
2. Search through existing issues
3. Try the examples in `/examples`
4. Review configuration settings

## Security

### Reporting Security Issues

Do not open public issues for security vulnerabilities. Instead:

- Email: dev-contributions@ambivo.com
- Include detailed reproduction steps
- Allow time for investigation and patching

### Security Best Practices

- Store API keys in environment variables
- Use Docker for isolated execution
- Validate all user inputs
- Follow principle of least privilege

## License

By contributing, you agree that your contributions will be licensed under the same MIT License that covers the project.

## Recognition

Contributors are recognized in:

- CONTRIBUTORS.md file
- Release notes for significant contributions
- README.md acknowledgments

---

**Thank you for contributing to Ambivo Agents!**

For questions about contributing, contact dev-contributions@ambivo.com or the Ambivo team.