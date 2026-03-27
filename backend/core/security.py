from typing import Optional
from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from core.config import DASHBOARD_API_KEY

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def require_api_key(api_key: Optional[str] = Security(_api_key_header)):
    """Ha DASHBOARD_API_KEY be van állítva, ellenőrzi az X-API-Key headert.
    Ha üres, az auth ki van kapcsolva (fejlesztői mód).
    """
    if not DASHBOARD_API_KEY:
        return
    if api_key != DASHBOARD_API_KEY:
        raise HTTPException(status_code=401, detail="Érvénytelen vagy hiányzó API kulcs (X-API-Key)")
