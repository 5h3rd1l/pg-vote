import json, random, time, sys, os, re
from curl_cffi.requests import Session

DOMAIN = "https://www.agentofferings.propertyguru.com.sg"
VOTE_URL = f"{DOMAIN}/agent-choice-awards/vote/"
AJAX_URL = f"{DOMAIN}/wp-admin/admin-ajax.php"
POST_ID = "24454"
VOTE_VAL = 10
TOTAL = int(os.getenv("PG_VOTES", "30"))

FPS = ["chrome110", "chrome116", "chrome120", "chrome123", "chrome124"]
HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": VOTE_URL,
    "Origin": DOMAIN,
}

def cea():
    return f"R{random.randint(100000, 999999)}{chr(random.randint(65, 90))}"

def extract_nonce(html):
    for pat in [
        r'"nonce"\s*:\s*"([a-f0-9]{8,12})"',
        r"'nonce'\s*:\s*'([a-f0-9]{8,12})'",
        r'nonce[=:]\s*["\']([a-f0-9]{8,12})["\']',
    ]:
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None

fp = random.choice(FPS)
session = Session(impersonate=fp)

print(f"Fetching vote page for nonce (fingerprint={fp})...")
try:
    r = session.get(VOTE_URL, headers={
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
    }, timeout=30)
    print(f"Vote page: HTTP {r.status_code}, len={len(r.text)}")
except Exception as e:
    print(f"Failed to fetch vote page: {e}")
    sys.exit(1)

if r.status_code != 200 or len(r.text) < 5000:
    print(f"Page not loaded properly. Status={r.status_code} Snippet: {r.text[:300]}")
    # Try alternate fingerprints
    for alt_fp in FPS:
        if alt_fp == fp:
            continue
        print(f"Trying fingerprint {alt_fp}...")
        session = Session(impersonate=alt_fp)
        try:
            r = session.get(VOTE_URL, headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }, timeout=30)
            if r.status_code == 200 and len(r.text) > 5000:
                fp = alt_fp
                print(f"Success with {alt_fp}: HTTP {r.status_code}, len={len(r.text)}")
                break
        except:
            continue
    else:
        print("All fingerprints failed to get past CF")
        sys.exit(1)

nonce = extract_nonce(r.text)
if not nonce:
    all_nonces = re.findall(r'["\']([a-f0-9]{10})["\']', r.text)
    if all_nonces:
        nonce = all_nonces[0]
        print(f"Fallback nonce: {nonce} (from {len(all_nonces)} candidates)")

if not nonce:
    print("ERROR: No nonce found")
    print(f"Page snippet: {r.text[:500]}")
    sys.exit(1)

print(f"Nonce: {nonce}")
print(f"Voting {TOTAL} times...")

ok = 0
for i in range(TOTAL):
    c = cea()
    try:
        resp = session.post(AJAX_URL, data={
            "action": "pg_vote_submit",
            "mobile": c,
            "votes": json.dumps({POST_ID: VOTE_VAL}),
            "nonce": nonce,
        }, headers=HEADERS, timeout=30)

        success = False
        if resp.status_code == 200:
            try:
                body = resp.json()
                success = body.get("success", False)
            except:
                success = "success" in resp.text

        if success:
            ok += 1

        if i < 3 or (i + 1) % 10 == 0:
            print(f"  {i+1}/{TOTAL} cea={c} status={resp.status_code} ok={success}")
        if not success and i < 3:
            print(f"    resp: {resp.text[:200]}")

        if resp.status_code == 403 and i < 3:
            print("CF block detected, rotating session...")
            fp = random.choice(FPS)
            session = Session(impersonate=fp)
            session.get(VOTE_URL, timeout=30)

    except Exception as e:
        print(f"  {i+1}/{TOTAL} cea={c} error={str(e)[:100]}")
        session = Session(impersonate=random.choice(FPS))

    time.sleep(random.uniform(0.3, 1.0))

print(f"DONE {ok}/{TOTAL} = {ok * VOTE_VAL}v")
