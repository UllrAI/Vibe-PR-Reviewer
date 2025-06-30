
import logging
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field

from services.github_service import get_file_content

logger = logging.getLogger("pr_review_bot.repo_config")

CONFIG_FILE_PATH = ".pr-review-bot.yml"

class RepoConfig(BaseModel):
    exclude_paths: List[str] = Field(default_factory=list)
    include_paths: List[str] = Field(default_factory=list)
    review_language: str = "english"
    custom_prompt: Optional[str] = None

async def get_repo_config(repo_full_name: str, head_sha: str) -> RepoConfig:
    """Fetch and parse the repository-specific configuration file."""
    try:
        config_content = await get_file_content(repo_full_name, CONFIG_FILE_PATH, head_sha)
        if config_content:
            config_dict = yaml.safe_load(config_content)
            if config_dict:
                return RepoConfig(**config_dict)
    except Exception as e:
        logger.warning(f"Could not load or parse {CONFIG_FILE_PATH} from {repo_full_name}: {e}")
    
    return RepoConfig()
