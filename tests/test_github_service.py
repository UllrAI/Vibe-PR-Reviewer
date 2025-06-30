import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from services.github_service import get_file_content, get_pr_diff, get_pull_request, post_review

@pytest.mark.asyncio
async def test_get_file_content_success():
    mock_response = {"content": "ZmlsZSBjb250ZW50", "encoding": "base64"}
    with patch("httpx.AsyncClient") as MockAsyncClient:
        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
        mock_client_instance.get.return_value = AsyncMock(status_code=200, json=AsyncMock(return_value=mock_response), raise_for_status=MagicMock())

        content = await get_file_content("owner/repo", "path/to/file.txt", "sha123")
        assert content == "file content"
        mock_client_instance.get.assert_called_once()

@pytest.mark.asyncio
async def test_get_file_content_not_found():
    with patch("httpx.AsyncClient") as MockAsyncClient:
        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
        mock_client_instance.get.return_value = AsyncMock(status_code=404, raise_for_status=MagicMock(side_effect=httpx.HTTPStatusError("Not Found", request=httpx.Request("GET", "url"), response=httpx.Response(404))))

        content = await get_file_content("owner/repo", "nonexistent.txt", "sha123")
        assert content is None
        mock_client_instance.get.assert_called_once()

@pytest.mark.asyncio
async def test_get_pr_diff_success():
    mock_diff = "diff --git a/file.txt b/file.txt\nindex..."
    with patch("httpx.AsyncClient") as MockAsyncClient:
        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
        mock_client_instance.get.return_value = AsyncMock(status_code=200, text=mock_diff, raise_for_status=MagicMock())

        diff = await get_pr_diff("owner/repo", 123)
        assert diff == mock_diff
        mock_client_instance.get.assert_called_once()

@pytest.mark.asyncio
async def test_get_pull_request_success():
    mock_pr_data = {"number": 123, "head": {"sha": "abc"}}
    with patch("httpx.AsyncClient") as MockAsyncClient:
        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
        mock_client_instance.get.return_value = AsyncMock(status_code=200, json=AsyncMock(return_value=mock_pr_data), raise_for_status=MagicMock())

        pr_data = await get_pull_request("owner/repo", 123)
        assert pr_data == mock_pr_data
        mock_client_instance.get.assert_called_once()

@pytest.mark.asyncio
async def test_post_review_success():
    with patch("httpx.AsyncClient") as MockAsyncClient:
        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
        mock_client_instance.post.return_value = AsyncMock(status_code=201, raise_for_status=MagicMock())

        comments = [{
            "path": "file.txt",
            "position": 1,
            "body": "Test comment"
        }]
        await post_review("owner/repo", 123, "abc", comments)
        mock_client_instance.post.assert_called_once()
        args, kwargs = mock_client_instance.post.call_args
        assert kwargs["json"]["comments"][0]["body"] == "Test comment"