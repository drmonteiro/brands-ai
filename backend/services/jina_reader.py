"""
Jina Reader Service - Content Extraction Fallback

Jina Reader (r.jina.ai) provides:
- Better JavaScript rendering than Tavily
- Clean markdown output optimized for LLMs
- Free tier with rate limits (20 req/min)
- No API key required for basic usage

Usage:
    content = await extract_with_jina("https://example.com")
"""

import aiohttp
import asyncio
from typing import Optional, Dict
import os

# Jina Reader base URL
JINA_READER_URL = "https://r.jina.ai/"

# Optional API key for higher rate limits
JINA_API_KEY = os.getenv("JINA_API_KEY")

# Rate limiting
JINA_REQUESTS_PER_MINUTE = 20


async def extract_with_jina(
    url: str, 
    timeout: int = 30,
    max_length: int = 15000
) -> Dict[str, any]:
    """
    Extract content from a URL using Jina Reader.
    
    Jina Reader converts web pages to clean markdown,
    handles JavaScript rendering, and removes ads/noise.
    
    Args:
        url: URL to extract content from
        timeout: Request timeout in seconds
        max_length: Maximum characters to return
        
    Returns:
        Dict with:
        - success: bool
        - content: str (markdown content)
        - title: str (page title)
        - error: str (if failed)
    """
    try:
        # Jina Reader URL format: https://r.jina.ai/https://target-url.com
        jina_url = f"{JINA_READER_URL}{url}"
        
        headers = {
            "Accept": "text/markdown",
            "User-Agent": "Confecos-Lanca-Prospector/1.0"
        }
        
        # Add API key if available (for higher rate limits)
        if JINA_API_KEY:
            headers["Authorization"] = f"Bearer {JINA_API_KEY}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                jina_url, 
                headers=headers, 
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Truncate if too long
                    if len(content) > max_length:
                        content = content[:max_length] + "\n\n[Content truncated...]"
                    
                    # Extract title from markdown (first # heading)
                    title = ""
                    for line in content.split("\n"):
                        if line.startswith("# "):
                            title = line[2:].strip()
                            break
                    
                    print(f"[JINA] ✅ Extracted {len(content)} chars from {url}")
                    
                    return {
                        "success": True,
                        "content": content,
                        "title": title,
                        "url": url,
                        "source": "jina_reader",
                    }
                    
                elif response.status == 429:
                    print(f"[JINA] ⚠️ Rate limited for {url}")
                    return {
                        "success": False,
                        "content": "",
                        "error": "rate_limited",
                        "url": url,
                    }
                else:
                    error_text = await response.text()
                    print(f"[JINA] ❌ Error {response.status} for {url}: {error_text[:100]}")
                    return {
                        "success": False,
                        "content": "",
                        "error": f"http_{response.status}",
                        "url": url,
                    }
                    
    except asyncio.TimeoutError:
        print(f"[JINA] ⏱️ Timeout for {url}")
        return {
            "success": False,
            "content": "",
            "error": "timeout",
            "url": url,
        }
    except Exception as e:
        print(f"[JINA] ❌ Exception for {url}: {e}")
        return {
            "success": False,
            "content": "",
            "error": str(e),
            "url": url,
        }


async def extract_with_fallback(
    url: str,
    primary_content: str,
    min_content_length: int = 500
) -> Dict[str, any]:
    """
    Use Jina Reader as fallback when primary extraction (Tavily) fails.
    
    Args:
        url: URL to extract
        primary_content: Content from primary extraction (Tavily)
        min_content_length: Minimum acceptable content length
        
    Returns:
        Dict with content from Jina if primary was too short, else original
    """
    # Check if primary content is sufficient
    if primary_content and len(primary_content) >= min_content_length:
        return {
            "success": True,
            "content": primary_content,
            "url": url,
            "source": "primary",
            "used_fallback": False,
        }
    
    # Primary content too short, try Jina
    print(f"[JINA] Primary content too short ({len(primary_content or '')} chars), trying Jina...")
    
    jina_result = await extract_with_jina(url)
    
    if jina_result["success"] and len(jina_result["content"]) > len(primary_content or ""):
        return {
            "success": True,
            "content": jina_result["content"],
            "url": url,
            "source": "jina_reader",
            "used_fallback": True,
        }
    
    # Jina also failed, return whatever we have
    return {
        "success": bool(primary_content),
        "content": primary_content or "",
        "url": url,
        "source": "primary",
        "used_fallback": True,
        "fallback_failed": True,
    }


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == "__main__":
    import sys
    
    async def test():
        # Test URL (default or from command line)
        test_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.huntsman.com"
        
        print("=" * 60)
        print("🔍 Testing Jina Reader")
        print("=" * 60)
        print(f"\nURL: {test_url}")
        
        result = await extract_with_jina(test_url)
        
        if result["success"]:
            print(f"\n✅ Success!")
            print(f"Title: {result.get('title', 'N/A')}")
            print(f"Content length: {len(result['content'])} chars")
            print(f"\n--- First 500 chars ---\n")
            print(result["content"][:500])
        else:
            print(f"\n❌ Failed: {result['error']}")
    
    asyncio.run(test())
