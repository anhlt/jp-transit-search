from bs4 import BeautifulSoup
import re

# Read the HTML file
with open('/home/anh.le/workspace/transist_mcp/jp-transit-search/tests/fixtures/search_results/search_大船羽田空港.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')

# Find the route detail sections
route_details = soup.find_all("div", class_="routeDetail")
print(f"=== FOUND {len(route_details)} ROUTE DETAILS ===")

for route_idx, route_detail in enumerate(route_details):
    print(f"\n=== ROUTE DETAIL {route_idx} ===")
    
    # Find all stations
    stations = route_detail.find_all("div", class_="station")
    print(f"Stations found: {len(stations)}")
    for i, station in enumerate(stations):
        station_name = station.find("dt").get_text().strip() if station.find("dt") else "Unknown"
        times = station.find("ul", class_="time")
        time_list = []
        if times:
            time_elements = times.find_all("li")
            time_list = [t.get_text().strip() for t in time_elements]
        
        # Check for riding position info
        riding_pos = station.find("p", class_="ridingPos")
        riding_info = riding_pos.get_text().strip() if riding_pos else "No riding info"
        
        print(f"  Station {i}: {station_name}, Times: {time_list}, Riding: {riding_info}")
    
    # Find all fare sections
    fare_sections = route_detail.find_all("div", class_="fareSection")
    print(f"\nFare sections found: {len(fare_sections)}")
    
    for i, section in enumerate(fare_sections):
        print(f"\n--- Fare Section {i} ---")
        
        # Find all access divs within this fare section
        access_divs = section.find_all("div", class_="access")
        print(f"Access divs in this fare section: {len(access_divs)}")
        
        for j, access in enumerate(access_divs):
            print(f"\n  Access {j}:")
            transport = access.find("li", class_="transport")
            if transport:
                line_div = transport.find("div")
                if line_div:
                    line_text = line_div.get_text().strip()
                    print(f"    Full line text: {line_text}")
                    
                    # Look for line name specifically
                    destination_span = line_div.find("span", class_="destination")
                    if destination_span:
                        destination_text = destination_span.get_text().strip()
                        print(f"    Destination: {destination_text}")
                    
                    # Look for platform info
                    platform_span = transport.find("span", class_="platform")
                    if platform_span:
                        platform_text = platform_span.get_text().strip()
                        print(f"    Platform: {platform_text}")
            
            # Look for stop info
            stop_info = access.find("li", class_="stop")
            if stop_info:
                stop_text = stop_info.get_text().strip()
                print(f"    Stop info: {stop_text}")
        
        # Check for fare info
        fare_element = section.find("p", class_="fare")
        if fare_element:
            fare_text = fare_element.get_text().strip()
            print(f"  Fare: {fare_text}")

