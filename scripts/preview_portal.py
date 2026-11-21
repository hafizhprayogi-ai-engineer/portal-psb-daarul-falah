"""Periksa tampilan portal pada browser Chrome terisolasi dan simpan pratinjau."""

import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / "test-results" / "portal-preview"
    output.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        for name, width, height in [
            ("desktop", 1440, 960),
            ("mobile", 390, 844),
            ("mobile-small", 320, 740),
            ("tablet", 768, 1024),
        ]:
            context = browser.new_context(
                viewport={"width": width, "height": height}, device_scale_factor=1
            )
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(args.base_url.rstrip("/") + "/login", wait_until="networkidle")
            assert response.status == 200
            page.locator(".portal-people").wait_for(state="visible")
            assert page.locator(".brand-logo").is_visible()
            assert page.get_by_role("heading", name="Masuk ke portal").is_visible()
            assert page.get_by_text("LINGKUNGAN DEMONSTRASI", exact=False).count() == 0
            dimensions = page.evaluate("""() => ({
                page: document.documentElement.scrollWidth,
                viewport: window.innerWidth,
                images: [...document.querySelectorAll('img')].map(image => ({
                    source: image.getAttribute('src'), loaded: image.complete && image.naturalWidth > 0
                }))
            })""")
            assert dimensions["page"] <= dimensions["viewport"], dimensions
            assert all(image["loaded"] for image in dimensions["images"]), dimensions
            password = page.get_by_label("Kata sandi", exact=True)
            password.fill("Contoh-kata-sandi")
            page.get_by_role("button", name="Tampilkan kata sandi", exact=True).click()
            assert password.get_attribute("type") == "text"
            page.get_by_role("button", name="Sembunyikan kata sandi", exact=True).click()
            assert password.get_attribute("type") == "password"
            password.fill("")
            password.evaluate("(element) => element.blur()")
            page.evaluate("window.scrollTo(0, 0)")
            intro = page.locator(".portal-intro").bounding_box()
            people = page.locator(".portal-people").bounding_box()
            assert (
                intro["y"] + intro["height"] <= people["y"]
            ), "Teks sambutan bertumpuk dengan foto santri."
            page.screenshot(path=str(output / f"{name}.png"), full_page=True)
            assert not errors, errors
            print(
                f"{name} {width}x{height}: gambar, formulir, tombol kata sandi, dan lebar halaman sesuai."
            )
            context.close()
        browser.close()
    print(f"Pratinjau tersimpan di {output}")


if __name__ == "__main__":
    main()
