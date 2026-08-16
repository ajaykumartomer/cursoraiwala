#!/usr/bin/env python3
"""Capture a complete screenshot of an X/Twitter post (article element)."""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

TWEET_SELECTOR = 'article[data-testid="tweet"]'
ENGAGEMENT_SELECTOR = '[data-testid="reply"], [data-testid="retweet"], [data-testid="like"]'
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def normalize_tweet_url(url: str) -> str:
    url = url.strip()
    url = url.replace("twitter.com", "x.com")
    return url


def filename_from_url(url: str) -> str:
    match = re.search(r"status/(\d+)", url)
    return f"tweet_{match.group(1)}.png" if match else "tweet_screenshot.png"


async def dismiss_overlays(page) -> None:
    """Close login/cookie/consent layers that cover the tweet."""
    await page.keyboard.press("Escape")
    await asyncio.sleep(0.3)

    close_selectors = [
        '[data-testid="xMigrationBottomBar"] [role="button"]',
        '[aria-label="Close"]',
        '[data-testid="app-bar-close"]',
        'div[aria-modal="true"] [aria-label="Close"]',
        'div[role="dialog"] [aria-label="Close"]',
    ]
    for selector in close_selectors:
        locator = page.locator(selector).first
        try:
            if await locator.count() and await locator.is_visible():
                await locator.click(timeout=1500)
                await asyncio.sleep(0.2)
        except Exception:
            continue

    # Hide leftover modal/backdrop so the article is fully visible.
    await page.evaluate(
        """
        () => {
            const hide = (el) => {
                if (!el) return;
                el.style.setProperty('display', 'none', 'important');
                el.style.setProperty('visibility', 'hidden', 'important');
                el.style.setProperty('pointer-events', 'none', 'important');
            };
            document.querySelectorAll('[aria-modal="true"], [role="dialog"]').forEach(hide);
            document.querySelectorAll('[data-testid="mask"], [data-testid="sheetDialog"]').forEach(hide);
            document.querySelectorAll('#layers > div').forEach((layer) => {
                const style = window.getComputedStyle(layer);
                if (style.position === 'fixed' || Number(style.zIndex) >= 1) {
                    hide(layer);
                }
            });
        }
        """
    )


async def wait_for_tweet_media(tweet) -> None:
    """Wait until images/video posters inside the tweet have finished loading."""
    try:
        await tweet.locator("img").first.wait_for(state="visible", timeout=12000)
    except PlaywrightTimeoutError:
        pass

    await tweet.evaluate(
        """
        async (el) => {
            const images = Array.from(el.querySelectorAll('img'));
            await Promise.all(
                images.map((img) => {
                    if (img.complete && img.naturalWidth > 0) return Promise.resolve();
                    return new Promise((resolve) => {
                        const done = () => resolve();
                        img.addEventListener('load', done, { once: true });
                        img.addEventListener('error', done, { once: true });
                        setTimeout(done, 8000);
                    });
                })
            );
        }
        """
    )


async def capture_tweet(url: str, output_filename: str = "tweet_screenshot.png") -> Path:
    url = normalize_tweet_url(url)
    output_path = Path(output_filename).resolve()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 2400},
            device_scale_factor=2,
            user_agent=USER_AGENT,
            locale="en-US",
            timezone_id="UTC",
            color_scheme="light",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page = await context.new_page()

        print(f"Loading URL: {url}")
        try:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            except PlaywrightTimeoutError:
                print("Navigation timed out; continuing with whatever loaded.")

            print("Waiting for the tweet to render...")
            await page.wait_for_selector(TWEET_SELECTOR, state="visible", timeout=25000)
            await dismiss_overlays(page)

            tweet = page.locator(TWEET_SELECTOR).first
            await tweet.wait_for(state="visible", timeout=10000)
            await tweet.scroll_into_view_if_needed()

            print("Waiting for media and engagement bar...")
            await wait_for_tweet_media(tweet)
            try:
                await tweet.locator(ENGAGEMENT_SELECTOR).first.wait_for(
                    state="visible", timeout=8000
                )
            except PlaywrightTimeoutError:
                pass

            await asyncio.sleep(1.5)
            await dismiss_overlays(page)

            box = await tweet.bounding_box()
            if not box:
                raise RuntimeError("Could not measure the tweet element.")

            # Pad so the avatar, rounded media corners, and share icons
            # are not clipped at the article edges.
            pad = 8
            clip = {
                "x": max(box["x"] - pad, 0),
                "y": max(box["y"] - pad, 0),
                "width": box["width"] + pad * 2,
                "height": box["height"] + pad * 2,
            }

            print("Capturing screenshot of the full tweet (username through likes/share)...")
            await page.screenshot(
                path=str(output_path),
                type="png",
                clip=clip,
                animations="disabled",
            )

            print(f"Success! Screenshot saved as: {output_path}")
            return output_path
        except Exception as exc:
            debug_path = output_path.with_name(output_path.stem + "_page.png")
            try:
                await page.screenshot(path=str(debug_path), full_page=True)
                print(f"Saved full-page debug screenshot: {debug_path}")
            except Exception:
                pass
            print(
                "An error occurred. X.com might have blocked the request or "
                f"demanded a login. Details: {exc}"
            )
            raise
        finally:
            await browser.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Screenshot a complete X/Twitter post from username through likes and share."
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="Tweet URL. If omitted, you will be prompted to paste one.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output PNG path. Defaults to tweet_<id>.png",
    )
    return parser.parse_args()


def main() -> int:
    print("=== X/Twitter Element Screenshotter ===")
    args = parse_args()
    user_url = (args.url or input("Paste the X/Twitter URL: ")).strip()
    if not user_url:
        print("Invalid URL.")
        return 1

    filename = args.output or filename_from_url(user_url)
    try:
        asyncio.run(capture_tweet(user_url, output_filename=filename))
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
