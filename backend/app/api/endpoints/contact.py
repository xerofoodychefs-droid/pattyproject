from fastapi import APIRouter, Request, status
from app.schemas.contact import ContactFormRequest, ContactFormResponse
from app.core.rate_limiter import contact_rate_limiter
from app.services.email_service import send_contact_email

router = APIRouter()


@router.post(
    "",
    response_model=ContactFormResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit Contact Form Message",
    description="Validates customer message, applies anti-spam rate limiting, and sends contact email via Resend to xerofoodychefs@gmail.com."
)
@router.post(
    "/",
    response_model=ContactFormResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False
)
def submit_contact_form(
    payload: ContactFormRequest,
    request: Request
) -> ContactFormResponse:
    """
    Public Contact Us endpoint.
    - Validates required fields, formats, and maximum sizes.
    - Enforces rate limits per IP.
    - Sends message to xerofoodychefs@gmail.com with customer email as Reply-To.
    """
    # 1. Anti-spam rate limiting check
    contact_rate_limiter.check(request)

    # 2. Transmit email via Resend service
    send_contact_email(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        subject=payload.subject,
        message=payload.message
    )

    # 3. Return clean success response
    return ContactFormResponse(message="Your message has been sent successfully.")
