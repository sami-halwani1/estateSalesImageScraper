# Estate Sale Image Scraper

This Python script scrapes and downloads images from an estate sale listing page. It extracts all image URLs from the gallery thumbnails and saves them locally with custom filenames.

---

## Features

- Scrapes images from estate sale pages automatically.  
- Uses a **browser-like User-Agent** to reduce chances of being blocked.  
- Saves images with a **custom filename prefix** and ordered numbering.  
- Creates a dedicated folder for each run automatically.  
- Environment variables allow easy configuration for different pages.  

---

## Requirements

- **Python 3.8+**  
- Install required packages:

```bash
pip install requests beautifulsoup4
```


