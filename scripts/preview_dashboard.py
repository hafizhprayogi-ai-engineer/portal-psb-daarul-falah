"""Periksa dashboard dan halaman menu seluruh peran pada Chrome terisolasi."""

import argparse
from urllib.parse import urlsplit
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def check_width(page):
    sizes = page.evaluate("() => [document.documentElement.scrollWidth, innerWidth]")
    assert sizes[0] <= sizes[1], f"Halaman melebar: {page.url} {sizes}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    root = Path(__file__).resolve().parents[1]
    text = (root / "instance/akun-demo.txt").read_text(encoding="utf-8")
    password = next(
        line.split(": ", 1)[1]
        for line in text.splitlines()
        if line.startswith("Password seluruh akun: ")
    )
    output = root / "test-results/dashboard-preview"
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        for username in ("MI-01", "admin.demo", "bendahara.demo", "berkas.demo", "rangkap.demo"):
            storage = None
            sizes = (
                ((390, 844), (1440, 1000), (320, 740), (768, 1024))
                if username == "MI-01"
                else ((390, 844), (1440, 1000))
            )
            for width, height in sizes:
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    device_scale_factor=1,
                    storage_state=storage,
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                if storage is None:
                    page.goto(base + "/login", wait_until="networkidle")
                    page.get_by_label("Nomor pendaftaran / username petugas").fill(username)
                    page.get_by_label("Kata sandi", exact=True).fill(password)
                    page.get_by_role("button", name="Masuk ke portal", exact=False).click()
                else:
                    page.goto(base + "/dashboard", wait_until="networkidle")
                page.wait_for_url(
                    lambda url: urlsplit(url).path == "/dashboard"
                    or urlsplit(url).path.startswith("/peserta/"),
                    wait_until="networkidle",
                )
                storage = context.storage_state()
                home = page.url
                expect(page.locator("#menu")).to_be_visible()
                check_width(page)
                if username == "MI-01":
                    assert page.locator(".flow-card [role=progressbar]").count() == 1
                    assert page.locator('form[action$="/bio"]').count() == 0
                    assert page.locator('form[action$="/schedule"]').count() == 0
                tiles = page.locator("#menu .app-menu-tile")
                links = tiles.evaluate_all(
                    '(elements) => elements.map(element => element.getAttribute("href"))'
                )
                assert len(links) >= 6
                if width == 390:
                    expect(page.locator(".mobile-dock")).to_be_visible()
                    page.get_by_role("link", name="Buka semua menu", exact=True).click()
                    expect(page.locator("#app-menu-dialog")).to_be_visible()
                    page.get_by_role("button", name="Tutup menu", exact=True).click()
                    expect(page.locator("#app-menu-dialog")).not_to_be_visible()
                page.screenshot(path=str(output / f"{username}-{width}.png"), full_page=True)

                # Semua tujuan menu harus dapat dibuka oleh akun terkait.
                for link in links:
                    response = context.request.get(base + link)
                    assert response.status == 200, (username, link, response.status)
                selected = links[:8] if username == "MI-01" else links[:3]
                for link in selected:
                    page.goto(base + link, wait_until="networkidle")
                    check_width(page)
                    if username == "MI-01":
                        section = link.rsplit("/", 1)[1]
                        ids = page.locator(".participant-menu-content section[id]").evaluate_all(
                            "(elements) => elements.map(element => element.id)"
                        )
                        assert all(value == section for value in ids), (section, ids)
                if username == "MI-01":
                    response = context.request.get(base + home.removeprefix(base) + "/menu/progres")
                    assert response.status == 200
                    page.goto(base + links[0], wait_until="networkidle")
                    page.screenshot(path=str(output / f"biodata-{width}.png"), full_page=True)
                    bio_root = page.url
                    for group in ("santri", "orang-tua", "alamat-kontak", "sekolah"):
                        page.goto(bio_root + "/" + group, wait_until="networkidle")
                        expect(page.locator(".bio-tabs a[aria-current=page]")).to_have_count(1)
                        check_width(page)
                        if width in (390, 1440):
                            page.screenshot(path=str(output / f"biodata-{group}-{width}.png"), full_page=True)
                    if width == 1440:
                        group_menu = page.locator(".sidebar-group")
                        expect(group_menu).to_have_attribute("open", "")
                        group_menu.locator("summary").click()
                        page.wait_for_timeout(300)
                        expect(group_menu).not_to_have_attribute("open", "")
                        group_menu.locator("summary").click()
                        page.wait_for_timeout(300)
                        expect(group_menu.locator(".sidebar-submenu")).to_be_visible()
                        category = page.locator(".sidebar-category")
                        category.locator(":scope > summary").click()
                        page.wait_for_timeout(300)
                        expect(category).not_to_have_attribute("open", "")
                        category.locator(":scope > summary").click()
                        page.wait_for_timeout(300)
                    page.go_back(wait_until="networkidle")
                    page.goto(home, wait_until="networkidle")
                    if width == 390:
                        page.get_by_role("link", name="Buka semua menu", exact=True).click()
                        page.locator("#app-menu-dialog .app-menu-tile").filter(
                            has_text="Berkas"
                        ).click()
                        page.wait_for_url("**/menu/berkas", wait_until="networkidle")
                assert not errors, errors
                print(
                    f"{username} {width}px: dashboard, izin tujuan menu, navigasi, dan lebar halaman lulus."
                )
                context.close()
        browser.close()
    print(f"Pratinjau tersimpan di {output}")


if __name__ == "__main__":
    main()
