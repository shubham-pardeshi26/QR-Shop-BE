"""Small shared utilities."""
import re

_slug_strip = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Lowercase, hyphenated, URL-safe slug (e.g. 'Bob's Cafe!' -> 'bobs-cafe')."""
    slug = _slug_strip.sub("-", value.strip().lower()).strip("-")
    return slug or "shop"
