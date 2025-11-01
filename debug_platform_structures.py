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
            
            # Look for platform info in different structures
            platform_span = access.find("span", class_="platform")
            platform_li = access.find("li", class_="platform")
            
            if platform_span:
                print(f"  Found platform SPAN: {platform_span.get_text().strip()}")
            elif platform_li:
                print(f"  Found platform LI: {platform_li.get_text().strip()}")
            else:
                print("  No platform info found")

