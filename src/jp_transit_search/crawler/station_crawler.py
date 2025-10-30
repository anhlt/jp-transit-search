"""Station data crawler for building station database."""

import csv
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.exceptions import NetworkError, ScrapingError
from ..core.models import Station

logger = logging.getLogger(__name__)


class CrawlingProgress:
    """Track crawling progress and statistics."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.stations_found = 0
        self.duplicates_filtered = 0
        self.prefectures_completed = 0
        self.lines_completed = 0
        self.current_prefecture = ""
        self.current_line = ""
        self.errors = 0
        self.retries = 0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert progress to dictionary for serialization."""
        return {
            'start_time': self.start_time.isoformat(),
            'stations_found': self.stations_found,
            'duplicates_filtered': self.duplicates_filtered,
            'prefectures_completed': self.prefectures_completed,
            'lines_completed': self.lines_completed,
            'current_prefecture': self.current_prefecture,
            'current_line': self.current_line,
            'errors': self.errors,
            'retries': self.retries
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CrawlingProgress':
        """Create progress from dictionary."""
        progress = cls()
        progress.start_time = datetime.fromisoformat(data.get('start_time', datetime.now().isoformat()))
        progress.stations_found = data.get('stations_found', 0)
        progress.duplicates_filtered = data.get('duplicates_filtered', 0)
        progress.prefectures_completed = data.get('prefectures_completed', 0)
        progress.lines_completed = data.get('lines_completed', 0)
        progress.current_prefecture = data.get('current_prefecture', '')
        progress.current_line = data.get('current_line', '')
        progress.errors = data.get('errors', 0)
        progress.retries = data.get('retries', 0)
        return progress


class StationCrawler:
    """Crawler for Japanese train station data."""
    
    def __init__(self, timeout: int = 30, progress_callback: Optional[Callable] = None):
        """Initialize the station crawler.
        
        Args:
            timeout: Request timeout in seconds  
            progress_callback: Optional callback for progress updates
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.stations: List[Station] = []
        self.existing_stations: Set[tuple] = set()  # For deduplication
        self.progress = CrawlingProgress()
        self.progress_callback = progress_callback
        self.state_file: Optional[Path] = None
        self.checkpoint_interval = 50  # Save progress every 50 stations
        
    def crawl_all_stations(self, resume_from_csv: Optional[Path] = None,
                          state_file: Optional[Path] = None) -> List[Station]:
        """Crawl station data from multiple sources with resume capability.
        
        Args:
            resume_from_csv: Path to existing CSV file to resume from
            state_file: Path to state file for tracking progress
        
        Returns:
            List of Station objects
        """
        logger.info("Starting resumable station data crawl")
        self.state_file = state_file
        
        # Load existing stations for deduplication
        if resume_from_csv and resume_from_csv.exists():
            self._load_existing_stations(resume_from_csv)
            logger.info(f"Loaded {len(self.existing_stations)} existing stations for deduplication")
        
        # Load previous progress state
        crawl_state = self._load_crawl_state()
        
        self.stations = []
        self._update_progress("Starting crawl...")
        
        try:
            # Crawl Yahoo Transit stations with resume capability
            self._crawl_yahoo_transit_stations_resumable(crawl_state)
            
            # Remove duplicates and return
            unique_stations = self._deduplicate_stations()
            
            # Update final progress
            self.progress.stations_found = len(unique_stations)
            self._update_progress("Crawling completed!")
            
            # Clean up state file on successful completion
            if self.state_file and self.state_file.exists():
                self.state_file.unlink()
                
            logger.info(f"Crawled {len(unique_stations)} unique stations")
            return unique_stations
            
        except Exception as e:
            # Save current state before re-raising
            self._save_crawl_state(crawl_state)
            logger.error(f"Crawling interrupted: {e}")
            raise
    
    def save_to_csv(self, stations: List[Station], file_path: Path) -> None:
        """Save stations to CSV file.
        
        Args:
            stations: List of stations to save
            file_path: Path to CSV file
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'name', 'prefecture', 'city', 'railway_company', 
                'line_name', 'station_code', 'latitude', 'longitude', 'aliases',
                'line_name_kana', 'line_color', 'line_type', 'company_code', 'all_lines'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for station in stations:
                writer.writerow({
                    'name': station.name,
                    'prefecture': station.prefecture or '',
                    'city': station.city or '',
                    'railway_company': station.railway_company or '',
                    'line_name': station.line_name or '',
                    'station_code': station.station_code or '',
                    'latitude': station.latitude or '',
                    'longitude': station.longitude or '',
                    'aliases': '|'.join(station.aliases) if station.aliases else '',
                    'line_name_kana': station.line_name_kana or '',
                    'line_color': station.line_color or '',
                    'line_type': station.line_type or '',
                    'company_code': station.company_code or '',
                    'all_lines': '|'.join(station.all_lines) if station.all_lines else ''
                })
        
        logger.info(f"Saved {len(stations)} stations to {file_path}")
    
    def append_to_csv(self, stations: List[Station], file_path: Path) -> None:
        """Append stations to existing CSV file.
        
        Args:
            stations: List of stations to append
            file_path: Path to CSV file
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if file exists to determine if we need headers
        write_headers = not file_path.exists()
        
        with open(file_path, 'a', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'name', 'prefecture', 'city', 'railway_company', 
                'line_name', 'station_code', 'latitude', 'longitude', 'aliases',
                'line_name_kana', 'line_color', 'line_type', 'company_code', 'all_lines'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            if write_headers:
                writer.writeheader()
                
            for station in stations:
                writer.writerow({
                    'name': station.name,
                    'prefecture': station.prefecture or '',
                    'city': station.city or '',
                    'railway_company': station.railway_company or '',
                    'line_name': station.line_name or '',
                    'station_code': station.station_code or '',
                    'latitude': station.latitude or '',
                    'longitude': station.longitude or '',
                    'aliases': '|'.join(station.aliases) if station.aliases else '',
                    'line_name_kana': station.line_name_kana or '',
                    'line_color': station.line_color or '',
                    'line_type': station.line_type or '',
                    'company_code': station.company_code or '',
                    'all_lines': '|'.join(station.all_lines) if station.all_lines else ''
                })
        
        logger.info(f"Appended {len(stations)} stations to {file_path}")
    
    def load_from_csv(self, file_path: Path) -> List[Station]:
        """Load stations from CSV file.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            List of Station objects
        """
        stations = []
        
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                aliases = row['aliases'].split('|') if row.get('aliases') else []
                all_lines = row['all_lines'].split('|') if row.get('all_lines') else []
                
                station = Station(
                    name=row['name'],
                    prefecture=row['prefecture'] or None,
                    city=row['city'] or None,
                    railway_company=row['railway_company'] or None,
                    line_name=row['line_name'] or None,
                    station_code=row['station_code'] or None,
                    latitude=float(row['latitude']) if row['latitude'] else None,
                    longitude=float(row['longitude']) if row['longitude'] else None,
                    aliases=aliases,
                    line_name_kana=row.get('line_name_kana') or None,
                    line_color=row.get('line_color') or None,
                    line_type=row.get('line_type') or None,
                    company_code=row.get('company_code') or None,
                    all_lines=all_lines
                )
                stations.append(station)
        
        logger.info(f"Loaded {len(stations)} stations from {file_path}")
        return stations
    
    def _load_existing_stations(self, csv_path: Path) -> None:
        """Load existing stations for deduplication.
        
        Args:
            csv_path: Path to existing CSV file
        """
        try:
            existing_stations = self.load_from_csv(csv_path)
            self.existing_stations = {(s.name, s.prefecture) for s in existing_stations}
        except Exception as e:
            logger.warning(f"Failed to load existing stations: {e}")
            self.existing_stations = set()
    
    def _save_crawl_state(self, state: Dict[str, Any]) -> None:
        """Save current crawling state to disk.
        
        Args:
            state: Current crawling state
        """
        if not self.state_file:
            return
            
        try:
            state['progress'] = self.progress.to_dict()
            state['timestamp'] = datetime.now().isoformat()
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.warning(f"Failed to save crawl state: {e}")
    
    def _load_crawl_state(self) -> Dict[str, Any]:
        """Load previous crawling state from disk.
        
        Returns:
            Previous crawling state or empty dict
        """
        if not self.state_file or not self.state_file.exists():
            return {
                'completed_prefectures': [],
                'completed_lines': {},
                'current_prefecture_index': 0,
                'current_line_index': 0
            }
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
                
            # Restore progress if available
            if 'progress' in state:
                self.progress = CrawlingProgress.from_dict(state['progress'])
                
            return state
            
        except Exception as e:
            logger.warning(f"Failed to load crawl state: {e}")
            return {
                'completed_prefectures': [],
                'completed_lines': {},
                'current_prefecture_index': 0,
                'current_line_index': 0
            }
    
    def _update_progress(self, message: str, increment_stations: int = 0) -> None:
        """Update progress and notify callback.
        
        Args:
            message: Progress message
            increment_stations: Number of stations to add to count
        """
        if increment_stations > 0:
            self.progress.stations_found += increment_stations
            
        if self.progress_callback:
            self.progress_callback({
                'message': message,
                'stations_found': self.progress.stations_found,
                'duplicates_filtered': self.progress.duplicates_filtered,
                'prefectures_completed': self.progress.prefectures_completed,
                'lines_completed': self.progress.lines_completed,
                'current_prefecture': self.progress.current_prefecture,
                'current_line': self.progress.current_line,
                'errors': self.progress.errors,
                'elapsed_time': (datetime.now() - self.progress.start_time).total_seconds()
            })
    
    def _checkpoint_save(self, stations_batch: List[Station], output_path: Path) -> None:
        """Save a batch of stations and update progress.
        
        Args:
            stations_batch: Batch of stations to save
            output_path: CSV file path to append to
        """
        if not stations_batch:
            return
            
        # Filter out duplicates before saving
        new_stations = []
        for station in stations_batch:
            key = (station.name, station.prefecture)
            if key not in self.existing_stations:
                new_stations.append(station)
                self.existing_stations.add(key)
            else:
                self.progress.duplicates_filtered += 1
        
        if new_stations:
            self.append_to_csv(new_stations, output_path)
            self._update_progress(
                f"Saved {len(new_stations)} new stations (filtered {len(stations_batch) - len(new_stations)} duplicates)",
                increment_stations=len(new_stations)
            )
    
    def _crawl_yahoo_transit_stations_resumable(self, crawl_state: Dict[str, Any]) -> None:
        """Crawl station data from Yahoo Transit with resume capability."""
        logger.info("Crawling Yahoo Transit station data (resumable)")
        
        # Crawl Tokyo prefecture (13) - can expand to other prefectures
        prefectures_to_crawl = [
            {'code': '13', 'name': '東京都'},
            {'code': '14', 'name': '神奈川県'},
            {'code': '11', 'name': '埼玉県'},
            {'code': '12', 'name': '千葉県'},
        ]
        
        completed_prefectures = set(crawl_state.get('completed_prefectures', []))
        start_index = crawl_state.get('current_prefecture_index', 0)
        
        for i, pref in enumerate(prefectures_to_crawl[start_index:], start_index):
            pref_key = f"{pref['code']}_{pref['name']}"
            
            if pref_key in completed_prefectures:
                logger.info(f"Skipping already completed prefecture: {pref['name']}")
                continue
                
            self.progress.current_prefecture = pref['name']
            self._update_progress(f"Starting prefecture: {pref['name']}")
            
            try:
                self._crawl_prefecture_stations_resumable(
                    pref['code'], pref['name'], crawl_state
                )
                
                # Mark prefecture as completed
                completed_prefectures.add(pref_key)
                crawl_state['completed_prefectures'] = list(completed_prefectures)
                crawl_state['current_prefecture_index'] = i + 1
                self.progress.prefectures_completed += 1
                
                # Save state after each prefecture
                self._save_crawl_state(crawl_state)
                
            except Exception as e:
                self.progress.errors += 1
                self._update_progress(f"Failed to crawl {pref['name']}: {e}")
                logger.warning(f"Failed to crawl {pref['name']} stations: {e}")
                continue

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _crawl_yahoo_transit_stations(self) -> None:
        """Legacy method - use _crawl_yahoo_transit_stations_resumable instead."""
        crawl_state = {'completed_prefectures': [], 'completed_lines': {}}
        self._crawl_yahoo_transit_stations_resumable(crawl_state)
    
    def _crawl_prefecture_stations_resumable(self, pref_code: str, pref_name: str, 
                                           crawl_state: Dict[str, Any]) -> None:
        """Crawl all railway lines in a prefecture with resume capability.
        
        Args:
            pref_code: Prefecture code (e.g., '13' for Tokyo)
            pref_name: Prefecture name (e.g., '東京都')
            crawl_state: Current crawling state
        """
        pref_url = f'https://transit.yahoo.co.jp/station/pref/{pref_code}'
        logger.info(f"Crawling {pref_name} prefecture: {pref_url}")
        
        try:
            response = self.session.get(pref_url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all railway line links
            line_links = []
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text().strip()
                
                # Look for line links in format /station/{pref_code}/{company}/{line}
                if f'/station/{pref_code}/' in href and ('線' in text or 'JR' in text):
                    full_url = f'https://transit.yahoo.co.jp{href}'
                    line_links.append((text, full_url))
            
            logger.info(f"Found {len(line_links)} railway lines in {pref_name}")
            
            # Get completed lines for this prefecture
            pref_key = f"{pref_code}_{pref_name}"
            completed_lines = set(crawl_state.get('completed_lines', {}).get(pref_key, []))
            
            stations_batch = []
            
            # Crawl each line (limit to first 20 lines to avoid overwhelming)
            for i, (line_name, line_url) in enumerate(line_links[:20]):
                line_key = f"{line_name}_{line_url}"
                
                if line_key in completed_lines:
                    logger.info(f"Skipping already completed line: {line_name}")
                    continue
                
                self.progress.current_line = line_name
                self._update_progress(f"Crawling line: {line_name}")
                
                try:
                    line_stations = self._parse_yahoo_line_page_resumable(
                        line_url, line_name, pref_name
                    )
                    stations_batch.extend(line_stations)
                    
                    # Mark line as completed
                    completed_lines.add(line_key)
                    if pref_key not in crawl_state['completed_lines']:
                        crawl_state['completed_lines'][pref_key] = []
                    crawl_state['completed_lines'][pref_key] = list(completed_lines)
                    self.progress.lines_completed += 1
                    
                    # Checkpoint save every batch or when reaching checkpoint interval
                    if len(stations_batch) >= self.checkpoint_interval:
                        self._update_progress(f"Checkpoint: saving {len(stations_batch)} stations")
                        self.stations.extend(stations_batch)
                        stations_batch = []
                        self._save_crawl_state(crawl_state)
                    
                    # Add delay to be respectful
                    time.sleep(1)
                    
                except Exception as e:
                    self.progress.errors += 1
                    self._update_progress(f"Failed to crawl line {line_name}: {e}")
                    logger.warning(f"Failed to crawl line {line_name}: {e}")
                    continue
            
            # Save any remaining stations
            if stations_batch:
                self.stations.extend(stations_batch)
                self._update_progress(f"Final batch: saved {len(stations_batch)} stations")
                    
        except requests.RequestException as e:
            raise NetworkError(f"Failed to fetch prefecture page: {e}")
        except Exception as e:
            raise ScrapingError(f"Failed to parse prefecture page: {e}")
    
    def _crawl_prefecture_stations(self, pref_code: str, pref_name: str) -> None:
        """Legacy method - use _crawl_prefecture_stations_resumable instead."""
        crawl_state = {'completed_lines': {}}
        self._crawl_prefecture_stations_resumable(pref_code, pref_name, crawl_state)
    
    def _parse_yahoo_line_page(self, url: str, line_name: str, prefecture: str = None) -> None:
        """Parse a Yahoo Transit line page to extract stations.
        
        Args:
            url: Yahoo Transit line page URL
            line_name: Railway line name
            prefecture: Prefecture name
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for station links - Yahoo uses pattern /station/{id}?pref={pref}&company={company}&line={line}
            station_links = []
            stations_found = []
            
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text().strip()
                
                # Look for station links with query parameters
                if '/station/' in href and 'pref=' in href and 'company=' in href and text:
                    # Filter out non-station links
                    if text not in ['駅情報', '時刻表'] and len(text) <= 15:
                        station_links.append((text, href))
            
            # Extract detailed station information
            for station_name, station_href in station_links:
                if station_name in stations_found:
                    continue  # Skip duplicates
                
                stations_found.append(station_name)
                
                # Extract additional info from URL parameters
                station_info = self._extract_station_info_from_url(station_href, url)
                
                # Get prefecture from URL or parameter
                station_prefecture = prefecture or self._get_prefecture_from_url(url)
                
                # Determine railway company from line name
                railway_company = self._get_company_from_line(line_name)
                
                # Try to get additional details by visiting station page
                station_details = self._get_station_details(station_href)
                
                # Create station with comprehensive line information
                station = Station(
                    name=station_name,
                    prefecture=station_prefecture,
                    city=station_details.get('city'),
                    railway_company=railway_company,
                    line_name=line_name,
                    station_code=station_details.get('station_code'),
                    latitude=station_details.get('latitude'),
                    longitude=station_details.get('longitude'),
                    aliases=station_details.get('aliases', []),
                    line_name_kana=station_details.get('line_name_kana'),
                    line_color=station_details.get('line_color'),
                    line_type=self._get_line_type(line_name),
                    company_code=self._get_company_code(railway_company),
                    all_lines=station_details.get('all_lines', [])
                )
                
                self.stations.append(station)
            
            logger.info(f"Found {len(stations_found)} stations on {line_name}")
                        
        except requests.RequestException as e:
            raise NetworkError(f"Failed to fetch Yahoo Transit page: {e}")
        except Exception as e:
            raise ScrapingError(f"Failed to parse Yahoo Transit page: {e}")
    
    def _parse_yahoo_line_page_resumable(self, url: str, line_name: str, 
                                       prefecture: str = None) -> List[Station]:
        """Parse a Yahoo Transit line page to extract stations (resumable version).
        
        Args:
            url: Yahoo Transit line page URL
            line_name: Railway line name
            prefecture: Prefecture name
        
        Returns:
            List of Station objects found on this line
        """
        line_stations = []
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for station links - Yahoo uses pattern /station/{id}?pref={pref}&company={company}&line={line}
            station_links = []
            stations_found = []
            
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text().strip()
                
                # Look for station links with query parameters
                if '/station/' in href and 'pref=' in href and 'company=' in href and text:
                    # Filter out non-station links
                    if text not in ['駅情報', '時刻表'] and len(text) <= 15:
                        station_links.append((text, href))
            
            # Extract detailed station information
            for station_name, station_href in station_links:
                if station_name in stations_found:
                    continue  # Skip duplicates
                
                # Check if this station already exists
                station_key = (station_name, prefecture)
                if station_key in self.existing_stations:
                    self.progress.duplicates_filtered += 1
                    continue
                
                stations_found.append(station_name)
                
                # Extract additional info from URL parameters
                station_info = self._extract_station_info_from_url(station_href, url)
                
                # Get prefecture from URL or parameter
                station_prefecture = prefecture or self._get_prefecture_from_url(url)
                
                # Determine railway company from line name
                railway_company = self._get_company_from_line(line_name)
                
                # Try to get additional details by visiting station page
                station_details = self._get_station_details(station_href)
                
                # Create station with comprehensive line information
                station = Station(
                    name=station_name,
                    prefecture=station_prefecture,
                    city=station_details.get('city'),
                    railway_company=railway_company,
                    line_name=line_name,
                    station_code=station_details.get('station_code'),
                    latitude=station_details.get('latitude'),
                    longitude=station_details.get('longitude'),
                    aliases=station_details.get('aliases', []),
                    line_name_kana=station_details.get('line_name_kana'),
                    line_color=station_details.get('line_color'),
                    line_type=self._get_line_type(line_name),
                    company_code=self._get_company_code(railway_company),
                    all_lines=station_details.get('all_lines', [])
                )
                
                line_stations.append(station)
            
            logger.info(f"Found {len(stations_found)} stations on {line_name}")
            return line_stations
                        
        except requests.RequestException as e:
            raise NetworkError(f"Failed to fetch Yahoo Transit page: {e}")
        except Exception as e:
            raise ScrapingError(f"Failed to parse Yahoo Transit page: {e}")
    
    def _extract_station_info_from_url(self, station_href: str, line_url: str) -> Dict[str, str]:
        """Extract station information from URL parameters.
        
        Args:
            station_href: Station link href
            line_url: Original line URL
            
        Returns:
            Dictionary with extracted information
        """
        from urllib.parse import parse_qs, urlparse
        
        parsed = urlparse(station_href)
        params = parse_qs(parsed.query)
        
        return {
            'pref': params.get('pref', [''])[0],
            'company': params.get('company', [''])[0],
            'line': params.get('line', [''])[0],
        }
    
    def _get_station_details(self, station_href: str) -> Dict[str, Any]:
        """Get detailed station information from station page.
        
        Args:
            station_href: Station page href
            
        Returns:
            Dictionary with station details
        """
        details = {
            'city': None,
            'station_code': None,
            'latitude': None,
            'longitude': None,
            'aliases': [],
            'line_name_kana': None,
            'line_color': None,
            'all_lines': []
        }
        
        try:
            # Make full URL
            if station_href.startswith('/'):
                station_url = f'https://transit.yahoo.co.jp{station_href}'
            else:
                station_url = station_href
            
            response = self.session.get(station_url, timeout=self.timeout)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                page_text = soup.get_text()
                
                # Extract station name with prefecture disambiguation
                title_elem = soup.find('title')
                if title_elem:
                    title_text = title_elem.get_text()
                    # Extract station name from title like "青山(岩手県)駅の駅周辺情報"
                    import re
                    station_match = re.search(r'(.+?)駅の', title_text)
                    if station_match:
                        station_name_with_pref = station_match.group(1)
                        if '(' in station_name_with_pref:
                            details['aliases'].append(station_name_with_pref)
                
                # Extract all lines serving this station
                line_elements = soup.find_all('a', href=True)
                lines_found = set()
                for elem in line_elements:
                    href = elem.get('href', '')
                    text = elem.get_text().strip()
                    
                    # Look for line links or line names
                    if ('線' in text or 'Line' in text) and len(text) < 30:
                        # Filter out common non-line texts
                        exclude_terms = ['路線図', '路線情報', '線路', '新幹線情報']
                        if not any(term in text for term in exclude_terms) and text not in lines_found:
                            lines_found.add(text)
                
                details['all_lines'] = list(lines_found)
                
                # Extract city/ward information
                # Try broader patterns for different prefectures
                city_patterns = [
                    # Tokyo wards
                    r'(千代田区|中央区|港区|新宿区|文京区|台東区|墨田区|江東区|品川区|目黒区|大田区|世田谷区|渋谷区|中野区|杉並区|豊島区|北区|荒川区|板橋区|練馬区|足立区|葛飾区|江戸川区)',
                    # Other cities
                    r'([^\\s]+市)',
                    r'([^\\s]+町)',
                    r'([^\\s]+村)',
                    r'([^\\s]+郡)',
                ]
                
                import re
                for pattern in city_patterns:
                    matches = re.findall(pattern, page_text)
                    if matches:
                        details['city'] = matches[0]
                        break
                
                # Look for station codes with more comprehensive patterns
                code_patterns = [
                    r'[A-Z]{1,4}-[A-Z]?\\d{2,3}',  # JR-Y01, M-01, etc.
                    r'[A-Z]{2,3}\\d{2,3}',  # JY01, JR01, etc.
                    r'[A-Z]\\d{2}',  # Y01, M01, etc.
                    r'\\b[A-Z]{1,2}-\\d{1,3}\\b',  # Alternative formats
                ]
                
                for pattern in code_patterns:
                    matches = re.findall(pattern, page_text)
                    if matches:
                        # Take the first reasonable match
                        for match in matches:
                            if len(match) <= 10:  # Reasonable length
                                details['station_code'] = match
                                break
                        if details['station_code']:
                            break
                
                # Look for coordinates in the page (sometimes embedded in maps)
                coord_patterns = [
                    r'(\\d+\\.\\d+),(\\d+\\.\\d+)',  # lat,lng format
                    r'lat[^\\d]*(\\d+\\.\\d+)',  # latitude
                    r'lng[^\\d]*(\\d+\\.\\d+)',  # longitude
                ]
                
                for pattern in coord_patterns:
                    matches = re.findall(pattern, page_text)
                    if matches:
                        if len(matches[0]) == 2:  # lat,lng pair
                            try:
                                details['latitude'] = float(matches[0][0])
                                details['longitude'] = float(matches[0][1])
                                break
                            except ValueError:
                                continue
                
                # Extract line color information (if available in page)
                # This might be in CSS or data attributes
                color_patterns = [
                    r'#[0-9A-Fa-f]{6}',  # Hex colors
                    r'rgb\\((\\d+,\\s*\\d+,\\s*\\d+)\\)',  # RGB colors
                ]
                
                for pattern in color_patterns:
                    matches = re.findall(pattern, page_text)
                    if matches:
                        details['line_color'] = matches[0]
                        break
            
            # Add small delay to be respectful
            import time
            time.sleep(0.5)
            
        except Exception as e:
            logger.debug(f"Failed to get station details: {e}")
        
        return details
    
    def _get_prefecture_from_url(self, url: str) -> str:
        """Extract prefecture from Yahoo Transit URL.
        
        Args:
            url: Yahoo Transit URL
            
        Returns:
            Prefecture name
        """
        # Yahoo uses prefecture codes: 13=Tokyo, 14=Kanagawa, etc.
        prefecture_map = {
            '/13/': '東京都',
            '/14/': '神奈川県', 
            '/12/': '千葉県',
            '/11/': '埼玉県',
            '/27/': '大阪府',
        }
        
        for code, prefecture in prefecture_map.items():
            if code in url:
                return prefecture
        
        return '東京都'  # Default to Tokyo
    
    def _get_company_from_line(self, line_name: str) -> str:
        """Extract railway company from line name.
        
        Args:
            line_name: Railway line name
            
        Returns:
            Railway company name
        """
        if 'JR' in line_name:
            return 'JR東日本'
        elif '東京メトロ' in line_name:
            return '東京メトロ'
        elif '都営' in line_name:
            return '都営地下鉄'
        elif '小田急' in line_name:
            return '小田急電鉄'
        elif '京急' in line_name:
            return '京浜急行電鉄'
        else:
            return 'その他'
    
    def _get_line_type(self, line_name: str) -> str:
        """Determine line type from line name.
        
        Args:
            line_name: Railway line name
            
        Returns:
            Line type classification
        """
        if 'JR' in line_name:
            return 'JR'
        elif '東京メトロ' in line_name or 'メトロ' in line_name:
            return 'Metro'
        elif '都営' in line_name:
            return 'Metro'
        elif any(term in line_name for term in ['私鉄', '電鉄', '鉄道']):
            return 'Private'
        else:
            return 'Other'
    
    def _get_company_code(self, company_name: str) -> str:
        """Get company code from company name.
        
        Args:
            company_name: Railway company name
            
        Returns:
            Company code
        """
        company_codes = {
            'JR東日本': 'JR-E',
            '東京メトロ': 'TM',
            '都営地下鉄': 'TS',
            '小田急電鉄': 'OH',
            '京浜急行電鉄': 'KK',
            'その他': 'OTHER'
        }
        return company_codes.get(company_name, 'OTHER')
    

    
    def _deduplicate_stations(self) -> List[Station]:
        """Remove duplicate stations based on name and prefecture.
        
        Returns:
            List of unique stations
        """
        seen: Set[tuple] = set()
        unique_stations = []
        
        for station in self.stations:
            key = (station.name, station.prefecture)
            if key not in seen:
                seen.add(key)
                unique_stations.append(station)
        
        return unique_stations


class StationSearcher:
    """Search engine for station data."""
    
    def __init__(self, stations: List[Station]):
        """Initialize searcher with station data.
        
        Args:
            stations: List of stations to search
        """
        self.stations = stations
        self._build_search_index()
    
    def _build_search_index(self) -> None:
        """Build search index for faster lookups."""
        self.name_index: Dict[str, List[Station]] = {}
        self.prefecture_index: Dict[str, List[Station]] = {}
        
        for station in self.stations:
            # Index by name
            if station.name not in self.name_index:
                self.name_index[station.name] = []
            self.name_index[station.name].append(station)
            
            # Index by prefecture
            if station.prefecture:
                if station.prefecture not in self.prefecture_index:
                    self.prefecture_index[station.prefecture] = []
                self.prefecture_index[station.prefecture].append(station)
    
    def search_by_name(self, query: str, exact: bool = False) -> List[Station]:
        """Search stations by name.
        
        Args:
            query: Search query
            exact: Whether to perform exact match
            
        Returns:
            List of matching stations
        """
        if exact:
            return self.name_index.get(query, [])
        
        # Fuzzy search
        results = []
        query_lower = query.lower()
        
        for station in self.stations:
            if query_lower in station.name.lower():
                results.append(station)
            elif station.aliases:
                for alias in station.aliases:
                    if query_lower in alias.lower():
                        results.append(station)
                        break
        
        return results
    
    def search_by_prefecture(self, prefecture: str) -> List[Station]:
        """Search stations by prefecture.
        
        Args:
            prefecture: Prefecture name
            
        Returns:
            List of stations in the prefecture
        """
        return self.prefecture_index.get(prefecture, [])
    
    def get_all_prefectures(self) -> List[str]:
        """Get list of all prefectures in the database.
        
        Returns:
            List of prefecture names
        """
        return sorted([p for p in self.prefecture_index.keys() if p])
    
    def search_stations(self, query: str, limit: int = 10) -> List[Station]:
        """Search stations with limit.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching stations (up to limit)
        """
        results = self.search_by_name(query, exact=False)
        return results[:limit]
    
    def get_station_by_name(self, station_name: str) -> Optional[Station]:
        """Get a specific station by exact name.
        
        Args:
            station_name: Exact station name
            
        Returns:
            Station object if found, None otherwise
        """
        matches = self.name_index.get(station_name, [])
        return matches[0] if matches else None
    
    def list_stations(
        self, 
        prefecture: Optional[str] = None, 
        line: Optional[str] = None, 
        limit: int = 50
    ) -> List[Station]:
        """List stations with optional filters.
        
        Args:
            prefecture: Filter by prefecture
            line: Filter by line name
            limit: Maximum number of results
            
        Returns:
            List of matching stations
        """
        stations = self.stations
        
        # Filter by prefecture
        if prefecture:
            stations = [s for s in stations if s.prefecture == prefecture]
        
        # Filter by line
        if line:
            stations = [s for s in stations if s.line_name and line.lower() in s.line_name.lower()]
        
        return stations[:limit]