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
    AI_MODEL_NAME: str = 'gemini-2.0-flash-exp'
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
            AI_MODEL_NAME=os.getenv('AI_MODEL_NAME', 'gemini-2.0-flash-exp')
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
    return logging.getLogger(__name__)

# --- 3. 错误处理和重试装饰器 ---
def retry_on_failure(max_attempts: int = 3, delay: float = 1.0):
    """重试装饰器"""
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
                        logger.warning(f"{func.__name__} 失败 (尝试 {attempt + 1}/{max_attempts}): {e}")
                        time.sleep(delay * (attempt + 1))  # 指数退避
                    else:
                        logger.error(f"{func.__name__} 最终失败: {e}")
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
    """封装 GitHub API 操作"""
    def __init__(self, token: str, timeout: int = 30):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        })
        self.timeout = timeout
    
    @retry_on_failure(max_attempts=3)
    def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """获取 PR 文件变更"""
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    @retry_on_failure(max_attempts=3)
    def post_comment(self, owner: str, repo: str, pr_number: int, comment: str) -> Dict[str, Any]:
        """发布 PR 评论"""
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
        response = self.session.post(url, json={"body": comment}, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    @retry_on_failure(max_attempts=3)
    def add_label(self, owner: str, repo: str, pr_number: int, label: str) -> None:
        """添加 PR 标签"""
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/labels"
        response = self.session.post(url, json={"labels": [label]}, timeout=self.timeout)
        response.raise_for_status()

github_client = GitHubClient(config.GITHUB_TOKEN, config.REQUEST_TIMEOUT)

# --- 5. 核心功能 ---
class PRReviewer:
    """PR 审查核心逻辑"""
    
    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str) -> bool:
        """验证 GitHub webhook 签名"""
        if not signature:
            return False
        
        hash_object = hmac.new(
            config.GITHUB_WEBHOOK_SECRET.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        )
        expected_signature = f"sha256={hash_object.hexdigest()}"
        return hmac.compare_digest(expected_signature, signature)
    
    @staticmethod
    def create_review_prompt(files: List[Dict[str, Any]]) -> str:
        """创建 AI 审查提示词"""
        # 限制文件数量
        files = files[:config.MAX_FILES_PER_REVIEW]
        
        diffs_text = ""
        total_length = 0
        
        for file in files:
            filename = file.get('filename', 'unknown')
            patch = file.get('patch', '')
            
            # 跳过太大的文件
            if len(patch) > 5000:
                file_text = f"### 文件: {filename}\n\n_文件变更过大，已跳过_\n\n---\n\n"
            else:
                # 安全处理代码块
                safe_patch = patch.replace("```", "`` `") if patch else "_无变更内容_"
                file_text = f"### 文件: {filename}\n\n```diff\n{safe_patch}\n```\n\n---\n\n"
            
            # 检查总长度
            if total_length + len(file_text) > config.MAX_PROMPT_LENGTH:
                diffs_text += "\n_[更多文件已省略...]_"
                break
            
            diffs_text += file_text
            total_length += len(file_text)
        
        return f"""你是一位高级软件工程师，正在进行代码审查。请分析以下代码变更：

{diffs_text}

审查要求：
1. 识别潜在的bug、安全问题和性能问题
2. 检查代码风格和最佳实践
3. 提供具体的改进建议
4. 使用简洁的中文和 Markdown 格式
5. 如果代码质量良好，请给予正面反馈

请直接开始你的审查意见，不需要开场白。"""
    
    @staticmethod
    @retry_on_failure(max_attempts=3, delay=2.0)
    def get_ai_review(prompt: str) -> str:
        """调用 AI 获取审查意见"""
        try:
            response = ai_model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"AI 审查失败: {e}")
            return "⚠️ AI 审查服务暂时不可用，请稍后重试。"
    
    @staticmethod
    def process_pr_review(pr_number: int, owner: str, repo: str) -> Dict[str, Any]:
        """处理 PR 审查的完整流程"""
        start_time = time.time()
        result = {
            "pr_number": pr_number,
            "status": "success",
            "message": "",
            "duration": 0
        }
        
        try:
            # 获取文件变更
            logger.info(f"开始审查 PR #{pr_number}")
            files = github_client.get_pr_files(owner, repo, pr_number)
            
            if not files:
                result["status"] = "skipped"
                result["message"] = "PR 无文件变更"
                return result
            
            logger.info(f"PR #{pr_number} 包含 {len(files)} 个文件变更")
            
            # 创建提示词并获取 AI 审查
            prompt = PRReviewer.create_review_prompt(files)
            review_comment = PRReviewer.get_ai_review(prompt)
            
            # 发布评论
            comment_with_footer = f"{review_comment}\n\n---\n*🤖 此评论由 UllrAI 代码审查助手自动生成*"
            github_client.post_comment(owner, repo, pr_number, comment_with_footer)
            
            # 添加标签
            github_client.add_label(owner, repo, pr_number, config.REVIEW_LABEL)
            
            result["message"] = f"成功审查 {len(files)} 个文件"
            logger.info(f"PR #{pr_number} 审查完成")
            
        except Exception as e:
            result["status"] = "error"
            result["message"] = str(e)
            logger.error(f"PR #{pr_number} 审查失败: {e}")
        
        finally:
            result["duration"] = round(time.time() - start_time, 2)
        
        return result

# --- 6. Web 端点 ---
@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        "status": "healthy",
        "service": "pr-reviewer",
        "version": "1.0.0",
        "model": config.AI_MODEL_NAME
    })

@app.route('/webhook', methods=['POST'])
def github_webhook():
    """GitHub Webhook 处理端点"""
    # 验证签名
    # signature = request.headers.get('X-Hub-Signature-256')
    # if not PRReviewer.verify_webhook_signature(request.data, signature):
    #     logger.warning("Webhook 签名验证失败")
    #     abort(401)
    logger.warning("⚠️ 签名验证已跳过！")
    
    # 解析事件
    try:
        data = request.json
        event_type = request.headers.get('X-GitHub-Event')
        
        # 检查是否需要处理
        should_process, pr_number = should_process_event(data, event_type)
        if not should_process:
            return jsonify({"status": "skipped", "reason": "非目标事件"}), 200
        
        # 异步处理可以在这里实现
        result = PRReviewer.process_pr_review(
            pr_number,
            config.TARGET_OWNER,
            config.TARGET_REPO
        )
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Webhook 处理失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def should_process_event(data: Dict[str, Any], event_type: str) -> tuple[bool, Optional[int]]:
    """判断是否应该处理该事件"""
    # 检查仓库
    repo = data.get('repository', {})
    if repo.get('owner', {}).get('login') != config.TARGET_OWNER:
        return False, None
    if repo.get('name') != config.TARGET_REPO:
        return False, None
    
    # PR 事件
    if event_type == 'pull_request':
        action = data.get('action')
        if action in ['opened', 'synchronize', 'reopened']:
            pr_number = data.get('pull_request', {}).get('number')
            return True, pr_number
    
    # 评论触发
    elif event_type == 'issue_comment':
        if data.get('action') == 'created':
            comment_body = data.get('comment', {}).get('body', '')
            if '/review' in comment_body:
                issue = data.get('issue', {})
                if issue.get('pull_request'):
                    return True, issue.get('number')
    
    return False, None

@app.route('/metrics', methods=['GET'])
def metrics():
    """简单的指标端点"""
    # 这里可以集成 Prometheus 或其他监控工具
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
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({"error": "Internal server error"}), 500

# --- 8. 启动应用 ---
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info(f"PR 代码审查机器人启动 - {config.TARGET_OWNER}/{config.TARGET_REPO}")
    logger.info(f"监听端口: {port}")
    logger.info(f"AI 模型: {config.AI_MODEL_NAME}")
    
    # 生产环境建议使用 gunicorn 或 uwsgi
    app.run(host='0.0.0.0', port=port, debug=False)