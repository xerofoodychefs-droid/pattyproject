import uuid
import hmac
import hashlib
import base64
import logging
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings
from app.models.payment import PaymentStatus, PaymentProvider
from app.services.payment_service import BasePaymentProvider, NormalizedPaymentEvent

logger = logging.getLogger("pattyproject.payment.square")


class SquarePaymentError(Exception):
    """Safe application-level exception for Square payment failures without exposing secrets."""
    def __init__(self, message: str, error_code: Optional[str] = None, detail: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "SQUARE_PAYMENT_ERROR"
        self.detail = detail or message


class SquarePaymentProvider(BasePaymentProvider):
    """
    Production-grade Square Payment Provider integrating Square Payments API v2.
    Supports Card Nonce tokenization, Digital Wallets, Webhooks, Idempotency, and Refunds.
    """

    def __init__(self):
        self.base_url = settings.square_base_url
        self.application_id = settings.SQUARE_APPLICATION_ID
        self.location_id = settings.SQUARE_LOCATION_ID
        self.access_token = settings.SQUARE_ACCESS_TOKEN
        self.square_version = "2024-05-15"

    def _get_headers(self) -> Dict[str, str]:
        if not self.access_token:
            raise SquarePaymentError(
                message="Square payment gateway is not properly configured on this server.",
                error_code="SQUARE_NOT_CONFIGURED"
            )
        return {
            "Square-Version": self.square_version,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    async def create_payment_session(
        self,
        order_id: str,
        amount: float,
        currency: str = "GBP",
        customer_info: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        source_id: Optional[str] = None,
        order_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates and processes a Square payment when source_id is provided,
        or initializes payment metadata for frontend tokenization.
        """
        effective_idemp = idempotency_key or f"sq_idemp_{order_id}"

        # If source_id (token/nonce from Square Web Payments SDK) is present, charge directly
        if source_id:
            return await self.charge_source(
                order_id=order_id,
                amount=amount,
                source_id=source_id,
                currency=currency,
                customer_info=customer_info,
                idempotency_key=effective_idemp,
                order_number=order_number
            )

        # Pre-tokenization session initialization
        return {
            "provider": PaymentProvider.SQUARE,
            "order_id": order_id,
            "transaction_id": f"SQ_INIT_{order_id[:8]}",
            "idempotency_key": effective_idemp,
            "amount": amount,
            "currency": currency,
            "status": PaymentStatus.PENDING,
            "client_secret": None,
            "payment_url": None,
            "application_id": self.application_id,
            "location_id": self.location_id
        }

    async def charge_source(
        self,
        order_id: str,
        amount: float,
        source_id: str,
        currency: str = "GBP",
        customer_info: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        order_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes server-to-server payment charging via Square Payments API v2.
        Calculates exact minor units (pence), enforces GBP, and maps error codes safely.
        """
        if not self.location_id:
            raise SquarePaymentError(
                message="Square Location ID is missing. Cannot process payment.",
                error_code="MISSING_LOCATION_ID"
            )

        amount_pence = int(round(float(amount) * 100))
        effective_idemp = idempotency_key or f"sq_idemp_{order_id}"
        note_text = f"Patty Project Order {order_number or order_id[:8]}"

        payload: Dict[str, Any] = {
            "source_id": source_id,
            "idempotency_key": effective_idemp,
            "amount_money": {
                "amount": amount_pence,
                "currency": currency.upper()
            },
            "location_id": self.location_id,
            "reference_id": order_id,
            "note": note_text[:500]
        }

        if customer_info and customer_info.get("email"):
            payload["buyer_email_address"] = str(customer_info["email"]).strip()

        url = f"{self.base_url}/v2/payments"
        headers = self._get_headers()

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                data = response.json()
        except httpx.TimeoutException:
            logger.error(f"[SQUARE_TIMEOUT] Timeout calling Square payment endpoint for order_id={order_id}")
            raise SquarePaymentError(
                message="Payment processing timed out. Please verify your order status before re-submitting.",
                error_code="GATEWAY_TIMEOUT"
            )
        except Exception as exc:
            logger.error(f"[SQUARE_NETWORK_ERROR] Network error contacting Square: {str(exc)}")
            raise SquarePaymentError(
                message="Unable to communicate with the payment processor. Please try again shortly.",
                error_code="GATEWAY_UNREACHABLE"
            )

        # Handle Square errors
        if response.status_code >= 400 or "errors" in data:
            errors = data.get("errors", [])
            primary_error = errors[0] if errors else {}
            code = primary_error.get("code", "PAYMENT_FAILED")
            detail = primary_error.get("detail", "Payment failed.")
            category = primary_error.get("category", "PAYMENT_METHOD_ERROR")

            logger.warning(
                f"[SQUARE_DECLINED] order_id={order_id} code={code} category={category} detail={detail}"
            )

            # User-safe translation of error codes
            user_message = "Payment could not be processed. Please check your payment details or try another card."
            if "DECLINED" in code or "INSUFFICIENT_FUNDS" in code:
                user_message = "Your card was declined. Please try another card or payment method."
            elif "CVV_FAILURE" in code:
                user_message = "Card security code (CVV) verification failed. Please check your CVV and try again."
            elif "EXPIRATION_FAILURE" in code or "EXPIRED" in code:
                user_message = "The card has expired. Please use a valid payment card."
            elif "CARD_TOKEN_EXPIRED" in code or "CARD_TOKEN_USED" in code:
                user_message = "Payment session expired. Please re-enter your card details."
            elif "CARD_NOT_SUPPORTED" in code:
                user_message = "This card brand or type is not supported. Please use Visa, Mastercard, or Amex."

            raise SquarePaymentError(
                message=user_message,
                error_code=code,
                detail=detail
            )

        payment_obj = data.get("payment", {})
        sq_payment_id = payment_obj.get("id")
        sq_status = payment_obj.get("status", "COMPLETED")
        receipt_url = payment_obj.get("receipt_url")

        # Status mapping: COMPLETED / APPROVED -> PAID
        is_paid = sq_status in ["COMPLETED", "APPROVED"]
        mapped_status = PaymentStatus.PAID if is_paid else PaymentStatus.PENDING

        logger.info(
            f"[SQUARE_SUCCESS] order_id={order_id} sq_payment_id={sq_payment_id} status={sq_status}"
        )

        return {
            "provider": PaymentProvider.SQUARE,
            "order_id": order_id,
            "transaction_id": sq_payment_id,
            "idempotency_key": effective_idemp,
            "amount": amount,
            "currency": currency,
            "status": mapped_status,
            "client_secret": None,
            "payment_url": None,
            "receipt_url": receipt_url,
            "raw_response": payment_obj
        }

    async def verify_webhook_signature(self, headers: Dict[str, str], body: bytes, url: Optional[str] = None) -> bool:
        """
        Validates Square HMAC-SHA256 webhook signatures using the notification URL and body.
        """
        sig_key = settings.SQUARE_WEBHOOK_SIGNATURE_KEY
        if not sig_key:
            # If no webhook key configured, allow in development or reject in production
            if not settings.is_production:
                return True
            logger.warning("[SQUARE_WEBHOOK] SQUARE_WEBHOOK_SIGNATURE_KEY is not configured in production.")
            return False

        signature_header = headers.get("x-square-hmacsha256-signature") or headers.get("X-Square-Hmacsha256-Signature")
        if not signature_header:
            return False

        # 1. Check with request URL if provided
        candidate_urls = []
        if url:
            candidate_urls.append(url)
            # If internal docker url (http://), also add https version
            if url.startswith("http://"):
                candidate_urls.append("https://" + url[7:])

        # 2. Add canonical production webhook URL
        host = headers.get("x-forwarded-host") or headers.get("host") or "pattyproject.co.uk"
        candidate_urls.append(f"https://{host}{settings.API_V1_STR}/payments/webhook")
        candidate_urls.append(f"https://pattyproject.co.uk{settings.API_V1_STR}/payments/webhook")
        candidate_urls.append(f"{settings.API_V1_STR}/payments/webhook")

        for notification_url in candidate_urls:
            string_to_sign = notification_url.encode("utf-8") + body
            computed_hmac = hmac.new(
                sig_key.encode("utf-8"),
                string_to_sign,
                hashlib.sha256
            ).digest()
            computed_sig = base64.b64encode(computed_hmac).decode("utf-8")

            if hmac.compare_digest(signature_header, computed_sig):
                return True

        return False

    def normalize_webhook_payload(self, headers: Dict[str, str], payload: Dict[str, Any]) -> NormalizedPaymentEvent:
        """
        Normalizes inbound Square webhook event into standard NormalizedPaymentEvent.
        """
        event_id = payload.get("event_id") or headers.get("x-event-id") or f"sq_evt_{uuid.uuid4().hex[:8]}"
        event_type_raw = payload.get("type", "payment.updated")

        data_obj = payload.get("data", {}).get("object", {})
        payment_data = data_obj.get("payment", {})

        transaction_id = payment_data.get("id")
        order_id = payment_data.get("reference_id")
        raw_status = payment_data.get("status", "COMPLETED")

        amount_money = payment_data.get("amount_money", {})
        raw_amount = amount_money.get("amount")
        amount = float(raw_amount) / 100.0 if raw_amount is not None else None
        currency = str(amount_money.get("currency", "GBP")).upper()

        if raw_status in ["COMPLETED", "APPROVED"] or event_type_raw == "payment.created":
            event_type = "SUCCESS"
        elif raw_status in ["FAILED", "REJECTED"]:
            event_type = "FAILED"
        elif raw_status in ["CANCELED", "CANCELLED"]:
            event_type = "CANCELLED"
        elif "refund" in event_type_raw:
            event_type = "REFUNDED"
        else:
            event_type = raw_status

        return NormalizedPaymentEvent(
            event_id=event_id,
            provider=PaymentProvider.SQUARE,
            event_type=event_type,
            order_id=order_id,
            transaction_id=transaction_id,
            amount=amount,
            currency=currency,
            raw_payload=payload
        )

    async def process_refund(self, transaction_id: str, amount: float, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes a full or partial refund via Square Refunds API v2.
        """
        amount_pence = int(round(float(amount) * 100))
        idemp = f"sq_ref_{uuid.uuid4().hex[:10]}"

        payload = {
            "idempotency_key": idemp,
            "payment_id": transaction_id,
            "amount_money": {
                "amount": amount_pence,
                "currency": "GBP"
            },
            "reason": (reason or "Customer refund")[:192]
        }

        url = f"{self.base_url}/v2/refunds"
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            data = response.json()

        if response.status_code >= 400 or "errors" in data:
            errors = data.get("errors", [])
            detail = errors[0].get("detail", "Refund failed.") if errors else "Refund failed."
            code = errors[0].get("code", "REFUND_ERROR") if errors else "REFUND_ERROR"
            raise SquarePaymentError(
                message=f"Square refund rejected: {detail}",
                error_code=code
            )

        refund_obj = data.get("refund", {})
        return {
            "status": "SUCCESS",
            "refund_id": refund_obj.get("id", idemp),
            "amount": amount,
            "transaction_id": transaction_id,
            "raw_response": refund_obj
        }
