#!/usr/bin/env python3
"""
Test script to verify city extraction from Yahoo Transit HTML pages.
This script will help identify issues with the current parsing logic.
"""

import re
import requests
from bs4 import BeautifulSoup
import time
from typing import Optional


def extract_city_from_html(html_content: str, debug: bool = False) -> Optional[str]:
    """
    Extract city information from Yahoo Transit HTML using the same logic as the crawler.
    
    Args:
        html_content: Raw HTML content from Yahoo Transit
        debug: Print debug information
        
    Returns:
        Extracted city name or None
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        page_text = soup.get_text()
        
        if debug:
            print("=== PAGE TITLE ===")
            title_elem = soup.find("title")
            if title_elem:
                print(f"Title: {title_elem.get_text()}")
            
            print("\n=== FIRST 500 CHARS OF PAGE TEXT ===")
            print(page_text[:500])
            print("...")
        
        # City extraction patterns from the current crawler
        city_patterns = [
            # Tokyo wards
            r"(千代田区|中央区|港区|新宿区|文京区|台東区|墨田区|江東区|品川区|目黒区|大田区|世田谷区|渋谷区|中野区|杉並区|豊島区|北区|荒川区|板橋区|練馬区|足立区|葛飾区|江戸川区)",
            # Other cities
            r"([^\s]+市)",
            r"([^\s]+町)",
            r"([^\s]+村)",
            r"([^\s]+郡)",
        ]
        
        if debug:
            print("\n=== TESTING CITY PATTERNS ===")
        
        for i, pattern in enumerate(city_patterns):
            matches = re.findall(pattern, page_text)
            if debug:
                print(f"Pattern {i+1} ({pattern}): {matches[:5] if matches else 'No matches'}")
            
            if matches:
                # Return first reasonable match
                for match in matches:
                    if len(match) <= 20:  # Reasonable city name length
                        if debug:
                            print(f"Selected city: {match}")
                        return match
        
        if debug:
            print("No city found with current patterns")
        
        return None
        
    except Exception as e:
        if debug:
            print(f"Error extracting city: {e}")
        return None


def test_station_pages():
    """Test city extraction on various station pages."""
    
    # Test stations - mix of problematic and working ones
    test_stations = [
        {
            "name": "一ノ割駅",
            "url": "https://transit.yahoo.co.jp/station/21974",
            "expected_city": None  # We'll see what we get
        },
        {
            "name": "東結城駅", 
            "url": "https://transit.yahoo.co.jp/station/21690",
            "expected_city": None
        }
    ]
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    })
    
    for station in test_stations:
        print(f"\n{'='*60}")
        print(f"TESTING: {station['name']}")
        print(f"URL: {station['url']}")
        print(f"{'='*60}")
        
        try:
            response = session.get(station['url'], timeout=10)
            if response.status_code == 200:
                extracted_city = extract_city_from_html(response.text, debug=True)
                print(f"\n>>> RESULT: {extracted_city}")
                
                if station['expected_city']:
                    if extracted_city == station['expected_city']:
                        print("✅ PASS: Matches expected city")
                    else:
                        print(f"❌ FAIL: Expected '{station['expected_city']}', got '{extracted_city}'")
                else:
                    print("ℹ️  INFO: No expected city to compare against")
            else:
                print(f"❌ Failed to fetch page: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error testing {station['name']}: {e}")
        
        # Be respectful to the server
        time.sleep(2)


def test_csv_problematic_data():
    """Test the problematic data we found in the CSV."""
    print(f"\n{'='*60}")
    print("TESTING PROBLEMATIC CSV DATA")
    print(f"{'='*60}")
    
    # Sample of the HTML content found in the CSV city column
    problematic_html = """渋谷駅の駅周辺情報 - Yahoo!路線情報路線情報（乗換案内・時刻表・路線図）道路交通情報地図路線情報乗換案内運行情報駅情報時刻表情報対応履歴路線図(Yahoo!マップ)マイページ - 各種設定・確認現在位置：路線情報トップ > 駅情報 > 渋谷駅しぶや渋谷駅を登録駅情報時刻表出口案内周辺情報：グルメホテル駐車場コンビニ郵便局銀行病院レンタカー"""
    
    print("Testing extraction from problematic CSV data...")
    extracted_city = extract_city_from_html(f"<html><body>{problematic_html}</body></html>", debug=True)
    print(f"\n>>> RESULT FROM PROBLEMATIC DATA: {extracted_city}")
    
    # What we would expect for Shibuya
    expected_city = "渋谷区"
    if extracted_city:
        if "渋谷" in extracted_city:
            print("✅ Contains 'Shibuya' - partially correct")
        else:
            print("❌ Does not contain 'Shibuya'")
    else:
        print("❌ No city extracted")


def analyze_current_issue():
    """Analyze why the current approach is storing full HTML instead of city names."""
    print(f"\n{'='*60}")
    print("ANALYZING CURRENT ISSUE")
    print(f"{'='*60}")
    
    print("""
IDENTIFIED ISSUES:

1. **HTML Storage Instead of City Names**:
   - The CSV shows full HTML content in the city column
   - This suggests the extraction is failing and falling back to storing raw HTML

2. **Regex Pattern Issues**:
   - Current patterns might be too restrictive or not matching the actual HTML structure
   - Need to verify if the patterns work with real Yahoo Transit HTML

3. **Data Flow Problem**:
   - The _get_station_details method might be returning HTML instead of parsed city name
   - Need to check if soup.get_text() is properly converting HTML to text

4. **Missing Error Handling**:
   - If city extraction fails, the code might be storing the entire HTML response

RECOMMENDATIONS:

1. **Improve Pattern Matching**:
   - Test patterns against real HTML content
   - Add more specific patterns for different prefecture formats
   - Add fallback patterns for edge cases

2. **Better Data Validation**:
   - Validate extracted city names (length, content)
   - Reject HTML-like content with tags or excessive length
   - Add logging for failed extractions

3. **Enhanced Error Handling**:
   - Return None or empty string instead of HTML on failure
   - Log extraction failures for debugging
   - Add retry logic for network issues

4. **Test Coverage**:
   - Test against various station types (ward, city, town, village)
   - Test different prefectures and HTML structures
   - Validate all columns can be properly extracted
    """)


if __name__ == "__main__":
    print("Yahoo Transit City Extraction Test Script")
    print("=" * 60)
    
    # Test live station pages
    test_station_pages()
    
    # Test problematic CSV data
    test_csv_problematic_data()
    
    # Analyze the issues
    analyze_current_issue()
    
    print(f"\n{'='*60}")
    print("TEST COMPLETE")
    print(f"{'='*60}")
