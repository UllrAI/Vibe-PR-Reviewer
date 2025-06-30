
import logging

from core.repo_config import RepoConfig
from services.github_service import get_pr_diff, post_review
from services.ai_service import generate_review_comment
from utils.diff_parser import parse_diff

logger = logging.getLogger("pr_review_bot.review_service")

async def review_pull_request(repo_full_name: str, pr_number: int, head_sha: str, config: RepoConfig):
    logger.info(f"Starting review for PR #{pr_number} in {repo_full_name}")
    logger.info(f"Using config: {config.model_dump_json(indent=2)}")
    
    try:
        pr_diff = await get_pr_diff(repo_full_name, pr_number)
        if not pr_diff:
            logger.info(f"No diff found for PR #{pr_number}. Skipping review.")
            return

        parsed_files = parse_diff(pr_diff)
        
        comments_to_post = []
        for file_change in parsed_files:
            file_path = file_change["file_path"]
            file_diff = file_change["diff"]
            
            # Apply include/exclude filters
            if config.exclude_paths and any(file_path.startswith(p) for p in config.exclude_paths):
                logger.info(f"Excluding {file_path} based on config.")
                continue
            if config.include_paths and not any(file_path.startswith(p) for p in config.include_paths):
                logger.info(f"Excluding {file_path} as it's not in include_paths.")
                continue

            logger.info(f"Reviewing file: {file_path}")
            review_comment_body = await generate_review_comment(
                file_diff=file_diff,
                filename=file_path,
                custom_prompt=config.custom_prompt,
                output_language=config.review_language
            )
            
            # Find the line number to comment on. For simplicity, we'll comment on the first changed line.
            # In a real scenario, you'd parse hunks to find specific lines.
            position = None
            if file_change["hunks"]:
                # Find the first line that is actually changed (starts with + or -)
                for hunk in file_change["hunks"]:
                    for line_idx, line_content in enumerate(hunk["lines"]):
                        if line_content.startswith("+") or line_content.startswith("-"):
                            # Position is 1-indexed relative to the start of the diff hunk
                            # For simplicity, we'll just use the target_start_line for now.
                            # A more robust solution would involve mapping diff lines to actual file lines.
                            position = hunk["target_start_line"] + line_idx
                            break
                    if position is not None:
                        break

            if review_comment_body and review_comment_body != "No issues found." and position is not None:
                comments_to_post.append({
                    "path": file_path,
                    "position": position,
                    "body": review_comment_body
                })
            else:
                logger.info(f"No significant comments generated for {file_path} or no suitable position found.")
        
        if comments_to_post:
            logger.info(f"Posting {len(comments_to_post)} comments to PR #{pr_number}.")
            await post_review(repo_full_name, pr_number, head_sha, comments=comments_to_post)
            logger.info("Review posted successfully.")
        else:
            logger.info(f"No comments to post for PR #{pr_number}.")

    except Exception as e:
        logger.error(f"Error during PR review for #{pr_number} in {repo_full_name}: {e}", exc_info=True)
        # TODO: Optionally post a comment to GitHub about the error
