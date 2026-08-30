import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket_manager import manager

logger = logging.getLogger("pattyproject.websocket")
router = APIRouter()


@router.websocket("/products")
@router.websocket("")
async def customer_products_websocket(websocket: WebSocket):
    """
    Read-only public/customer WebSocket endpoint for real-time product availability notifications.
    Endpoint URL: /api/v1/ws/products

    Guarantees:
    - Zero authentication required (public customer menu updates).
    - Read-only: customer cannot perform any mutations through WebSocket.
    - Automatic heartbeat / keepalive support.
    - Disconnected clients are safely cleaned up without interrupting delivery to others.
    """
    await manager.connect_products(websocket)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "CONNECTED",
            "channel": "products",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # Main receive / heartbeat loop
        while True:
            try:
                # Wait for client messages (e.g. ping) or 25s keepalive timeout
                data = await asyncio.wait_for(websocket.receive_json(), timeout=25.0)
                if isinstance(data, dict):
                    msg_type = str(data.get("type", "")).upper()
                    if msg_type == "PING":
                        await websocket.send_json({
                            "type": "PONG",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
            except asyncio.TimeoutError:
                # Send server-to-client keepalive ping to maintain connection across proxies
                try:
                    await websocket.send_json({
                        "type": "PING",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                except Exception:
                    break
    except (WebSocketDisconnect, ConnectionResetError):
        logger.info("[WS_PRODUCT] Customer disconnected cleanly.")
    except Exception as exc:
        logger.warning(f"[WS_PRODUCT_EXC] WebSocket error: {exc}")
    finally:
        await manager.disconnect_products(websocket)
