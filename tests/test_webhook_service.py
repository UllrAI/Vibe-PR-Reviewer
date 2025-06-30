
import pytest
from unittest.mock import AsyncMock, patch

from services.webhook_service import handle_webhook_event
from core.repo_config import RepoConfig

@pytest.mark.asyncio
async def test_handle_pull_request_opened():
    payload = {
        "action": "opened",
        "repository": {"full_name": "owner/repo"},
        "pull_request": {"number": 1, "head": {"sha": "abc"}}
    }
    with (patch("services.webhook_service.get_repo_config", new_callable=AsyncMock) as mock_get_repo_config,
          patch("services.webhook_service.review_pull_request", new_callable=AsyncMock) as mock_review_pull_request):
        
        mock_get_repo_config.return_value = RepoConfig()
        
        await handle_webhook_event("pull_request", payload)
        
        mock_get_repo_config.assert_called_once_with("owner/repo", "abc")
        mock_review_pull_request.assert_called_once_with("owner/repo", 1, "abc", RepoConfig())

@pytest.mark.asyncio
async def test_handle_issue_comment_re_review_command():
    payload = {
        "action": "created",
        "issue": {"number": 1, "pull_request": {}},
        "comment": {"body": "@pr-review-bot re-review"},
        "repository": {"full_name": "owner/repo"}
    }
    mock_pr_data = {"head": {"sha": "def"}}
    with (patch("services.webhook_service.parse_comment") as mock_parse_comment,
          patch("services.webhook_service.get_pull_request", new_callable=AsyncMock) as mock_get_pull_request,
          patch("services.webhook_service.get_repo_config", new_callable=AsyncMock) as mock_get_repo_config,
          patch("services.webhook_service.review_pull_request", new_callable=AsyncMock) as mock_review_pull_request):
        
        mock_parse_comment.return_value = ("re-review", "")
        mock_get_pull_request.return_value = mock_pr_data
        mock_get_repo_config.return_value = RepoConfig()

        await handle_webhook_event("issue_comment", payload)
        
        mock_parse_comment.assert_called_once_with("@pr-review-bot re-review")
        mock_get_pull_request.assert_called_once_with("owner/repo", 1)
        mock_get_repo_config.assert_called_once_with("owner/repo", "def")
        mock_review_pull_request.assert_called_once_with("owner/repo", 1, "def", RepoConfig())

@pytest.mark.asyncio
async def test_handle_issue_comment_no_command():
    payload = {
        "action": "created",
        "issue": {"number": 1, "pull_request": {}},
        "comment": {"body": "This is a regular comment."},
        "repository": {"full_name": "owner/repo"}
    }
    with (patch("services.webhook_service.parse_comment") as mock_parse_comment,
          patch("services.webhook_service.get_pull_request", new_callable=AsyncMock) as mock_get_pull_request,
          patch("services.webhook_service.get_repo_config", new_callable=AsyncMock) as mock_get_repo_config,
          patch("services.webhook_service.review_pull_request", new_callable=AsyncMock) as mock_review_pull_request):
        
        mock_parse_comment.return_value = None

        await handle_webhook_event("issue_comment", payload)
        
        mock_parse_comment.assert_called_once_with("This is a regular comment.")
        mock_get_pull_request.assert_not_called()
        mock_get_repo_config.assert_not_called()
        mock_review_pull_request.assert_not_called()
