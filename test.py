import requests
import sys
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Setup colors
class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    GRAY = '\033[90m'
    END = '\033[0m'

def write_header(title):
    print(f"\n{Colors.GRAY}=================================================={Colors.END}")
    print(f"  {Colors.CYAN}{title}{Colors.END}")
    print(f"{Colors.GRAY}=================================================={Colors.END}")

# =============================================================================
# 1. AcademicTransfer — Discovery
# =============================================================================
write_header("AcademicTransfer — all class names")
url_at = 'https://www.academictransfer.com/en/jobs/?q=artificial+intelligence'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    page = ctx.new_page()
    try:
        page.goto(url_at, timeout=30000, wait_until='networkidle')
        page.wait_for_timeout(3000)
        html = page.content()
        soup = BeautifulSoup(html, 'lxml')

        print('=== Elements with job-related classes ===')
        for tag in soup.find_all(['div','li','article','section'], class_=True):
            classes = ' '.join(tag.get('class', []))
            if any(kw in classes.lower() for kw in ('job','vacancy','position','listing','result','card','item')):
                text = tag.get_text(strip=True)[:60]
                print(f'  <{tag.name} class="{classes[:80]}"> {text}')

        print('\n=== Links that look like job URLs ===')
        count = 0
        for a in soup.find_all('a', href=True):
            href = a.get('href','')
            if any(kw in href for kw in ('/job','/vacancy','/position','/jobs')):
                print(f'  {a.text.strip()[:60]} -> {href[:80]}')
                count += 1
                if count > 10: break
    except Exception as e:
        print(f"Error: {e}")
    finally:
        browser.close()

# =============================================================================
# 2. Euraxess — Structural Inspection
# =============================================================================
write_header("Euraxess — job card structure")
url_ex = 'https://euraxess.ec.europa.eu/jobs/search?q=artificial+intelligence'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    page = ctx.new_page()
    try:
        page.goto(url_ex, timeout=30000, wait_until='networkidle')
        page.wait_for_timeout(3000)
        html = page.content()
        soup = BeautifulSoup(html, 'lxml')

        cards = soup.select('div[class*="job"]')
        print(f'Total cards found: {len(cards)}')
        for i, card in enumerate(cards[:2]):
            print(f'--- Card {i+1} ---')
            print(f'Classes: {card.get("class")}')
            
            # Test multiple title selectors
            for sel in ['h3 a','h2 a','h4 a','.title a','a[href*="/jobs/"]','a']:
                el = card.select_one(sel)
                if el and el.text.strip():
                    print(f'  Title [{sel}]: {el.text.strip()[:60]}')
                    break
            
            # Test org/location
            org = card.select_one('.field-organisation, [class*="org"], [class*="institution"]')
            if org: print(f'  Org: {org.text.strip()[:50]}')
            
            loc = card.select_one('[class*="country"], [class*="location"]')
            if loc: print(f'  Loc: {loc.text.strip()[:40]}')
    except Exception as e:
        print(f"Error: {e}")
    finally:
        browser.close()

# =============================================================================
# 3. MIT OCW — Playwright
# =============================================================================
write_header("MIT OCW — Playwright check")
url_mit = 'https://ocw.mit.edu/search/?t=Artificial+Intelligence'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    try:
        page.goto(url_mit, timeout=30000, wait_until='networkidle')
        page.wait_for_timeout(4000)
        soup = BeautifulSoup(page.content(), 'lxml')
        print(f'Title: {soup.title.text if soup.title else "None"}')

        for tag in soup.find_all(['div','li','article'], class_=True):
            classes = ' '.join(tag.get('class', []))
            if any(kw in classes.lower() for kw in ('course','card','result','tile')):
                a = tag.find('a', href=True)
                href = a.get('href','') if a else ''
                print(f'  <{tag.name} class="{classes[:50]}"> -> {href[:60]}')
    finally:
        browser.close()

# =============================================================================
# 4. fast.ai + HuggingFace — Static Check
# =============================================================================
def debug_static(name, url):
    write_header(f"{name} — actual structure")
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        soup = BeautifulSoup(r.text, 'lxml')
        print(f'Status: {r.status_code}')
        
        if "fast" in name.lower():
            for a in soup.find_all('a', href=True)[:15]:
                text = a.text.strip()
                if len(text) > 5: print(f'  {text[:40]} -> {a.get("href")}')
        else:
            for tag in soup.find_all(['div','article','li','a'], class_=True)[:15]:
                classes = ' '.join(tag.get('class', []))
                text = tag.get_text(strip=True)[:50]
                if len(text) > 10: print(f'  <{tag.name} class="{classes[:40]}"> {text}')
    except Exception as e:
        print(f"Error: {e}")

debug_static("fast.ai", "https://www.fast.ai/")
debug_static("HuggingFace", "https://huggingface.co/learn")

print(f"\n{Colors.GREEN}Done — Analyze this output to update your scraper selectors!{Colors.END}")