import os
import sys
import json
import subprocess
import traceback

# Setup colors for the terminal
class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    GRAY = '\033[90m'
    END = '\033[0m'

stats = {"PASS": 0, "FAIL": 0, "SKIP": 0}
errors_list = []

def write_header(title):
    print(f"\n{Colors.GRAY}=================================================={Colors.END}")
    print(f"  {Colors.CYAN}{title}{Colors.END}")
    print(f"{Colors.GRAY}=================================================={Colors.END}")

def report_pass(label, detail=""):
    stats["PASS"] += 1
    msg = f"[{Colors.GREEN}PASS{Colors.END}] {label}"
    if detail: msg += f" ({detail})"
    print(msg)

def report_fail(label, reason):
    stats["FAIL"] += 1
    errors_list.append(f"{label} - {reason}")
    print(f"[{Colors.RED}FAIL{Colors.END}] {label} - {reason}")

def report_skip(label, reason):
    stats["SKIP"] += 1
    print(f"[{Colors.YELLOW}SKIP{Colors.END}] {label} - {reason}")

def run_scraper_test(name, class_name, module_path, min_expected=1):
    print(f"  {Colors.GRAY}Running {name}...{Colors.END}")
    
    # Environment setup for the scraper
    os.environ.setdefault('SECRET_KEY', 'a' * 32)
    os.environ.setdefault('POSTGRES_PASSWORD', 'test')
    sys.path.insert(0, '.')

    try:
        # Dynamic import
        import importlib
        module = importlib.import_module(module_path)
        scraper_class = getattr(module, class_name)
        
        scraper = scraper_class()
        items = scraper.run()
        
        valid = [i for i in items if i.get('url') and i.get('title') and i.get('type')]
        count = len(items)
        valid_count = len(valid)

        if count >= min_expected:
            report_pass(name, f"{valid_count} valid items out of {count} collected")
        elif count > 0:
            report_skip(name, f"only {count} items (expected {min_expected}+)")
        else:
            report_fail(name, "0 items returned — site blocked or selectors stale")

        # Print samples
        for s in valid[:3]:
            print(f"    {Colors.GRAY}- {s.get('title', '')[:60]}{Colors.END}")
            print(f"      {Colors.GRAY}{s.get('url', '')[:80]}{Colors.END}")

    except Exception as e:
        report_fail(name, str(e))
        print(f"    {Colors.GRAY}{traceback.format_exc()[-300:]}{Colors.END}")

# =============================================================================
# 0. Dependency checks
# =============================================================================
write_header("0. Dependency checks")

deps = ["feedparser", "playwright", "bs4", "requests", "lxml"]
for dep in deps:
    try:
        __import__(dep)
        report_pass(f"import {dep}")
    except ImportError:
        report_fail(f"import {dep}", f"not installed — run: pip install {dep}")

try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        browser.close()
    report_pass("Playwright chromium")
except Exception as e:
    report_fail("Playwright chromium", "run: playwright install chromium")

# =============================================================================
# 1. RSS feeds
# =============================================================================
write_header("1. RSS feeds (static)")
import feedparser

feeds = [
    ('Nature Careers - research', 'https://www.nature.com/naturecareers/rss/jobs?type=research'),
    ('Nature Careers - postdoc',  'https://www.nature.com/naturecareers/rss/jobs?type=postdoc'),
    ('Nature Careers - all jobs', 'https://www.nature.com/naturecareers/rss/jobs'),
]

for name, url in feeds:
    try:
        feed = feedparser.parse(url)
        if len(feed.entries) > 0:
            report_pass(f"RSS: {name}", f"{len(feed.entries)} entries")
        else:
            report_skip(f"RSS: {name}", "0 entries")
    except Exception as e:
        report_fail(f"RSS: {name}", str(e))

# =============================================================================
# 2-6. Individual scrapers
# =============================================================================
write_header("2-6. Scraper Suite")
scrapers = [
    ("InternshipScraper", "InternshipScraper", "backend.workers.worker_app.scrapers.internship_scraper", 5),
    ("ScholarshipScraper", "ScholarshipScraper", "backend.workers.worker_app.scrapers.scholarship_scraper", 5),
    ("ProjectScraper", "ProjectScraper", "backend.workers.worker_app.scrapers.project_scraper", 3),
    ("CertificationScraper", "CertificationScraper", "backend.workers.worker_app.scrapers.certification_scraper", 3),
    ("PostdocScraper", "PostdocScraper", "backend.workers.worker_app.scrapers.postdoc_scraper", 5),
]

for s in scrapers:
    run_scraper_test(*s)

# =============================================================================
# Summary
# =============================================================================
total = stats["PASS"] + stats["FAIL"]
color = Colors.GREEN if stats["FAIL"] == 0 else Colors.YELLOW

print(f"\n{Colors.GRAY}=================================================={Colors.END}")
print(f"  Results: {color}{stats['PASS']}/{total} passed{Colors.END}  ({stats['SKIP']} skipped)")
print(f"{Colors.GRAY}=================================================={Colors.END}")

if errors_list:
    print(f"\n{Colors.RED}  Failures:{Colors.END}")
    for e in errors_list:
        print(f"  {Colors.RED}{e}{Colors.END}")

if stats["FAIL"] > 0:
    sys.exit(1)