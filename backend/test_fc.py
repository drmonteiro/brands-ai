import os
from firecrawl import FirecrawlApp
app = FirecrawlApp(api_key=os.environ.get("FIRECRAWL_API_KEY"))
res = app.batch_scrape(["https://example.com"], {"formats": ["markdown"], "onlyMainContent": True})
print(res)
