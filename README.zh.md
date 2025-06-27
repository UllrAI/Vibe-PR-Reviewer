# PR Review Bot

一个基于 Gemini AI 的智能 Pull Request 代码审查机器人，能够自动对 GitHub PR 进行深入的代码审查并提供建设性的修改建议。

## 功能特性

- 🤖 基于 Google Gemini AI 的智能代码审查
- 📝 自动生成详细的审查报告，包含问题定位和修改建议
- 🔄 支持 Webhook 自动触发和手动评论触发（`/review`）
- 📁 智能文件上下文分析，提供更准确的审查意见
- 🏷️ 自动添加审查标签
- ⚡ 支持重试机制和错误处理
- 🛠️ 灵活的环境变量配置

## 示例演示

查看实际运行效果：[示例 PR 审查](https://github.com/UllrAI/Vibe-PR-Reviewer/pull/1)

## 安装与部署

### 1. 克隆项目

```bash
git clone <repository-url>
cd pr-review-bot
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 环境变量配置

复制示例配置文件并填写实际值：

```bash
cp env.example .env
```

然后编辑 `.env` 文件，或直接设置以下环境变量：

#### 必须配置的环境变量

```bash
# GitHub Personal Access Token（需要 repo 权限）
# 获取方式：GitHub Settings → Developer settings → Personal access tokens → Tokens
# 权限要求：Pull requests, Issues
GITHUB_TOKEN=your_github_token

# Google Gemini API Key
GEMINI_API_KEY=your_gemini_api_key
```

#### 可选配置的环境变量

```bash
# AI 模型配置
AI_MODEL_NAME=gemini-2.5-pro                    # 默认: gemini-2.5-pro

# 审查配置
REVIEW_LABEL=ReviewedByUllrAI                   # 默认: ReviewedByUllrAI
MAX_PROMPT_LENGTH=200000                        # 默认: 200000
INCLUDE_FILE_CONTEXT=true                       # 默认: true
CONTEXT_MAX_LINES=400                          # 默认: 400
CONTEXT_SURROUNDING_LINES=50                   # 默认: 50
MAX_FILES_PER_REVIEW=50                        # 默认: 50

# 网络和重试配置
MAX_RETRY_ATTEMPTS=3                           # 默认: 3
RETRY_DELAY=2.0                               # 默认: 2.0
REQUEST_TIMEOUT=60                            # 默认: 60

# 服务器配置
PORT=5001                                     # 默认: 5001
```

### 4. 启动服务

```bash
python app.py
```

服务将在指定端口（默认 5001）启动。

### 5. GitHub Webhook 配置

在你的 GitHub 仓库中配置 Webhook：

1. 进入仓库设置 → Webhooks → Add webhook
2. Payload URL: `http://your-server:5001/webhook`
3. Content type: `application/json`
4. Events: 选择 `Pull requests` 和 `Issue comments`

**注意**: 目前不需要 Webhook 签名验证，无需配置 secret。

## 使用方法

### 自动审查

机器人会自动对以下事件进行审查：

- PR 创建时（`pull_request.opened`）
- PR 更新时（`pull_request.synchronize`）
- PR 重新打开时（`pull_request.reopened`）

### 手动触发审查

在 PR 评论中输入 `/review` 来手动触发代码审查。

## 配置说明

### 核心配置

- `GITHUB_TOKEN`: GitHub Personal Access Token，需要 `repo` 权限
- `GEMINI_API_KEY`: Google Gemini API 密钥

### AI 配置

- `AI_MODEL_NAME`: 使用的 Gemini 模型名称
- `MAX_PROMPT_LENGTH`: 发送给 AI 的最大提示词长度
- `INCLUDE_FILE_CONTEXT`: 是否包含完整文件上下文进行分析

### 上下文配置

- `CONTEXT_MAX_LINES`: 完整文件的最大行数限制
- `CONTEXT_SURROUNDING_LINES`: 代码片段的上下文行数
- `MAX_FILES_PER_REVIEW`: 单次审查的最大文件数

### 网络配置

- `MAX_RETRY_ATTEMPTS`: API 调用失败时的重试次数
- `RETRY_DELAY`: 重试间隔时间（秒）
- `REQUEST_TIMEOUT`: HTTP 请求超时时间（秒）

## API 端点

### 健康检查

```bash
GET /health
```

返回服务状态和配置信息。

### Webhook 处理

```bash
POST /webhook
```

接收 GitHub Webhook 事件并处理 PR 审查。

## 日志

应用使用结构化日志记录所有操作，包括：

- GitHub API 调用
- AI 模型调用
- 审查流程状态
- 错误和异常信息

日志级别为 INFO，错误日志会包含完整的堆栈跟踪。

## 部署建议

### 生产环境

- 使用 Gunicorn 或 uWSGI 作为 WSGI 服务器
- 配置反向代理（如 Nginx）
- 设置适当的日志轮转
- 监控服务健康状态

### Docker 部署

创建 `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .
CMD ["python", "app.py"]
```

### 环境变量示例

参考 `env.example` 文件，包含所有配置项的详细说明和示例值。

## 故障排除

### 常见问题

1. **权限错误**: 确保 GITHUB_TOKEN 具有足够的权限
2. **API 限制**: 检查 GitHub API 速率限制和 Gemini API 配额
3. **网络超时**: 调整 `REQUEST_TIMEOUT` 和重试配置
4. **内存使用**: 大型 PR 可能需要调整 `MAX_PROMPT_LENGTH` 和 `MAX_FILES_PER_REVIEW`

### 日志调试

查看应用日志以获取详细的错误信息：

```bash
python app.py 2>&1 | tee app.log
```
