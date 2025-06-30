
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.ai_service import generate_review_comment

@pytest.mark.asyncio
async def test_generate_review_comment_success():
    mock_response_text = "Looks good!"
    with patch("google.generativeai.GenerativeModel") as MockGenerativeModel:
        mock_instance = MockGenerativeModel.return_value
        mock_instance.generate_content_async = AsyncMock(return_value=MagicMock(text=mock_response_text))

        comment = await generate_review_comment("diff content", "file.py")
        assert comment == mock_response_text
        mock_instance.generate_content_async.assert_called_once()

@pytest.mark.asyncio
async def test_generate_review_comment_with_custom_prompt():
    mock_response_text = "Custom review."
    custom_prompt = "Review {filename} for security issues. Diff: {file_diff}"
    with patch("google.generativeai.GenerativeModel") as MockGenerativeModel:
        mock_instance = MockGenerativeModel.return_value
        mock_instance.generate_content_async = AsyncMock(return_value=MagicMock(text=mock_response_text))

        comment = await generate_review_comment("diff content", "file.py", custom_prompt=custom_prompt)
        assert comment == mock_response_text
        mock_instance.generate_content_async.assert_called_once()
        args, kwargs = mock_instance.generate_content_async.call_args
        assert "security issues" in args[0]
        assert "file.py" in args[0]

@pytest.mark.asyncio
async def test_generate_review_comment_error():
    with patch("google.generativeai.GenerativeModel") as MockGenerativeModel:
        mock_instance = MockGenerativeModel.return_value
        mock_instance.generate_content_async.side_effect = Exception("AI error")

        comment = await generate_review_comment("diff content", "file.py")
        assert "[AI Review Failed for file.py: AI error]" in comment
        mock_instance.generate_content_async.assert_called_once()
