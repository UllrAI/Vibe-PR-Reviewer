
from utils.command_parser import parse_comment

def test_parse_comment_no_mention():
    assert parse_comment("This is a regular comment.") is None

def test_parse_comment_simple_command():
    assert parse_comment("@pr-review-bot re-review") == ("re-review", "")

def test_parse_comment_command_with_args():
    assert parse_comment("@pr-review-bot ask Please explain this function.") == ("ask", "Please explain this function.")

def test_parse_comment_multiline_comment():
    comment = "Hello there.\n@pr-review-bot re-review\nThanks!"
    assert parse_comment(comment) == ("re-review", "")

def test_parse_comment_command_at_end():
    assert parse_comment("Some text. @pr-review-bot status") == ("status", "")

def test_parse_comment_no_command_after_mention():
    assert parse_comment("@pr-review-bot") is None

def test_parse_comment_empty_string():
    assert parse_comment("") is None

def test_parse_comment_only_mention():
    assert parse_comment("@pr-review-bot ") is None
