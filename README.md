# PR Review Bot

*[中文](README.zh.md) | English*

An intelligent Pull Request code review bot based on Gemini AI that automatically performs in-depth code reviews on GitHub PRs and provides constructive improvement suggestions.

## Features

- 🤖 Intelligent code review based on Google Gemini AI
- 📝 Automatic generation of detailed review reports with issue identification and improvement suggestions
- 🔄 Support for automatic Webhook triggers and manual comment triggers (`/review`)
- 📁 Smart file context analysis for more accurate review opinions
- 🏷️ Automatic addition of review labels
- ⚡ Support for retry mechanisms and error handling
- 🛠️ Flexible environment variable configuration

## Demo

View actual operation results: [Example PR Review](https://github.com/UllrAI/Vibe-PR-Reviewer/pull/1)

## Installation and Deployment

### 1. Clone the Project

```bash
git clone <repository-url>
cd pr-review-bot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Variable Configuration

Copy the example configuration file and fill in actual values:

```bash
cp env.example .env
```

Then edit the `.env` file, or directly set the following environment variables:

#### Required Environment Variables

```bash
# GitHub Personal Access Token (requires repo permissions)
# How to get: GitHub Settings → Developer settings → Personal access tokens → Tokens
# Required permissions: Pull requests, Issues
GITHUB_TOKEN=your_github_token

# Google Gemini API Key
GEMINI_API_KEY=your_gemini_api_key
```

#### Optional Environment Variables

```bash
# AI model configuration
AI_MODEL_NAME=gemini-2.5-pro                    # Default: gemini-2.5-pro

# Review configuration
REVIEW_LABEL=ReviewedByUllrAI                   # Default: ReviewedByUllrAI
MAX_PROMPT_LENGTH=200000                        # Default: 200000
INCLUDE_FILE_CONTEXT=true                       # Default: true
CONTEXT_MAX_LINES=400                          # Default: 400
CONTEXT_SURROUNDING_LINES=50                   # Default: 50
MAX_FILES_PER_REVIEW=50                        # Default: 50

# Output language configuration
OUTPUT_LANGUAGE=english                        # Default: english (can be any language like "Chinese", "Japanese", etc.)

# Network and retry configuration
MAX_RETRY_ATTEMPTS=3                           # Default: 3
RETRY_DELAY=2.0                               # Default: 2.0
REQUEST_TIMEOUT=60                            # Default: 60

# Server configuration
PORT=5001                                     # Default: 5001
```

### 4. Start the Service

```bash
python app.py
```

The service will start on the specified port (default 5001).

### 5. GitHub Webhook Configuration

Configure Webhook in your GitHub repository:

1. Go to repository settings → Webhooks → Add webhook
2. Payload URL: `http://your-server:5001/webhook`
3. Content type: `application/json`
4. Events: Select `Pull requests` and `Issue comments`

**Note**: Currently no Webhook signature verification is required, no need to configure secret.

## Usage

### Automatic Review

The bot will automatically review the following events:

- When PR is created (`pull_request.opened`)
- When PR is updated (`pull_request.synchronize`)
- When PR is reopened (`pull_request.reopened`)

### Manual Review Trigger

Enter `/review` in PR comments to manually trigger code review.

## Configuration Instructions

### Core Configuration

- `GITHUB_TOKEN`: GitHub Personal Access Token, requires `repo` permissions
- `GEMINI_API_KEY`: Google Gemini API key

### AI Configuration

- `AI_MODEL_NAME`: Gemini model name to use
- `MAX_PROMPT_LENGTH`: Maximum prompt length sent to AI
- `INCLUDE_FILE_CONTEXT`: Whether to include complete file context for analysis

### Context Configuration

- `CONTEXT_MAX_LINES`: Maximum line limit for complete files
- `CONTEXT_SURROUNDING_LINES`: Number of context lines for code snippets
- `MAX_FILES_PER_REVIEW`: Maximum number of files per review

### Output Language Configuration

- `OUTPUT_LANGUAGE`: Specifies the language for AI review comments (default: english). Can be set to any language like "Chinese", "Japanese", "French", etc. If set to "english" or not configured, no language instruction will be added to AI prompts.

### Network Configuration

- `MAX_RETRY_ATTEMPTS`: Number of retries when API calls fail
- `RETRY_DELAY`: Retry interval time (seconds)
- `REQUEST_TIMEOUT`: HTTP request timeout (seconds)

## API Endpoints

### Health Check

```bash
GET /health
```

Returns service status and configuration information.

### Webhook Handling

```bash
POST /webhook
```

Receives GitHub Webhook events and handles PR reviews.

## Logging

The application uses structured logging to record all operations, including:

- GitHub API calls
- AI model calls
- Review process status
- Error and exception information

Log level is INFO, error logs will include complete stack traces.

## Deployment Recommendations

### Production Environment

- Use Gunicorn or uWSGI as WSGI server
- Configure reverse proxy (like Nginx)
- Set up appropriate log rotation
- Monitor service health status

### Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .
CMD ["python", "app.py"]
```

### Environment Variable Examples

Refer to the `env.example` file, which contains detailed descriptions and example values for all configuration items.

## Troubleshooting

### Common Issues

1. **Permission errors**: Ensure GITHUB_TOKEN has sufficient permissions
2. **API limits**: Check GitHub API rate limits and Gemini API quotas
3. **Network timeouts**: Adjust `REQUEST_TIMEOUT` and retry configuration
4. **Memory usage**: Large PRs may require adjusting `MAX_PROMPT_LENGTH` and `MAX_FILES_PER_REVIEW`

### Log Debugging

View application logs for detailed error information:

```bash
python app.py 2>&1 | tee app.log
```