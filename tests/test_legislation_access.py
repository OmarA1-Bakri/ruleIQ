"""

# Constants

Test different methods to access legislation.gov.uk API
"""

import requests
import time

from tests.test_constants import HTTP_OK


def test_direct_access():
    """Test direct access to legislation.gov.uk API"""
    test_urls = [
        "https://www.legislation.gov.uk/ukpga/2018/12/data.xml",
        "https://www.legislation.gov.uk/ukpga/2000/8/data.xml",
        "https://www.legislation.gov.uk/uksi/2017/692/data.xml",
    ]
    headers_options = [
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        {"User-Agent": "ruleIQ Compliance Platform", "Accept": "application/xml"},
        {"Accept": "*/*"},
    ]
    for url in test_urls[:1]:
        print(f"\n{'=' * 60}")
        print(f"Testing: {url}")
        for i, headers in enumerate(headers_options):
            print(f"\nAttempt {i + 1} with headers: {list(headers.keys())}")
            try:
                response = requests.get(url, headers=headers, timeout=10)
                print(f"  Status: {response.status_code}")
                if response.status_code == HTTP_OK:
                    print(f"  ✅ Success! Content length: {len(response.content)}")
                    print(f"  Content-Type: {response.headers.get('Content-Type')}")
                    with open("data/test_legislation.xml", "wb") as f:
                        f.write(response.content)
                    print("  Saved to data/test_legislation.xml")
                    if response.content.startswith(b"<?xml"):
                        print("  ✅ Valid XML response")
                    return True
                elif response.status_code == 437:
                    print(f"  ❌ Error 437: {response.text[:200]}")
                else:
                    print(f"  ❌ Error {response.status_code}")
            except Exception as e:
                print(f"  ❌ Exception: {e}")
            time.sleep(1)
    return False


if __name__ == "__main__":
    print("Testing access to legislation.gov.uk API...")
    success = test_direct_access()
    if success:
        print("\n✅ Successfully accessed legislation.gov.uk API!")
        print("Check data/test_legislation.xml for the response")
    else:
        print("\n❌ Could not access the API")
