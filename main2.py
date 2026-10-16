import os
import time
import requests
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from openai import OpenAI
import json

# =========================
# Config
# =========================
def setup_config():
    url = os.environ.get("SCRAPED_URL")
    filename = os.environ.get("FILE_NAME", "estate_sale")
    max_images = 12  # Set a reasonable default limit to avoid excessive downloads

    folder_name = f"{filename} downloaded_images"
    output_dir = os.path.join("Images", folder_name)
    os.makedirs(output_dir, exist_ok=True)

    return url, filename, max_images, output_dir

# =========================
# Browser setup
# =========================
def setup_browser():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 20)
    return driver, wait

# =========================
# Helper: download file
# =========================
def download_image(session, img_url, file_path, referer):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": referer,
    }
    resp = session.get(img_url, headers=headers, timeout=30)
    resp.raise_for_status()
    with open(file_path, "wb") as f:
        f.write(resp.content)

# =========================
# Scrape thumbnails
# =========================
def get_thumbnail_links(driver, wait, url, max_images):
    driver.get(url)
    wait.until(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "div.sale-picture-gallery__thumbnail a.sale-picture-gallery__wrap")
        )
    )
    thumbnail_links = driver.find_elements(
        By.CSS_SELECTOR, "div.sale-picture-gallery__thumbnail a.sale-picture-gallery__wrap"
    )

    if not thumbnail_links:
        raise SystemExit("❌ No thumbnails found.")

    picture_urls = []
    seen_picture_urls = set()

    for link in thumbnail_links:
        href = link.get_attribute("href")
        if not href:
            continue
        full_href = urljoin(url, href)
        if full_href in seen_picture_urls:
            continue
        seen_picture_urls.add(full_href)
        picture_urls.append(full_href)

        if len(picture_urls) >= max_images:
            break

    if not picture_urls:
        raise SystemExit("❌ No picture page URLs found.")

    print(f"🔎 Found {len(picture_urls)} picture pages.")
    return picture_urls

# =========================
# Process images
# =========================
def process_images(driver, session, picture_urls, output_dir, filename):
    downloaded = 0
    seen_final_image_urls = set()

    for idx, picture_url in enumerate(picture_urls, start=1):
        print(f"\n➡️ Processing image {idx}: {picture_url}")
        driver.get(picture_url)

        time.sleep(2)

        candidates = driver.execute_script("""
            const imgs = Array.from(document.images);

            return imgs
                .map(img => {
                    const src = img.currentSrc || img.src || "";
                    return {
                        src,
                        naturalWidth: img.naturalWidth || 0,
                        naturalHeight: img.naturalHeight || 0,
                        area: (img.naturalWidth || 0) * (img.naturalHeight || 0)
                    };
                })
                .filter(x =>
                    x.src &&
                    x.src.includes("picturescdn.estatesales.net") &&
                    x.naturalWidth > 200 &&
                    x.naturalHeight > 200
                )
                .sort((a, b) => {
                    const aThumb = a.src.includes("/1-2/");
                    const bThumb = b.src.includes("/1-2/");
                    if (aThumb !== bThumb) return aThumb ? 1 : -1;
                    return b.area - a.area;
                });
        """)

        if not candidates:
            print("❌ No rendered image candidates found on page.")
            continue

        selected = next((c for c in candidates if c["src"] not in seen_final_image_urls), None)

        if not selected:
            print("⚠️ Only duplicate image candidates found, skipping.")
            continue

        img_url = selected["src"]
        seen_final_image_urls.add(img_url)

        print(f"✅ Selected image URL: {img_url}")
        print(f"   Size: {selected['naturalWidth']}x{selected['naturalHeight']}")

        file_path = os.path.join(output_dir, f"{filename}_{idx}.jpg")

        try:
            download_image(session, img_url, file_path, picture_url)
            downloaded += 1
            print(f"✅ Downloaded: {file_path}")
        except Exception as e:
            print(f"❌ Download failed for {img_url}")
            print(f"   Error: {e}")

    print(f"\n✅ Finished. Downloaded {downloaded} actual images into '{output_dir}'.")


from openai import OpenAI
import json

def generate_metadata(driver, url):
    driver.get(url)
    time.sleep(2)

    try:
        # Click the "View More" button to expand the description
        view_more_button = driver.find_element(
            By.XPATH, "//button[span[contains(text(), 'View More')]]"
        )
        view_more_button.click()
        time.sleep(2)
        print("🔎 Clicked 'View More' button to expand description.")
    except Exception as e:
        print(f"❌ Failed to click 'View More' button: {e}")
        return "Unknown Title", "No description available.", "<p>No summary available.</p>"

    try:
        # Extract the specific section for metadata generation
        description_section = driver.find_element(
            By.CSS_SELECTOR, "div.cke-r"
        ).text.strip()
        print("🔎 Extracted description section for metadata generation.")
    except Exception as e:
        print(f"❌ Failed to extract description section: {e}")
        return "Unknown Title", "No description available.", "<p>No summary available.</p>"

    if not description_section:
        return "Unknown Title", "No description available.", "<p>No summary available.</p>"

    # Avoid sending a giant section
    description_section = description_section[:8000]
    #print(description_section)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY is not set.")
        return "Unknown Title", "No description available.", "<p>No summary available.</p>"

    try:
        client = OpenAI(api_key=api_key)

        response = client.responses.create(
            model="gpt-4",
            input=[
                {
                    "role": "system",
                    "content": (
                        "You generate SEO metadata and a summary for estate sale pages. "
                        "Return valid JSON only with exactly these keys: "
                        "meta_title, meta_description, and summary_html. "
                        "Meta title should be under 60 characters. "
                        "Meta description should be under 160 characters. "
                        "Summary should be a concise HTML-formatted summary of the description. Use A combination of Bullet points and short paragraphs (~30-50 Words each). "
                        "Avoid fluff. Focus on key details that would interest potential buyers. "

                        "Headers should be H2 or smaller.  "
                        "Do not include <title>"
                    ),
                },
                {
                    "role": "user",
                    "content": f"Generate SEO metadata and summary for this description:\n\n{description_section}",
                },
            ],
        )

        raw_text = response.output_text.strip()
        data = json.loads(raw_text)

        meta_title = data.get("meta_title", "Unknown Title").strip()
        meta_description = data.get("meta_description", "No description available.").strip()
        summary_html = data.get("summary_html", "<p>No summary available.</p>").strip()

        print(f"🔎 Generated Meta Title: {meta_title}")
        print(f"🔎 Generated Meta Description: {meta_description}")
        print(f"🔎 Generated Summary HTML: {summary_html}")

        return meta_title, meta_description, summary_html

    except Exception as e:
        print(f"❌ Failed to generate metadata using OpenAI API: {e}")
        return "Unknown Title", "No description available.", "<p>No summary available.</p>"

# =========================
# Main
# =========================





def main():
    url, filename, max_images, output_dir = setup_config()
    driver, wait = setup_browser()
    session = requests.Session()

    try:
        meta_title, meta_description, summary_html = generate_metadata(driver, url)
        print(f"\nMeta Title: {meta_title}")
        print(f"Meta Description: {meta_description}\n")
        print(f"Summary HTML:\n{summary_html}\n")

        # Save metadata and summary to an HTML file
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta name="description" content="{meta_description}">
            <title>{meta_title}</title>
        </head>
        <body>
            <h1>{meta_title}</h1>
            <div>{summary_html}</div>
        </body>
        </html>
        """
        output_file = os.path.join(output_dir, f"{filename}_metadata.html")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"✅ Metadata and summary saved to: {output_file}")

        picture_urls = get_thumbnail_links(driver, wait, url, max_images)
        process_images(driver, session, picture_urls, output_dir, filename)
    finally:
        driver.quit()
    

if __name__ == "__main__":
    main()