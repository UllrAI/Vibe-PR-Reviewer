import os
import hmac
import hashlib
import json
import logging
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
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
    TARGET_OWNER: str
    TARGET_REPO: str
    REVIEW_LABEL: str = 'ReviewedByUllrAI'
    AI_MODEL_NAME: str = 'gemini-1.5-flash-latest' # 更新为推荐的模型
    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_DELAY: float = 1.0
    REQUEST_TIMEOUT: int = 30
    MAX_FILES_PER_REVIEW: int = 50
    MAX_PROMPT_LENGTH: int = 30000

    @classmethod
    def from_env(cls) -> 'Config':
        """从环境变量加载配置"""
        required_vars = ['GITHUB_TOKEN', 'GITHUB_WEBHOOK_SECRET', 'GEMINI_API_KEY']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"缺少必需的环境变量: {', '.join(missing_vars)}")
        
        return cls(
            GITHUB_TOKEN=os.getenv('GITHUB_TOKEN'),
            GITHUB_WEBHOOK_SECRET=os.getenv('GITHUB_WEBHOOK_SECRET'),
            GEMINI_API_KEY=os.getenv('GEMINI_API_KEY'),
            TARGET_OWNER=os.getenv('TARGET_OWNER', 'UllrAI'),
            TARGET_REPO=os.getenv('TARGET_REPO', 'SaaS-Starter'),
            REVIEW_LABEL=os.getenv('REVIEW_LABEL', 'ReviewedByUllrAI'),
            AI_MODEL_NAME=os.getenv('AI_MODEL_NAME', 'gemini-1.5-flash-latest')
        )

# --- 2. 日志配置 ---
def setup_logging():
    """配置结构化日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            # 可选：添加文件处理器
            # logging.FileHandler('pr_reviewer.log')
        ]
    )
    # 禁用 requests 和 urllib3 的冗余日志
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

# 配置 Gemini
genai.configure(api_key=config.GEMINI_API_KEY)
ai_model = genai.GenerativeModel(config.AI_MODEL_NAME)

# GitHub API 客户端
class GitHubClient:
    """封装 GitHub API 操作，并为每个操作添加日志"""
    def __init__(self, token: str, timeout: int = 30):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        })
        self.timeout = timeout
    
    @retry_on_failure(max_attempts=config.MAX_RETRY_ATTEMPTS)
    def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """获取 PR 文件变更"""
        logger.info(f"[GitHub API] ==> 'get_pr_files'")
        logger.info(f"  Input: owner='{owner}', repo='{repo}', pr_number={pr_number}")
        
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        files = response.json()
        
        logger.info(f"  Output: 成功获取 {len(files)} 个文件变更。")
        return files
    
    @retry_on_failure(max_attempts=config.MAX_RETRY_ATTEMPTS)
    def post_comment(self, owner: str, repo: str, pr_number: int, comment: str) -> Dict[str, Any]:
        """发布 PR 评论"""
        logger.info(f"[GitHub API] ==> 'post_comment'")
        logger.info(f"  Input: owner='{owner}', repo='{repo}', pr_number={pr_number}, comment_length={len(comment)}")
        
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
        response = self.session.post(url, json={"body": comment}, timeout=self.timeout)
        response.raise_for_status()
        response_json = response.json()
        
        logger.info(f"  Output: 评论成功发布。URL: {response_json.get('html_url')}")
        return response_json
    
    @retry_on_failure(max_attempts=config.MAX_RETRY_ATTEMPTS)
    def add_label(self, owner: str, repo: str, pr_number: int, label: str) -> None:
        """添加 PR 标签"""
        logger.info(f"[GitHub API] ==> 'add_label'")
        logger.info(f"  Input: owner='{owner}', repo='{repo}', pr_number={pr_number}, label='{label}'")
        
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/labels"
        response = self.session.post(url, json={"labels": [label]}, timeout=self.timeout)
        response.raise_for_status()
        
        logger.info("  Output: 标签成功添加。")

github_client = GitHubClient(config.GITHUB_TOKEN, config.REQUEST_TIMEOUT)

# --- 5. 核心功能 ---
class PRReviewer:
    """PR 审查核心逻辑，包含详细的步骤日志"""
    
    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str) -> bool:
        """验证 GitHub webhook 签名"""
        logger.info("[Step] 验证 Webhook 签名...")
        if not signature:
            logger.warning("  Input: 未找到 'X-Hub-Signature-256' 请求头。")
            logger.info("  Output: 签名验证失败 (无签名)。")
            return False
        
        logger.info(f"  Input: 找到签名 ('{signature[:12]}...').")
        hash_object = hmac.new(
            config.GITHUB_WEBHOOK_SECRET.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        )
        expected_signature = f"sha256={hash_object.hexdigest()}"
        is_valid = hmac.compare_digest(expected_signature, signature)
        
        logger.info(f"  Output: 签名有效: {is_valid}。")
        return is_valid
    
    @staticmethod
    def create_review_prompt(files: List[Dict[str, Any]]) -> str:
        """创建 AI 审查提示词"""
        logger.info("[Step] 创建 AI 审查提示词...")
        num_files_before_limit = len(files)
        files = files[:config.MAX_FILES_PER_REVIEW]
        num_files_after_limit = len(files)
        
        logger.info(f"  Input: {num_files_before_limit} 个文件。由于 MAX_FILES_PER_REVIEW={config.MAX_FILES_PER_REVIEW} 的限制，将处理 {num_files_after_limit} 个文件。")
        
        diffs_text = ""
        total_length = 0
        files_processed_count = 0
        files_skipped_large = 0
        files_skipped_length = 0
        
        for file in files:
            filename = file.get('filename', 'unknown')
            patch = file.get('patch', '')
            
            if len(patch) > 5000: # 跳过太大的文件补丁
                files_skipped_large += 1
                file_text = f"### 文件: {filename}\n\n_文件变更过大，已跳过_\n\n---\n\n"
            else:
                safe_patch = patch.replace("```", "`` `") if patch else "_无变更内容_"
                file_text = f"### 文件: {filename}\n\n```diff\n{safe_patch}\n```\n\n---\n\n"
            
            if total_length + len(file_text) > config.MAX_PROMPT_LENGTH:
                files_skipped_length += (len(files) - files_processed_count)
                diffs_text += "\n_[更多文件因超出总长度限制已被省略...]_"
                logger.warning(f"  提示词长度达到限制 ({config.MAX_PROMPT_LENGTH})。在处理 {files_processed_count} 个文件后停止。")
                break
            
            diffs_text += file_text
            total_length += len(file_text)
            files_processed_count += 1
        
        prompt = f"""你是一位资深软件工程师和代码审查专家。请仔细分析以下从一个 Pull Request 中提取的代码变更。

{diffs_text}

你的审查任务是：
1.  **识别潜在的 Bug**：寻找逻辑错误、边界情况问题或可能导致运行时错误的代码。
2.  **发现安全漏洞**：检查是否存在常见的安全问题（如注入、XSS、不安全的配置等）。
3.  **评估代码可读性和可维护性**：代码是否清晰、易于理解？命名是否规范？是否存在过于复杂的逻辑？
4.  **检查最佳实践**：代码是否遵循了语言和框架的通用最佳实践？
5.  **提供具体的、可操作的改进建议**。请使用代码片段来解释你的建议。
6.  以**简洁、专业的中文**和 **Markdown** 格式提供反馈。
7.  如果代码质量很高，请给予积极的肯定。

请直接开始你的审查意见，无需任何开场白。"""
        
        logger.info(f"  Output: 提示词创建完毕。长度: {len(prompt)} 字符。处理文件: {files_processed_count}, 因过大跳过: {files_skipped_large}, 因超长跳过: {files_skipped_length}。")
        return prompt
    
    @staticmethod
    @retry_on_failure(max_attempts=config.MAX_RETRY_ATTEMPTS, delay=2.0)
    def get_ai_review(prompt: str) -> str:
        """调用 AI 获取审查意见"""
        logger.info("[Step] 调用 Gemini AI 进行代码审查...")
        logger.info(f"  Input: 提示词长度 {len(prompt)} 字符。")
        try:
            response = ai_model.generate_content(prompt)
            review_text = response.text
            logger.info(f"  Output: 成功接收到 AI 审查意见，长度 {len(review_text)} 字符。")
            return review_text
        except Exception as e:
            logger.error(f"  AI 调用期间发生错误: {e}")
            raise # 重新抛出异常以触发重试逻辑
    
    @staticmethod
    def process_pr_review(pr_number: int, owner: str, repo: str) -> Dict[str, Any]:
        """处理 PR 审查的完整流程"""
        start_time = time.time()
        logger.info(f"--- 开始处理 PR #{pr_number} 在 {owner}/{repo} 的审查流程 ---")
        result = {"pr_number": pr_number, "status": "success", "message": "", "duration": 0}
        
        try:
            # 1. 获取文件变更
            files = github_client.get_pr_files(owner, repo, pr_number)
            if not files:
                result.update({"status": "skipped", "message": "PR 无文件变更。"})
                logger.info(f"PR #{pr_number} 无文件变更，跳过审查。")
                return result
            
            # 2. 创建提示词
            prompt = PRReviewer.create_review_prompt(files)
            
            # 3. 获取 AI 审查
            review_comment = PRReviewer.get_ai_review(prompt)
            
            # 4. 发布评论
            comment_with_footer = f"{review_comment}\n\n---\n*🤖 此评论由 UllrAI 代码审查助手自动生成*"
            github_client.post_comment(owner, repo, pr_number, comment_with_footer)
            
            # 5. 添加标签
            github_client.add_label(owner, repo, pr_number, config.REVIEW_LABEL)
            
            result["message"] = f"成功审查 {len(files)} 个文件。"
            logger.info(f"--- PR #{pr_number} 审查流程成功完成 ---")
            
        except Exception as e:
            result.update({"status": "error", "message": str(e)})
            logger.error(f"--- PR #{pr_number} 审查流程失败: {e} ---", exc_info=True)
        
        finally:
            duration = round(time.time() - start_time, 2)
            result["duration"] = duration
            logger.info(f"PR #{pr_number} 总处理时长: {duration} 秒。")
        
        return result

# --- 6. Web 端点 ---
@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    logger.info("健康检查端点被访问。")
    return jsonify({
        "status": "healthy",
        "service": "pr-reviewer",
        "version": "1.1.0",
        "model": config.AI_MODEL_NAME
    })

@app.route('/webhook', methods=['POST'])
def github_webhook():
    """GitHub Webhook 处理端点"""
    event_type = request.headers.get('X-GitHub-Event', 'unknown')
    delivery_id = request.headers.get('X-GitHub-Delivery', 'unknown')
    logger.info(f"--- 收到 Webhook 请求。Event: '{event_type}', Delivery ID: '{delivery_id}' ---")

    # 1. 验证签名（在生产环境中强烈建议启用）
    # signature = request.headers.get('X-Hub-Signature-256')
    # if not PRReviewer.verify_webhook_signature(request.data, signature):
    #     logger.error(f"Webhook 签名验证失败，Delivery ID: {delivery_id}。中止请求。")
    #     abort(401)
    logger.warning(f"注意: Webhook 签名验证当前已跳过。Delivery ID: {delivery_id}。")
    
    # 2. 解析和处理事件
    try:
        data = request.json
        logger.info("[Step] 解析 Webhook JSON 负载。")
        
        should_process, pr_number = should_process_event(data, event_type)
        if not should_process:
            logger.info(f"事件 '{event_type}' (Delivery ID: {delivery_id}) 无需处理，已跳过。")
            return jsonify({"status": "skipped", "reason": "事件不满足处理条件。"}), 200
        
        logger.info(f"事件 '{event_type}' (PR #{pr_number}) 将被处理。")
        
        # 异步处理可以在此实现（当前为同步处理）
        result = PRReviewer.process_pr_review(
            pr_number,
            config.TARGET_OWNER,
            config.TARGET_REPO
        )
        
        logger.info(f"Webhook 处理完成，Delivery ID: {delivery_id}。结果: {result['status']}")
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"处理 Webhook 时发生未捕获的错误，Delivery ID: {delivery_id}。错误: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

def should_process_event(data: Dict[str, Any], event_type: str) -> tuple[bool, Optional[int]]:
    """判断是否应该处理该事件，并记录判断过程"""
    logger.info(f"[Step] 判断事件 '{event_type}' 是否需要处理...")
    
    repo_full_name = data.get('repository', {}).get('full_name', 'N/A')
    target_full_name = f"{config.TARGET_OWNER}/{config.TARGET_REPO}"
    logger.info(f"  Input: 事件来自仓库 '{repo_full_name}'。目标仓库是 '{target_full_name}'。")
    if repo_full_name.lower() != target_full_name.lower():
        logger.info(f"  Output: 跳过。事件并非来自目标仓库。")
        return False, None
    
    if event_type == 'pull_request':
        action = data.get('action')
        logger.info(f"  Input: 'pull_request' 事件，动作为 '{action}'。")
        if action in ['opened', 'synchronize', 'reopened']:
            pr_number = data.get('pull_request', {}).get('number')
            logger.info(f"  Output: 处理。动作 '{action}' 是目标动作，针对 PR #{pr_number}。")
            return True, pr_number
        else:
            logger.info(f"  Output: 跳过。动作 '{action}' 不是目标动作。")
    
    elif event_type == 'issue_comment':
        action = data.get('action')
        logger.info(f"  Input: 'issue_comment' 事件，动作为 '{action}'。")
        if data.get('action') == 'created':
            if not data.get('issue', {}).get('pull_request'):
                logger.info("  Output: 跳过。评论位于 Issue 而非 Pull Request。")
                return False, None
            
            comment_body = data.get('comment', {}).get('body', '')
            logger.info(f"  Input: 评论内容前50个字符: '{comment_body[:50].strip()}'。")
            if '/review' in comment_body.lower():
                pr_number = data.get('issue', {}).get('number')
                logger.info(f"  Output: 处理。评论包含 '/review' 触发指令，针对 PR #{pr_number}。")
                return True, pr_number
            else:
                logger.info("  Output: 跳过。评论不包含 '/review' 触发指令。")
        else:
            logger.info(f"  Output: 跳过。动作 '{action}' 不是 'created'。")

    logger.info(f"  Output: 跳过。事件类型 '{event_type}' 不是目标事件类型。")
    return False, None

@app.route('/metrics', methods=['GET'])
def metrics():
    """简单的指标端点"""
    logger.info("指标端点被访问。")
    return jsonify({
        "timestamp": time.time(),
        "config": {
            "target_repo": f"{config.TARGET_OWNER}/{config.TARGET_REPO}",
            "model": config.AI_MODEL_NAME
        }
    })

# --- 7. 错误处理 ---
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
    logger.info(f"PR 代码审查机器人启动 - 目标仓库: {config.TARGET_OWNER}/{config.TARGET_REPO}")
    logger.info(f"监听端口: {port}")
    logger.info(f"AI 模型: {config.AI_MODEL_NAME}")
    logger.info("="*50)
    
    # 生产环境建议使用 Gunicorn 或 uWSGI
    app.run(host='0.0.0.0', port=port, debug=False)