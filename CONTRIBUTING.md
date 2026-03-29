# Contributing to Telegram-Obsidian Bot

Thank you for your interest in contributing! This guide will help you get started.

## How to Contribute

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally: `git clone https://github.com/<your-username>/telegram-obsidian-bot.git`
3. **Create a branch** for your change: `git checkout -b feature/my-feature`
4. **Make your changes**, commit with clear messages.
5. **Push** to your fork: `git push origin feature/my-feature`
6. **Open a Pull Request** against the `main` branch.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- An Obsidian vault directory

### Installation

```bash
git clone https://github.com/<your-username>/telegram-obsidian-bot.git
cd telegram-obsidian-bot
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration values
```

### Environment Variables

Copy `.env.example` to `.env` and fill in the required values. Never commit your `.env` file.

## Code Style Guidelines

- Follow the existing code patterns and structure in the project.
- Use type hints where possible.
- Keep functions focused and single-purpose.
- Write descriptive variable and function names.
- Add docstrings for public functions and classes.

## Running Tests

```bash
pytest
```

Run tests before submitting a PR to ensure nothing is broken.

## Reporting Bugs

- Use the [Bug Report](https://github.com/<owner>/telegram-obsidian-bot/issues/new?template=bug_report.md) issue template.
- Include steps to reproduce, expected vs. actual behavior, and your environment details.
- Attach logs or screenshots if applicable.

## Feature Requests

- Use the [Feature Request](https://github.com/<owner>/telegram-obsidian-bot/issues/new?template=feature_request.md) issue template.
- Clearly describe the problem you want to solve and your proposed solution.
- Check existing issues first to avoid duplicates.

## Pull Request Guidelines

- Keep PRs focused on a single change.
- Reference related issues in the PR description (e.g., `Closes #12`).
- Ensure all tests pass before requesting review.
- Do not commit secrets, credentials, or `.env` files.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
