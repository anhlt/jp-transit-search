from bs4 import BeautifulSoup
import re

# Read both HTML files
files = [
    'tests/fixtures/search_results/search_横浜渋谷_fastest.html',
    'tests/fixtures/search_results/search_大船羽田空港.html'
]

for file_path in files:
    print(f"\n=== {file_path.split('/')[-1]} ===")
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find first route detail
    route_detail = soup.find("div", class_="routeDetail")
    if route_detail:
        access_divs = route_detail.find_all("div", class_="access")
        
        for i, access in enumerate(access_divs):
            print(f"\nAccess {i}:")
            
            # Look for stop info
            stop_info = access.find("li", class_="stop")
            if stop_info:
                stop_text = stop_info.get_text().strip()
                print(f"  Stop info text: {stop_text}")
                
                # Look for hidden list of intermediate stations
                stop_list = stop_info.find("ul", style="display:none")
                if stop_list:
                    stations = stop_list.find_all("li")
                    print(f"  Intermediate stations: {len(stations)}")
                    for j, station in enumerate(stations):
                        dt = station.find("dt")
                        dd = station.find("dd")
                        time = dt.get_text().strip() if dt else "No time"
                        name_elem = dd.find("span", class_="icnStopPoint") if dd else None
                        if name_elem and name_elem.next_sibling:
                            station_name = name_elem.next_sibling.strip()
                        else:
                            station_name = dd.get_text().strip() if dd else "Unknown"
                        print(f"    Station {j}: {time} - {station_name}")
                else:
                    print("  No detailed station list found")
            else:
                print("  No stop info found")

