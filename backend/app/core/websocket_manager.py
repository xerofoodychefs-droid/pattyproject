import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Set, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from app.models.user import UserRole
from app.models.order import Order

logger = logging.getLogger("pattyproject.websocket")


@dataclass
class AdminConnectionInfo:
    user_id: str
    role: str
    branch_ids: Set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def format_order_payload(order: Order) -> Dict[str, Any]:
    """
    Constructs a minimal, secure order payload for real-time admin notifications.
    Strictly excludes sensitive customer auth credentials, payment secrets, and private internal models.
    """
    return {
        "id": str(order.id),
        "order_number": str(order.order_number),
        "branch_id": str(order.branch_id),
        "status": str(order.status),
        "payment_status": str(order.payment_status),
        "order_type": str(order.order_type),
        "total_amount": float(order.total_amount),
        "customer_name": str(order.customer_name),
        "customer_phone": str(order.customer_phone),
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "items_count": len(order.items) if order.items else 0
    }


class ConnectionManager:
    """
    Thread-safe, branch-isolated WebSocket connection manager for Patty Project Admins.
    Guarantees strict branch data isolation between Super Admins and Branch Admins,
    resilient multi-client delivery, and automatic cleanup of disconnected sockets.
    """

    def __init__(self):
        self._connections: Dict[WebSocket, AdminConnectionInfo] = {}
        self._lock = asyncio.Lock()

    @property
    def active_connections_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket, user_id: str, role: str, branch_ids: Set[str]) -> None:
        """Accepts and registers a verified admin WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = AdminConnectionInfo(
                user_id=user_id,
                role=role,
                branch_ids=branch_ids
            )
        logger.info(
            f"[WS_CONNECT] user_id={user_id} role={role} assigned_branches={len(branch_ids)} "
            f"active_connections={len(self._connections)}"
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregisters a WebSocket connection safely."""
        async with self._lock:
            info = self._connections.pop(websocket, None)
        if info:
            logger.info(
                f"[WS_DISCONNECT] user_id={info.user_id} active_connections={len(self._connections)}"
            )

    async def broadcast_order_event(
        self,
        event_type: str,
        order_data: Dict[str, Any],
        branch_id: str
    ) -> None:
        """
        Broadcasts an order event strictly to authorized admins:
        - SUPER_ADMIN: Receives events for all branches.
        - BRANCH_ADMIN: Receives events ONLY if branch_id is in their assigned branch_ids.

        Isolates failures so a broken socket never interrupts delivery to other clients.
        """
        payload = {
            "type": event_type,
            "order": order_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        async with self._lock:
            recipients = list(self._connections.items())

        if not recipients:
            logger.debug(f"[WS_BROADCAST_NOOP] No active admin sockets connected for event={event_type}")
            return

        dead_sockets = []
        delivered_count = 0

        for ws, info in recipients:
            # Enforce strict branch isolation
            is_super_admin = info.role == UserRole.SUPER_ADMIN
            is_branch_authorized = str(branch_id) in info.branch_ids

            if not (is_super_admin or is_branch_authorized):
                continue

            try:
                await ws.send_json(payload)
                delivered_count += 1
            except (WebSocketDisconnect, ConnectionResetError, RuntimeError) as exc:
                logger.warning(f"[WS_DELIVERY_FAIL] Socket disconnected during send: {type(exc).__name__}")
                dead_sockets.append(ws)
            except Exception as exc:
                logger.error(f"[WS_DELIVERY_ERROR] Unexpected send error for user={info.user_id}: {exc}")
                dead_sockets.append(ws)

        # Clean up any dead sockets detected during broadcast
        if dead_sockets:
            async with self._lock:
                for ws in dead_sockets:
                    self._connections.pop(ws, None)
            logger.info(f"[WS_CLEANUP] Pruned {len(dead_sockets)} dead sockets. Remaining: {len(self._connections)}")

        logger.info(
            f"[WS_BROADCAST] event={event_type} branch_id={branch_id} "
            f"delivered={delivered_count} pruned={len(dead_sockets)}"
        )

    def sync_broadcast_order_event(
        self,
        event_type: str,
        order_data: Dict[str, Any],
        branch_id: str
    ) -> None:
        """
        Synchronous wrapper allowing background DB hooks / synchronous endpoints to trigger
        the async broadcast safely without blocking the event loop.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast_order_event(event_type, order_data, branch_id))
        except RuntimeError:
            # In non-async threads/contexts (e.g. background threads)
            try:
                asyncio.run(self.broadcast_order_event(event_type, order_data, branch_id))
            except Exception as e:
                logger.error(f"[WS_SYNC_BROADCAST_ERR] Failed to run broadcast in new event loop: {e}")

    async def ping_all(self) -> None:
        """Sends keepalive heartbeat to all connected clients and prunes dead sockets."""
        async with self._lock:
            recipients = list(self._connections.items())

        if not recipients:
            return

        dead_sockets = []
        for ws, info in recipients:
            try:
                await ws.send_json({"type": "PING", "timestamp": datetime.now(timezone.utc).isoformat()})
            except Exception:
                dead_sockets.append(ws)

        if dead_sockets:
            async with self._lock:
                for ws in dead_sockets:
                    self._connections.pop(ws, None)
            logger.info(f"[WS_HEARTBEAT_CLEANUP] Pruned {len(dead_sockets)} unresponsive sockets.")


# Global Singleton ConnectionManager instance
manager = ConnectionManager()
