#!/usr/bin/env python3
"""
PG Awards voter — headed Playwright browser.
Solves CF challenge via real browser, votes from within page context.
Sends parallel batches of fetch() calls for throughput.
"""

import random, re, sys, time, string
from playwright.sync_api import sync_playwright

AWARDS_URL = "https://www.agentofferings.propertyguru.com.sg/agent-choice-awards/"
AJAX_URL = "https://www.agentofferings.propertyguru.com.sg/wp-admin/admin-ajax.php"
POST_ID = "24454"
VOTE_VAL = 10
PARALLEL = 5       # concurrent fetch calls per batch
BATCHES = 9999
NONCE_REFRESH = 900

def cea():
    return f"{random.choice('RP')}{''.join(random.choices(string.digits, k=6))}{random.choice(string.ascii_uppercase)}"

def wait_cf(page, timeout=90):
    for i in range(timeout):
        t = page.title().lower()
        if "moment" not in t and "challenge" not in t and "loading" not in t:
            return True
        if i % 5 == 0:
            print(f"  CF waiting... ({i}s)", flush=True)
        time.sleep(1)
    return False

def get_nonce(page):
    html = page.content()
    m = re.search(r"const\s+nonce\s*=\s*'([a-f0-9]{10})'", html)
    return m.group(1) if m else None

def vote_parallel(page, nonce, ceas):
    """Send multiple votes in parallel via Promise.allSettled."""
    try:
        results = page.evaluate("""async (args) => {
            const [url, ceas, nonce] = args;
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 15000);

            const promises = ceas.map(async (c) => {
                try {
                    const fd = new FormData();
                    fd.append('action', 'pg_vote_submit');
                    fd.append('mobile', c);
                    fd.append('votes', JSON.stringify({"24454": 10}));
                    fd.append('nonce', nonce);
                    const r = await fetch(url, {
                        method: 'POST',
                        body: fd,
                        signal: controller.signal
                    });
                    const body = await r.text();
                    let p = null;
                    try { p = JSON.parse(body); } catch(e) {}
                    return {
                        cea: c,
                        s: r.status,
                        ok: p ? p.success : false,
                        m: p && p.data ? (p.data.message||'') : body.substring(0,150)
                    };
                } catch(e) {
                    return {cea: c, s: 0, ok: false, m: e.toString().substring(0,100)};
                }
            });

            const settled = await Promise.allSettled(promises);
            clearTimeout(timeout);
            return settled.map(r => r.status === 'fulfilled' ? r.value : {cea:'?',s:0,ok:false,m:'rejected'});
        }""", [AJAX_URL, ceas, nonce])
        return results
    except Exception as e:
        print(f"  evaluate error: {str(e)[:100]}", flush=True)
        return []

def main():
    print("=== PG Awards Voter (Parallel) ===", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            executable_path="/usr/bin/chromium",
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_init_script('Object.defineProperty(navigator,"webdriver",{get:()=>false});')
        page = ctx.new_page()
        total = 0
        cycle = 0
        start = time.time()

        while True:
            cycle += 1
            print(f"\n{'='*50}", flush=True)
            print(f"Cycle {cycle} | Total: {total}v | Elapsed: {(time.time()-start)/60:.1f}m", flush=True)
            print(f"{'='*50}", flush=True)

            try:
                page.goto(AWARDS_URL, timeout=60000, wait_until="domcontentloaded")
            except Exception as e:
                print(f"Nav failed: {e}", flush=True)
                time.sleep(10)
                continue

            if not wait_cf(page):
                print("CF timeout. Retrying...", flush=True)
                time.sleep(10)
                continue

            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except:
                pass
            time.sleep(2)

            nonce = get_nonce(page)
            if not nonce:
                print("No nonce. Retrying...", flush=True)
                time.sleep(5)
                continue
            print(f"Nonce: {nonce}", flush=True)

            t0 = time.time()
            batch_n = 0
            consecutive_fails = 0

            while time.time() - t0 < NONCE_REFRESH:
                batch_n += 1
                ceas = [cea() for _ in range(PARALLEL)]
                results = vote_parallel(page, nonce, ceas)

                ok = sum(1 for r in results if r.get("ok"))
                total += ok * VOTE_VAL
                elapsed = time.time() - start
                vph = total / max(1, elapsed / 3600)

                sample = results[0] if results else {}
                tag = "OK" if sample.get("ok") else "FAIL"
                msg = sample.get("m", "")[:50]
                print(f"  B{batch_n}: {ok}/{len(results)} ok | +{ok*VOTE_VAL}v | Total: {total}v | {vph:.0f}v/hr | {tag} {msg}", flush=True)

                if ok == 0:
                    consecutive_fails += 1
                    if consecutive_fails >= 3:
                        print("  3 consecutive zero batches — refreshing page", flush=True)
                        break
                    # Check if it's a CF block
                    if any(r.get("s") == 403 for r in results):
                        print("  CF block detected — waiting 30s", flush=True)
                        time.sleep(30)
                else:
                    consecutive_fails = 0

                time.sleep(random.uniform(0.1, 0.3))

if __name__ == "__main__":
    main()
