import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv()

from services.crawl4ai_client import get_crawl4ai_client
from services.extraction.css_extractor import css_extractor

async def test_extract():
    test_urls = [
        "https://www.hawesandcurtis.co.uk/mens-suits",
        "https://suitsupply.com/en-pt/men/suits"
    ]
    
    async for client in get_crawl4ai_client():
        for url in test_urls:
            print(f"\n--- Testing CSS Extraction on {url} ---")
            res = await client.scrape(url)
            print(f"Scrape Success: {res.success}")
            if res.success:
                print(f"Status Code: {res.status_code}")
                
                # Apply Layer 1 CSS Extraction
                extracted_data = css_extractor.extract(res.cleaned_html)
                score, reasons = css_extractor.extraction_quality_score(extracted_data)
                
                print(f"--- LAYER 1 RESULTS ---")
                print(f"Score: {score}")
                print(f"Reasons: {reasons}")
                print(f"Data: {extracted_data.model_dump_json(indent=2)}")
                
                md_len = len(res.best_markdown)
                print(f"Best Markdown Length: {md_len}")
                if md_len < 1000:
                    print(f"Warning: Low markdown length, possibly bot protection hit.")
            else:
                print(f"Error: {res.error_message}")

if __name__ == "__main__":
    asyncio.run(test_extract())
