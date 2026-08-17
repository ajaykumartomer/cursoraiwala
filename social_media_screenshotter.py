import sys
import os
import ctypes
import subprocess
import importlib
import asyncio
import re
import warnings
from pathlib import Path
from datetime import datetime

# Suppress harmless third-party syntax warnings from the WMI library
warnings.filterwarnings("ignore", category=SyntaxWarning, module="wmi")

# ============================================================================
# 1. PATHS & BOOTSTRAP CONFIGURATION
# ============================================================================
LIB_ROOT = r"C:\AKT Media Tools"
SITE_PACKAGES = os.path.join(LIB_ROOT, "Lib", "site-packages")
TOOLS_DIR = os.path.join(LIB_ROOT, "Tools")
PW_BROWSERS = os.path.join(TOOLS_DIR, "pw-browsers")

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = PW_BROWSERS

S24_VIEWPORT = {"width": 412, "height": 915}
S24_CHROME_UA = (
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36"
)
# Match Playwright Firefox so Instagram does not get Chrome-only JS that paints blank.
S24_FIREFOX_UA = "Mozilla/5.0 (Android 14; Mobile; rv:125.0) Gecko/125.0 Firefox/125.0"
S24_UA = S24_CHROME_UA
IG_SHORTCODE_RE = re.compile(
    r"instagram\.com/(?:[^/]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)

# ============================================================================
# 2. ADMIN / WRITE HELPERS
# ============================================================================
def is_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def can_write(folder: str) -> bool:
    try:
        os.makedirs(folder, exist_ok=True)
        test_file = os.path.join(folder, ".write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return True
    except Exception:
        return False

def relaunch_as_admin():
    if os.name != "nt":
        return
    script = os.path.abspath(sys.argv[0])
    print("\n[!] Administrator privileges needed to set up C:\\AKT Media Tools.")
    print("Click YES on the UAC prompt...")
    params = subprocess.list2cmdline([script] + sys.argv[1:])
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, os.path.dirname(script), 1
        )
    except Exception as e:
        print(f"Elevation failed: {e}")
        input("Press Enter to exit...")
    sys.exit(0)

# ============================================================================
# 3. ENVIRONMENT PREPARATION
# ============================================================================
def _has_browser_dir(browser_name: str) -> bool:
    browser_check_path = Path(PW_BROWSERS)
    if not browser_check_path.exists():
        return False
    return any(
        browser_name in d.name for d in browser_check_path.iterdir() if d.is_dir()
    )

def prepare_environment():
    print("=== AKT Environment Setup ===")

    if not can_write(LIB_ROOT):
        if not is_admin():
            relaunch_as_admin()
        else:
            os.makedirs(SITE_PACKAGES, exist_ok=True)
            os.makedirs(TOOLS_DIR, exist_ok=True)
            os.makedirs(PW_BROWSERS, exist_ok=True)

    if SITE_PACKAGES not in sys.path:
        sys.path.insert(0, SITE_PACKAGES)

    pywin32_path = os.path.join(SITE_PACKAGES, "pywin32_system32")
    if os.path.isdir(pywin32_path) and pywin32_path not in os.environ.get("PATH", ""):
        os.environ["PATH"] = pywin32_path + os.pathsep + os.environ.get("PATH", "")

    missing_libs = []
    if not os.path.isdir(os.path.join(SITE_PACKAGES, "playwright")):
        missing_libs.append("playwright")
    if not os.path.isdir(os.path.join(SITE_PACKAGES, "browser_cookie3")):
        missing_libs.append("browser-cookie3")

    if missing_libs:
        print(f"[-] Installing missing libraries {missing_libs} to AKT Tools folder...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--target", SITE_PACKAGES] + missing_libs
        )
        importlib.invalidate_caches()
        print("[OK] Libraries installed.")
    else:
        print("[OK] Core libraries are already present.")

    env = os.environ.copy()
    env["PYTHONPATH"] = SITE_PACKAGES + os.pathsep + env.get("PYTHONPATH", "")

    if not _has_browser_dir("firefox"):
        print("[-] Downloading Playwright Firefox browser binaries (this happens only once)...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "firefox"], env=env)
        print("[OK] Firefox binaries installed.")
    else:
        print("[OK] Firefox browser binaries already present.")

# ============================================================================
# 4. INSTAGRAM CACHE/COOKIE EXTRACTOR
# ============================================================================
def get_instagram_cookies():
    try:
        import browser_cookie3
    except ImportError as e:
        print(f"⚠️ Could not load cookie extractor: {e}. You might hit a login wall.")
        return []

    browsers = [
        ("Firefox", browser_cookie3.firefox),
        ("Brave", browser_cookie3.brave),
        ("Chrome", browser_cookie3.chrome),
        ("Edge", browser_cookie3.edge),
    ]

    print("\n[+] Hunting for active Instagram logins in your local browsers...")
    for name, b_func in browsers:
        try:
            cj = b_func(domain_name="instagram.com")
            cookies = []
            has_session = False

            for c in cj:
                if c.name == "sessionid":
                    has_session = True

                domain = c.domain or ".instagram.com"
                if domain.startswith("."):
                    cookie_domain = domain
                elif "instagram.com" in domain:
                    cookie_domain = domain
                else:
                    cookie_domain = ".instagram.com"

                cookie = {
                    "name": c.name,
                    "value": c.value,
                    "domain": cookie_domain,
                    "path": c.path or "/",
                    "secure": True,
                    "httpOnly": c.name in {"sessionid", "rur", "mid"},
                    "sameSite": "Lax",
                }
                if c.expires:
                    cookie["expires"] = int(c.expires)
                cookies.append(cookie)

            if has_session:
                print(f"✅ Successfully copied active Instagram session from {name}!")
                return cookies
        except Exception:
            pass

    print("⚠️ No active Instagram session found. You might hit a login wall.")
    return []

# ============================================================================
# 5. INSTAGRAM HELPERS
# ============================================================================
def instagram_shortcode(url: str) -> str:
    match = IG_SHORTCODE_RE.search(url)
    return match.group(1) if match else ""

def instagram_embed_url(url: str) -> str:
    """Official embed card — same idea as the Twitter embed that already works."""
    code = instagram_shortcode(url)
    if not code:
        return url.split("?")[0].rstrip("/") + "/embed/captioned/"
    kind = "reel" if re.search(r"/(?:reel|reels|tv)/", url, re.IGNORECASE) else "p"
    return f"https://www.instagram.com/{kind}/{code}/embed/captioned/"

async def dismiss_instagram_walls(page):
    """Dismiss login/cookie nags without closing the post itself.

    The old logic clicked every Close/Allow button and deleted role=dialog
    nodes. Instagram often renders the post *inside* that dialog, so those
    clicks left a blank white page.
    """
    try:
        await page.evaluate(
            """() => {
                const skip = /not now|cancel|maybe later|log in later|skip/i;
                const cookieOk = /allow all cookies|accept all|accept cookies|allow cookies/i;
                document.querySelectorAll('button, div[role="button"]').forEach(b => {
                    const txt = (b.innerText || b.getAttribute('aria-label') || '').trim();
                    if (!txt) return;
                    if (skip.test(txt) || cookieOk.test(txt)) {
                        try { b.click(); } catch (e) {}
                    }
                });

                document.querySelectorAll('nav, [role="navigation"]').forEach(n => n.remove());

                document.querySelectorAll('a').forEach(a => {
                    if (a.href && (a.href.includes('android-app') || a.href.includes('ios-app'))) {
                        const p = a.closest('div');
                        if (p && /\\bapp\\b/i.test(p.innerText || '')) p.remove();
                    }
                });
            }"""
        )
    except Exception:
        pass

async def wait_for_instagram_media(page, timeout_ms: int = 25000) -> bool:
    """Wait until a real photo/video frame has painted (not an empty shell)."""
    try:
        await page.wait_for_function(
            """() => {
                const imgs = Array.from(document.images || []);
                const photo = imgs.some(img =>
                    img.complete &&
                    img.naturalWidth > 40 &&
                    img.offsetWidth > 20 &&
                    getComputedStyle(img).visibility !== 'hidden' &&
                    getComputedStyle(img).opacity !== '0'
                );
                const videos = Array.from(document.querySelectorAll('video'));
                const vid = videos.some(v =>
                    (v.readyState >= 2 && v.videoWidth > 40) ||
                    (v.poster && v.offsetWidth > 20)
                );
                return photo || vid;
            }""",
            timeout=timeout_ms,
        )
        return True
    except Exception:
        return False

async def prepare_instagram_media(page):
    """Force lazy images to load and park videos on a visible first frame."""
    try:
        await page.evaluate(
            """() => {
                document.querySelectorAll('img').forEach(img => {
                    img.loading = 'eager';
                    const ds = img.getAttribute('data-src') || img.dataset.src;
                    if (ds && !img.src) img.src = ds;
                    img.scrollIntoView({block: 'center'});
                });
                document.querySelectorAll('video').forEach(v => {
                    v.muted = true;
                    v.playsInline = true;
                    v.pause();
                    try { if (v.currentTime < 0.05) v.currentTime = 0.15; } catch (e) {}
                });
            }"""
        )
    except Exception:
        pass

async def pick_instagram_element(page):
    """Choose a visible, non-zero post container instead of an empty article/main."""
    selectors = [
        "iframe.EmbeddedMediaImage, iframe.embedFrame",
        "div.Embed",
        "article",
        'div[role="dialog"]',
        "main",
        "#react-root",
        "body",
    ]
    best = None
    best_area = 0
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            if await loc.count() == 0:
                continue
            box = await loc.bounding_box()
            if not box:
                continue
            area = box["width"] * box["height"]
            if box["width"] >= 80 and box["height"] >= 80 and area > best_area:
                best = loc
                best_area = area
        except Exception:
            continue
    return best or page.locator("body")

def _windows_browser_exe(*relative_parts: str) -> list:
    bases = [
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", ""),
    ]
    found = []
    for base in bases:
        if not base:
            continue
        path = os.path.join(base, *relative_parts)
        if os.path.isfile(path):
            found.append(path)
    return found

async def launch_installed_chrome_family(playwright):
    """Use Chrome / Brave / Edge already on the PC. Never download Playwright Chromium."""
    chromium = playwright.chromium
    launch_args = ["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"]

    for channel, label in (("chrome", "Google Chrome"), ("msedge", "Microsoft Edge")):
        try:
            browser = await chromium.launch(headless=True, channel=channel, args=launch_args)
            print(f"[+] Using installed {label} (no Chromium download).")
            return browser
        except Exception:
            pass

    for exe in _windows_browser_exe("BraveSoftware", "Brave-Browser", "Application", "brave.exe"):
        try:
            browser = await chromium.launch(headless=True, executable_path=exe, args=launch_args)
            print("[+] Using installed Brave (no Chromium download).")
            return browser
        except Exception:
            continue

    raise RuntimeError(
        "Firefox produced a blank Instagram shot, and no installed Chrome/Brave/Edge "
        "could be launched. Install Google Chrome or run the capture again in Firefox."
    )

def screenshot_looks_blank(path: str) -> bool:
    """Treat missing/tiny PNGs as failed Instagram captures.

    A real IG photo at mobile width is tens of KB+. A white empty shell
    compresses to a very small PNG, which is the usual 'blank screenshot'.
    """
    try:
        return (not os.path.exists(path)) or os.path.getsize(path) < 12000
    except Exception:
        return True

async def inject_instagram_timestamp(page, timestamp_str: str):
    await page.evaluate(
        """(ts) => {
            const existing = document.getElementById('akt-saved-stamp');
            if (existing) existing.remove();

            const stamp = document.createElement('div');
            stamp.id = 'akt-saved-stamp';
            stamp.innerText = "Post_Saved_On : " + ts;
            stamp.style.fontFamily = "Arial, Helvetica, sans-serif";
            stamp.style.fontWeight = "800";
            stamp.style.fontSize = "7pt";
            stamp.style.whiteSpace = "nowrap";
            stamp.style.setProperty("color", "#000000", "important");
            stamp.style.setProperty("-webkit-text-fill-color", "#000000", "important");
            stamp.style.marginLeft = "8px";
            stamp.style.marginRight = "10px";
            stamp.style.paddingLeft = "0";
            stamp.style.paddingRight = "2px";
            stamp.style.flexShrink = "0";
            stamp.style.overflow = "visible";
            stamp.style.lineHeight = "1.2";

            const fitStamp = (row) => {
                row.style.overflow = "visible";
                if (row.parentElement) row.parentElement.style.overflow = "visible";
                let size = 7;
                stamp.style.fontSize = size + "pt";
                const rightLimit = () => row.getBoundingClientRect().right - 8;
                while (size > 5 && stamp.getBoundingClientRect().right > rightLimit()) {
                    size -= 0.25;
                    stamp.style.fontSize = size + "pt";
                }
            };

            let viewMore = null;
            document.querySelectorAll('a, span, p, div').forEach(el => {
                const t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                if (/^view more on instagram$/i.test(t)) viewMore = el;
            });
            if (viewMore) {
                const row = viewMore.closest('p') || viewMore.parentElement;
                if (row) {
                    row.style.display = "flex";
                    row.style.flexDirection = "row";
                    row.style.alignItems = "center";
                    row.style.justifyContent = "space-between";
                    row.style.width = "100%";
                    row.style.boxSizing = "border-box";
                    row.style.paddingRight = "8px";
                    row.appendChild(stamp);
                    fitStamp(row);
                    return;
                }
            }

            const svgs = document.querySelectorAll(
                'svg[aria-label="Save"], svg[aria-label="Remove"]'
            );
            if (svgs.length > 0) {
                const btn = svgs[0].closest('div[role="button"]') || svgs[0].parentElement;
                const rightWrapper = btn ? btn.parentElement : null;
                const mainRow = rightWrapper ? rightWrapper.parentElement : null;
                if (mainRow && rightWrapper) {
                    stamp.style.flexGrow = "1";
                    stamp.style.textAlign = "right";
                    stamp.style.marginRight = "10px";
                    stamp.style.display = "flex";
                    stamp.style.alignItems = "center";
                    stamp.style.justifyContent = "flex-end";
                    stamp.style.setProperty("color", "#000000", "important");
                    stamp.style.setProperty("-webkit-text-fill-color", "#000000", "important");
                    mainRow.insertBefore(stamp, rightWrapper);
                    return;
                }
            }

            stamp.style.position = "absolute";
            stamp.style.bottom = "12px";
            stamp.style.right = "12px";
            stamp.style.background = "rgba(255,255,255,0.85)";
            stamp.style.padding = "2px 6px";
            stamp.style.borderRadius = "4px";
            stamp.style.zIndex = "99999";
            const host = document.querySelector('div.Embed, article, main, body');
            if (host) {
                if (getComputedStyle(host).position === 'static') host.style.position = 'relative';
                host.appendChild(stamp);
            }
        }""",
        timestamp_str,
    )

async def hide_instagram_below_actions(page):
    """Keep like/share/likes; hide caption, comments, and Add a comment (Gemini crop)."""
    try:
        await page.evaluate(
            """() => {
                const hide = (el) => {
                    if (el) el.style.setProperty('display', 'none', 'important');
                };

                document.querySelectorAll(
                    '.Caption, .CaptionText, .Comments, .EmbedComments, .embedComment'
                ).forEach(hide);

                const heartSvg = document.querySelector(
                    'svg[aria-label="Like"], svg[aria-label="Unlike"], svg[aria-label="Like "], svg[aria-label*="Like" i], [aria-label="Like"], .coreSpriteHeartOpen'
                );
                if (heartSvg) {
                    const btn = heartSvg.closest('div[role="button"], button, a') || heartSvg.parentElement;
                    const actionRow = btn && btn.parentElement;
                    const targetFeedback = actionRow && actionRow.parentElement;
                    if (targetFeedback) {
                        let sibling = targetFeedback.nextElementSibling;
                        while (sibling) {
                            hide(sibling);
                            sibling = sibling.nextElementSibling;
                        }
                    }
                }

                document.querySelectorAll('form, section, footer, div, span, textarea, p').forEach(el => {
                    const t = ((el.innerText || el.getAttribute('placeholder') || '') + '')
                        .replace(/\\s+/g, ' ').trim();
                    if (/^add a comment/i.test(t) || /^view all \\d+ comments/i.test(t)) {
                        hide(el.closest('form, footer, section') || el);
                    }
                });
            }"""
        )
    except Exception:
        pass

async def instagram_crop_clip(element):
    """Clip PNG to bottom of like/share row plus likes, excluding Add a comment."""
    try:
        clip = await element.evaluate(
            """(el) => {
                const rootRect = el.getBoundingClientRect();
                const heartSvg = el.querySelector(
                    'svg[aria-label="Like"], svg[aria-label="Unlike"], svg[aria-label="Like "], svg[aria-label*="Like" i], [aria-label="Like"], .coreSpriteHeartOpen'
                ) || document.querySelector(
                    'svg[aria-label="Like"], svg[aria-label="Unlike"], svg[aria-label="Like "], svg[aria-label*="Like" i], [aria-label="Like"], .coreSpriteHeartOpen'
                );
                if (!heartSvg) return null;

                const btn = heartSvg.closest('div[role="button"], button, a') || heartSvg.parentElement;
                const actionRow = btn && btn.parentElement;
                let cut = (actionRow || heartSvg).getBoundingClientRect().bottom;

                const likeRe = /^[\\d,.\\s]+likes$/i;
                el.querySelectorAll('span, a, div').forEach(node => {
                    const own = Array.from(node.childNodes)
                        .filter(n => n.nodeType === 3)
                        .map(n => (n.textContent || '').trim())
                        .join(' ')
                        .trim();
                    const t = (own || (node.children.length === 0 ? (node.innerText || '').trim() : ''))
                        .replace(/\\s+/g, ' ');
                    if (!likeRe.test(t)) return;
                    const r = node.getBoundingClientRect();
                    if (r.top >= cut - 16 && r.top <= cut + 80 && r.height < 48) {
                        cut = Math.max(cut, r.bottom);
                    }
                });

                const height = Math.min(
                    rootRect.height - 1,
                    Math.max(80, cut - rootRect.top + 10)
                );
                const width = Math.max(1, rootRect.width - 1);
                if (height < 80 || width < 40) return null;
                return {
                    x: 0,
                    y: 0,
                    width: Math.floor(width),
                    height: Math.floor(height)
                };
            }"""
        )
        if clip and clip.get("width") and clip.get("height"):
            return clip
    except Exception:
        pass
    return None

# ============================================================================
# 6. SOCIAL MEDIA SCREENSHOTTER (MOBILE VIEWPORT)
# ============================================================================
async def new_mobile_context(browser, user_agent: str, ig_cookies=None):
    context = await browser.new_context(
        viewport=S24_VIEWPORT,
        is_mobile=True,
        has_touch=True,
        user_agent=user_agent,
        locale="en-US",
        color_scheme="light",
        java_script_enabled=True,
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    if ig_cookies is not None:
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        if ig_cookies:
            try:
                await context.add_cookies(ig_cookies)
            except Exception as cookie_err:
                print(f"    [!] Some cookies could not be applied: {cookie_err}")
    return context

async def capture_instagram(page, url: str, output_dir: str, timestamp_str: str, timestamp_display: str) -> list:
    """Load IG, screenshot slides, return saved file paths."""
    saved_paths = []
    print("[+] Waiting for Instagram media to paint...")

    embed_url = instagram_embed_url(url)
    media_ready = False

    if embed_url.rstrip("/") != url.split("?")[0].rstrip("/"):
        print(f"[+] Trying Instagram embed card: {embed_url}")
        try:
            await page.goto(embed_url, wait_until="domcontentloaded", timeout=45000)
            await prepare_instagram_media(page)
            media_ready = await wait_for_instagram_media(page, timeout_ms=18000)
        except Exception as embed_err:
            print(f"    [!] Embed navigation failed: {embed_err}")

    if not media_ready:
        print("[+] Embed empty or blocked — loading the original post URL...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(1500)
        await dismiss_instagram_walls(page)
        await prepare_instagram_media(page)
        media_ready = await wait_for_instagram_media(page, timeout_ms=20000)

    if not media_ready:
        print("    [!] Media still not painted — extra settle wait...")
        await page.wait_for_timeout(4000)
        await prepare_instagram_media(page)
        media_ready = await wait_for_instagram_media(page, timeout_ms=8000)

    await dismiss_instagram_walls(page)
    await page.wait_for_timeout(800)

    ig_username = await page.evaluate(
        """() => {
        const ok = (t) => /^[A-Za-z0-9._]+$/.test(t) && t.toLowerCase() !== 'instagram';
        let iosUrl = document.querySelector('meta[property="al:ios:url"]');
        if (iosUrl && iosUrl.content && iosUrl.content.includes('username=')) {
            return iosUrl.content.split('username=')[1].split('&')[0];
        }
        let ogTitle = document.querySelector('meta[property="og:title"]');
        if (ogTitle && ogTitle.content) {
            let match = ogTitle.content.match(/@([a-zA-Z0-9_.]+)/);
            if (match) return match[1];
            let match2 = ogTitle.content.match(/^([a-zA-Z0-9_.]+)\\s+on Instagram/);
            if (match2) return match2[1];
        }
        let header = document.querySelector('header');
        if (header) {
            let first = header.innerText.trim().split('\\n')[0].trim();
            if (ok(first)) return first;
        }
        let headerLinks = document.querySelectorAll('header a, header span, header strong');
        for (let a of headerLinks) {
            let text = (a.innerText || '').trim().split('\\n')[0].trim();
            if (ok(text)) return text;
        }
        for (let a of document.querySelectorAll('a[href]')) {
            let href = a.getAttribute('href') || '';
            let m = href.match(/instagram\\.com\\/([A-Za-z0-9._]+)\\/?$/);
            if (m && ok(m[1]) && !['p','reel','reels','tv','stories','accounts'].includes(m[1])) return m[1];
            let text = (a.innerText || '').trim().split('\\n')[0].trim();
            if (ok(text) && a.closest('header, .Header, .EmbedHeader')) return text;
        }
        return 'unknown';
    }"""
    )
    if ig_username == "unknown":
        m = re.search(r"instagram\.com/([A-Za-z0-9._]+)/(?:p|reel|reels|tv)/", url, re.I)
        if m and m.group(1).lower() not in {"p", "reel", "reels", "tv", "stories"}:
            ig_username = m.group(1)
    filename_base = f"instagram.com_@{ig_username}_{timestamp_str}"
    print(f"[+] Username identified: @{ig_username}")

    print("[+] Injecting perfectly aligned 8pt Bold Timestamp...")
    await inject_instagram_timestamp(page, timestamp_display)
    await hide_instagram_below_actions(page)

    element = await pick_instagram_element(page)

    slide_num = 1
    while True:
        current_filename = (
            f"{filename_base}.png"
            if slide_num == 1
            else f"{filename_base}_slide{slide_num}.png"
        )
        output_path = os.path.join(output_dir, current_filename)

        print(f"[+] Taking tight crop screenshot... Saving as {current_filename}")
        await prepare_instagram_media(page)
        await hide_instagram_below_actions(page)
        await page.wait_for_timeout(400)

        try:
            box = await element.bounding_box()
            if not box or box["height"] < 80:
                element = await pick_instagram_element(page)
                box = await element.bounding_box()
            clip = await instagram_crop_clip(element)
            if clip and box:
                clip["width"] = max(1, min(int(clip["width"]), int(box["width"])))
                clip["height"] = max(1, min(int(clip["height"]), int(box["height"])))
                await element.screenshot(path=output_path, animations="disabled", clip=clip)
            else:
                await element.screenshot(path=output_path, animations="disabled")
        except Exception:
            await element.screenshot(path=output_path, animations="disabled")

        if screenshot_looks_blank(output_path):
            print("    [!] Capture looked blank — retrying cropped shot...")
            await page.wait_for_timeout(1500)
            await prepare_instagram_media(page)
            await hide_instagram_below_actions(page)
            try:
                element = await pick_instagram_element(page)
                box = await element.bounding_box()
                clip = await instagram_crop_clip(element)
                if clip and box:
                    clip["width"] = max(1, min(int(clip["width"]), int(box["width"])))
                    clip["height"] = max(1, min(int(clip["height"]), int(box["height"])))
                    await element.screenshot(path=output_path, animations="disabled", clip=clip)
                else:
                    await element.screenshot(path=output_path, animations="disabled")
            except Exception:
                pass

        saved_paths.append(output_path)

        next_btn = page.locator('button[aria-label="Next"]')
        if await next_btn.count() > 0 and await next_btn.is_visible():
            print("    [>] Found multi-slide post. Clicking next...")
            await next_btn.click()
            await page.wait_for_timeout(1500)
            await prepare_instagram_media(page)
            await hide_instagram_below_actions(page)
            await wait_for_instagram_media(page, timeout_ms=8000)

            if slide_num == 1:
                first_slide_new_name = os.path.join(
                    output_dir, f"{filename_base}_slide1.png"
                )
                if os.path.exists(output_path):
                    os.rename(output_path, first_slide_new_name)
                    saved_paths[-1] = first_slide_new_name

            slide_num += 1
            if slide_num > 20:
                break
        else:
            break

    return saved_paths

async def capture_post(url: str):
    from playwright.async_api import async_playwright

    is_twitter = "twitter.com" in url or "x.com" in url
    is_instagram = "instagram.com" in url or "instagr.am" in url

    if not is_twitter and not is_instagram:
        print("\n❌ ERROR: Please enter a valid X/Twitter or Instagram URL.")
        return

    now = datetime.now()
    timestamp_str = now.strftime("%d_%b_%Y_%H%M")
    timestamp_display = now.strftime("%d_%b_%Y_%H:%M")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "Social Media Screenshots")
    os.makedirs(output_dir, exist_ok=True)

    if is_twitter:
        match = re.search(r"(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)", url)
        tw_username = match.group(1) if match else "unknown"
        tweet_id = match.group(2) if match else "0"
        filename_base = f"x.com_@{tw_username}_{timestamp_str}"
        target_url = f"https://platform.twitter.com/embed/Tweet.html?id={tweet_id}&theme=light"
    else:
        target_url = url
        filename_base = ""

    print("[+] Launching Playwright Firefox in Mobile (S24 Ultra) Mode...")
    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.firefox.launch(headless=True)
            ig_cookies = get_instagram_cookies() if is_instagram else None
            # Twitter already works with the Chrome-style UA on Firefox.
            # Instagram gets a real Firefox UA so the page actually paints.
            ua = S24_FIREFOX_UA if is_instagram else S24_UA
            context = await new_mobile_context(browser, ua, ig_cookies)
            page = await context.new_page()

            print(f"[+] Loading Target URL: {target_url}")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

            # =================================================================
            # TWITTER LOGIC (unchanged — this path already works)
            # =================================================================
            if is_twitter:
                print("[+] Waiting for the tweet to render...")
                await page.wait_for_selector("article", state="visible", timeout=15000)
                await page.wait_for_timeout(3000)

                print("[+] Injecting 11pt Bold Timestamp...")
                await page.evaluate(
                    """(ts) => {
                    let timeElems = document.querySelectorAll('time');
                    if (timeElems.length > 0) {
                        let parent = timeElems[0].parentElement;
                        let stamp = document.createElement('span');
                        stamp.innerText = "Post_Saved_On : " + ts;
                        stamp.style.fontFamily = "Arial, Helvetica, sans-serif";
                        stamp.style.fontWeight = "bold";
                        stamp.style.fontSize = "11pt";
                        stamp.style.whiteSpace = "nowrap";
                        stamp.style.marginLeft = "auto";
                        stamp.style.paddingLeft = "20px";
                        stamp.style.color = "#000";

                        parent.style.display = "flex";
                        parent.style.width = "100%";
                        parent.style.alignItems = "center";
                        parent.appendChild(stamp);
                    }
                }""",
                    timestamp_display,
                )

                output_path = os.path.join(output_dir, f"{filename_base}.png")
                element = page.locator("article").first

                await element.screenshot(path=output_path)
                print(f"\n✅ SUCCESS! Screenshot securely saved to: {output_dir}")

            # =================================================================
            # INSTAGRAM LOGIC — Firefox first
            # =================================================================
            else:
                saved_paths = await capture_instagram(page, url, output_dir, timestamp_str, timestamp_display)
                still_blank = saved_paths and all(screenshot_looks_blank(p) for p in saved_paths)

                if still_blank:
                    print(
                        "[!] Firefox still saved a blank Instagram frame. "
                        "Falling back to your installed Chrome/Brave/Edge (not downloading Chromium)..."
                    )
                    await browser.close()
                    browser = None
                    browser = await launch_installed_chrome_family(p)
                    context = await new_mobile_context(browser, S24_CHROME_UA, ig_cookies)
                    page = await context.new_page()
                    saved_paths = await capture_instagram(page, url, output_dir, timestamp_str, timestamp_display)

                print(f"\n✅ SUCCESS! Mobile Screenshot(s) securely saved to: {output_dir}")

        except Exception as e:
            print("\n❌ AN ERROR OCCURRED DURING CAPTURE:")
            print(str(e))

        finally:
            if browser is not None:
                await browser.close()

if __name__ == "__main__":
    try:
        prepare_environment()

        print("\n" + "=" * 60)
        user_url = input(
            "Paste the X/Twitter or Instagram URL (or press Enter to quit): "
        ).strip()
        if user_url:
            asyncio.run(capture_post(user_url))

    except Exception as e:
        print(f"\nCRITICAL SCRIPT CRASH: {e}")
    finally:
        input("\nPress Enter to exit...")
