"""QR code generation for a shop's customer entry URL."""
import io

import segno

from app.core.config import settings


def customer_url(shop_slug: str) -> str:
    """The URL the QR points to — the customer portal for this shop."""
    return f"{settings.frontend_base_url.rstrip('/')}/s/{shop_slug}"


def qr_svg(shop_slug: str, scale: int = 8) -> str:
    """Return an SVG string of the QR code for the shop's customer URL."""
    qr = segno.make(customer_url(shop_slug), error="m")
    buffer = io.BytesIO()
    qr.save(buffer, kind="svg", scale=scale, border=2)
    return buffer.getvalue().decode("utf-8")
