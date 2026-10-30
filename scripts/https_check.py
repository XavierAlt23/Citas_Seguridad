"""Check real browser HTTPS certificate validation; no certificate-error bypass."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
with sync_playwright() as playwright:
    options = {'headless': True, 'args': ['--no-sandbox', '--disable-dev-shm-usage']}
    brave = Path('/opt/brave.com/brave/brave')
    if brave.exists(): options['executable_path'] = str(brave)
    browser = playwright.chromium.launch(**options)
    context = browser.new_context(ignore_https_errors=False, viewport={'width': 1440, 'height': 1000})
    page = context.new_page()
    response = page.goto('https://localhost:8443/', wait_until='networkidle')
    assert response is not None and response.status == 200
    assert page.evaluate('window.isSecureContext')
    details = response.security_details()
    assert details and details.get('protocol', '').startswith('TLS')
    folder = ROOT/'evidence'; folder.mkdir(exist_ok=True)
    (folder/'screenshots').mkdir(exist_ok=True)
    page.screenshot(path=str(folder/'screenshots/https-trusted.png'))
    result = {'passed': True, 'url': page.url, 'status': response.status, 'ignore_https_errors': False, 'certificate_validation_bypassed': False, 'secure_context': True, 'tls': details, 'trust_scope': 'Current user NSS: only the localhost server certificate is trusted as SSL peer.'}
    (folder/'https-trusted.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    context.close(); browser.close()
