import asyncio
import logging
from typing import Optional
from app.core.database import SessionLocal
from app.core.websocket_manager import manager
from app.services.shop_hours_service import get_authoritative_shop_status

logger = logging.getLogger("pattyproject.shop_ticker")


class ShopHoursTicker:
    """
    Background asynchronous ticker that periodically evaluates UK shop opening/closing hours.
    Automatically broadcasts real-time transition events to all connected clients when
    the shop crosses opening or closing boundaries without requiring admin intervention.
    """

    def __init__(self, interval_seconds: float = 10.0):
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._last_is_open: Optional[bool] = None
        self._last_opening_time: Optional[str] = None
        self._last_closing_time: Optional[str] = None

    def start(self) -> None:
        """Starts the background ticker task on the running asyncio event loop."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop())
            logger.info(f"[SHOP_TICKER_START] Ticker started with {self.interval_seconds}s interval.")

    def stop(self) -> None:
        """Cancels the background ticker task."""
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("[SHOP_TICKER_STOP] Ticker stopped.")

    async def _run_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.interval_seconds)
                self.check_and_broadcast_transition()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"[SHOP_TICKER_ERROR] Unexpected error in ticker: {exc}")

    def check_and_broadcast_transition(self) -> None:
        """Synchronously checks if a state transition occurred and triggers broadcast if needed."""
        db = SessionLocal()
        try:
            status = get_authoritative_shop_status(db)
            is_open = status["is_open"]
            opening_time = status["opening_time"]
            closing_time = status["closing_time"]
            reason = status["reason"]

            # Initialize baseline state on first evaluation
            if self._last_is_open is None:
                self._last_is_open = is_open
                self._last_opening_time = opening_time
                self._last_closing_time = closing_time
                return

            # Check if open/closed state transitioned or hours changed
            if is_open != self._last_is_open:
                logger.info(
                    f"[SHOP_STATUS_TRANSITION] Shop transitioned from "
                    f"{'OPEN' if self._last_is_open else 'CLOSED'} -> {'OPEN' if is_open else 'CLOSED'}"
                )
                self._last_is_open = is_open
                self._last_opening_time = opening_time
                self._last_closing_time = closing_time
                manager.sync_broadcast_shop_status(
                    is_open=is_open,
                    opening_time=opening_time,
                    closing_time=closing_time,
                    reason=reason
                )
        except Exception as exc:
            logger.error(f"[SHOP_TICKER_CHECK_ERR] Failed to evaluate shop status: {exc}")
        finally:
            db.close()


shop_ticker = ShopHoursTicker(interval_seconds=10.0)
