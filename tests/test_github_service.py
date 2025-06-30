import pytest
import httpx
from unittest.mock import AsyncMock, patch

from services.github_service import get_file_content, get_pr_diff, get_pull_request, post_review

@pytest.mark.asyncio
async def test_get_file_content_success():
    mock_response = {"content": "ZmlsZSBjb250ZW50", "encoding": "base64"}
    with patch("httpx.AsyncClient") as MockAsyncClient:
        mock_instance = MockAsyncClient.return_value
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status.return_value = None
        mock_instance.get.return_value = mock_response_obj

        content = await get_file_content("owner/repo", "path/to/file.txt", "sha123")
        assert content == "file content"
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_get_file_content_not_found():
    with patch("httpx.AsyncClient") as MockAsyncClient:
        mock_instance = MockAsyncClient.return_value
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status.return_value = None
        mock_instance.get.return_value = mock_response_obj

        content = await get_file_content("owner/repo", "nonexistent.txt", "sha123")
        assert content is None
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_get_pr_diff_success():
    mock_diff = "diff --git a/file.txt b/file.txt\nindex..."
    with patch("httpx.AsyncClient") as MockAsyncClient:
        mock_instance = MockAsyncClient.return_value
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status.return_value = None
        mock_instance.get.return_value = mock_response_obj

        diff = await get_pr_diff("owner/repo", 123)
        assert diff == mock_diff
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_get_pull_request_success():
    mock_pr_data = {"number": 123, "head": {"sha": "abc"}}
    with patch("httpx.AsyncClient") as MockAsyncClient:
        mock_instance = MockAsyncClient.return_value
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status.return_value = None
        mock_instance.get.return_value = mock_response_obj

        pr_data = await get_pull_request("owner/repo", 123)
        assert pr_data == mock_pr_data
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_post_review_success():
    with patch("httpx.AsyncClient") as MockAsyncClient:
        mock_instance = MockAsyncClient.return_value
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 201
        mock_response_obj.raise_for_status.return_value = None
        mock_instance.post.return_value = mock_response_obj

        comments = [{
            "path": "file.txt",
            "position": 1,
            "body": "Test comment"
        }]
        await post_review("owner/repo", 123, "abc", comments)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["comments"][0]["body"] == "Test comment"
