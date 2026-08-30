import time
import threading
from collections import defaultdict
from typing import Dict, List, Optional
from fastapi import Request, HTTPException

# Rate limiting rules for public contact form
MAX_CONTACT_REQUESTS_PER_WINDOW = 5
CONTACT_WINDOW_SECONDS = 600  # 10 minutes
MIN_CONTACT_INTERVAL_SECONDS = 5  # minimum seconds between requests to block rapid duplicates


class ContactRateLimiter:
    def __init__(
        self,
        max_requests: int = MAX_CONTACT_REQUESTS_PER_WINDOW,
        window_seconds: int = CONTACT_WINDOW_SECONDS,
        min_interval_seconds: int = MIN_CONTACT_INTERVAL_SECONDS,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.min_interval_seconds = min_interval_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def get_client_ip(self, request: Request) -> str:
        """Extracts the real client IP address considering reverse proxies / Cloudflare."""
        # 1. Cloudflare header
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip and cf_ip.strip():
            return cf_ip.strip()

        # 2. X-Forwarded-For (take the first client IP)
        x_forwarded = request.headers.get("x-forwarded-for")
        if x_forwarded and x_forwarded.strip():
            client_ip = x_forwarded.split(",")[0].strip()
            if client_ip:
                return client_ip

        # 3. X-Real-IP
        x_real_ip = request.headers.get("x-real-ip")
        if x_real_ip and x_real_ip.strip():
            return x_real_ip.strip()

        # 4. Direct socket client host
        if request.client and request.client.host:
            return request.client.host

        return "127.0.0.1"

    def check(self, request: Request) -> None:
        """
        Enforces rate limits on contact form submissions.
        Raises HTTPException 429 if the client exceeds the limit or submits too rapidly.
        """
        client_ip = self.get_client_ip(request)
        now = time.time()

        with self._lock:
            history = self._requests[client_ip]

            # Prune records older than the window
            cutoff = now - self.window_seconds
            history = [t for t in history if t > cutoff]
            self._requests[client_ip] = history

            # Check duplicate / rapid spam protection
            if history:
                last_time = history[-1]
                if now - last_time < self.min_interval_seconds:
                    raise HTTPException(
                        status_code=429,
                        detail="Please wait a few seconds before submitting another message."
                    )

            # Check window limit
            if len(history) >= self.max_requests:
                raise HTTPException(
                    status_code=429,
                    detail="Too many contact form submissions. Please wait a few minutes before trying again."
                )

            # Record this attempt
            history.append(now)

    def reset(self) -> None:
        """Resets all recorded rate limit history (useful for test isolation)."""
        with self._lock:
            self._requests.clear()


contact_rate_limiter = ContactRateLimiter()


# Rate limiting rules for password reset flows
MAX_RESET_REQUESTS_PER_IP = 5
MAX_RESET_REQUESTS_PER_EMAIL = 3
RESET_WINDOW_SECONDS = 900  # 15 minutes
MIN_RESET_INTERVAL_SECONDS = 5


class PasswordResetRateLimiter:
    def __init__(
        self,
        max_ip_requests: int = MAX_RESET_REQUESTS_PER_IP,
        max_email_requests: int = MAX_RESET_REQUESTS_PER_EMAIL,
        window_seconds: int = RESET_WINDOW_SECONDS,
        min_interval_seconds: int = MIN_RESET_INTERVAL_SECONDS,
    ):
        self.max_ip_requests = max_ip_requests
        self.max_email_requests = max_email_requests
        self.window_seconds = window_seconds
        self.min_interval_seconds = min_interval_seconds
        self._ip_requests: Dict[str, List[float]] = defaultdict(list)
        self._email_requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def get_client_ip(self, request: Request) -> str:
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip and cf_ip.strip():
            return cf_ip.strip()

        x_forwarded = request.headers.get("x-forwarded-for")
        if x_forwarded and x_forwarded.strip():
            client_ip = x_forwarded.split(",")[0].strip()
            if client_ip:
                return client_ip

        x_real_ip = request.headers.get("x-real-ip")
        if x_real_ip and x_real_ip.strip():
            return x_real_ip.strip()

        if request.client and request.client.host:
            return request.client.host

        return "127.0.0.1"

    def check_forgot_password(self, request: Request, email: Optional[str] = None) -> None:
        """Enforces rate limits on forgot-password requests by IP and email."""
        client_ip = self.get_client_ip(request)
        clean_email = email.strip().lower() if email else ""
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            # IP check
            ip_history = [t for t in self._ip_requests[client_ip] if t > cutoff]
            self._ip_requests[client_ip] = ip_history

            if ip_history:
                last_time = ip_history[-1]
                if now - last_time < self.min_interval_seconds:
                    raise HTTPException(
                        status_code=429,
                        detail="Please wait a few seconds before requesting another reset link."
                    )

            if len(ip_history) >= self.max_ip_requests:
                raise HTTPException(
                    status_code=429,
                    detail="Too many password reset requests. Please wait a few minutes before trying again."
                )

            # Email check (if provided)
            if clean_email:
                email_history = [t for t in self._email_requests[clean_email] if t > cutoff]
                self._email_requests[clean_email] = email_history

                if len(email_history) >= self.max_email_requests:
                    raise HTTPException(
                        status_code=429,
                        detail="Too many password reset requests for this account. Please wait a few minutes before trying again."
                    )

                email_history.append(now)

            ip_history.append(now)

    def check_reset_password(self, request: Request) -> None:
        """Enforces rate limits on password-reset submissions by IP to prevent token brute-forcing."""
        client_ip = self.get_client_ip(request)
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            ip_history = [t for t in self._ip_requests[f"reset_{client_ip}"] if t > cutoff]
            self._ip_requests[f"reset_{client_ip}"] = ip_history

            if len(ip_history) >= (self.max_ip_requests * 2):
                raise HTTPException(
                    status_code=429,
                    detail="Too many password reset attempts. Please request a new reset link."
                )

            ip_history.append(now)

    def reset(self) -> None:
        """Resets all recorded rate limit history (useful for test isolation)."""
        with self._lock:
            self._ip_requests.clear()
            self._email_requests.clear()


password_reset_rate_limiter = PasswordResetRateLimiter()
