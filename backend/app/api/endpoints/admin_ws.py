import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from jose import JWTError, jwt
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.core.websocket_manager import manager

logger = logging.getLogger("pattyproject.websocket")
router = APIRouter()


def authenticate_websocket_token(token: Optional[str]) -> Optional[User]:
    """
    Validates the admin JWT token for WebSocket connection handshakes.
    Strictly enforces:
    1. Cryptographic signature and expiration checks.
    2. Active user account in database.
    3. Admin role authorization (SUPER_ADMIN or BRANCH_ADMIN).
    4. Customer roles are strictly rejected.
    """
    if not token:
        logger.warning("[WS_AUTH_REJECT] WebSocket connection attempted without auth token.")
        return None

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            logger.warning("[WS_AUTH_REJECT] JWT payload missing subject (user_id).")
            return None
    except JWTError as exc:
        logger.warning(f"[WS_AUTH_REJECT] Invalid or expired JWT token: {exc}")
        return None

    from app.core.database import get_db
    try:
        from app.main import app
        db_gen = app.dependency_overrides.get(get_db, get_db)
    except Exception:
        db_gen = get_db

    db = next(db_gen())
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            logger.warning(f"[WS_AUTH_REJECT] User {user_id} not found or inactive.")
            return None

        if user.role not in [UserRole.SUPER_ADMIN, UserRole.BRANCH_ADMIN]:
            logger.warning(f"[WS_AUTH_REJECT] User {user_id} role '{user.role}' is not authorized for admin WebSocket.")
            return None

        # Pre-load branch assignments inside session
        _ = [bu.branch_id for bu in user.branch_assignments]
        db.expunge_all()
        return user
    finally:
        db.close()


@router.websocket("/orders")
@router.websocket("")
async def admin_orders_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    Authenticated WebSocket endpoint for real-time Admin order events.
    Endpoint URL: /api/v1/admin/ws/orders?token=<admin_jwt_token>

    Provides:
    - Instant push of ORDER_INCOMING events on successful payment.
    - Instant push of ORDER_STATUS_CHANGED events on status updates (e.g. Accept).
    - 25-second server-to-client heartbeat keepalive to prevent Nginx proxy timeouts.
    - Full branch isolation between branches.
    """
    user = authenticate_websocket_token(token)
    if not user:
        # Close connection immediately with 1008 Policy Violation
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized: Admin authentication required")
        return

    branch_ids: Set[str] = set(str(bu.branch_id) for bu in user.branch_assignments)
    await manager.connect(
        websocket=websocket,
        user_id=user.id,
        role=user.role,
        branch_ids=branch_ids
    )

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "CONNECTED",
            "user_id": user.id,
            "role": user.role,
            "branch_ids": list(branch_ids),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # Main receive / heartbeat loop
        while True:
            try:
                # Wait for client messages or 25s keepalive timeout
                data = await asyncio.wait_for(websocket.receive_json(), timeout=25.0)
                if isinstance(data, dict):
                    msg_type = data.get("type", "").upper()
                    if msg_type == "PING":
                        await websocket.send_json({
                            "type": "PONG",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
            except asyncio.TimeoutError:
                # 25-second periodic server keepalive ping (prevents Nginx 60s timeout)
                try:
                    await websocket.send_json({
                        "type": "PING",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                except Exception:
                    break
    except WebSocketDisconnect:
        logger.info(f"[WS_DISCONNECTED] Client disconnected normally: user_id={user.id}")
    except Exception as exc:
        logger.warning(f"[WS_SOCKET_ERROR] Socket terminated unexpectedly: user_id={user.id}, error={exc}")
    finally:
        await manager.disconnect(websocket)
