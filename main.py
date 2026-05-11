
from playwright.sync_api import sync_playwright
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)
from reportlab.lib.styles import getSampleStyleSheet

import pandas as pd
import requests
import ollama
import json
import os
import re
import urllib3
import sqlite3
import subprocess
import logging
import time

# ==============================
# SETTINGS
# ==============================
HEADLESS = True
MAX_THREADS = 20
TIMEOUT = 60000
AI_MODEL = "phi3"

# ==============================
# CREATE FOLDERS
# ==============================
folders = [
    "screenshots",
    "reports",
    "reports/pdf",
    "reports/excel",
    "reports/csv",
    "reports/lighthouse",
    "reports/json",
    "database",
    "logs"
]

for folder in folders:
    os.makedirs(folder, exist_ok=True)

# ==============================
# LOGGING
# ==============================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)

# ==============================
# HIDE SSL WARNINGS
# ==============================
urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

# ==============================
# INPUT
# ==============================
website = input("Enter website URL: ").strip()

if not website.startswith("http"):
    website = "https://" + website

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# ==============================
# FILE PATHS
# ==============================
screenshot_name = f"screenshots/test_{timestamp}.png"

txt_report = f"reports/report_{timestamp}.txt"

html_report_file = f"reports/report_{timestamp}.html"

json_report_file = f"reports/json/report_{timestamp}.json"

excel_report_file = f"reports/excel/report_{timestamp}.xlsx"

csv_report_file = f"reports/csv/report_{timestamp}.csv"

pdf_report_file = f"reports/pdf/report_{timestamp}.pdf"

db_file = "database/history.db"

lighthouse_json = (
    f"reports/lighthouse/lighthouse_{timestamp}.json"
)

# ==============================
# STORAGE
# ==============================
broken_links = []
console_errors = []
js_errors = []
network_failures = []

all_links_data = set()

broken_images = []
missing_alt = []

accessibility_issues = []

performance_score = "N/A"
seo_score = "N/A"
best_practices_score = "N/A"

# ==============================
# REQUEST SESSION
# ==============================
headers = {
    "User-Agent": "Mozilla/5.0 (QA-Automation-Bot)"
}

session = requests.Session()
session.headers.update(headers)

# ==============================
# DATABASE
# ==============================
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    website TEXT,
    timestamp TEXT,
    broken_links INTEGER,
    console_errors INTEGER,
    broken_images INTEGER,
    missing_alt INTEGER,
    performance_score TEXT,
    seo_score TEXT
)
""")

conn.commit()

# ==============================
# LINK CHECKER
# ==============================
def check_link(full_url):

    retries = 2

    for attempt in range(retries):

        try:

            response = session.head(
                full_url,
                timeout=5,
                allow_redirects=True,
                verify=False
            )

            if response.status_code >= 400:

                response = session.get(
                    full_url,
                    timeout=5,
                    allow_redirects=True,
                    verify=False
                )

            status_code = response.status_code

            logging.info(f"{full_url} --> {status_code}")

            if status_code >= 400:

                broken_links.append(
                    (full_url, status_code)
                )

            return

        except Exception as e:

            if attempt == retries - 1:

                logging.error(f"{full_url} --> FAILED")

                broken_links.append(
                    (full_url, str(e))
                )

            time.sleep(1)

# ==============================
# LIGHTHOUSE FIXED
# ==============================
def run_lighthouse():

    global performance_score
    global seo_score
    global best_practices_score

    try:

        logging.info("Running Lighthouse Audit...")

        os.makedirs(
            "reports/lighthouse",
            exist_ok=True
        )

        lighthouse_path = os.path.abspath(
            lighthouse_json
        )

        cmd = [
            "lighthouse",
            website,
            "--quiet",
            "--chrome-flags=--headless",
            "--output=json",
            f"--output-path={lighthouse_path}"
        ]

        subprocess.run(
            cmd,
            check=True,
            shell=True
        )

        wait_time = 0

        while (
            not os.path.exists(lighthouse_path)
            and wait_time < 20
        ):
            time.sleep(1)
            wait_time += 1

        with open(
            lighthouse_path,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        performance_score = round(
            data["categories"]["performance"]["score"] * 100
        )

        seo_score = round(
            data["categories"]["seo"]["score"] * 100
        )

        best_practices_score = round(
            data["categories"]["best-practices"]["score"] * 100
        )

        logging.info("Lighthouse Completed")

    except Exception as e:

        logging.error(
            f"Lighthouse Failed: {e}"
        )

        performance_score = "N/A"
        seo_score = "N/A"
        best_practices_score = "N/A"

# ==============================
# PLAYWRIGHT
# ==============================
with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=HEADLESS,
        args=[
            "--disable-dev-shm-usage",
            "--no-sandbox"
        ]
    )

    page = browser.new_page()

    # ==============================
    # CONSOLE ERRORS
    # ==============================
    def handle_console(msg):

        if msg.type == "error":

            console_errors.append(msg.text)
            js_errors.append(msg.text)

    page.on("console", handle_console)

    # ==============================
    # NETWORK FAILURES
    # ==============================
    page.on(
        "requestfailed",
        lambda request: network_failures.append(
            request.url
        )
    )

    logging.info("Opening website...")

    try:

        page.goto(
            website,
            timeout=TIMEOUT,
            wait_until="domcontentloaded"
        )

    except Exception as e:

        logging.error(f"Primary load failed: {e}")

        page.goto(
            website,
            timeout=TIMEOUT,
            wait_until="load"
        )

    logging.info("Analyzing website...")

    page_title = page.title()

    # ==============================
    # PAGE LOAD TIME
    # ==============================
    load_time = page.evaluate("""
    () => {
        const nav =
        performance.getEntriesByType('navigation')[0];

        if (nav) {
            return Math.round(nav.loadEventEnd);
        }

        return Math.round(performance.now());
    }
    """)

    logging.info(f"Load Time: {load_time} ms")

    # ==============================
    # ELEMENTS
    # ==============================
    links = page.locator("a")

    buttons = page.locator("button").count()

    forms = page.locator("form").count()

    inputs_total = page.locator("input").count()

    links_count = links.count()

    # ==============================
    # ACCESSIBILITY
    # ==============================
    logging.info("Checking accessibility...")

    images = page.locator("img")

    image_count = images.count()

    for i in range(image_count):

        src = images.nth(i).get_attribute("src")

        alt = images.nth(i).get_attribute("alt")

        if not alt:

            missing_alt.append(f"Image {i+1}")

            accessibility_issues.append(
                f"Missing alt tag on image {i+1}"
            )

        if not src:
            continue

        img_url = urljoin(website, src)

        try:

            r = session.get(
                img_url,
                timeout=5,
                verify=False
            )

            if r.status_code >= 400:

                broken_images.append(img_url)

        except:

            broken_images.append(img_url)

    # ==============================
    # INPUT LABEL CHECK
    # ==============================
    inputs = page.locator("input")

    input_count = inputs.count()

    for i in range(input_count):

        input_id = inputs.nth(i).get_attribute("id")

        if input_id:

            label = page.locator(
                f'label[for="{input_id}"]'
            ).count()

            if label == 0:

                accessibility_issues.append(
                    f"Input '{input_id}' missing label"
                )

    # ==============================
    # SECURITY HEADERS
    # ==============================
    security_headers = [
        "Content-Security-Policy",
        "X-Frame-Options",
        "Strict-Transport-Security"
    ]

    missing_security_headers = []

    try:

        main_response = session.get(
            website,
            timeout=10,
            verify=False
        )

        for header in security_headers:

            if header not in main_response.headers:

                missing_security_headers.append(header)

    except:
        pass

    # ==============================
    # SEO CHECKS
    # ==============================
    meta_description = page.locator(
        'meta[name="description"]'
    ).count()

    title_length = len(page_title)

    seo_issues = []

    if meta_description == 0:

        seo_issues.append(
            "Meta description missing"
        )

    if title_length < 10:

        seo_issues.append(
            "Title too short"
        )

    if title_length > 60:

        seo_issues.append(
            "Title too long"
        )

    # ==============================
    # EXTRACT LINKS
    # ==============================
    logging.info("Checking links...")

    urls_to_check = []

    base_domain = urlparse(website).netloc

    for i in range(links_count):

        href = links.nth(i).get_attribute("href")

        if not href:
            continue

        if href.startswith((
            "javascript:",
            "mailto:",
            "#",
            "tel:"
        )):
            continue

        full_url = urljoin(website, href)

        full_url = full_url.split("#")[0]

        if full_url in all_links_data:
            continue

        parsed = urlparse(full_url)

        if parsed.netloc != base_domain:
            continue

        all_links_data.add(full_url)

        urls_to_check.append(full_url)

    # ==============================
    # MULTITHREADING
    # ==============================
    with ThreadPoolExecutor(
        max_workers=MAX_THREADS
    ) as executor:

        executor.map(
            check_link,
            urls_to_check
        )

    # ==============================
    # SCREENSHOT
    # ==============================
    logging.info("Taking screenshot...")

    page.screenshot(
        path=screenshot_name,
        full_page=True
    )

    browser.close()

# ==============================
# LIGHTHOUSE
# ==============================
run_lighthouse()

# ==============================
# AI TEST CASES
# ==============================
logging.info("Generating AI test cases...")

prompt = f"""
You are a Senior QA Engineer.

Return ONLY valid JSON array.

Each test case format:

{{
  "id": "TC_01",
  "type": "Functional/UI/Security/Accessibility",
  "priority": "High/Medium/Low",
  "severity": "Critical/Major/Minor",
  "title": "",
  "steps": "",
  "expected_result": ""
}}

RULES:
- Generate ONLY 5 test cases
- Keep response short
- Use provided website data only

Website:
Title: {page_title}
URL: {website}
Links: {links_count}
Buttons: {buttons}
Forms: {forms}
Images: {image_count}
Load Time: {load_time}

Broken Links:
{broken_links[:5]}

Accessibility:
{accessibility_issues[:5]}

Security:
{missing_security_headers}

SEO:
{seo_issues}

Return ONLY JSON ARRAY.
"""

response = ollama.chat(
    model=AI_MODEL,
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ]
)

raw_output = response['message']['content']

logging.info("AI Output Received")

# ==============================
# JSON CLEANING
# ==============================
cleaned = raw_output.strip()

cleaned = cleaned.replace(
    "```json",
    ""
).replace(
    "```",
    ""
)

try:

    test_cases = json.loads(cleaned)

    logging.info("JSON Parsed Successfully")

except:

    logging.warning("JSON Parse Failed")

    match = re.search(
        r"\[.*\]",
        cleaned,
        re.DOTALL
    )

    if match:

        try:

            test_cases = json.loads(match.group())

        except:

            test_cases = []

    else:

        test_cases = []

# ==============================
# COMPLETE REPORT DATA
# ==============================
complete_report = {
    "website": website,
    "title": page_title,
    "timestamp": timestamp,
    "load_time_ms": load_time,
    "performance_score": performance_score,
    "seo_score": seo_score,
    "best_practices_score": best_practices_score,
    "broken_links": broken_links,
    "broken_images": broken_images,
    "console_errors": console_errors,
    "network_failures": network_failures,
    "accessibility_issues": accessibility_issues,
    "seo_issues": seo_issues,
    "security_headers_missing": missing_security_headers,
    "ai_test_cases": test_cases
}

# ==============================
# SAVE JSON
# ==============================
with open(
    json_report_file,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        complete_report,
        f,
        indent=4
    )

# ==============================
# EXCEL + CSV
# ==============================
df = pd.DataFrame(test_cases)

df.to_excel(
    excel_report_file,
    index=False
)

df.to_csv(
    csv_report_file,
    index=False
)

# ==============================
# PDF REPORT
# ==============================
styles = getSampleStyleSheet()

doc = SimpleDocTemplate(pdf_report_file)

elements = []

elements.append(
    Paragraph(
        "QA AUTOMATION REPORT",
        styles['Title']
    )
)

elements.append(Spacer(1, 20))

summary = f"""
Website: {website}<br/>
Title: {page_title}<br/>
Load Time: {load_time} ms<br/>
Broken Links: {len(broken_links)}<br/>
Broken Images: {len(broken_images)}<br/>
Console Errors: {len(console_errors)}<br/>
Accessibility Issues: {len(accessibility_issues)}<br/>
Performance Score: {performance_score}<br/>
SEO Score: {seo_score}<br/>
Best Practices Score: {best_practices_score}<br/>
"""

elements.append(
    Paragraph(
        summary,
        styles['BodyText']
    )
)

elements.append(Spacer(1, 20))

for tc in test_cases:

    tc_text = f"""
    <b>{tc.get('id')}</b>
    - {tc.get('title')}<br/>

    Type: {tc.get('type')}<br/>

    Priority: {tc.get('priority')}<br/>

    Severity: {tc.get('severity')}<br/>

    Steps: {tc.get('steps')}<br/>

    Expected:
    {tc.get('expected_result')}<br/><br/>
    """

    elements.append(
        Paragraph(
            tc_text,
            styles['BodyText']
        )
    )

    elements.append(Spacer(1, 10))

doc.build(elements)

# ==============================
# HTML REPORT
# ==============================
html = f"""
<html>

<head>

<title>QA Report</title>

<style>

body {{
    font-family: Arial;
    margin: 20px;
    background: #121212;
    color: white;
}}

.card {{
    border: 1px solid #333;
    padding: 15px;
    margin: 15px 0;
    border-radius: 8px;
    background: #1e1e1e;
}}

.error {{
    color: red;
}}

.success {{
    color: lightgreen;
}}

</style>

</head>

<body>

<h1>QA Automation Report</h1>

<h3>Website: {website}</h3>

<h3>Title: {page_title}</h3>

<h3>Load Time: {load_time} ms</h3>

<h3>Performance Score: {performance_score}</h3>

<h3>SEO Score: {seo_score}</h3>

<h3>Best Practices Score: {best_practices_score}</h3>

<h2>Accessibility Issues</h2>

<ul>
"""

if accessibility_issues:

    for issue in accessibility_issues:

        html += f'<li class="error">{issue}</li>'

else:

    html += '''
    <li class="success">
    No accessibility issues found.
    </li>
    '''

html += "</ul>"

html += "<h2>SEO Issues</h2><ul>"

if seo_issues:

    for issue in seo_issues:

        html += f'<li class="error">{issue}</li>'

else:

    html += '''
    <li class="success">
    No SEO issues found.
    </li>
    '''

html += "</ul>"

html += "<h2>AI Test Cases</h2>"

for tc in test_cases:

    html += f"""
    <div class="card">

        <h3>
        {tc.get('id')}
        - {tc.get('title')}
        </h3>

        <p>
        <b>Type:</b>
        {tc.get('type')}
        </p>

        <p>
        <b>Priority:</b>
        {tc.get('priority')}
        </p>

        <p>
        <b>Severity:</b>
        {tc.get('severity')}
        </p>

        <p>
        <b>Steps:</b>
        {tc.get('steps')}
        </p>

        <p>
        <b>Expected:</b>
        {tc.get('expected_result')}
        </p>

    </div>
    """

html += "</body></html>"

with open(
    html_report_file,
    "w",
    encoding="utf-8"
) as f:

    f.write(html)

# ==============================
# TXT REPORT
# ==============================
with open(
    txt_report,
    "w",
    encoding="utf-8"
) as file:

    file.write(
        "=== QA AUTOMATION REPORT ===\n\n"
    )

    file.write(f"Website: {website}\n")

    file.write(f"Title: {page_title}\n")

    file.write(f"Load Time: {load_time} ms\n\n")

    file.write(
        f"Performance Score: "
        f"{performance_score}\n"
    )

    file.write(f"SEO Score: {seo_score}\n")

    file.write(
        f"Best Practices Score: "
        f"{best_practices_score}\n\n"
    )

    file.write(
        f"Broken Links: "
        f"{len(broken_links)}\n"
    )

    file.write(
        f"Broken Images: "
        f"{len(broken_images)}\n"
    )

    file.write(
        f"Console Errors: "
        f"{len(console_errors)}\n"
    )

    file.write(
        f"Accessibility Issues: "
        f"{len(accessibility_issues)}\n\n"
    )

    file.write(
        json.dumps(
            test_cases,
            indent=4
        )
    )

# ==============================
# DATABASE INSERT
# ==============================
cursor.execute("""
INSERT INTO reports (
    website,
    timestamp,
    broken_links,
    console_errors,
    broken_images,
    missing_alt,
    performance_score,
    seo_score
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (
    website,
    timestamp,
    len(broken_links),
    len(console_errors),
    len(broken_images),
    len(missing_alt),
    str(performance_score),
    str(seo_score)
))

conn.commit()
conn.close()

# ==============================
# FINAL SUMMARY
# ==============================
logging.info("===== FINAL SUMMARY =====")

logging.info(
    f"Broken Links: {len(broken_links)}"
)

logging.info(
    f"Broken Images: {len(broken_images)}"
)

logging.info(
    f"Console Errors: {len(console_errors)}"
)

logging.info(
    f"Accessibility Issues: "
    f"{len(accessibility_issues)}"
)

logging.info(
    f"Performance Score: "
    f"{performance_score}"
)

logging.info(f"SEO Score: {seo_score}")

logging.info(
    f"Best Practices Score: "
    f"{best_practices_score}"
)

logging.info("===== REPORTS GENERATED =====")

logging.info(f"TXT: {txt_report}")

logging.info(f"HTML: {html_report_file}")

logging.info(f"JSON: {json_report_file}")

logging.info(f"EXCEL: {excel_report_file}")

logging.info(f"CSV: {csv_report_file}")

logging.info(f"PDF: {pdf_report_file}")

logging.info(f"LIGHTHOUSE: {lighthouse_json}")

logging.info(f"SCREENSHOT: {screenshot_name}")

logging.info(f"Database Saved: {db_file}")

print("\n====================================")
print("QA AUTOMATION COMPLETED")
print("====================================")
print(f"Website Tested: {website}")
print(f"Broken Links Found: {len(broken_links)}")
print(f"Broken Images Found: {len(broken_images)}")
print(f"Accessibility Issues: {len(accessibility_issues)}")
print(f"Performance Score: {performance_score}")
print(f"SEO Score: {seo_score}")
print("====================================")
print("Reports Generated Successfully")
print("====================================")