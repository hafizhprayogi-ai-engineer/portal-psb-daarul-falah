"""Uji interaksi animasi menggunakan akun demo dan Chrome terisolasi."""

import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def login(page, base_url, password):
    page.goto(base_url + "/login", wait_until="networkidle")
    page.get_by_label("Nomor pendaftaran / username petugas").fill("rangkap.demo")
    page.get_by_label("Kata sandi", exact=True).fill(password)
    page.get_by_role("button", name="Masuk ke portal", exact=False).click()
    page.wait_for_url("**/dashboard", wait_until="networkidle")


def wait_details(page):
    expect(page.locator("details.details-animating")).to_have_count(0)


def check_forms(page):
    summary = page.get_by_text("Buat akun petugas", exact=True)
    details = summary.locator("..")
    summary.click()
    wait_details(page)
    expect(details).to_have_attribute("open", "")
    form = details.locator("form")
    expect(form.get_by_label("Username petugas")).to_be_visible()

    summary.focus()
    page.keyboard.press("Enter")
    wait_details(page)
    expect(details).not_to_have_attribute("open", "")
    page.keyboard.press("Space")
    wait_details(page)
    expect(details).to_have_attribute("open", "")

    # Beberapa klik dalam satu animasi harus berakhir sesuai klik terakhir.
    summary.evaluate("(element) => { element.click(); element.click(); element.click(); }")
    wait_details(page)
    expect(details).not_to_have_attribute("open", "")
    summary.click()
    wait_details(page)
    form.get_by_role("button", name="Buat petugas", exact=True).click()
    expect(form.get_by_label("Username petugas")).to_be_focused()
    expect(page.locator("#utama")).to_have_css("opacity", "1")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    root = Path(__file__).resolve().parents[1]
    credentials = (root / "instance" / "akun-demo.txt").read_text(encoding="utf-8")
    password = next(
        line.split(": ", 1)[1]
        for line in credentials.splitlines()
        if line.startswith("Password seluruh akun: ")
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        for width, height, preference in [
            (1440, 960, "no-preference"),
            (390, 844, "no-preference"),
            (390, 844, "reduce"),
        ]:
            context = browser.new_context(
                viewport={"width": width, "height": height}, reduced_motion=preference
            )
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.add_init_script("""
                document.addEventListener('animationstart', event => {
                    if (event.animationName === 'psb-page-enter') {
                        sessionStorage.setItem('psb-motion-observed', 'yes');
                    }
                });
            """)
            page.goto(base_url + "/login", wait_until="networkidle")
            page.locator(".header").get_by_role("link", name="Daftar akun", exact=True).click()
            page.wait_for_url("**/daftar-akun", wait_until="networkidle")
            expect(page.get_by_role("heading", name="Buat akun peserta")).to_be_visible()
            page.go_back(wait_until="networkidle")
            expect(page.locator("#utama")).to_have_css("opacity", "1")
            submit = page.locator(".portal-submit")
            submit.hover()
            page.mouse.down()
            expect(submit).to_have_css("scale", "1" if preference == "reduce" else "0.98")
            page.mouse.up()
            if preference == "reduce":
                expect(page.locator("#utama")).to_have_css("animation-name", "none")
                assert (
                    page.evaluate("getComputedStyle(document.documentElement).scrollBehavior")
                    == "auto"
                )
            else:
                expect(page.locator("#utama")).to_have_css("animation-name", "psb-page-enter")
                assert (
                    page.evaluate("sessionStorage.getItem('psb-motion-observed')") == "yes"
                ), "Transisi antar halaman belum teramati."

            login(page, base_url, password)
            page.goto(base_url + "/pengaturan/petugas", wait_until="networkidle")
            check_forms(page)

            # Unduhan tetap pada halaman yang terlihat dan dapat dipakai.
            page.goto(base_url + "/keuangan", wait_until="networkidle")
            with page.expect_download() as download_event:
                page.get_by_role("link", name="Formulir kosong", exact=True).click()
            assert download_event.value.suggested_filename.endswith(".pdf")
            expect(page.locator("#utama")).to_have_css("opacity", "1")

            if preference == "no-preference":
                page.goto(base_url + "/pengaturan/petugas", wait_until="networkidle")
                summary = page.get_by_text("Buat akun petugas", exact=True)
                summary.evaluate("(element) => element.click()")
                page.emulate_media(reduced_motion="reduce")
                wait_details(page)
                assert page.locator("details.details-animating").count() == 0
                expect(page.locator("#utama")).to_have_css("animation-name", "none")

            assert not errors, errors
            print(
                f"{width}x{height}, {preference}: navigasi, kembali, detail, keyboard, klik cepat, validasi, dan unduhan lulus."
            )
            context.close()

        context = browser.new_context(
            java_script_enabled=False, viewport={"width": 390, "height": 844}
        )
        page = context.new_page()
        login(page, base_url, password)
        page.goto(base_url + "/pengaturan/petugas", wait_until="networkidle")
        summary = page.get_by_text("Buat akun petugas", exact=True)
        summary.click()
        expect(summary.locator("..")).to_have_attribute("open", "")
        context.close()
        browser.close()
    print("Navigasi dan formulir juga berfungsi saat JavaScript dinonaktifkan.")


if __name__ == "__main__":
    main()
