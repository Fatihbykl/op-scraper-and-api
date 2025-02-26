from playwright.sync_api import sync_playwright, Page
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
import time
import psutil
import os

def get_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # MB

SECTION_TAG_NAMES = ["description", "aside", "details", "availability", "availability_table", "location"]
XML_FILE_PATH = "feed.xml"
OPP_URLS_PATH = "opportunity_urls.txt"

# Scrapes all urls and compares from existing ones. If new url exists, scrape that opportunities.
def update_opportunities():
    existing_urls = read_urls_txt()
    updated_urls = scrape_opportunity_urls("https://volunteercentrenewcastle.org.uk/search-results")
    new_urls = list(set(updated_urls) - set(existing_urls))

    if len(new_urls) == 0:
        print("There are no new opportunities.")
        return
    
    existing_urls.extend(new_urls)
    write_urls_txt(existing_urls)

    feed = read_xml()
    entries = feed.find("entries")
    scrape_url(new_urls, entries)
    write_xml(feed)

# Scrapes all opportunity details (used for only initializing xml)
def scrape_all_urls():
    urls = read_urls_txt()
    feed = read_xml()
    entries = feed.find("entries")
    scrape_url(urls, entries)
    write_xml(feed)

# Scrapes all urls of opportunities
def scrape_opportunity_urls(start_url: str) -> list:
    with sync_playwright() as pw:
        browser = pw.firefox.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.goto(start_url)
        page.wait_for_selector("ul.pagination li")
        print(f"Memory Usage Before Closing Browser: {get_memory_usage():.2f} MB")
        urls = []
        page_count = len(page.query_selector_all("ul.pagination li"))
        # iterate all pages
        for page_number in range(1, page_count + 1):
            page_url = f"{start_url}?results_page={str(page_number)}"
            page.goto(url=page_url)
            page.wait_for_selector("ul.vp_opportunities")

            # extract opportunity urls in the page
            opportunities = page.query_selector_all("ul.vp_opportunities li")
            for op in opportunities:
                link = op.query_selector("p.more a")
                urls.append("https://volunteercentrenewcastle.org.uk" + link.get_attribute("href"))
        
        return urls

# Scrapes opportunity details from given urls
def scrape_url(page_urls: list, entries: ET.Element) -> None:
    with sync_playwright() as pw:
        browser = pw.firefox.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        for page_url in page_urls:
            page.goto(url=page_url)
            page.wait_for_selector("div.twelve.columns")
            #time.sleep(1)

            description_elements = page.locator("div.twelve.columns").locator("p, ul, h1, h2, h3, h4, h5").all()
            aside_elements = page.locator("div.four.columns aside.details").locator("p, ul, h1, h2, h3, h4, h5").all()
            bottom_divs = page.locator("div#content div.container div.eight.columns").all()
            details_elements = bottom_divs[0].locator("h3, ul").all()
            availability_elements = bottom_divs[1].locator("h1, h2, h3, h4, h5, p").all()
            availability_table = bottom_divs[1].locator("table").all()
            location_elements = page.locator("div#vp-address p").all()

            elements = [description_elements, aside_elements, details_elements, availability_elements, availability_table, location_elements]

            entry = ET.SubElement(entries, "entry")
            for index, element_list in enumerate(elements):
                section = ET.SubElement(entry, SECTION_TAG_NAMES[index])
                entry_string = ""
                for element in element_list:
                    if element == None:
                        continue
                    tag_name = element.evaluate("el => el.tagName.toLowerCase()")
                    text = element.inner_text().strip().replace("<br>", " ").replace("\n", " ")

                    if tag_name.startswith("h"):
                        entry_string += f"\n{text}\n\n"

                    elif tag_name == "p":
                        entry_string += f"\n{text}\n"

                    elif tag_name == "ul":
                        list_items = element.locator("li").all()
                        for li in list_items:
                            symbol = ""
                            class_attr = li.get_attribute("class")
                            if not class_attr:
                                symbol = "●"
                            else:
                                symbol = "☒" if class_attr == "status_2" else "☑"
                            entry_string += f"{symbol} {li.inner_text().strip()}\n"

                    elif tag_name == "table":
                        rows = [[cell.strip() if cell else "" for cell in row.locator("th, td").all_inner_texts()] for row in element.locator("tr").all()]
                        col_widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
                        formatted_rows = ["  ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row)) for row in rows]
                        
                        entry_string += "\n".join(formatted_rows)

                    section.text = entry_string

def read_xml():
    tree = ET.parse(XML_FILE_PATH)
    root = tree.getroot()
    return root

def write_xml(root: ET.Element):
    last_updated = root.find("lastUpdate")
    last_updated.text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z%z")
    tree = ET.ElementTree(root)
    with open(XML_FILE_PATH, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)

def read_urls_txt() -> list:
    urls = []
    with open(OPP_URLS_PATH, "r") as f:
        urls = f.read().splitlines()
    return urls

def write_urls_txt(url_list):
    with open(OPP_URLS_PATH, "w") as file:
        for url in url_list:
            file.write(url + "\n")
