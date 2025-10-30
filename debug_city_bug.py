#!/usr/bin/env python3
"""
Debug script to understand exactly where the HTML content is coming from in the city field.
"""

import re
import requests
from bs4 import BeautifulSoup

class StationDetails:
    """Details for a station."""
    city: str | None = None
    station_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    aliases: list[str] | None = None
    line_name_kana: str | None = None
    line_color: str | None = None
    all_lines: list[str] | None = None

def debug_get_station_details(station_href: str):
    """Debug version of _get_station_details to trace the issue."""
    details = StationDetails()
    
    try:
        # Make full URL
        if station_href.startswith("/"):
            station_url = f"https://transit.yahoo.co.jp{station_href}"
        else:
            station_url = station_href
            
        print(f"Fetching: {station_url}")
        
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        
        response = session.get(station_url, timeout=10)
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            page_text = soup.get_text()
            
            print(f"Page text length: {len(page_text)}")
            print(f"First 200 chars of page_text: {repr(page_text[:200])}")
            print(f"Last 200 chars of page_text: {repr(page_text[-200:])}")
            
            # Look for ward/city mentions in the page
            import re
            ward_mentions = re.findall(r"[^\s、。]*[区市町村郡]", page_text)
            print(f"All ward/city mentions found: {ward_mentions[:10]}")  # First 10
            
            # Extract station name with prefecture disambiguation
            title_elem = soup.find("title")
            if title_elem:
                title_text = title_elem.get_text()
                print(f"Title: {repr(title_text)}")
                
                # Extract station name from title like "青山(岩手県)駅の駅周辺情報"
                station_match = re.search(r"(.+?)駅の", title_text)
                if station_match:
                    station_name_with_pref = station_match.group(1)
                    print(f"Station name with pref: {repr(station_name_with_pref)}")
                    if "(" in station_name_with_pref:
                        if details.aliases is None:
                            details.aliases = []
                        details.aliases.append(station_name_with_pref)
                        print(f"Added alias: {repr(station_name_with_pref)}")
            
        # Debug the city extraction patterns - FIXED VERSION
        city_patterns = [
            # Tokyo wards (specific list)
            r"(千代田区|中央区|港区|新宿区|文京区|台東区|墨田区|江東区|品川区|目黒区|大田区|世田谷区|渋谷区|中野区|杉並区|豊島区|北区|荒川区|板橋区|練馬区|足立区|葛飾区|江戸川区)",
            # Cities - limit length to avoid matching entire page
            r"([^\s、。]{1,10}市)",
            # Towns - limit length to avoid matching entire page  
            r"([^\s、。]{1,10}町)",
            # Villages - limit length to avoid matching entire page
            r"([^\s、。]{1,10}村)",
            # Counties - limit length to avoid matching entire page
            r"([^\s、。]{1,10}郡)",
        ]
        
        print("\n=== CITY EXTRACTION DEBUG ===")
        for i, pattern in enumerate(city_patterns):
            matches = re.findall(pattern, page_text)
            if matches:
                print(f"Pattern {i+1} matched: {matches[:5]}")
                # Additional validation to ensure we got a reasonable city name
                city_candidate = matches[0]
                print(f"City candidate: {repr(city_candidate)}")
                # Reject if it's too long or contains obvious HTML artifacts
                if (len(city_candidate) <= 20 and 
                    not any(bad in city_candidate for bad in ["駅の", "情報", "路線", "時刻表", "乗換"])):
                    details.city = city_candidate
                    print(f"✅ ACCEPTED: Set details.city to: {repr(details.city)}")
                    break
                else:
                    print(f"❌ REJECTED: City candidate failed validation")
                    continue
            else:
                print(f"Pattern {i+1} no matches: {pattern}")
                    
            if details.city is None:
                print("No city found with any pattern")
                
    except Exception as e:
        print(f"Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        
    print(f"\nFinal details.city value: {repr(details.city)}")
    return details

if __name__ == "__main__":
    # Test with multiple stations
    test_urls = [
        "https://transit.yahoo.co.jp/station/22828",  # Tokyo Station
        "https://transit.yahoo.co.jp/station/22631",  # Shibuya Station - should be 渋谷区
        "https://transit.yahoo.co.jp/station/22828",  # Tokyo Station - should be 千代田区
    ]
    
    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"TESTING URL: {url}")
        print(f"{'='*60}")
        
        details = debug_get_station_details(url)
        print(f"Result: {details.city}")