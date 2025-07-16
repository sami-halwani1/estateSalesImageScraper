import os
import requests
from bs4 import BeautifulSoup

# URL of the estate sale page
url = os.environ.get('SCRAPED_URL')  # Allow overriding via environment variable

# Desired filename prefix
filename = os.environ.get('FILE_NAME')  # Allow overriding via environment variable
# Folder to store images
folder_name = f'{filename} downloaded_images'
os.makedirs(f"Images/{folder_name}", exist_ok=True)


# Request the page (with a browser-like user-agent to avoid blocks)
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
response = requests.get(url, headers=headers)
response.raise_for_status()

# Parse the HTML
soup = BeautifulSoup(response.text, 'html.parser')

# Locate the image gallery thumbnails
thumbnails = soup.find_all('div', class_='sale-picture-gallery__thumbnail')

if not thumbnails:
    print("❌ Could not locate the image gallery. Exiting.")
    exit()

# Extract image URLs from the 'lazyload' attribute of <source> tags
image_urls = []
for thumbnail in thumbnails:
    source_tag = thumbnail.find('source', {'lazyload': True})
    if source_tag and source_tag.has_attr('lazyload'):
        image_urls.append(source_tag['lazyload'])

# Download each image with the custom filename format
for index, img_url in enumerate(image_urls):
    img_data = requests.get(img_url).content
    file_path = os.path.join(f"Images/{folder_name}", f'{filename}_{index+1}.jpg')
    with open(file_path, 'wb') as img_file:
        img_file.write(img_data)

print(f"✅ Downloaded {len(image_urls)} images into '{folder_name}' with filenames like '{filename}_1.jpg'")