import os
import sys
import json
import subprocess
import traceback
import importlib

# Terminal Colors
class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    GRAY = '\033[90m'
    END = '\033[0m'

# Test State
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
    
    # Mock environment variables
    os.environ.setdefault('SECRET_KEY', 'a' * 32)
    os.environ.setdefault('POSTGRES_PASSWORD', 'test')
    sys.path.insert(0, '.')

    try:
        # Dynamic import of your project modules
        module = importlib.import_module(module_path)
        scraper_class = getattr(module, class_name)
        
        scraper = scraper_class()
        items = scraper.run()
        
        # Validation logic from your PS1
        valid = [i for i in items if i.get('url') and i.get('title') and i.get('type')]
        count = len(items)
        valid_count = len(valid)

        if count >= min_expected:
            report_pass(name, f"{valid_count} valid / {count} collected")
        elif count > 0:
            report_skip(name, f"only {count} items (expected {min_expected}+)")
        else:
            report_fail(name, "0 items — site blocked or selectors stale")

        # Sample printing
        for s in valid[:3]:
            print(f"    {Colors.GRAY}+ {s.get('title', '')[:70]}{Colors.END}")
            print(f"      {Colors.GRAY}{s.get('url', '')[:80]}{Colors.END}")
            
        return valid_count

    except Exception as e:
        report_fail(name, str(e))
        print(f"    {Colors.GRAY}{traceback.format_exc()[-500:]}{Colors.END}")
        return 0

# =============================================================================
# 0. Dependencies
# =============================================================================
write_header("0. Dependency checks")

for dep in ["playwright", "bs4", "requests", "lxml"]:
    try:
        __import__(dep if dep != "bs4" else "bs4")
        report_pass(f"import {dep}")
    except ImportError:
        report_fail(f"import {dep}", "not installed")

try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        b.close()
    report_pass("Playwright chromium")
except Exception as e:
    report_fail("Playwright chromium", "run: playwright install chromium")

# =============================================================================
# 1-5. Individual Scrapers + 6. KMeans Readiness
# =============================================================================
write_header("1-5. Individual Scrapers")

scraper_configs = [
    ("InternshipScraper", "InternshipScraper", "backend.workers.worker_app.scrapers.internship_scraper", 10),
    ("ScholarshipScraper", "ScholarshipScraper", "backend.workers.worker_app.scrapers.scholarship_scraper", 12),
    ("ProjectScraper", "ProjectScraper", "backend.workers.worker_app.scrapers.project_scraper", 5),
    ("CertificationScraper", "CertificationScraper", "backend.workers.worker_app.scrapers.certification_scraper", 8),
    ("PostdocScraper", "PostdocScraper", "backend.workers.worker_app.scrapers.postdoc_scraper", 10),
]

grand_total = 0
for cfg in scraper_configs:
    grand_total += run_scraper_test(*cfg)

write_header("6. Total count + KMeans readiness check")
print(f"  {Colors.GRAY}Total valid items across all scrapers: {grand_total}{Colors.END}")

if grand_total >= 20:
    report_pass("Total", f"{grand_total} items — KMeans will trigger on next cluster run")
else:
    report_skip("Total", f"{grand_total} items — need 20+ for KMeans clustering")

# =============================================================================
# 7. Celery trigger
# =============================================================================
write_header("7. Enqueue scraper tasks via Celery")

confirm = input(f"  {Colors.YELLOW}Is Celery worker running? (y/n): {Colors.END}").lower()

if confirm == 'y':
    task_types = ["internship", "scholarship", "project", "certification", "postdoc"]
    try:
        from backend.job_queue.producer import (
            enqueue_internship_scraper, enqueue_scholarship_scraper,
            enqueue_project_scraper, enqueue_certification_scraper,
            enqueue_postdoc_scraper
        )
        # Map strings to functions
        task_map = {
            "internship": enqueue_internship_scraper,
            "scholarship": enqueue_scholarship_scraper,
            "project": enqueue_project_scraper,
            "certification": enqueue_certification_scraper,
            "postdoc": enqueue_postdoc_scraper
        }

        for t in task_types:
            try:
                result = task_map[t]()
                report_pass(f"Enqueue {t} scraper", f"task={result.id}")
            except Exception as e:
                report_fail(f"Enqueue {t}", str(e))
        
        print(f"\n  {Colors.GRAY}Poll task status: GET http://localhost:8000/tasks/{{task_id}}{Colors.END}")
        print(f"  {Colors.GRAY}Trigger pipeline: python -c \"from backend.job_queue.producer import enqueue_classifier; enqueue_classifier()\"{Colors.END}")

    except ImportError as e:
        report_fail("Celery Producer", f"Could not import producer: {e}")
else:
    report_skip("Celery tasks", "worker not running")

# =============================================================================
# Summary
# =============================================================================
total_tests = stats["PASS"] + stats["FAIL"]
final_color = Colors.GREEN if stats["FAIL"] == 0 else Colors.YELLOW

print(f"\n{Colors.GRAY}=================================================={Colors.END}")
print(f"  Results: {final_color}{stats['PASS']}/{total_tests} passed{Colors.END}  ({stats['SKIP']} skipped)")
print(f"{Colors.GRAY}=================================================={Colors.END}")

if errors_list:
    print(f"\n{Colors.RED}  Failures:{Colors.END}")
    for e in errors_list:
        print(f"  {Colors.RED}{e}{Colors.END}")

print(f"\n{Colors.CYAN}  Next steps after scrapers pass:{Colors.END}")
print(f"  {Colors.GRAY}1. Run scrapers via Celery Beat (auto) or manually trigger{Colors.END}")
print(f"  {Colors.GRAY}2. Classifier runs every 15 min — embeds new opportunities{Colors.END}")
print(f"  {Colors.GRAY}3. Cluster runs every 12h — triggers KMeans once >= 20 items{Colors.END}")
print(f"  {Colors.GRAY}4. Recommendations recompute every 6h with cluster context{Colors.END}\n")

if stats["FAIL"] > 0:
    sys.exit(1)