import time
import pytest
import httpx
from unittest.mock import patch, MagicMock
from app.tests.db import client
from app.core.config import settings
from app.core.rate_limiter import contact_rate_limiter
from app.services.email_service import (
    build_contact_email_html,
    build_contact_email_text,
    send_contact_email,
)


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Reset rate limiter before each test to guarantee isolation."""
    contact_rate_limiter.reset()
    yield
    contact_rate_limiter.reset()


def test_valid_contact_submission_success():
    """Scenario 1: Valid contact submission returns 200 and success message."""
    payload = {
        "first_name": "Oliver",
        "last_name": "Twist",
        "email": "oliver.twist@example.co.uk",
        "subject": "Table reservation inquiry",
        "message": "Hello, do you have halal options for large party bookings on weekends?"
    }

    with patch("app.api.endpoints.contact.send_contact_email", return_value=True) as mock_send:
        response = client.post("/api/v1/contact", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Your message has been sent successfully."
        mock_send.assert_called_once_with(
            first_name="Oliver",
            last_name="Twist",
            email="oliver.twist@example.co.uk",
            subject="Table reservation inquiry",
            message="Hello, do you have halal options for large party bookings on weekends?"
        )


def test_missing_first_name_validation_error():
    """Scenario 2: Missing or whitespace-only first_name returns 422."""
    # Missing key
    response = client.post("/api/v1/contact", json={
        "last_name": "Smith",
        "email": "smith@example.com",
        "subject": "Inquiry",
        "message": "Hello"
    })
    assert response.status_code == 422

    # Whitespace only
    response = client.post("/api/v1/contact", json={
        "first_name": "   ",
        "last_name": "Smith",
        "email": "smith@example.com",
        "subject": "Inquiry",
        "message": "Hello"
    })
    assert response.status_code == 422


def test_missing_last_name_validation_error():
    """Scenario 3: Missing or whitespace-only last_name returns 422."""
    response = client.post("/api/v1/contact", json={
        "first_name": "John",
        "email": "john@example.com",
        "subject": "Feedback",
        "message": "Great burgers!"
    })
    assert response.status_code == 422

    response = client.post("/api/v1/contact", json={
        "first_name": "John",
        "last_name": "   ",
        "email": "john@example.com",
        "subject": "Feedback",
        "message": "Great burgers!"
    })
    assert response.status_code == 422


def test_invalid_email_validation_error():
    """Scenario 4: Invalid email format returns 422."""
    for bad_email in ["not-an-email", "test@", "@example.com", "foo@bar..com", ""]:
        response = client.post("/api/v1/contact", json={
            "first_name": "John",
            "last_name": "Doe",
            "email": bad_email,
            "subject": "Inquiry",
            "message": "Test message content"
        })
        assert response.status_code == 422


def test_missing_subject_validation_error():
    """Scenario 5: Missing or whitespace-only subject returns 422."""
    response = client.post("/api/v1/contact", json={
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "message": "Test message content"
    })
    assert response.status_code == 422

    response = client.post("/api/v1/contact", json={
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "subject": "   \n\r  ",
        "message": "Test message content"
    })
    assert response.status_code == 422


def test_missing_message_validation_error():
    """Scenario 6: Missing or whitespace-only message returns 422."""
    response = client.post("/api/v1/contact", json={
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "subject": "Question"
    })
    assert response.status_code == 422

    response = client.post("/api/v1/contact", json={
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "subject": "Question",
        "message": "    "
    })
    assert response.status_code == 422


def test_oversized_message_rejected():
    """Scenario 7: Message exceeding 5,000 characters is rejected with 422."""
    oversized = "A" * 5001
    response = client.post("/api/v1/contact", json={
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "subject": "Question",
        "message": oversized
    })
    assert response.status_code == 422


def test_resend_provider_success():
    """Scenario 8: Resend API returns 200 OK $\rightarrow$ returns 200."""
    mock_response = MagicMock(status_code=200, json=lambda: {"id": "resend-msg-12345"})
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    with patch.object(settings, "RESEND_API_KEY", "re_test_secret_api_key_12345"):
        result = send_contact_email(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            subject="Catering request",
            message="We would like to book catering for 50 people.",
            client=mock_client
        )
        assert result is True
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://api.resend.com/emails"
        sent_json = call_args[1]["json"]
        assert sent_json["to"] == [settings.CONTACT_EMAIL_TO]
        assert sent_json["reply_to"] == "jane@example.com"
        assert sent_json["subject"] == "[Patty Project Contact] Catering request"


def test_resend_provider_timeout_safe_failure():
    """Scenario 9: Resend provider timeout returns safe error without leaking keys."""
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")

    with patch.object(settings, "RESEND_API_KEY", "re_test_secret_api_key_12345"):
        with patch.object(settings, "ENVIRONMENT", "production"):
            response = client.post("/api/v1/contact", json={
                "first_name": "Alice",
                "last_name": "Brown",
                "email": "alice@example.com",
                "subject": "Support",
                "message": "Need help with order #12345."
            })
            # Should fail safely with 504 / 502
            assert response.status_code in (504, 502)
            error_body = response.text
            assert "re_test_secret_api_key" not in error_body
            assert "timed out" in error_body.lower() or "unable" in error_body.lower()


def test_resend_provider_error_status_safe_failure():
    """Scenario 10: Resend API 4xx/5xx returns safe failure."""
    mock_response = MagicMock(status_code=403, text='{"statusCode": 403, "message": "Domain not verified"}')
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    with patch.object(settings, "RESEND_API_KEY", "re_test_secret_api_key_12345"):
        with patch.object(settings, "ENVIRONMENT", "production"):
            response = client.post("/api/v1/contact", json={
                "first_name": "Bob",
                "last_name": "Builder",
                "email": "bob@example.com",
                "subject": "Delivery",
                "message": "When will you deliver to SE1?"
            })
            assert response.status_code == 502
            error_body = response.text
            assert "re_test_secret_api_key" not in error_body
            assert "Unable to deliver your message" in error_body


def test_rate_limit_exceeded_returns_429():
    """Scenario 11: Submitting more than allowed limit in window returns 429."""
    # Fast-forward time for each request so they bypass the rapid duplicate interval
    with patch("app.api.endpoints.contact.send_contact_email", return_value=True):
        with patch("time.time") as mock_time:
            base_time = 1000000.0

            # Send 5 allowed requests spaced 10 seconds apart
            for i in range(5):
                mock_time.return_value = base_time + (i * 10)
                res = client.post("/api/v1/contact", json={
                    "first_name": "User",
                    "last_name": f"Num{i}",
                    "email": f"user{i}@example.com",
                    "subject": f"Inquiry {i}",
                    "message": "Legitimate question"
                }, headers={"X-Forwarded-For": "198.51.100.22"})
                assert res.status_code == 200

            # 6th request within window should be rejected with 429
            mock_time.return_value = base_time + 60
            res = client.post("/api/v1/contact", json={
                "first_name": "User",
                "last_name": "Num6",
                "email": "user6@example.com",
                "subject": "Inquiry 6",
                "message": "Another question"
            }, headers={"X-Forwarded-For": "198.51.100.22"})
            assert res.status_code == 429
            assert "Too many" in res.json()["detail"]


def test_duplicate_rapid_submission_protection():
    """Scenario 12: Submitting two requests within 5 seconds from same IP returns 429."""
    with patch("app.api.endpoints.contact.send_contact_email", return_value=True):
        # 1st request
        res1 = client.post("/api/v1/contact", json={
            "first_name": "Fast",
            "last_name": "Clicker",
            "email": "fast@example.com",
            "subject": "Double click test",
            "message": "Clicking twice"
        }, headers={"X-Forwarded-For": "203.0.113.88"})
        assert res1.status_code == 200

        # Immediate 2nd request (0 seconds gap)
        res2 = client.post("/api/v1/contact", json={
            "first_name": "Fast",
            "last_name": "Clicker",
            "email": "fast@example.com",
            "subject": "Double click test",
            "message": "Clicking twice"
        }, headers={"X-Forwarded-For": "203.0.113.88"})
        assert res2.status_code == 429
        assert "Please wait a few seconds" in res2.json()["detail"]


def test_reply_to_and_html_escaping_sanitization():
    """Scenario 13 & 15: Reply-To is correctly constructed and HTML/script injection is sanitized."""
    malicious_first = "John<script>alert('xss')</script>"
    malicious_last = "Doe<b>bold</b>"
    malicious_sub = "Inquiry\r\nBcc: evil@hacker.com"
    malicious_msg = "Hello <img src=x onerror=alert(1)> & special characters."

    html_result = build_contact_email_html(
        first_name=malicious_first,
        last_name=malicious_last,
        email="customer@example.co.uk",
        subject=malicious_sub,
        message=malicious_msg
    )

    # Must NOT contain unescaped script or html injection tags
    assert "<script>" not in html_result
    assert "&lt;script&gt;" in html_result
    assert "alert(1)" not in html_result or "&lt;img" in html_result
    assert "mailto:customer@example.co.uk" in html_result

    text_result = build_contact_email_text(
        first_name=malicious_first,
        last_name=malicious_last,
        email="customer@example.co.uk",
        subject=malicious_sub,
        message=malicious_msg
    )
    assert "customer@example.co.uk" in text_result


def test_resend_api_key_never_leaked_in_response():
    """Scenario 14: Resend API key is never exposed in client responses."""
    with patch.object(settings, "RESEND_API_KEY", "re_super_secret_production_key_xyz987"):
        with patch("app.api.endpoints.contact.send_contact_email", return_value=True):
            response = client.post("/api/v1/contact", json={
                "first_name": "Safe",
                "last_name": "User",
                "email": "safe@example.com",
                "subject": "Security Check",
                "message": "Checking response body"
            })
            assert response.status_code == 200
            assert "re_super_secret_production_key_xyz987" not in response.text
            assert "re_super_secret" not in response.text
