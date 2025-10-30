#!/usr/bin/env python3
"""
HTML Download Script for Yahoo Transit Parser Testing

This script downloads sample HTML pages from Yahoo Transit to test
the parsing functionality of station data extraction.

Usage:
    python download_html_samples.py
    python download_html_samples.py --prefecture 東京都
    python download_html_samples.py --limit 5
"""

import argparse
import csv
import time
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from rich.console import Console
from rich.progress import Progress, TaskID

from src.jp_transit_search.core.models import Station
from src.jp_transit_search.crawler.station_crawler import StationCrawler


class HTMLDownloader:
    """Downloads HTML samples from Yahoo Transit for parser testing."""

    def __init__(self, output_dir: Path = Path("html_samples")):
        """Initialize HTML downloader.
        
        Args:
            output_dir: Directory to save HTML samples
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        self.console = Console()
        
        # Create subdirectories for different types of pages
        (self.output_dir / "station_pages").mkdir(exist_ok=True)
        (self.output_dir / "prefecture_pages").mkdir(exist_ok=True)
        (self.output_dir / "search_results").mkdir(exist_ok=True)

    def download_station_page(self, station: Station, client: httpx.Client) -> Optional[Path]:
        """Download HTML for a specific station page.
        
        Args:
            station: Station object with station_id
            client: HTTP client for requests
            
        Returns:
            Path to downloaded HTML file, or None if failed
        """
        if not station.station_id:
            return None
            
        # Construct Yahoo Transit station URL
        station_url = f"https://transit.yahoo.co.jp/station/{station.station_id}/"
        
        try:
            response = client.get(station_url, timeout=10.0)
            response.raise_for_status()
            
            # Create safe filename
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in station.name)
            filename = f"{safe_name}_{station.prefecture_id}_{station.station_id}.html"
            file_path = self.output_dir / "station_pages" / filename
            
            # Save HTML content
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(response.text)
                
            return file_path
            
        except Exception as e:
            self.console.print(f"[red]Failed to download {station.name}: {e}[/red]")
            return None

    def download_prefecture_page(self, prefecture: str, client: httpx.Client) -> Optional[Path]:
        """Download HTML for a prefecture's station list.
        
        Args:
            prefecture: Prefecture name (e.g., "東京都")
            client: HTTP client for requests
            
        Returns:
            Path to downloaded HTML file, or None if failed
        """
        # Map prefecture names to Yahoo Transit URLs (these are examples)
        prefecture_urls = {
            "東京都": "https://transit.yahoo.co.jp/station/pref/13/",
            "神奈川県": "https://transit.yahoo.co.jp/station/pref/14/",
            "大阪府": "https://transit.yahoo.co.jp/station/pref/27/",
            "愛知県": "https://transit.yahoo.co.jp/station/pref/23/",
            "北海道": "https://transit.yahoo.co.jp/station/pref/01/",
        }
        
        if prefecture not in prefecture_urls:
            self.console.print(f"[yellow]No URL mapping for prefecture: {prefecture}[/yellow]")
            return None
            
        try:
            response = client.get(prefecture_urls[prefecture], timeout=10.0)
            response.raise_for_status()
            
            # Create safe filename
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in prefecture)
            filename = f"prefecture_{safe_name}.html"
            file_path = self.output_dir / "prefecture_pages" / filename
            
            # Save HTML content
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(response.text)
                
            return file_path
            
        except Exception as e:
            self.console.print(f"[red]Failed to download prefecture {prefecture}: {e}[/red]")
            return None

    def download_search_results(self, query: str, client: httpx.Client) -> Optional[Path]:
        """Download HTML for search results page.
        
        Args:
            query: Search query (station name)
            client: HTTP client for requests
            
        Returns:
            Path to downloaded HTML file, or None if failed
        """
        search_url = "https://transit.yahoo.co.jp/search/result"
        params = {"q": query}
        
        try:
            response = client.get(search_url, params=params, timeout=10.0)
            response.raise_for_status()
            
            # Create safe filename
            safe_query = "".join(c if c.isalnum() or c in "-_" else "_" for c in query)
            filename = f"search_{safe_query}.html"
            file_path = self.output_dir / "search_results" / filename
            
            # Save HTML content
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(response.text)
                
            return file_path
            
        except Exception as e:
            self.console.print(f"[red]Failed to download search for '{query}': {e}[/red]")
            return None

    def download_samples(
        self,
        stations_csv_path: Path,
        prefecture: Optional[str] = None,
        limit: int = 10,
        download_delay: float = 1.0
    ) -> None:
        """Download HTML samples for parser testing.
        
        Args:
            stations_csv_path: Path to stations CSV file
            prefecture: Filter by specific prefecture
            limit: Maximum number of stations to download
            download_delay: Delay between requests in seconds
        """
        # Load stations from CSV
        try:
            crawler = StationCrawler()
            stations = crawler.load_from_csv(stations_csv_path)
        except Exception as e:
            self.console.print(f"[red]Failed to load stations CSV: {e}[/red]")
            return
            
        # Filter by prefecture if specified
        if prefecture:
            stations = [s for s in stations if s.prefecture == prefecture]
            
        # Limit number of stations
        stations = stations[:limit]
        
        if not stations:
            self.console.print("[yellow]No stations found to download[/yellow]")
            return
            
        # Download samples with progress bar
        with httpx.Client(
            headers={"User-Agent": "Mozilla/5.0 (compatible; Transit Parser Test)"},
            follow_redirects=True
        ) as client:
            
            with Progress() as progress:
                task = progress.add_task("Downloading HTML samples...", total=len(stations))
                
                downloaded_count = 0
                failed_count = 0
                
                for station in stations:
                    # Download station page
                    result = self.download_station_page(station, client)
                    if result:
                        downloaded_count += 1
                        self.console.print(f"[green]Downloaded:[/green] {station.name} -> {result.name}")
                    else:
                        failed_count += 1
                        
                    progress.advance(task)
                    
                    # Respectful delay between requests
                    if download_delay > 0:
                        time.sleep(download_delay)
                        
                # Download prefecture pages for unique prefectures
                unique_prefectures = list(set(s.prefecture for s in stations if s.prefecture))
                for pref in unique_prefectures:
                    result = self.download_prefecture_page(pref, client)
                    if result:
                        self.console.print(f"[green]Downloaded prefecture:[/green] {pref} -> {result.name}")
                        
                    if download_delay > 0:
                        time.sleep(download_delay)
                
                # Download some search result samples
                search_queries = [s.name for s in stations[:3]]  # First 3 station names
                for query in search_queries:
                    result = self.download_search_results(query, client)
                    if result:
                        self.console.print(f"[green]Downloaded search:[/green] {query} -> {result.name}")
                        
                    if download_delay > 0:
                        time.sleep(download_delay)
        
        # Summary
        self.console.print(f"\n[bold]Download Summary:[/bold]")
        self.console.print(f"✓ Downloaded: {downloaded_count} station pages")
        self.console.print(f"✗ Failed: {failed_count} station pages")
        self.console.print(f"✓ Prefecture pages: {len(unique_prefectures)}")
        self.console.print(f"✓ Search samples: {len(search_queries)}")
        self.console.print(f"📁 Output directory: {self.output_dir}")

    def create_test_manifest(self) -> None:
        """Create a manifest file listing all downloaded HTML samples."""
        manifest_path = self.output_dir / "test_manifest.csv"
        
        html_files = []
        for subdir in self.output_dir.iterdir():
            if subdir.is_dir():
                for html_file in subdir.glob("*.html"):
                    html_files.append({
                        "category": subdir.name,
                        "filename": html_file.name,
                        "relative_path": html_file.relative_to(self.output_dir),
                        "size_bytes": html_file.stat().st_size,
                        "created": html_file.stat().st_mtime
                    })
        
        # Write manifest CSV
        with open(manifest_path, "w", newline="", encoding="utf-8") as f:
            if html_files:
                writer = csv.DictWriter(f, fieldnames=html_files[0].keys())
                writer.writeheader()
                writer.writerows(html_files)
        
        self.console.print(f"[green]Test manifest created:[/green] {manifest_path}")
        self.console.print(f"Total HTML files: {len(html_files)}")


def main():
    """Main entry point for HTML download script."""
    parser = argparse.ArgumentParser(
        description="Download HTML samples from Yahoo Transit for parser testing"
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/stations.csv"),
        help="Path to stations CSV file (default: data/stations.csv)"
    )
    parser.add_argument(
        "--prefecture",
        type=str,
        help="Filter by specific prefecture (e.g., '東京都')"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of stations to download (default: 10)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("html_samples"),
        help="Output directory for HTML samples (default: html_samples)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Only create test manifest for existing files"
    )
    
    args = parser.parse_args()
    
    # Initialize downloader
    downloader = HTMLDownloader(output_dir=args.output)
    
    if args.manifest_only:
        downloader.create_test_manifest()
        return
    
    # Check if stations CSV exists
    if not args.data.exists():
        console = Console()
        console.print(f"[red]Stations CSV not found:[/red] {args.data}")
        console.print("Run 'jp-transit stations crawl' first to create the database")
        return
    
    # Download HTML samples
    downloader.download_samples(
        stations_csv_path=args.data,
        prefecture=args.prefecture,
        limit=args.limit,
        download_delay=args.delay
    )
    
    # Create test manifest
    downloader.create_test_manifest()
    
    console = Console()
    console.print("\n[bold green]HTML samples ready for parser testing![/bold green]")
    console.print(f"Use these files to test:")
    console.print(f"  • Station parsing: {args.output}/station_pages/")
    console.print(f"  • Prefecture parsing: {args.output}/prefecture_pages/")
    console.print(f"  • Search parsing: {args.output}/search_results/")


if __name__ == "__main__":
    main()