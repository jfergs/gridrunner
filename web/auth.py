from typing import Optional
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from config import WEB_PASSWORD, WEB_USER

security = HTTPBasic(auto_error=False)


def require_auth(credentials: Optional[HTTPBasicCredentials] = Depends(security)):
    if not WEB_PASSWORD:
        return None

    valid_user = credentials and secrets.compare_digest(credentials.username, WEB_USER)
    valid_password = credentials and secrets.compare_digest(credentials.password, WEB_PASSWORD)
    if valid_user and valid_password:
        return credentials.username

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Basic"},
    )
