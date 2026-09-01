import base64
import io
import os
import pathlib
import sys
import uuid
import pytest
from PIL import Image

# Ensure backend root is on sys.path
backend_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.tests.db import client, reset_test_db, TestingSessionLocal
from app.models import User, UserRole, Product, Category
from app.core.security import get_password_hash, create_access_token


@pytest.fixture(autouse=True)
def setup_image_test_environment():
    reset_test_db()
    db = TestingSessionLocal()

    # Create Super Admin
    super_admin = User(
        id="user-super-admin-001",
        email="superadmin@pattyproject.co.uk",
        password_hash=get_password_hash("SuperAdmin123!"),
        full_name="Super Admin",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        email_verified=True
    )
    # Create Customer
    customer = User(
        id="user-customer-001",
        email="customer@example.com",
        password_hash=get_password_hash("Customer123!"),
        full_name="Customer User",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add_all([super_admin, customer])

    cat = db.query(Category).first()
    if not cat:
        cat = Category(id="cat-burgers", name="Burgers", slug="burgers", is_active=True, display_order=0)
        db.add(cat)

    db.commit()
    db.close()


def get_token_header(user_id: str, email: str, role) -> dict:
    role_str = role if isinstance(role, str) else role.value
    token = create_access_token(
        subject=user_id,
        roles=[role_str]
    )
    return {"Authorization": f"Bearer {token}"}


def generate_image_bytes(fmt="PNG", size=(20, 20), color="blue") -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=fmt)
    return buf.getvalue()


def generate_image_data_url(fmt="PNG", size=(20, 20), color="blue") -> str:
    raw = generate_image_bytes(fmt=fmt, size=size, color=color)
    mime = "jpeg" if fmt.upper() in ["JPEG", "JPG"] else fmt.lower()
    b64 = base64.b64encode(raw).decode("utf-8")
    return f"data:image/{mime};base64,{b64}"


def test_01_create_product_with_base64_image_saves_short_url_and_file():
    """1. Create product with a valid base64 PNG/JPEG and confirm DB image_url is a short /uploads/... path and file exists."""
    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)
    png_data_url = generate_image_data_url(fmt="PNG", color="green")

    res = client.post(
        "/api/v1/products",
        headers=super_headers,
        json={
            "category_id": "cat-burgers",
            "name": "Classic Cheeseburger",
            "base_price": 9.50,
            "sku": f"BURGER-{uuid.uuid4().hex[:6].upper()}",
            "image_url": png_data_url,
            "images": [png_data_url]
        }
    )
    assert res.status_code == 200, res.text
    data = res.json()

    # Confirm image_url is converted to a short /uploads/products/ path
    assert data["image_url"].startswith("/uploads/products/prod_")
    assert data["image_url"].endswith(".png")
    assert len(data["image_url"]) < 100
    assert len(data["images"]) == 1
    assert data["images"][0].startswith("/uploads/products/prod_")
    assert len(data["images"][0]) < 100

    # Verify the physical file was written to disk
    relative_path = data["image_url"].lstrip("/")
    file_on_disk = backend_root / relative_path
    assert file_on_disk.exists()
    assert file_on_disk.stat().st_size > 0

    # Confirm database record contains short URL (never base64)
    db = TestingSessionLocal()
    prod_in_db = db.query(Product).filter(Product.id == data["id"]).first()
    assert prod_in_db is not None
    assert prod_in_db.image_url == data["image_url"]
    assert "data:image" not in prod_in_db.image_url
    assert len(prod_in_db.image_url) <= 500
    db.close()


def test_02_update_product_with_base64_replaces_image():
    """2. Update product with new base64 image and confirm replacement works."""
    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)
    initial_img = generate_image_data_url(fmt="JPEG", color="yellow")

    create_res = client.post(
        "/api/v1/products",
        headers=super_headers,
        json={
            "category_id": "cat-burgers",
            "name": "Bacon Burger",
            "base_price": 11.00,
            "sku": f"BACON-{uuid.uuid4().hex[:6].upper()}",
            "image_url": initial_img
        }
    )
    assert create_res.status_code == 200
    prod_id = create_res.json()["id"]
    old_url = create_res.json()["image_url"]
    assert old_url.endswith(".jpg")

    # Update with a new PNG base64 image
    new_img = generate_image_data_url(fmt="PNG", color="purple")
    update_res = client.put(
        f"/api/v1/products/{prod_id}",
        headers=super_headers,
        json={
            "image_url": new_img
        }
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    new_url = updated_data["image_url"]

    assert new_url != old_url
    assert new_url.startswith("/uploads/products/prod_")
    assert new_url.endswith(".png")

    # Verify new file on disk
    file_on_disk = backend_root / new_url.lstrip("/")
    assert file_on_disk.exists()


def test_03_update_product_without_changing_image_preserves_existing():
    """3. Update product without changing image and confirm existing image remains unchanged."""
    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)
    initial_img = generate_image_data_url(fmt="PNG", color="red")

    create_res = client.post(
        "/api/v1/products",
        headers=super_headers,
        json={
            "category_id": "cat-burgers",
            "name": "Smash Burger",
            "base_price": 8.00,
            "sku": f"SMASH-{uuid.uuid4().hex[:6].upper()}",
            "image_url": initial_img
        }
    )
    assert create_res.status_code == 200
    prod_id = create_res.json()["id"]
    original_url = create_res.json()["image_url"]

    # Update only name and price (image_url omitted)
    update_res = client.put(
        f"/api/v1/products/{prod_id}",
        headers=super_headers,
        json={
            "name": "Smash Burger Double",
            "base_price": 10.50
        }
    )
    assert update_res.status_code == 200
    assert update_res.json()["image_url"] == original_url
    assert update_res.json()["name"] == "Smash Burger Double"


def test_04_ordinary_image_url_works_unchanged():
    """4. Ordinary image URL (e.g. /placeholder-burger.svg, https://...) still works unchanged."""
    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)
    ordinary_urls = [
        "/placeholder-burger.svg",
        "/images/menu/classic-burger.jpg",
        "https://images.unsplash.com/photo-1568901346375-23c9450c58cd"
    ]

    for ordinary_url in ordinary_urls:
        res = client.post(
            "/api/v1/products",
            headers=super_headers,
            json={
                "category_id": "cat-burgers",
                "name": f"Product with normal URL {uuid.uuid4().hex[:4]}",
                "base_price": 7.50,
                "sku": f"NORM-{uuid.uuid4().hex[:6].upper()}",
                "image_url": ordinary_url,
                "images": [ordinary_url]
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["image_url"] == ordinary_url
        assert data["images"] == [ordinary_url]


def test_05_oversized_or_corrupt_image_returns_400():
    """5. Oversized/invalid/corrupt image returns HTTP 400."""
    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)

    # 5a. Corrupt base64 data
    corrupt_data_url = "data:image/jpeg;base64,ThisIsNotAValidBase64OrImageData!!"
    res_corrupt = client.post(
        "/api/v1/products",
        headers=super_headers,
        json={
            "category_id": "cat-burgers",
            "name": "Corrupt Image Burger",
            "base_price": 5.00,
            "image_url": corrupt_data_url
        }
    )
    assert res_corrupt.status_code == 400

    # 5b. Valid base64 encoding of non-image junk bytes
    junk_b64 = "data:image/png;base64," + base64.b64encode(b"Not an image at all").decode("utf-8")
    res_junk = client.post(
        "/api/v1/products",
        headers=super_headers,
        json={
            "category_id": "cat-burgers",
            "name": "Junk Bytes Burger",
            "base_price": 5.00,
            "image_url": junk_b64
        }
    )
    assert res_junk.status_code == 400

    # 5c. URL exceeding 500 chars (not a data URL)
    long_url = "https://example.com/very/long/path/" + ("a" * 500) + ".jpg"
    res_long = client.post(
        "/api/v1/products",
        headers=super_headers,
        json={
            "category_id": "cat-burgers",
            "name": "Long URL Burger",
            "base_price": 5.00,
            "image_url": long_url
        }
    )
    assert res_long.status_code == 400


def test_06_multipart_upload_requires_auth_and_returns_short_url():
    """6. Multipart upload endpoint requires authorization and returns stored URL."""
    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)
    customer_headers = get_token_header("user-customer-001", "customer@example.com", UserRole.CUSTOMER)

    raw_png = generate_image_bytes(fmt="PNG", color="orange")

    # 6a. Unauthenticated request -> 401
    res_unauth = client.post(
        "/api/v1/products/upload-image",
        files={"file": ("test.png", raw_png, "image/png")}
    )
    assert res_unauth.status_code == 401

    # 6b. Customer role (non-admin) -> 403
    res_cust = client.post(
        "/api/v1/products/upload-image",
        headers=customer_headers,
        files={"file": ("test.png", raw_png, "image/png")}
    )
    assert res_cust.status_code == 403

    # 6c. Super Admin -> 200 with stored URL
    res_admin = client.post(
        "/api/v1/products/upload-image",
        headers=super_headers,
        files={"file": ("test.png", raw_png, "image/png")}
    )
    assert res_admin.status_code == 200
    res_data = res_admin.json()
    assert "url" in res_data
    assert res_data["url"].startswith("/uploads/products/prod_")
    assert res_data["url"].endswith(".png")

    # Verify file exists on disk
    file_on_disk = backend_root / res_data["url"].lstrip("/")
    assert file_on_disk.exists()


def test_07_product_image_update_emits_realtime_event_with_short_url():
    """7. Successful product image update remains compatible with product_changed realtime behavior."""
    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)
    png_data_url = generate_image_data_url(fmt="PNG", color="cyan")

    with client.websocket_connect("/api/v1/ws/products") as ws:
        init_msg = ws.receive_json()
        assert init_msg["type"] == "CONNECTED"

        create_res = client.post(
            "/api/v1/products",
            headers=super_headers,
            json={
                "category_id": "cat-burgers",
                "name": "Realtime Burger",
                "base_price": 12.00,
                "sku": f"RT-{uuid.uuid4().hex[:6].upper()}",
                "image_url": png_data_url
            }
        )
        assert create_res.status_code == 200
        new_prod_id = create_res.json()["id"]

        event = ws.receive_json()
        assert event["type"] == "product_changed"
        assert event["action"] == "created"
        assert event["product_id"] == new_prod_id

        # Fetch product to ensure image URL received is short
        fetch_res = client.get(f"/api/v1/products/{new_prod_id}")
        assert fetch_res.status_code == 200
        assert fetch_res.json()["image_url"].startswith("/uploads/products/prod_")


def test_08_failed_image_processing_does_not_partially_commit():
    """8. Failed image processing must not partially commit a product change."""
    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)
    sku_unique = f"FAILSKU-{uuid.uuid4().hex[:6].upper()}"

    res = client.post(
        "/api/v1/products",
        headers=super_headers,
        json={
            "category_id": "cat-burgers",
            "name": "Failed Product",
            "base_price": 15.00,
            "sku": sku_unique,
            "image_url": "data:image/png;base64,invalid_corrupt_data"
        }
    )
    assert res.status_code == 400

    # Ensure product was NOT committed to the database
    db = TestingSessionLocal()
    prod_in_db = db.query(Product).filter(Product.sku == sku_unique).first()
    assert prod_in_db is None
    db.close()


def test_09_static_file_serving_serves_uploaded_file():
    """9. FastAPI static file serving returns uploaded file from /uploads/products/..."""
    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)
    raw_png = generate_image_bytes(fmt="PNG", color="green")

    # Upload file
    res_upload = client.post(
        "/api/v1/products/upload-image",
        headers=super_headers,
        files={"file": ("static_test.png", raw_png, "image/png")}
    )
    assert res_upload.status_code == 200
    stored_url = res_upload.json()["url"]

    # Request file from static endpoint
    res_static = client.get(stored_url)
    assert res_static.status_code == 200
    assert res_static.headers["content-type"] in ["image/png", "application/octet-stream"]
    assert len(res_static.content) == len(raw_png)
