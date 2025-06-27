import os
import re
import hmac
import hashlib
import json
import logging
import time
import base64  # <--- 修正点：需要导入 base64 模块
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from functools import wraps

import requests
import google.generativeai as genai
from flask import Flask, request, abort, jsonify

# --- 1. 配置管理 ---
@dataclass
class Config:
    """集中管理所有配置"""
    GITHUB_TOKEN: str
    GITHUB_WEBHOOK_SECRET: str
    GEMINI_API_KEY: str
    
    # AI 和审查相关的配置
    AI_MODEL_NAME: str = 'gemini-2.5-pro'
    REVIEW_LABEL: str = 'ReviewedByUllrAI'
    MAX_PROMPT_LENGTH: int = 200000
    INCLUDE_FILE_CONTEXT: bool = True
    CONTEXT_MAX_LINES: int = 400
    CONTEXT_SURROUNDING_LINES: int = 50
    
    # API 和网络相关的配置
    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_DELAY: float = 2.0
    REQUEST_TIMEOUT: int = 60 # 增加超时以应对文件下载
    MAX_FILES_PER_REVIEW: int = 50
    

    @classmethod
    def from_env(cls) -> 'Config':
        """从环境变量加载配置"""
        required_vars = ['GITHUB_TOKEN', 'GEMINI_API_KEY']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"缺少必需的环境变量: {', '.join(missing_vars)}")
        
        return cls(
            GITHUB_TOKEN=os.getenv('GITHUB_TOKEN'),
            GITHUB_WEBHOOK_SECRET=os.getenv('GITHUB_WEBHOOK_SECRET', ''),
            GEMINI_API_KEY=os.getenv('GEMINI_API_KEY'),
            AI_MODEL_NAME=os.getenv('AI_MODEL_NAME', 'gemini-2.5-pro'),
            REVIEW_LABEL=os.getenv('REVIEW_LABEL', 'ReviewedByUllrAI'),
            MAX_PROMPT_LENGTH=int(os.getenv('MAX_PROMPT_LENGTH', '200000')),
            INCLUDE_FILE_CONTEXT=os.getenv('INCLUDE_FILE_CONTEXT', 'true').lower() in ('true', '1', 't'),
            CONTEXT_MAX_LINES=int(os.getenv('CONTEXT_MAX_LINES', '400')),
            CONTEXT_SURROUNDING_LINES=int(os.getenv('CONTEXT_SURROUNDING_LINES', '50')),
            MAX_RETRY_ATTEMPTS=int(os.getenv('MAX_RETRY_ATTEMPTS', '3')),
            RETRY_DELAY=float(os.getenv('RETRY_DELAY', '2.0')),
            REQUEST_TIMEOUT=int(os.getenv('REQUEST_TIMEOUT', '60')),
            MAX_FILES_PER_REVIEW=int(os.getenv('MAX_FILES_PER_REVIEW', '50')),
        )

# --- 2. 日志配置 ---
def setup_logging():
    """配置结构化日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return logging.getLogger(__name__)

# --- 3. 错误处理和重试装饰器 ---
def retry_on_failure(max_attempts: int = 3, delay: float = 1.0):
    """重试装饰器，增加了对失败的日志记录"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(f"函数 {func.__name__} 失败 (尝试 {attempt + 1}/{max_attempts}): {e}. 将在 {delay * (attempt + 1):.1f} 秒后重试...")
                        time.sleep(delay * (attempt + 1))
                    else:
                        logger.error(f"函数 {func.__name__} 在 {max_attempts} 次尝试后最终失败。")
            raise last_exception
        return wrapper
    return decorator

# --- 4. 初始化 ---
logger = setup_logging()
config = Config.from_env()
app = Flask(__name__)

genai.configure(api_key=config.GEMINI_API_KEY)
ai_model = genai.GenerativeModel(config.AI_MODEL_NAME)

class GitHubClient:
    """封装 GitHub API 操作，并为每个操作添加日志"""
    def __init__(self, token: str, timeout: int):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28" # 推荐添加 API 版本头
        })
        self.timeout = timeout

    @retry_on_failure(max_attempts=config.MAX_RETRY_ATTEMPTS)
    def get_pr_details(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """获取单个 PR 的详细信息"""
        logger.info(f"[GitHub API] ==> 'get_pr_details' for PR #{pr_number}")
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    @retry_on_failure(max_attempts=config.MAX_RETRY_ATTEMPTS)
    def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """获取 PR 文件变更"""
        logger.info(f"[GitHub API] ==> 'get_pr_files' for PR #{pr_number}")
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        files = response.json()
        logger.info(f"  Output: 成功获取 {len(files)} 个文件变更。")
        return files

    # <--- 修正点：用更稳健的 Contents API 替换 get_raw_file_content
    @retry_on_failure(max_attempts=config.MAX_RETRY_ATTEMPTS)
    def get_file_content_from_repo(self, owner: str, repo: str, file_path: str, ref: str) -> str:
        """
        使用 Contents API 获取仓库中特定版本的文件内容。
        这种方法比直接拼接 raw URL 更可靠。
        """
        logger.info(f"[GitHub API] ==> 'get_file_content_from_repo'")
        logger.info(f"  Input: owner={owner}, repo={repo}, path={file_path}, ref={ref}")
        
        # 使用官方的 Contents API 端点
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
        params = {"ref": ref}
        
        # 所有通过 self.session 的请求都会自动携带鉴权头
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        if 'content' not in data:
            raise ValueError(f"从 API 响应中未找到文件 '{file_path}' 的 'content' 字段。")

        # 内容是 Base64 编码的，需要解码
        content_b64 = data['content']
        content_bytes = base64.b64decode(content_b64)
        
        try:
            # 尝试使用 UTF-8 解码，这是最常见的情况
            content_str = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            # 如果失败，可以尝试其他编码或直接记录警告
            logger.warning(f"文件 '{file_path}' 解码为 UTF-8 失败，将使用带替换符的 latin-1 解码。")
            content_str = content_bytes.decode('latin-1', errors='replace')
        
        logger.info(f"  Output: 成功获取并解码文件内容，大小 {len(content_str)} 字节。")
        return content_str

    @retry_on_failure(max_attempts=config.MAX_RETRY_ATTEMPTS)
    def post_comment(self, owner: str, repo: str, pr_number: int, comment: str) -> Dict[str, Any]:
        """发布 PR 评论"""
        logger.info(f"[GitHub API] ==> 'post_comment' on PR #{pr_number}")
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
        response = self.session.post(url, json={"body": comment}, timeout=self.timeout)
        response.raise_for_status()
        response_json = response.json()
        logger.info(f"  Output: 评论成功发布。URL: {response_json.get('html_url')}")
        return response_json
    
    @retry_on_failure(max_attempts=config.MAX_RETRY_ATTEMPTS)
    def add_label(self, owner: str, repo: str, pr_number: int, label: str) -> None:
        """添加 PR 标签"""
        logger.info(f"[GitHub API] ==> 'add_label' on PR #{pr_number}")
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/labels"
        response = self.session.post(url, json={"labels": [label]}, timeout=self.timeout)
        response.raise_for_status()
        logger.info(f"  Output: 标签 '{label}' 成功添加。")

github_client = GitHubClient(config.GITHUB_TOKEN, config.REQUEST_TIMEOUT)

# --- 5. 核心功能 ---
class PRReviewer:
    """PR 审查核心逻辑"""

    @staticmethod
    def _get_context_line_from_patch(patch: str) -> int:
        """从 patch 字符串中解析出变更开始的行号"""
        match = re.search(r"@@ -(\d+),?\d* \+", patch)
        return int(match.group(1)) if match else 1

    @staticmethod
    def create_review_prompt(files: List[Dict[str, Any]], pr_data: Dict[str, Any]) -> str:
        """创建 AI 审查提示词，可选择性包含文件上下文"""
        logger.info("[Step] 创建 AI 审查提示词...")
        files = files[:config.MAX_FILES_PER_REVIEW]
        
        repo_info = pr_data.get("base", {}).get("repo", {})
        owner = repo_info.get("owner", {}).get("login")
        repo = repo_info.get("name")
        base_sha = pr_data.get("base", {}).get("sha")

        prompt_parts = []
        total_length = 0
        
        for file in files:
            filename = file.get('filename', 'unknown')
            patch = file.get('patch', '')
            status = file.get('status', 'modified')
            
            file_prompt = f"## 文件: `{filename}` (状态: {status})\n\n"

            # 1. 添加原始文件上下文（如果启用且文件被修改）
            if config.INCLUDE_FILE_CONTEXT and status == 'modified' and base_sha and owner and repo:
                try:
                    # <--- 修正点：调用新的、更可靠的方法获取文件内容
                    original_content = github_client.get_file_content_from_repo(
                        owner, repo, filename, base_sha
                    )
                    lines = original_content.splitlines()
                    
                    context_header = "### 原始文件上下文"
                    if len(lines) > config.CONTEXT_MAX_LINES:
                        start_line = PRReviewer._get_context_line_from_patch(patch)
                        slice_start = max(0, start_line - config.CONTEXT_SURROUNDING_LINES)
                        slice_end = min(len(lines), start_line + config.CONTEXT_SURROUNDING_LINES)
                        context_content = "\n".join(lines[slice_start:slice_end])
                        context_header += f" (代码片段，围绕第 {start_line} 行)"
                        logger.info(f"  - 为 '{filename}' 提取了代码片段 ({slice_end - slice_start} 行)。")
                    else:
                        context_content = original_content
                        context_header += " (完整文件)"
                        logger.info(f"  - 为 '{filename}' 包含了完整文件内容 ({len(lines)} 行)。")

                    file_prompt += f"{context_header}\n```\n{context_content}\n```\n\n"
                except Exception as e:
                    logger.warning(f"  - 无法为 '{filename}' 获取上下文: {e}")
                    file_prompt += "_[无法获取原始文件上下文]_\n\n"

            # 2. 添加 Diff
            safe_patch = patch.replace("```", "`` `") if patch else "_无变更内容_"
            file_prompt += f"### 本次提交的 Diff\n```diff\n{safe_patch}\n```\n\n---\n\n"
            
            if total_length + len(file_prompt) > config.MAX_PROMPT_LENGTH:
                logger.warning(f"  提示词长度达到限制。在处理 {len(prompt_parts)} 个文件后停止。")
                prompt_parts.append("\n_[更多文件因超出总长度限制已被省略...]_")
                break
            
            prompt_parts.append(file_prompt)
            total_length += len(file_prompt)

        diffs_text = "".join(prompt_parts)
        pr_title = pr_data.get('title', '')
        pr_body = pr_data.get('body', '')

        prompt = f"""# 审查指令
请对以下代码变更进行专业、深入的审查。你的目标是找出潜在的问题，并提供具体的、有建设性的修改建议。请遵循 GitHub Code Review 的最佳实践，保持评论的客观和简洁，按重要性紧急度优先级排列。

# 审查要点
1.  **逻辑和功能**：代码是否正确实现了其预定目标？是否存在BUG、逻辑漏洞或边界情况未处理？
2.  **性能**：是否存在明显的性能瓶颈，如不必要的循环、低效的查询或内存问题？
3.  **安全性**：是否存在常见的安全风险（如 SQL 注入、XSS、敏感信息硬编码等）？
4.  **代码风格与可读性**：如有，统一归类在最后一个问题中描述即可。代码是否遵循了项目或语言的最佳实践或通用规范？但忽略一些代码风格问题，如不影响逻辑的缩进、空格、换行等。
5.  **错误处理**：异常和错误情况是否得到了妥善处理？

# PR 上下文
*   **标题**: {pr_title}
*   **描述**:
{pr_body}

# 输出格式
请使用 Markdown 格式化你的审查意见。对于每一个发现点，请遵循以下模板，对极其需要关注的问题，标题适当使用⚠️之类强调。如果代码质量良好，没有发现问题，请明确指出。

---
**[1] 标题**
*   **类别**: [逻辑错误 / 性能 / 安全 / 代码风格 / 建议 等]
*   **代码定位**: `[文件名]:[行号]`
*   **说明**: [简洁地描述问题及其影响。]
*   **建议**:
    ```[语言]
    // 粘贴建议修改后的代码片段
    ```
---

# 待审查代码
{diffs_text}

请直接开始你的审查意见，无需任何开场白。"""
        
        logger.info(f"  Output: 提示词创建完毕。长度: {len(prompt)} 字符。处理文件: {len(prompt_parts)}。")
        return prompt

    @staticmethod
    @retry_on_failure(max_attempts=config.MAX_RETRY_ATTEMPTS, delay=config.RETRY_DELAY)
    def get_ai_review(prompt: str) -> str:
        """调用 AI 获取审查意见"""
        logger.info("[Step] 调用 Gemini AI 进行代码审查...")
        try:
            response = ai_model.generate_content(prompt)
            review_text = response.text
            logger.info(f"  Output: 成功接收到 AI 审查意见，长度 {len(review_text)} 字符。")
            return review_text
        except Exception as e:
            logger.error(f"  AI 调用期间发生错误: {e}")
            raise

    @staticmethod
    def process_pr_review(pr_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理 PR 审查的完整流程"""
        start_time = time.time()
        pr_number = pr_data['number']
        repo_info = pr_data.get("base", {}).get("repo", {})
        owner = repo_info.get("owner", {}).get("login")
        repo = repo_info.get("name")
        
        logger.info(f"--- 开始处理 PR #{pr_number} 在 {owner}/{repo} 的审查流程 ---")
        result = {"pr_number": pr_number, "status": "success", "message": "", "duration": 0}
        
        try:
            files = github_client.get_pr_files(owner, repo, pr_number)
            if not files:
                result.update({"status": "skipped", "message": "PR 无文件变更。"})
                return result
            
            prompt = PRReviewer.create_review_prompt(files, pr_data)
            review_comment = PRReviewer.get_ai_review(prompt)
            
            comment_with_footer = f"{review_comment}\n\n---\n*🤖 此评论由 UllrAI 代码审查助手，使用 {config.AI_MODEL_NAME} 模型生成*"
            github_client.post_comment(owner, repo, pr_number, comment_with_footer)
            github_client.add_label(owner, repo, pr_number, config.REVIEW_LABEL)
            
            result["message"] = f"成功审查 {len(files)} 个文件。"
            
        except Exception as e:
            result.update({"status": "error", "message": str(e)})
            logger.error(f"--- PR #{pr_number} 审查流程失败: {e} ---", exc_info=True)
        
        finally:
            duration = round(time.time() - start_time, 2)
            result["duration"] = duration
            logger.info(f"PR #{pr_number} 总处理时长: {duration} 秒。结果: {result['status']}")
        
        return result

# --- 6. Web 端点 ---
@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({"status": "healthy", "service": "pr-reviewer", "version": "2.0.0", "model": config.AI_MODEL_NAME})

@app.route('/webhook', methods=['POST'])
def github_webhook():
    """GitHub Webhook 处理端点"""
    event_type = request.headers.get('X-GitHub-Event', 'unknown')
    delivery_id = request.headers.get('X-GitHub-Delivery', 'unknown')
    logger.info(f"--- 收到 Webhook 请求。Event: '{event_type}', Delivery ID: '{delivery_id}' ---")

    # Webhook 签名验证已移除，无需配置 GITHUB_WEBHOOK_SECRET
    
    try:
        data = request.json
        should_process, pr_data = should_process_event(data, event_type)
        
        if not should_process:
            logger.info(f"事件 (Delivery ID: {delivery_id}) 无需处理，已跳过。")
            return jsonify({"status": "skipped", "reason": "事件不满足处理条件。"}), 200
        
        pr_number = pr_data.get('number')
        logger.info(f"事件 '{event_type}' (PR #{pr_number}) 将被处理。")
        
        # 异步处理可以在此实现（当前为同步处理）
        result = PRReviewer.process_pr_review(pr_data)
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"处理 Webhook 时发生未捕获的错误, Delivery ID: {delivery_id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

def should_process_event(data: Dict[str, Any], event_type: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """判断是否应该处理该事件，并返回完整的 PR 数据对象"""
    repo_info = data.get('repository', {})
    owner = repo_info.get('owner', {}).get('login')
    repo = repo_info.get('name')
    logger.info(f"[Step] 判断事件 '{owner}/{repo}' 的 '{event_type}' 是否需要处理...")
    action = data.get('action')

    if event_type == 'pull_request' and action in ['opened', 'synchronize', 'reopened']:
        pr_data = data.get('pull_request', {})
        if pr_data and not pr_data.get('draft', False):
            logger.info(f"  Output: 处理 'pull_request.{action}' 事件 for PR #{pr_data.get('number')}.")
            return True, pr_data
        else:
            logger.info("  Output: 跳过。PR 是草稿。")

    elif event_type == 'issue_comment' and action == 'created':
        if 'pull_request' in data.get('issue', {}):
            comment_body = data.get('comment', {}).get('body', '')
            if '/review' in comment_body.lower():
                pr_number = data.get('issue', {}).get('number')
                try:
                    pr_data = github_client.get_pr_details(owner, repo, pr_number)
                    logger.info(f"  Output: 处理 'issue_comment' 事件 for PR #{pr_number} (由 '/review' 触发)。")
                    return True, pr_data
                except Exception as e:
                    logger.error(f"  无法为评论触发的审查获取 PR #{pr_number} 的详细信息: {e}")
            else:
                logger.info("  Output: 跳过。评论不包含 '/review' 触发指令。")
        else:
            logger.info("  Output: 跳过。评论位于 Issue 而非 Pull Request。")

    logger.info(f"  Output: 跳过。事件 '{event_type}.{action}' 不是目标事件。")
    return False, None

# --- 7. 错误处理和附加端点 ---
@app.errorhandler(401)
def unauthorized(error):
    return jsonify({"error": "Unauthorized"}), 401
    
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not Found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"服务器内部错误: {error}", exc_info=True)
    return jsonify({"error": "Internal Server Error"}), 500

# --- 8. 启动应用 ---
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    logger.info("="*50)
    logger.info(f"PR 代码审查机器人启动 (v2.1.0)")
    logger.info(f"监听端口: {port}")
    logger.info(f"AI 模型: {config.AI_MODEL_NAME}")
    logger.info(f"包含文件上下文: {config.INCLUDE_FILE_CONTEXT}")
    logger.info("="*50)
    
    # 生产环境建议使用 Gunicorn 或 uWSGI
    app.run(host='0.0.0.0', port=port, debug=False)