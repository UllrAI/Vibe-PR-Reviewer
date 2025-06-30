
import logging

from core.repo_config import get_repo_config
from services.review_service import review_pull_request
from services.github_service import get_pull_request
from utils.command_parser import parse_comment

logger = logging.getLogger("pr_review_bot.webhook_service")

async def handle_webhook_event(event_type: str, payload: dict):
    logger.info(f"Handling event: {event_type}")
    
    if event_type == "pull_request":
        action = payload.get("action")
        if action in ["opened", "synchronize", "reopened"]:
            repo_full_name = payload["repository"]["full_name"]
            pr_number = payload["pull_request"]["number"]
            head_sha = payload["pull_request"]["head"]["sha"]
            
            logger.info(f"Processing PR #{pr_number} in {repo_full_name} ({action})")
            
            repo_config = await get_repo_config(repo_full_name, head_sha)
            await review_pull_request(repo_full_name, pr_number, head_sha, repo_config)
            
    elif event_type == "issue_comment":
        action = payload.get("action")
        if action == "created" and "pull_request" in payload["issue"]:
            repo_full_name = payload["repository"]["full_name"]
            pr_number = payload["issue"]["number"]
            comment_body = payload["comment"]["body"]
            
            command = parse_comment(comment_body)
            if not command:
                return

            cmd, args = command
            logger.info(f"Received command: '{cmd}' with args: '{args}' for PR #{pr_number}")

            if cmd == "re-review":
                pr_data = await get_pull_request(repo_full_name, pr_number)
                head_sha = pr_data["head"]["sha"]
                repo_config = await get_repo_config(repo_full_name, head_sha)
                await review_pull_request(repo_full_name, pr_number, head_sha, repo_config)
    else:
        logger.info(f"Ignoring event type: {event_type}")
