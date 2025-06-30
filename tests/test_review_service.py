
import pytest
from unittest.mock import AsyncMock, patch

from services.review_service import review_pull_request
from core.repo_config import RepoConfig

@pytest.mark.asyncio
async def test_review_pull_request_no_diff():
    with (patch("services.review_service.get_pr_diff", new_callable=AsyncMock) as mock_get_pr_diff,
          patch("services.review_service.parse_diff") as mock_parse_diff,
          patch("services.review_service.generate_review_comment", new_callable=AsyncMock) as mock_generate_review_comment,
          patch("services.review_service.post_review", new_callable=AsyncMock) as mock_post_review):
        
        mock_get_pr_diff.return_value = ""
        
        await review_pull_request("owner/repo", 123, "sha123", RepoConfig())
        
        mock_get_pr_diff.assert_called_once_with("owner/repo", 123)
        mock_parse_diff.assert_not_called()
        mock_generate_review_comment.assert_not_called()
        mock_post_review.assert_not_called()

@pytest.mark.asyncio
async def test_review_pull_request_with_comments():
    mock_diff = """
diff --git a/file1.py b/file1.py
index abc..def 100644
--- a/file1.py
+++ b/file1.py
@@ -1,1 +1,2 @@
-old line
+new line
"""
    mock_parsed_diff = [
        {
            "file_path": "file1.py",
            "diff": "+new line",
            "hunks": [{
                "source_start_line": 1,
                "target_start_line": 1,
                "lines": ["-old line", "+new line"]
            }]
        }
    ]
    mock_ai_comment = "This is a review comment."

    with (patch("services.review_service.get_pr_diff", new_callable=AsyncMock) as mock_get_pr_diff,
          patch("services.review_service.parse_diff") as mock_parse_diff,
          patch("services.review_service.generate_review_comment", new_callable=AsyncMock) as mock_generate_review_comment,
          patch("services.review_service.post_review", new_callable=AsyncMock) as mock_post_review):
        
        mock_get_pr_diff.return_value = mock_diff
        mock_parse_diff.return_value = mock_parsed_diff
        mock_generate_review_comment.return_value = mock_ai_comment
        
        await review_pull_request("owner/repo", 123, "sha123", RepoConfig())
        
        mock_get_pr_diff.assert_called_once_with("owner/repo", 123)
        mock_parse_diff.assert_called_once_with(mock_diff)
        mock_generate_review_comment.assert_called_once()
        mock_post_review.assert_called_once()
        args, kwargs = mock_post_review.call_args
        assert kwargs["comments"][0]["body"] == mock_ai_comment
        assert kwargs["comments"][0]["path"] == "file1.py"
        assert kwargs["comments"][0]["position"] == 2 # +new line is the second line in the hunk

@pytest.mark.asyncio
async def test_review_pull_request_no_ai_comments():
    mock_diff = """
diff --git a/file1.py b/file1.py
index abc..def 100644
--- a/file1.py
+++ b/file1.py
@@ -1,1 +1,2 @@
-old line
+new line
"""
    mock_parsed_diff = [
        {
            "file_path": "file1.py",
            "diff": "+new line",
            "hunks": [{
                "source_start_line": 1,
                "target_start_line": 1,
                "lines": ["-old line", "+new line"]
            }]
        }
    ]
    mock_ai_comment = "No issues found."

    with (patch("services.review_service.get_pr_diff", new_callable=AsyncMock) as mock_get_pr_diff,
          patch("services.review_service.parse_diff") as mock_parse_diff,
          patch("services.review_service.generate_review_comment", new_callable=AsyncMock) as mock_generate_review_comment,
          patch("services.review_service.post_review", new_callable=AsyncMock) as mock_post_review):
        
        mock_get_pr_diff.return_value = mock_diff
        mock_parse_diff.return_value = mock_parsed_diff
        mock_generate_review_comment.return_value = mock_ai_comment
        
        await review_pull_request("owner/repo", 123, "sha123", RepoConfig())
        
        mock_get_pr_diff.assert_called_once()
        mock_parse_diff.assert_called_once()
        mock_generate_review_comment.assert_called_once()
        mock_post_review.assert_not_called() # No comments should be posted

@pytest.mark.asyncio
async def test_review_pull_request_with_exclude_paths():
    mock_diff = """
diff --git a/src/docs/README.md b/src/docs/README.md
index abc..def 100644
--- a/src/docs/README.md
+++ b/src/docs/README.md
@@ -1,1 +1,2 @@
-old line
+new line
"""
    mock_parsed_diff = [
        {
            "file_path": "src/docs/README.md",
            "diff": "+new line",
            "hunks": [{
                "source_start_line": 1,
                "target_start_line": 1,
                "lines": ["-old line", "+new line"]
            }]
        }
    ]
    repo_config = RepoConfig(exclude_paths=["src/docs"])

    with (patch("services.review_service.get_pr_diff", new_callable=AsyncMock) as mock_get_pr_diff,
          patch("services.review_service.parse_diff") as mock_parse_diff,
          patch("services.review_service.generate_review_comment", new_callable=AsyncMock) as mock_generate_review_comment,
          patch("services.review_service.post_review", new_callable=AsyncMock) as mock_post_review):
        
        mock_get_pr_diff.return_value = mock_diff
        mock_parse_diff.return_value = mock_parsed_diff
        
        await review_pull_request("owner/repo", 123, "sha123", repo_config)
        
        mock_get_pr_diff.assert_called_once()
        mock_parse_diff.assert_called_once()
        mock_generate_review_comment.assert_not_called() # Should be skipped due to exclude_paths
        mock_post_review.assert_not_called()
