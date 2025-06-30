import pytest
import os

@pytest.fixture(scope="session", autouse=True)
def set_test_environment():
    os.environ["GITHUB_TOKEN"] = "test_github_token"
    os.environ["GEMINI_API_KEY"] = "test_gemini_api_key"
