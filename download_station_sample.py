#!/usr/bin/env python3
"""Download Yahoo Transit station detail page for testing."""

import requests
from pathlib import Path
import time

def download_station_page():
    """Download the station detail page for testing station data extraction."""
    
    # The URL provided by the user
    url = "https://transit.yahoo.co.jp/station/20042?pref=1&company=%E6%9C%AD%E5%B9%8C%E5%B8%82%E4%BA%A4%E9%80%9A%E4%BA%8B%E6%A5%AD%E6%8C%AF%E8%88%88%E5%85%AC%E7%A4%BE&line=%E5%B1%B1%E9%BC%BB%E7%B7%9A"
    
    # Set up headers to mimic a real browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        print(f"Downloading station page from: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Create fixtures directory if it doesn't exist
        fixtures_dir = Path("tests/fixtures/station_pages")
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        
        # Save the HTML file
        filename = fixtures_dir / "station_20042_yamanose_line.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        print(f"Station page saved to: {filename}")
        print(f"File size: {len(response.text)} characters")
        
        # Extract some basic info for verification
        content = response.text
        if "駅情報" in content:
            print("✓ Page contains station information")
        if "時刻表" in content:
            print("✓ Page contains timetable information")
        if "路線" in content:
            print("✓ Page contains line information")
            
        return str(filename)
        
    except requests.exceptions.RequestException as e:
        print(f"Error downloading page: {e}")
        return None

if __name__ == "__main__":
    download_station_page()