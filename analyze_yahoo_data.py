#!/usr/bin/env python3
"""
Comprehensive analysis of what data is available in Yahoo Transit pages.
"""

import re
import requests
from bs4 import BeautifulSoup
import json

def analyze_yahoo_page(station_url: str, station_name: str):
    """Analyze a Yahoo Transit page to see what data is extractable."""
    print(f"\n{'='*80}")
    print(f"ANALYZING: {station_name} - {station_url}")
    print(f"{'='*80}")
    
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        
        response = session.get(station_url, timeout=10)
        if response.status_code != 200:
            print(f"❌ Failed to fetch: {response.status_code}")
            return
            
        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text()
        
        print(f"✅ Fetched successfully")
        print(f"Page length: {len(response.text)} chars, Text length: {len(page_text)} chars")
        
        # 1. Title analysis
        title_elem = soup.find("title")
        if title_elem:
            title = title_elem.get_text()
            print(f"Title: {repr(title)}")
            
        # 2. Meta tags analysis
        print("\n--- META TAGS ---")
        meta_tags = soup.find_all("meta")
        for meta in meta_tags:
            name = meta.get("name") or meta.get("property")
            content = meta.get("content")
            if name and content and any(keyword in name.lower() for keyword in ["description", "keyword", "location", "geo"]):
                print(f"{name}: {content[:100]}...")
                
        # 3. URL analysis - check for prefecture codes
        print(f"\n--- URL ANALYSIS ---")
        print(f"Full URL: {station_url}")
        
        # Extract station ID from URL
        station_id_match = re.search(r"/station/(\d+)", station_url)
        if station_id_match:
            station_id = station_id_match.group(1)
            print(f"Station ID: {station_id}")
            
        # 4. Prefecture analysis from breadcrumbs/navigation
        print(f"\n--- PREFECTURE/LOCATION ANALYSIS ---")
        
        # Look for breadcrumb elements
        breadcrumbs = soup.find_all(["nav", "ol", "ul"], {"class": re.compile(r"breadcrumb|nav", re.I)})
        for breadcrumb in breadcrumbs:
            text = breadcrumb.get_text(strip=True)
            if text:
                print(f"Breadcrumb: {text}")
                
        # Look for prefecture mentions in structured data
        prefecture_patterns = [
            r"(北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄県)",
        ]
        
        for pattern in prefecture_patterns:
            matches = re.findall(pattern, page_text)
            if matches:
                print(f"Prefecture mentions: {set(matches)}")
                
        # 5. Station code analysis
        print(f"\n--- STATION CODE ANALYSIS ---")
        code_patterns = [
            r"\b[A-Z]{1,4}-?[A-Z]?\d{1,3}\b",  # Various station code formats
            r"駅番号[：:]([A-Z0-9-]+)",
            r"Station Code[：:]([A-Z0-9-]+)",
        ]
        
        for i, pattern in enumerate(code_patterns):
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            if matches:
                print(f"Pattern {i+1} station codes: {matches[:10]}")
                
        # 6. Coordinate analysis
        print(f"\n--- COORDINATE ANALYSIS ---")
        coord_patterns = [
            r"(\d{2,3}\.\d+),(\d{2,3}\.\d+)",  # lat,lng
            r"lat[^0-9]*(\d{2,3}\.\d+)",
            r"lng[^0-9]*(\d{2,3}\.\d+)",
            r"latitude[^0-9]*(\d{2,3}\.\d+)",
            r"longitude[^0-9]*(\d{2,3}\.\d+)",
        ]
        
        for i, pattern in enumerate(coord_patterns):
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            if matches:
                print(f"Pattern {i+1} coordinates: {matches[:5]}")
                
        # 7. Line information analysis
        print(f"\n--- LINE INFORMATION ---")
        # Look for line names and colors
        line_patterns = [
            r"(JR[^線]*線)",
            r"(東京メトロ[^線]*線)",
            r"(都営[^線]*線)",
            r"(東急[^線]*線)",
            r"(京王[^線]*線)",
            r"(小田急[^線]*線)",
            r"color[：:]['\"#]([0-9a-fA-F]{6}|[0-9a-fA-F]{3})['\"]",
        ]
        
        for i, pattern in enumerate(line_patterns):
            matches = re.findall(pattern, page_text)
            if matches:
                print(f"Pattern {i+1} lines: {matches[:5]}")
                
        # 8. Structured data analysis (JSON-LD, microdata)
        print(f"\n--- STRUCTURED DATA ---")
        json_scripts = soup.find_all("script", {"type": "application/ld+json"})
        for i, script in enumerate(json_scripts):
            try:
                data = json.loads(script.get_text())
                print(f"JSON-LD {i+1}: {json.dumps(data, indent=2, ensure_ascii=False)[:200]}...")
            except:
                pass
                
        # 9. Look for hidden form data or API endpoints
        print(f"\n--- HIDDEN DATA/APIS ---")
        forms = soup.find_all("form")
        for form in forms:
            action = form.get("action")
            if action:
                print(f"Form action: {action}")
                
        # Look for data attributes
        try:
            elements_with_data = soup.find_all(True)
            data_attrs_found = 0
            for elem in elements_with_data:
                if hasattr(elem, 'attrs') and elem.attrs:
                    data_attrs = {k: v for k, v in elem.attrs.items() if k.startswith('data-')}
                    if data_attrs:
                        print(f"Data attributes: {data_attrs}")
                        data_attrs_found += 1
                        if data_attrs_found >= 5:  # Limit to first 5
                            break
        except Exception as e:
            print(f"Error getting data attributes: {e}")
                
        print(f"\n--- END ANALYSIS ---\n")
        
    except Exception as e:
        print(f"❌ Error analyzing {station_name}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Test with different types of stations
    test_stations = [
        ("https://transit.yahoo.co.jp/station/22828", "Tokyo Station (Major hub)"),
        ("https://transit.yahoo.co.jp/station/22631", "Kitasenzoku Station (Local)"),  
        ("https://transit.yahoo.co.jp/station/22522", "Shibuya Station (Ward center)"),  # Correct Shibuya ID
        ("https://transit.yahoo.co.jp/station/22741", "Shinjuku Station (Major hub)"),
    ]
    
    for url, name in test_stations:
        analyze_yahoo_page(url, name)