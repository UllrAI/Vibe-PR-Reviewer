
import logging

import google.generativeai as genai

from core.config import settings

logger = logging.getLogger("pr_review_bot.ai_service")

genai.configure(api_key=settings.GEMINI_API_KEY)

async def generate_review_comment(file_diff: str, filename: str, custom_prompt: str | None = None, output_language: str = "english") -> str:
    """Generate a review comment for a given file diff using the AI model."""
    model = genai.GenerativeModel(settings.AI_MODEL_NAME)
    
    prompt = f"""You are an AI assistant specialized in reviewing code. 
Review the following code changes for the file '{filename}'. 
Provide concise and actionable feedback. Focus on potential bugs, performance issues, security vulnerabilities, and best practices. 
If there are no issues, state 'No issues found.'.

Output language: {output_language}

Code Diff for {filename}:
```diff
{file_diff}
```
"""
    
    if custom_prompt:
        prompt = custom_prompt.format(filename=filename, file_diff=file_diff, output_language=output_language)

    try:
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error generating AI review for {filename}: {e}")
        return f"[AI Review Failed for {filename}: {e}]"
