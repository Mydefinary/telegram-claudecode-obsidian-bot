"""Common fixtures and path setup for telegram-obsidian-bot tests."""

import sys
import os

# Add project root to sys.path so source modules can be imported
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest


@pytest.fixture
def tmp_vault(tmp_path):
    """Create a temporary directory simulating an Obsidian vault."""
    vault_dir = tmp_path / "test_vault"
    vault_dir.mkdir()
    return vault_dir
