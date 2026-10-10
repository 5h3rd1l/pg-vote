import json, random, time, sys, re, os

from playwright.sync_api import sync_playwright

DOMAIN = "https://www.agentofferings.propertyguru.com.sg"
VOTE_URL = f"{DOMAIN}/agent-choice-awards/vote/"
AJAX_URL = f"{DOMAIN}/wp-admin/admin-ajax.php"
POST_ID = "24454"
VOTE_VAL = 10
TOTAL = int(os.getenv("PG_VOTES", "30"))

def cea():
    return f"R{random.randint(100000, 999999)}{chr(random.randint(65, 90))}"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=[
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
    ])
    ctx = browser.new_context(
        user_agent=f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(135,148)}.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
    )
    page = ctx.new_page()

    page.goto(VOTE_URL, timeout=60000, wait_until="domcontentloaded")

    for i in range(90):
        title = page.title()
        if "moment" not in title.lower() and "challenge" not in title.lower():
            break
        if i % 10 == 0:
            print(f"Waiting for Cloudflare... ({i}s) title={title}")
        time.sleep(1)

    title = page.title()
    if "moment" in title.lower() or "challenge" in title.lower():
        print(f"ERROR: Cloudflare not solved after 90s. Title: {title}")
        browser.close()
        sys.exit(1)

    print(f"Page loaded: {title}")
    time.sleep(3)

    nonce = page.evaluate("""() => {
        const scripts = document.querySelectorAll('script');
        for (const s of scripts) {
            const t = s.textContent;
            let m = t.match(/"nonce"\\s*:\\s*"([a-f0-9]{6,16})"/);
            if (m) return m[1];
            m = t.match(/'nonce'\\s*:\\s*'([a-f0-9]{6,16})'/);
            if (m) return m[1];
        }
        const el = document.querySelector('input[name="nonce"]');
        if (el) return el.value;
        const html = document.documentElement.innerHTML;
        const m = html.match(/nonce[=:]\\s*["']([a-f0-9]{6,16})["']/);
        return m ? m[1] : null;
    }""")

    if not nonce:
        html = page.content()
        for pat in [
            r'"nonce"\s*:\s*"([a-f0-9]{6,16})"',
            r"'nonce'\s*:\s*'([a-f0-9]{6,16})'",
            r'nonce[=:]\s*["\']([a-f0-9]{6,16})["\']',
        ]:
            m = re.search(pat, html)
            if m:
                nonce = m.group(1)
                break

    if not nonce:
        print("ERROR: Could not find nonce")
        browser.close()
        sys.exit(1)

    print(f"Nonce: {nonce}")

    ok = 0
    for i in range(TOTAL):
        c = cea()
        try:
            result = page.evaluate("""async (args) => {
                const [url, c, nonce, postId, voteVal] = args;
                try {
                    const r = await fetch(url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                        body: `action=pg_vote_submit&mobile=${c}&votes={"${postId}":${voteVal}}&nonce=${nonce}`,
                    });
                    const body = await r.text();
                    return {status: r.status, ok: body.includes('success'), body: body.substring(0, 200)};
                } catch(e) {
                    return {status: 0, ok: false, body: e.toString()};
                }
            }""", [AJAX_URL, c, nonce, POST_ID, VOTE_VAL])
            if result["ok"]:
                ok += 1
            if i < 3 or (i + 1) % 10 == 0:
                print(f"  {i+1}/{TOTAL} cea={c} status={result['status']} ok={result['ok']}")
            if not result["ok"] and i < 3:
                print(f"    body: {result['body']}")
        except Exception as e:
            print(f"  {i+1}/{TOTAL} cea={c} error={str(e)[:100]}")
        time.sleep(random.uniform(0.3, 0.8))

    print(f"DONE {ok}/{TOTAL} = {ok * VOTE_VAL}v")
    browser.close()
