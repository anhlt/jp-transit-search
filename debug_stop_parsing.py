#!/usr/bin/env python3
"""Debug script to examine stop info parsing in test fixtures."""

from bs4 import BeautifulSoup
import re

def debug_stop_parsing(file_path):
    """Debug the stop info parsing for a specific test file."""
    print(f"\n=== Debugging {file_path} ===")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all stop elements
    stop_elements = soup.find_all("li", class_="stop")
    print(f"Found {len(stop_elements)} stop elements")
    
    for i, stop_element in enumerate(stop_elements):
        print(f"\n--- Stop Element {i+1} ---")
        print(f"Raw HTML: {str(stop_element)[:200]}...")
        
        # Get text using current method
        stop_text = stop_element.get_text().strip()
        print(f"Text content: {stop_text}")
        
        # TEST NEW PARSING METHOD
        intermediate_stations = []
        stop_ul = stop_element.find("ul")
        if stop_ul:
            print("  Using structured HTML parsing...")
            station_items = stop_ul.find_all("li")
            for item in station_items:
                dt_time = item.find("dt")
                dd_station = item.find("dd") 
                if dt_time and dd_station:
                    time_text = dt_time.get_text().strip()
                    station_text = dd_station.get_text().strip()
                    # Clean station name by removing extra whitespace and icon spans
                    clean_station_name = re.sub(r"\s+", "", station_text.strip())
                    if clean_station_name and time_text:
                        intermediate_stations.append((time_text, clean_station_name))
        else:
            print("  Using regex fallback parsing...")
            station_pattern = r"(\d{2}:\d{2})([^0-9]+?)(?=\d{2}:\d{2}|$)"
            station_matches = re.findall(station_pattern, stop_text)
            
            for time_str, station_name in station_matches:
                clean_station_name = re.sub(r"\s+", "", station_name.strip())
                if clean_station_name:
                    intermediate_stations.append((time_str, clean_station_name))
        
        print(f"  Parsed stations: {intermediate_stations}")
        
        # Also try old regex approach for comparison
        station_pattern = r"(\d{2}:\d{2})([^0-9]+?)(?=\d{2}:\d{2}|$)"
        station_matches = re.findall(station_pattern, stop_text)
        regex_stations = [(time, re.sub(r"\s+", "", name.strip())) for time, name in station_matches if re.sub(r"\s+", "", name.strip())]
        print(f"  Regex comparison: {regex_stations}")
        
        # Check if results match
        if intermediate_stations == regex_stations:
            print("  ✅ Methods produce identical results")
        else:
            print("  ⚠️  Methods produce different results!")

if __name__ == "__main__":
    # Test with various fixtures
    test_files = [
        "tests/fixtures/search_results/search_横浜渋谷_fastest.html",
        "tests/fixtures/search_results/search_大船渋谷.html",
        "tests/fixtures/search_results/search_横浜豊洲.html",
        "tests/fixtures/search_results/search_大船羽田空港.html"
    ]
    
    for file_path in test_files:
        try:
            debug_stop_parsing(file_path)
        except FileNotFoundError:
            print(f"File not found: {file_path}")
        except Exception as e:
            print(f"Error processing {file_path}: {e}")