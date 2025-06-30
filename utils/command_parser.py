
from typing import Tuple, Optional

BOT_MENTION = "@pr-review-bot"

def parse_comment(comment_body: str) -> Optional[Tuple[str, str]]:
    """Parse a comment to find a bot command."""
    if not comment_body or BOT_MENTION not in comment_body:
        return None

    lines = comment_body.strip().splitlines()
    for line in lines:
        if BOT_MENTION in line:
            # Find the mention and get the text after it
            mention_index = line.find(BOT_MENTION)
            after_mention = line[mention_index + len(BOT_MENTION):].strip()
            parts = after_mention.split()
            if len(parts) > 0:
                command = parts[0]
                args = " ".join(parts[1:])
                return command, args
    return None
