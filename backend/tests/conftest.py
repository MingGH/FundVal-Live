"""Conftest: mock heavy/unavailable dependencies before app import."""
import sys
from unittest.mock import MagicMock

# Mock akshare (requires Python 3.13+ curl_cffi)
sys.modules["akshare"] = MagicMock()

# Mock langchain_openai (optional, heavy)
sys.modules["langchain_openai"] = MagicMock()
sys.modules["langchain_core"] = MagicMock()
sys.modules["langchain_core.prompts"] = MagicMock()
sys.modules["langchain_core.output_parsers"] = MagicMock()
