# Extends official Crawl4AI so Playwright always has Chromium on disk.
# Fixes: BrowserType.launch: Executable doesn't exist at .../ms-playwright/chromium-*/chrome
#
# install-deps → apt libs (must run as root)
# install chromium → downloads browser into /home/appuser/.cache/ms-playwright (matches gunicorn user)
FROM unclecode/crawl4ai:0.8.5

USER root
RUN playwright install-deps chromium

USER appuser
RUN playwright install chromium
