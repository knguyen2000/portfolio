"""Tests for Story 4: gallery page includes preconnect hint for GSAP CDN."""

from __future__ import annotations

from pathlib import Path

GALLERY_PATH = Path(__file__).resolve().parent.parent / "pages" / "gallery.py"


def _gallery_source() -> str:
    return GALLERY_PATH.read_text(encoding="utf-8")


class TestGSAPPreconnect:
    """The gallery page must include a preconnect link for cdnjs before GSAP scripts."""

    def test_preconnect_present(self):
        src = _gallery_source()
        assert '<link rel="preconnect" href="https://cdnjs.cloudflare.com">' in src

    def test_preconnect_before_gsap_scripts(self):
        src = _gallery_source()
        preconnect_pos = src.index(
            '<link rel="preconnect" href="https://cdnjs.cloudflare.com">'
        )
        gsap_pos = src.index("gsap.min.js")
        assert preconnect_pos < gsap_pos, (
            "Preconnect hint must appear before the GSAP script tags"
        )

    def test_gsap_scripts_still_present(self):
        src = _gallery_source()
        assert "gsap/3.12.2/gsap.min.js" in src
        assert "gsap/3.12.2/ScrollTrigger.min.js" in src
