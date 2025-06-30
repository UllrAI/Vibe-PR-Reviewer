
import hashlib
import hmac

from fastapi import Request, HTTPException, status

from core.config import settings

def verify_github_signature(request: Request, body: bytes):
    """Verify that the webhook request came from GitHub."""
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="X-Hub-Signature-256 header is missing!"
        )

    hash_object = hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"), 
        msg=body, 
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()

    if not hmac.compare_digest(expected_signature, signature_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Request signature does not match!"
        )
