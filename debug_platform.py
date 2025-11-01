#!/usr/bin/env python3
"""Debug platform display issues."""

from pathlib import Path
from src.jp_transit_search.core.scraper import YahooTransitScraper
from src.jp_transit_search.core.models import RouteSearchRequest
from src.jp_transit_search.cli.formatters import format_route_table, format_route_detailed

def main():
    # Load test HTML file
    test_file = Path("tests/fixtures/search_results/search_横浜渋谷_fastest.html")
    with open(test_file, encoding="utf-8") as f:
        html_content = f.read()
    
    # Create scraper and parse
    scraper = YahooTransitScraper()
    request = RouteSearchRequest(from_station="横浜", to_station="渋谷")
    
    try:
        routes = scraper._parse_route_page(html_content, request)
        print(f"Found {len(routes)} routes")
        
        for i, route in enumerate(routes, 1):
            print(f"\n=== Route {i} ===")
            print(f"From: {route.from_station}")
            print(f"To: {route.to_station}")
            print(f"Duration: {route.duration}")
            print(f"Cost: {route.cost}")
            print(f"Transfers: {route.transfer_count}")
            
            for j, transfer in enumerate(route.transfers, 1):
                print(f"\n  Transfer {j}:")
                print(f"    From: {transfer.from_station}")
                print(f"    To: {transfer.to_station}")
                print(f"    Line: {transfer.line_name}")
                print(f"    Duration: {transfer.duration_minutes} min")
                print(f"    Cost: {transfer.cost_yen} yen")
                print(f"    Departure time: {transfer.departure_time}")
                print(f"    Arrival time: {transfer.arrival_time}")
                print(f"    Departure platform: {transfer.departure_platform}")
                print(f"    Arrival platform: {transfer.arrival_platform}")
        
        # Test formatter output
        print("\n" + "="*50)
        print("FORMATTED TABLE OUTPUT:")
        print("="*50)
        format_route_table(routes, verbose=True)
        
        print("\n" + "="*50)
        print("FORMATTED DETAILED OUTPUT:")
        print("="*50)
        format_route_detailed(routes)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()