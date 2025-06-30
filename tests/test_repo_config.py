
import pytest
from unittest.mock import AsyncMock, patch

from core.repo_config import get_repo_config, RepoConfig, CONFIG_FILE_PATH

@pytest.mark.asyncio
async def test_get_repo_config_exists():
    mock_content = """
exclude_paths:
  - src/docs
  - tests/
review_language: chinese
custom_prompt: "Review this code for {filename} in {output_language}."
"""
    with patch("core.repo_config.get_file_content", new_callable=AsyncMock) as mock_get_file_content:
        mock_get_file_content.return_value = mock_content
        
        config = await get_repo_config("owner/repo", "sha123")
        
        mock_get_file_content.assert_called_once_with("owner/repo", CONFIG_FILE_PATH, "sha123")
        assert config.exclude_paths == ["src/docs", "tests/"]
        assert config.review_language == "chinese"
        assert config.custom_prompt == "Review this code for {filename} in {output_language}."

@pytest.mark.asyncio
async def test_get_repo_config_not_exists():
    with patch("core.repo_config.get_file_content", new_callable=AsyncMock) as mock_get_file_content:
        mock_get_file_content.return_value = None
        
        config = await get_repo_config("owner/repo", "sha123")
        
        mock_get_file_content.assert_called_once_with("owner/repo", CONFIG_FILE_PATH, "sha123")
        assert config == RepoConfig() # Should return default config

@pytest.mark.asyncio
async def test_get_repo_config_invalid_yaml():
    mock_content = """
invalid: yaml:
  - content
"""
    with patch("core.repo_config.get_file_content", new_callable=AsyncMock) as mock_get_file_content:
        mock_get_file_content.return_value = mock_content
        
        config = await get_repo_config("owner/repo", "sha123")
        
        mock_get_file_content.assert_called_once_with("owner/repo", CONFIG_FILE_PATH, "sha123")
        assert config == RepoConfig() # Should return default config on error

@pytest.mark.asyncio
async def test_get_repo_config_empty_yaml():
    mock_content = """
"""
    with patch("core.repo_config.get_file_content", new_callable=AsyncMock) as mock_get_file_content:
        mock_get_file_content.return_value = mock_content
        
        config = await get_repo_config("owner/repo", "sha123")
        
        mock_get_file_content.assert_called_once_with("owner/repo", CONFIG_FILE_PATH, "sha123")
        assert config == RepoConfig() # Should return default config
