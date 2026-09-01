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


@dataclass
class ProductConnectionInfo:
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
    Thread-safe WebSocket connection manager for Patty Project:
    - Admin order event channels with strict branch isolation.
    - Customer product availability channels for real-time out-of-stock updates.
    """

    def __init__(self):
        self._connections: Dict[WebSocket, AdminConnectionInfo] = {}
        self._product_connections: Dict[WebSocket, ProductConnectionInfo] = {}
        self._lock = asyncio.Lock()
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def active_connections_count(self) -> int:
        return len(self._connections)

    @property
    def active_product_connections_count(self) -> int:
        return len(self._product_connections)

    async def connect_products(self, websocket: WebSocket) -> None:
        """Accepts and registers a customer read-only product availability WebSocket connection."""
        await websocket.accept()
        try:
            self._main_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        async with self._lock:
            self._product_connections[websocket] = ProductConnectionInfo()
        logger.info(
            f"[WS_PRODUCT_CONNECT] active_product_connections={len(self._product_connections)}"
        )

    async def disconnect_products(self, websocket: WebSocket) -> None:
        """Unregisters a product WebSocket connection safely."""
        async with self._lock:
            info = self._product_connections.pop(websocket, None)
        if info:
            logger.info(
                f"[WS_PRODUCT_DISCONNECT] active_product_connections={len(self._product_connections)}"
            )

    async def broadcast_product_availability(
        self,
        product_id: str,
        is_out_of_stock: bool
    ) -> None:
        """
        Broadcasts product availability changes to all connected customer browsers in real-time.
        Minimal, non-sensitive payload.
        Isolates failures so a broken socket never interrupts delivery to other clients.
        """
        payload = {
            "type": "product_availability_changed",
            "product_id": str(product_id),
            "is_out_of_stock": bool(is_out_of_stock),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        async with self._lock:
            recipients = list(self._product_connections.keys())

        if not recipients:
            logger.debug(f"[WS_PRODUCT_BROADCAST_NOOP] No active customer sockets for product={product_id}")
            return

        dead_sockets = []
        delivered_count = 0

        for ws in recipients:
            try:
                await ws.send_json(payload)
                delivered_count += 1
            except (WebSocketDisconnect, ConnectionResetError, RuntimeError) as exc:
                logger.warning(f"[WS_PRODUCT_DELIVERY_FAIL] Socket disconnected during send: {type(exc).__name__}")
                dead_sockets.append(ws)
            except Exception as exc:
                logger.error(f"[WS_PRODUCT_DELIVERY_ERROR] Unexpected send error: {exc}")
                dead_sockets.append(ws)

        # Clean up any dead sockets detected during broadcast
        if dead_sockets:
            async with self._lock:
                for ws in dead_sockets:
                    self._product_connections.pop(ws, None)
            logger.info(f"[WS_PRODUCT_CLEANUP] Pruned {len(dead_sockets)} dead sockets. Remaining: {len(self._product_connections)}")

        logger.info(
            f"[WS_PRODUCT_BROADCAST] product_id={product_id} is_out_of_stock={is_out_of_stock} "
            f"delivered={delivered_count} pruned={len(dead_sockets)}"
        )

    def sync_broadcast_product_availability(
        self,
        product_id: str,
        is_out_of_stock: bool
    ) -> None:
        """
        Synchronous wrapper allowing synchronous endpoints to trigger the async product broadcast safely.
        Uses main ASGI event loop via run_coroutine_threadsafe when called from thread pools.
        """
        coro = self.broadcast_product_availability(product_id, is_out_of_stock)
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(coro)
                return
        except RuntimeError:
            pass

        if self._main_loop and self._main_loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self._main_loop)
        else:
            try:
                asyncio.run(coro)
            except Exception as e:
                logger.error(f"[WS_PRODUCT_SYNC_ERR] Failed to run product broadcast: {e}")

    async def broadcast_product_changed(
        self,
        action: str,
        product_id: str,
        branch_id: Optional[str] = None
    ) -> None:
        """
        Broadcasts product catalog changes (created, updated, deleted, availability_changed)
        to all connected customer browsers in real-time.
        Minimal, non-sensitive payload.
        Isolates failures so a broken socket never interrupts delivery to other clients.
        """
        payload = {
            "type": "product_changed",
            "action": str(action),
            "product_id": str(product_id),
            "branch_id": str(branch_id) if branch_id else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        async with self._lock:
            recipients = list(self._product_connections.keys())

        if not recipients:
            logger.debug(f"[WS_PRODUCT_CHANGE_NOOP] No active customer sockets for product={product_id} action={action}")
            return

        dead_sockets = []
        delivered_count = 0

        for ws in recipients:
            try:
                await ws.send_json(payload)
                delivered_count += 1
            except (WebSocketDisconnect, ConnectionResetError, RuntimeError) as exc:
                logger.warning(f"[WS_PRODUCT_CHANGE_FAIL] Socket disconnected during send: {type(exc).__name__}")
                dead_sockets.append(ws)
            except Exception as exc:
                logger.error(f"[WS_PRODUCT_CHANGE_ERROR] Unexpected send error: {exc}")
                dead_sockets.append(ws)

        if dead_sockets:
            async with self._lock:
                for ws in dead_sockets:
                    self._product_connections.pop(ws, None)
            logger.info(f"[WS_PRODUCT_CHANGE_CLEANUP] Pruned {len(dead_sockets)} dead sockets. Remaining: {len(self._product_connections)}")

        logger.info(
            f"[WS_PRODUCT_CHANGE_BROADCAST] action={action} product_id={product_id} branch_id={branch_id} "
            f"delivered={delivered_count} pruned={len(dead_sockets)}"
        )

    def sync_broadcast_product_changed(
        self,
        action: str,
        product_id: str,
        branch_id: Optional[str] = None
    ) -> None:
        """
        Synchronous wrapper allowing synchronous endpoints to trigger the async product catalog broadcast safely.
        """
        coro = self.broadcast_product_changed(action, product_id, branch_id)
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(coro)
                return
        except RuntimeError:
            pass

        if self._main_loop and self._main_loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self._main_loop)
        else:
            try:
                asyncio.run(coro)
            except Exception as e:
                logger.error(f"[WS_PRODUCT_CHANGE_SYNC_ERR] Failed to run product change broadcast: {e}")

    async def broadcast_shop_status(
        self,
        is_open: bool,
        opening_time: str,
        closing_time: str,
        reason: str = "OPEN"
    ) -> None:
        """
        Broadcasts shop open/closed status changes to all connected customers and admins in real time.
        """
        payload = {
            "type": "shop_status_changed",
            "is_open": bool(is_open),
            "opening_time": str(opening_time),
            "closing_time": str(closing_time),
            "reason": str(reason),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        async with self._lock:
            product_recipients = list(self._product_connections.keys())
            admin_recipients = list(self._connections.keys())

        dead_product = []
        dead_admin = []
        delivered_count = 0

        for ws in product_recipients:
            try:
                await ws.send_json(payload)
                delivered_count += 1
            except Exception:
                dead_product.append(ws)

        for ws in admin_recipients:
            try:
                await ws.send_json(payload)
                delivered_count += 1
            except Exception:
                dead_admin.append(ws)

        if dead_product or dead_admin:
            async with self._lock:
                for ws in dead_product:
                    self._product_connections.pop(ws, None)
                for ws in dead_admin:
                    self._connections.pop(ws, None)

        logger.info(
            f"[WS_SHOP_STATUS_BROADCAST] is_open={is_open} hours={opening_time}-{closing_time} "
            f"delivered={delivered_count}"
        )

    def sync_broadcast_shop_status(
        self,
        is_open: bool,
        opening_time: str,
        closing_time: str,
        reason: str = "OPEN"
    ) -> None:
        """
        Synchronous wrapper allowing synchronous endpoints to trigger the async shop status broadcast safely.
        """
        coro = self.broadcast_shop_status(is_open, opening_time, closing_time, reason)
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(coro)
                return
        except RuntimeError:
            pass

        if self._main_loop and self._main_loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self._main_loop)
        else:
            try:
                asyncio.run(coro)
            except Exception as e:
                logger.error(f"[WS_SHOP_STATUS_SYNC_ERR] Failed to run shop status broadcast: {e}")

    async def connect(self, websocket: WebSocket, user_id: str, role: str, branch_ids: Set[str]) -> None:
        """Accepts and registers a verified admin WebSocket connection."""
        await websocket.accept()
        try:
            self._main_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
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
        coro = self.broadcast_order_event(event_type, order_data, branch_id)
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(coro)
                return
        except RuntimeError:
            pass

        if self._main_loop and self._main_loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self._main_loop)
        else:
            try:
                asyncio.run(coro)
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
