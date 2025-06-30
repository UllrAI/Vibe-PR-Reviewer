
import base64
import logging

import httpx

from core.config import settings

logger = logging.getLogger("pr_review_bot.github_service")

BASE_URL = "https://api.github.com"

async def get_pull_request(repo_full_name: str, pr_number: int) -> dict:
    """Get details of a specific pull request."""
    url = f"{BASE_URL}/repos/{repo_full_name}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=settings.REQUEST_TIMEOUT)
        response.raise_for_status()
        return await response.json()

async def get_pr_diff(repo_full_name: str, pr_number: int) -> str:
    """Get the diff of a pull request."""
    url = f"{BASE_URL}/repos/{repo_full_name}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.diff",
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=settings.REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.text

async def post_review(repo_full_name: str, pr_number: int, commit_id: str, comments: list[dict]):
    """Post a review with multiple comments to a pull request."""
    url = f"{BASE_URL}/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {
        "commit_id": commit_id,
        "event": "COMMENT",
        "comments": comments,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data, timeout=settings.REQUEST_TIMEOUT)
        response.raise_for_status()

async def get_file_content(repo_full_name: str, file_path: str, ref: str) -> str | None:
    """Get the content of a file from a GitHub repository."""
    url = f"{BASE_URL}/repos/{repo_full_name}/contents/{file_path}?ref={ref}"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            data = await response.json()
            if data.get("encoding") == "base64":
                return base64.b64decode(data["content"]).decode("utf-8")
            return data.get("content")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"File not found: {file_path} in {repo_full_name}")
                return None
            raise
