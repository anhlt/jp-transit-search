"""Station data crawler for building station database."""

import csv
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.exceptions import NetworkError, ScrapingError
from ..core.models import Station
from ..utils.japanese_text import generate_text_variants

logger = logging.getLogger(__name__)

# JIS X 0401 prefecture codes mapping
PREFECTURE_ID_MAPPING = {
    "北海道": "01",
    "青森県": "02",
    "岩手県": "03",
    "宮城県": "04",
    "秋田県": "05",
    "山形県": "06",
    "福島県": "07",
    "茨城県": "08",
    "栃木県": "09",
    "群馬県": "10",
    "埼玉県": "11",
    "千葉県": "12",
    "東京都": "13",
    "神奈川県": "14",
    "新潟県": "15",
    "富山県": "16",
    "石川県": "17",
    "福井県": "18",
    "山梨県": "19",
    "長野県": "20",
    "岐阜県": "21",
    "静岡県": "22",
    "愛知県": "23",
    "三重県": "24",
    "滋賀県": "25",
    "京都府": "26",
    "大阪府": "27",
    "兵庫県": "28",
    "奈良県": "29",
    "和歌山県": "30",
    "鳥取県": "31",
    "島根県": "32",
    "岡山県": "33",
    "広島県": "34",
    "山口県": "35",
    "徳島県": "36",
    "香川県": "37",
    "愛媛県": "38",
    "高知県": "39",
    "福岡県": "40",
    "佐賀県": "41",
    "長崎県": "42",
    "熊本県": "43",
    "大分県": "44",
    "宮崎県": "45",
    "鹿児島県": "46",
    "沖縄県": "47",
}


@dataclass
class CrawlState:
    """State for resumable crawling."""

    completed_prefectures: list[str] = field(default_factory=list)
    completed_lines: dict[str, list[str]] = field(default_factory=dict)
    current_prefecture_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "completed_prefectures": self.completed_prefectures,
            "completed_lines": self.completed_lines,
            "current_prefecture_index": self.current_prefecture_index,
        }


@dataclass
class StationDetails:
    """Details for a station."""

    # city field removed - not available from Yahoo Transit data source
    # latitude, longitude, line_name_kana, line_color, station_code removed - no data available
    prefecture_id: str | None = None
    station_id: str | None = None  # Keep station_id - extractable from URLs
    aliases: list[str] | None = None
    all_lines: list[str] | None = None

    # Enhanced fields for better data extraction
    station_reading: str | None = None  # Kana reading from <span class="staKana">
    company_name: str | None = None  # Railway company from JSON data
    line_name: str | None = None  # Primary line name from JSON data


class CrawlingProgress:
    """Track crawling progress and statistics."""

    def __init__(self) -> None:
        self.start_time = datetime.now()
        self.stations_found = 0
        self.duplicates_filtered = 0
        self.prefectures_completed = 0
        self.lines_completed = 0
        self.current_prefecture = ""
        self.current_line = ""
        self.errors = 0
        self.retries = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert progress to dictionary for serialization."""
        return {
            "start_time": self.start_time.isoformat(),
            "stations_found": self.stations_found,
            "duplicates_filtered": self.duplicates_filtered,
            "prefectures_completed": self.prefectures_completed,
            "lines_completed": self.lines_completed,
            "current_prefecture": self.current_prefecture,
            "current_line": self.current_line,
            "errors": self.errors,
            "retries": self.retries,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CrawlingProgress":
        """Create progress from dictionary."""
        progress = cls()
        progress.start_time = datetime.fromisoformat(
            data.get("start_time", datetime.now().isoformat())
        )
        progress.stations_found = data.get("stations_found", 0)
        progress.duplicates_filtered = data.get("duplicates_filtered", 0)
        progress.prefectures_completed = data.get("prefectures_completed", 0)
        progress.lines_completed = data.get("lines_completed", 0)
        progress.current_prefecture = data.get("current_prefecture", "")
        progress.current_line = data.get("current_line", "")
        progress.errors = data.get("errors", 0)
        progress.retries = data.get("retries", 0)
        return progress


class StationCrawler:
    """Crawler for Japanese train station data."""

    def __init__(
        self,
        timeout: int = 30,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        max_lines_per_prefecture: int | None = None,
    ):
        """Initialize the station crawler.

        Args:
            timeout: Request timeout in seconds
            progress_callback: Optional callback for progress updates
            max_lines_per_prefecture: Maximum lines to crawl per prefecture (None for no limit)
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )
        self.stations: list[Station] = []
        self.existing_stations: set[str] = set()  # For deduplication by station_id
        self.progress = CrawlingProgress()
        self.progress_callback = progress_callback
        self.state_file: Path | None = None
        self.output_path: Path | None = None
        self.checkpoint_interval = 50  # Save progress every 50 stations
        self.max_lines_per_prefecture = max_lines_per_prefecture

    def crawl_all_stations(
        self,
        resume_from_csv: Path | None = None,
        state_file: Path | None = None,
        output_path: Path | None = None,
    ) -> list[Station]:
        """Crawl station data from multiple sources with resume capability.

        Args:
            resume_from_csv: Path to existing CSV file to resume from
            state_file: Path to state file for tracking progress
            output_path: Path to output CSV file for incremental writing

        Returns:
            List of Station objects
        """
        logger.info("Starting resumable station data crawl")
        self.state_file = state_file
        self.output_path = output_path

        # Load existing stations for deduplication
        if resume_from_csv and resume_from_csv.exists():
            self._load_existing_stations(resume_from_csv)
            logger.info(
                f"Loaded {len(self.existing_stations)} existing stations for deduplication"
            )
        elif output_path and output_path.exists():
            # If starting fresh but output file exists, clear it
            logger.info(
                f"Starting fresh crawl, clearing existing output file: {output_path}"
            )
            output_path.unlink()

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

    def save_to_csv(self, stations: list[Station], file_path: Path) -> None:
        """Save stations to CSV file.

        Args:
            stations: List of stations to save
            file_path: Path to CSV file
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "name",
                "name_hiragana",
                "name_katakana",
                "name_romaji",
                "prefecture",
                "prefecture_id",
                "station_id",
                "railway_company",
                "line_name",
                "aliases",
                "all_lines",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for station in stations:
                writer.writerow(
                    {
                        "name": station.name,
                        "name_hiragana": station.name_hiragana or "",
                        "name_katakana": station.name_katakana or "",
                        "name_romaji": station.name_romaji or "",
                        "prefecture": station.prefecture or "",
                        "prefecture_id": station.prefecture_id or "",
                        "station_id": station.station_id or "",
                        "railway_company": station.railway_company or "",
                        "line_name": station.line_name or "",
                        "aliases": "|".join(station.aliases) if station.aliases else "",
                        "all_lines": "|".join(station.all_lines)
                        if station.all_lines
                        else "",
                    }
                )

        logger.info(f"Saved {len(stations)} stations to {file_path}")

    def append_to_csv(self, stations: list[Station], file_path: Path) -> None:
        """Append stations to existing CSV file.

        Args:
            stations: List of stations to append
            file_path: Path to CSV file
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if file exists to determine if we need headers
        write_headers = not file_path.exists()

        with open(file_path, "a", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "name",
                "name_hiragana",
                "name_katakana",
                "name_romaji",
                "prefecture",
                "prefecture_id",
                "station_id",
                "railway_company",
                "line_name",
                "aliases",
                "all_lines",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            if write_headers:
                writer.writeheader()

            for station in stations:
                writer.writerow(
                    {
                        "name": station.name,
                        "name_hiragana": station.name_hiragana or "",
                        "name_katakana": station.name_katakana or "",
                        "name_romaji": station.name_romaji or "",
                        "prefecture": station.prefecture or "",
                        "prefecture_id": station.prefecture_id or "",
                        "station_id": station.station_id or "",
                        "railway_company": station.railway_company or "",
                        "line_name": station.line_name or "",
                        "aliases": "|".join(station.aliases) if station.aliases else "",
                        "all_lines": "|".join(station.all_lines)
                        if station.all_lines
                        else "",
                    }
                )

        logger.info(f"Appended {len(stations)} stations to {file_path}")

    def load_from_csv(self, file_path: Path) -> list[Station]:
        """Load stations from CSV file.

        Args:
            file_path: Path to CSV file

        Returns:
            List of Station objects
        """
        stations = []

        with open(file_path, encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                aliases = row["aliases"].split("|") if row.get("aliases") else []
                all_lines = row["all_lines"].split("|") if row.get("all_lines") else []

                # Generate prefecture_id from prefecture name if not in CSV
                prefecture_id = row.get("prefecture_id")
                if not prefecture_id and row.get("prefecture"):
                    prefecture_id = PREFECTURE_ID_MAPPING.get(row["prefecture"])

                station = Station(
                    name=row["name"],
                    name_hiragana=row.get("name_hiragana") or None,
                    name_katakana=row.get("name_katakana") or None,
                    name_romaji=row.get("name_romaji") or None,
                    prefecture=row["prefecture"] or None,
                    prefecture_id=prefecture_id or None,
                    station_id=row.get("station_id") or None,
                    railway_company=row["railway_company"] or None,
                    line_name=row["line_name"] or None,
                    aliases=aliases,
                    all_lines=all_lines,
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
            # Use station_id for deduplication, fallback to name+prefecture if no ID
            self.existing_stations = {
                s.station_id if s.station_id else f"{s.name}_{s.prefecture}"
                for s in existing_stations
            }
        except Exception as e:
            logger.warning(f"Failed to load existing stations: {e}")
            self.existing_stations = set()

    def _save_crawl_state(self, state: CrawlState) -> None:
        """Save current crawling state to disk.

        Args:
            state: Current crawling state
        """
        if not self.state_file:
            return

        try:
            state_dict = state.to_dict()
            state_dict["progress"] = self.progress.to_dict()
            state_dict["timestamp"] = datetime.now().isoformat()

            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state_dict, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.warning(f"Failed to save crawl state: {e}")

    def _load_crawl_state(self) -> CrawlState:
        """Load previous crawling state from disk.

        Returns:
            Previous crawling state or empty dict
        """
        if not self.state_file or not self.state_file.exists():
            return CrawlState()

        try:
            with open(self.state_file, encoding="utf-8") as f:
                state = json.load(f)

            # Restore progress if available
            if "progress" in state:
                self.progress = CrawlingProgress.from_dict(state["progress"])

            return CrawlState(
                completed_prefectures=state.get("completed_prefectures", []),
                completed_lines=state.get("completed_lines", {}),
                current_prefecture_index=state.get("current_prefecture_index"),
            )

        except Exception as e:
            logger.warning(f"Failed to load crawl state: {e}")
            return CrawlState()

    def _update_progress(
        self, message: str, increment_stations: int = 0, station_name: str | None = None
    ) -> None:
        """Update progress and notify callback.

        Args:
            message: Progress message
            increment_stations: Number of stations to add to count
            station_name: Name of station being processed (for detailed logging)
        """
        if increment_stations > 0:
            self.progress.stations_found += increment_stations

        elapsed = (datetime.now() - self.progress.start_time).total_seconds()
        progress_info = {
            "message": message,
            "stations_found": self.progress.stations_found,
            "duplicates_filtered": self.progress.duplicates_filtered,
            "prefectures_completed": self.progress.prefectures_completed,
            "lines_completed": self.progress.lines_completed,
            "current_prefecture": self.progress.current_prefecture,
            "current_line": self.progress.current_line,
            "errors": self.progress.errors,
            "elapsed_time": elapsed,
        }

        if station_name:
            progress_info["current_station"] = station_name

        # Always log progress to console for visibility
        if station_name:
            logger.info(
                f"[{self.progress.prefectures_completed + 1:2d}/47] {self.progress.current_prefecture} | {self.progress.current_line} | Found: {station_name} | Total: {self.progress.stations_found}"
            )
        else:
            logger.info(
                f"[{elapsed:6.1f}s] {message} | Stations: {self.progress.stations_found} | Errors: {self.progress.errors} | Duplicates: {self.progress.duplicates_filtered}"
            )

        if self.progress_callback:
            self.progress_callback(progress_info)

    def _checkpoint_save(
        self, stations_batch: list[Station], output_path: Path
    ) -> None:
        """Save a batch of stations and update progress.

        Args:
            stations_batch: Batch of stations to save (already deduplicated)
            output_path: CSV file path to append to
        """
        if not stations_batch:
            return

        # Stations in the batch are already deduplicated during parsing, so just save them
        self.append_to_csv(stations_batch, output_path)
        self._update_progress(
            f"Saved {len(stations_batch)} stations to CSV",
        )

    def _crawl_yahoo_transit_stations_resumable(self, crawl_state: CrawlState) -> None:
        """Crawl station data from Yahoo Transit with resume capability."""
        logger.info("Crawling Yahoo Transit station data (resumable)")

        # Generate all 47 prefectures from the mapping
        prefectures_to_crawl = [
            {"code": code, "name": name} for name, code in PREFECTURE_ID_MAPPING.items()
        ]
        # Sort by code to ensure consistent order
        prefectures_to_crawl.sort(key=lambda x: x["code"])

        completed_prefectures = set(crawl_state.completed_prefectures)
        start_index = crawl_state.current_prefecture_index or 0

        for i, pref in enumerate(prefectures_to_crawl[start_index:], start_index):
            pref_key = f"{pref['code']}_{pref['name']}"

            if pref_key in completed_prefectures:
                logger.info(f"Skipping already completed prefecture: {pref['name']}")
                continue

            self.progress.current_prefecture = pref["name"]
            self._update_progress(
                f"[{i + 1:2d}/47] Starting prefecture: {pref['name']} (Code: {pref['code']})"
            )

            try:
                pref_stations_before = self.progress.stations_found
                self._crawl_prefecture_stations_resumable(
                    pref["code"], pref["name"], crawl_state
                )
                pref_stations_added = (
                    self.progress.stations_found - pref_stations_before
                )

                # Mark prefecture as completed
                completed_prefectures.add(pref_key)
                crawl_state.completed_prefectures = list(completed_prefectures)
                crawl_state.current_prefecture_index = i + 1
                self.progress.prefectures_completed += 1

                self._update_progress(
                    f"[{i + 1:2d}/47] Completed prefecture: {pref['name']} ({pref_stations_added} stations added)"
                )

                # Save state after each prefecture
                self._save_crawl_state(crawl_state)

            except Exception as e:
                self.progress.errors += 1
                self._update_progress(f"Failed to crawl {pref['name']}: {e}")
                logger.error(f"Failed to crawl {pref['name']} stations: {e}")
                continue

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _crawl_yahoo_transit_stations(self) -> None:
        """Legacy method - use _crawl_yahoo_transit_stations_resumable instead."""
        crawl_state = CrawlState()
        self._crawl_yahoo_transit_stations_resumable(crawl_state)

    def _crawl_prefecture_stations_resumable(
        self, pref_code: str, pref_name: str, crawl_state: CrawlState
    ) -> None:
        """Crawl all railway lines in a prefecture with resume capability.

        Args:
            pref_code: Prefecture code (e.g., '13' for Tokyo)
            pref_name: Prefecture name (e.g., '東京都')
            crawl_state: Current crawling state
        """
        # Remove leading zero for URL (Yahoo uses 1, 2, 3... not 01, 02, 03...)
        pref_code_for_url = str(int(pref_code))
        pref_url = f"https://transit.yahoo.co.jp/station/pref/{pref_code_for_url}"
        logger.info(f"Fetching prefecture page: {pref_url}")

        try:
            response = self.session.get(pref_url, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Find all railway line links
            line_links = []
            for link in soup.find_all("a", href=True):
                href = str(link.get("href", ""))
                text = link.get_text().strip()

                # Look for line links in format /station/{pref_code}/{company}/{line}
                # Use unpadded code for URL matching
                if f"/station/{pref_code_for_url}/" in href and (
                    "線" in text or "JR" in text
                ):
                    full_url = f"https://transit.yahoo.co.jp{href}"
                    line_links.append((text, full_url))

            limit_msg = (
                f" (limited to {self.max_lines_per_prefecture})"
                if self.max_lines_per_prefecture
                else ""
            )
            logger.info(
                f"Found {len(line_links)} railway lines in {pref_name}{limit_msg}"
            )

            # Get completed lines for this prefecture
            pref_key = f"{pref_code}_{pref_name}"
            completed_lines = set(crawl_state.completed_lines.get(pref_key, []))

            stations_batch: list[Station] = []

            # Crawl each line (with configurable limit)
            if self.max_lines_per_prefecture is not None:
                line_links = line_links[: self.max_lines_per_prefecture]

            for line_idx, (line_name, line_url) in enumerate(line_links, 1):
                line_key = f"{line_name}_{line_url}"

                if line_key in completed_lines:
                    logger.info(f"Skipping already completed line: {line_name}")
                    continue

                self.progress.current_line = line_name
                self._update_progress(
                    f"[{line_idx:2d}/{len(line_links)}] Crawling line: {line_name}"
                )

                try:
                    line_stations = self._parse_yahoo_line_page_resumable(
                        line_url, line_name, pref_name
                    )
                    stations_batch.extend(line_stations)
                    line_stations_added = len(line_stations)

                    # Mark line as completed
                    completed_lines.add(line_key)
                    if pref_key not in crawl_state.completed_lines:
                        crawl_state.completed_lines[pref_key] = []
                    crawl_state.completed_lines[pref_key] = list(completed_lines)
                    self.progress.lines_completed += 1

                    # Update progress for completed line (stations already counted individually)
                    self._update_progress(
                        f"[{line_idx:2d}/{len(line_links)}] Completed line: {line_name} ({line_stations_added} stations)"
                    )

                    logger.info(
                        f"[{line_idx:2d}/{len(line_links)}] Line: {line_name} → {line_stations_added} stations"
                    )

                    # Checkpoint save every batch or when reaching checkpoint interval
                    if len(stations_batch) >= self.checkpoint_interval:
                        self._update_progress(
                            f"Checkpoint: saving {len(stations_batch)} stations"
                        )
                        # Write batch to CSV if output path is provided
                        if self.output_path:
                            self._checkpoint_save(stations_batch, self.output_path)
                        self.stations.extend(stations_batch)
                        stations_batch = []
                        self._save_crawl_state(crawl_state)

                    # Add delay to be respectful
                    time.sleep(1)

                except Exception as e:
                    self.progress.errors += 1
                    self._update_progress(f"Failed to crawl line {line_name}: {e}")
                    logger.error(f"Failed to crawl line {line_name}: {e}")
                    continue

            # Save any remaining stations
            if stations_batch:
                # Write final batch to CSV if output path is provided
                if self.output_path:
                    self._checkpoint_save(stations_batch, self.output_path)
                self.stations.extend(stations_batch)
                self._update_progress(
                    f"Final batch: saved {len(stations_batch)} stations"
                )

        except requests.RequestException as e:
            raise NetworkError(f"Failed to fetch prefecture page: {e}") from e
        except Exception as e:
            raise ScrapingError(f"Failed to parse prefecture page: {e}") from e

    def _crawl_prefecture_stations(self, pref_code: str, pref_name: str) -> None:
        """Legacy method - use _crawl_prefecture_stations_resumable instead."""
        crawl_state = CrawlState()
        self._crawl_prefecture_stations_resumable(pref_code, pref_name, crawl_state)

    def _parse_yahoo_line_page(
        self, url: str, line_name: str, prefecture: str | None = None
    ) -> None:
        """Parse a Yahoo Transit line page to extract stations.

        Args:
            url: Yahoo Transit line page URL
            line_name: Railway line name
            prefecture: Prefecture name
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Look for station links - Yahoo uses pattern /station/{id}?pref={pref}&company={company}&line={line}
            station_links = []
            stations_found = []

            for link in soup.find_all("a", href=True):
                href = str(link.get("href", ""))
                text = link.get_text().strip()

                # Look for station links with query parameters
                if (
                    "/station/" in href
                    and "pref=" in href
                    and "company=" in href
                    and text
                ):
                    # Filter out non-station links
                    if text not in ["駅情報", "時刻表"] and len(text) <= 15:
                        station_links.append((text, href))

            # Extract detailed station information
            for station_name, station_href in station_links:
                if station_name in stations_found:
                    continue  # Skip duplicates

                stations_found.append(station_name)

                # Extract additional info from URL parameters
                self._extract_station_info_from_url(station_href, url)

                # Get prefecture from URL or parameter
                station_prefecture = prefecture or self._get_prefecture_from_url(url)

                # Determine railway company from line name
                railway_company = self._get_company_from_line(line_name)

                # Try to get additional details by visiting station page
                station_details = self._get_station_details(station_href)

                # Create station with comprehensive line information
                # Ensure prefecture_id is set if not in station_details
                prefecture_id = station_details.prefecture_id
                if not prefecture_id and station_prefecture:
                    prefecture_id = PREFECTURE_ID_MAPPING.get(station_prefecture)

                # Generate Japanese text variants
                text_variants = generate_text_variants(station_name)

                station = Station(
                    name=station_name,
                    name_hiragana=text_variants.get("hiragana"),
                    name_katakana=text_variants.get("katakana"),
                    name_romaji=text_variants.get("romaji"),
                    prefecture=station_prefecture,
                    prefecture_id=prefecture_id,
                    station_id=station_details.station_id,
                    railway_company=railway_company,
                    line_name=line_name,
                    aliases=station_details.aliases or [],
                    all_lines=station_details.all_lines or [],
                )

                self.stations.append(station)

            logger.info(f"Found {len(stations_found)} stations on {line_name}")

        except requests.RequestException as e:
            raise NetworkError(f"Failed to fetch Yahoo Transit page: {e}") from e
        except Exception as e:
            raise ScrapingError(f"Failed to parse Yahoo Transit page: {e}") from e

    def _parse_yahoo_line_page_resumable(
        self, url: str, line_name: str, prefecture: str | None = None
    ) -> list[Station]:
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

            soup = BeautifulSoup(response.text, "html.parser")

            # Look for station links - Yahoo uses pattern /station/{id}?pref={pref}&company={company}&line={line}
            station_links = []
            stations_found = []

            for link in soup.find_all("a", href=True):
                href = str(link.get("href", ""))
                text = link.get_text().strip()

                # Look for station links with query parameters
                if (
                    "/station/" in href
                    and "pref=" in href
                    and "company=" in href
                    and text
                ):
                    # Filter out non-station links
                    if text not in ["駅情報", "時刻表"] and len(text) <= 15:
                        station_links.append((text, href))

            # Extract detailed station information
            for _station_idx, (station_name, station_href) in enumerate(
                station_links, 1
            ):
                if station_name in stations_found:
                    continue  # Skip duplicates

                # Extract station ID from href for deduplication
                import re

                station_id = None
                if "/station/" in station_href:
                    station_id_match = re.search(r"/station/(\d+)", station_href)
                    if station_id_match:
                        station_id = station_id_match.group(1)

                # Check if this station already exists (use station_id if available, otherwise name+prefecture)
                if station_id:
                    station_key = station_id
                else:
                    station_key = f"{station_name}_{prefecture}"

                if station_key in self.existing_stations:
                    self.progress.duplicates_filtered += 1
                    logger.debug(
                        f"Skipping duplicate station: {station_name} (ID: {station_id or 'None'}) ({prefecture})"
                    )
                    continue

                # Add to existing stations set for future duplicate checking
                self.existing_stations.add(station_key)

                stations_found.append(station_name)

                # Extract additional info from URL parameters
                self._extract_station_info_from_url(station_href, url)

                # Get prefecture from URL or parameter
                station_prefecture = prefecture or self._get_prefecture_from_url(url)

                # Determine railway company from line name
                railway_company = self._get_company_from_line(line_name)

                # Try to get additional details by visiting station page
                station_details = self._get_station_details(station_href)

                # Create station with comprehensive line information
                # Ensure prefecture_id is set if not in station_details
                prefecture_id = station_details.prefecture_id
                if not prefecture_id and station_prefecture:
                    prefecture_id = PREFECTURE_ID_MAPPING.get(station_prefecture)

                # Use station_id extracted from href if station_details doesn't have it
                final_station_id = station_details.station_id or station_id

                # Generate Japanese text variants
                text_variants = generate_text_variants(station_name)

                station = Station(
                    name=station_name,
                    name_hiragana=text_variants.get("hiragana"),
                    name_katakana=text_variants.get("katakana"),
                    name_romaji=text_variants.get("romaji"),
                    prefecture=station_prefecture,
                    prefecture_id=prefecture_id,
                    station_id=final_station_id,
                    railway_company=railway_company,
                    line_name=line_name,
                    aliases=station_details.aliases or [],
                    all_lines=station_details.all_lines or [],
                )

                line_stations.append(station)

                # Update progress with this newly processed station
                self._update_progress(
                    f"Found station: {station_name}",
                    increment_stations=1,
                    station_name=station_name,
                )

            logger.info(f"Found {len(stations_found)} stations on {line_name}")
            return line_stations

        except requests.RequestException as e:
            raise NetworkError(f"Failed to fetch Yahoo Transit page: {e}") from e
        except Exception as e:
            raise ScrapingError(f"Failed to parse Yahoo Transit page: {e}") from e

    def _extract_station_info_from_url(
        self, station_href: str, line_url: str
    ) -> dict[str, str]:
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
            "pref": params.get("pref", [""])[0],
            "company": params.get("company", [""])[0],
            "line": params.get("line", [""])[0],
        }

    def _get_station_details(self, station_href: str) -> StationDetails:
        """Get detailed station information from station page.

        Args:
            station_href: Station page href

        Returns:
            Dictionary with station details
        """
        details = StationDetails()

        try:
            # Extract prefecture from URL and map to prefecture ID
            prefecture_name = self._get_prefecture_from_url(station_href)
            details.prefecture_id = PREFECTURE_ID_MAPPING.get(prefecture_name)

            # Also try to extract from URL parameters if available
            if "?" in station_href:
                from urllib.parse import parse_qs, unquote, urlparse

                parsed_url = urlparse(station_href)
                params = parse_qs(parsed_url.query)

                if "pref" in params and params["pref"][0]:
                    # The pref parameter might contain prefecture code
                    pref_code = params["pref"][0]
                    # Find prefecture name by code
                    for _pref_name, code in PREFECTURE_ID_MAPPING.items():
                        if code == pref_code.zfill(2):  # Ensure 2-digit format
                            details.prefecture_id = code
                            break
            # Make full URL
            if station_href.startswith("/"):
                station_url = f"https://transit.yahoo.co.jp{station_href}"
            else:
                station_url = station_href

            response = self.session.get(station_url, timeout=self.timeout)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                # Extract station name with prefecture disambiguation
                title_elem = soup.find("title")
                if title_elem:
                    title_text = title_elem.get_text()
                    # Extract station name from title like "青山(岩手県)駅の駅周辺情報"
                    import re

                    station_match = re.search(r"(.+?)駅の", title_text)
                    if station_match:
                        station_name_with_pref = station_match.group(1)
                        if "(" in station_name_with_pref:
                            if details.aliases is None:
                                details.aliases = []
                            details.aliases.append(station_name_with_pref)

                # Extract all lines serving this station
                # Look for both link elements and dt elements (which contain line names)
                line_elements = soup.find_all("a", href=True) + soup.find_all("dt")
                lines_found = set()
                for elem in line_elements:
                    text = elem.get_text().strip()

                    # Look for line links or line names (including 市電, 電車, etc.)
                    if (
                        "線" in text
                        or "Line" in text
                        or "市電" in text
                        or "電車" in text
                    ) and len(text) < 30:
                        # Filter out common non-line texts
                        exclude_terms = ["路線図", "路線情報", "線路", "新幹線情報"]
                        if (
                            not any(term in text for term in exclude_terms)
                            and text not in lines_found
                        ):
                            lines_found.add(text)

                details.all_lines = list(lines_found)

                # Extract station ID from URL
                import re

                station_id_match = re.search(r"/station/(\d+)", station_url)
                if station_id_match:
                    details.station_id = station_id_match.group(1)

                # Extract station reading (kana) from HTML
                station_kana_elem = soup.find("span", class_="staKana")
                if station_kana_elem:
                    details.station_reading = station_kana_elem.get_text().strip()

                # Extract company and line info from JSON data structure
                script_tags = soup.find_all("script", type="application/json")
                for script in script_tags:
                    try:
                        json_data = json.loads(script.string or "")
                        # Look for Next.js data structure
                        if "props" in json_data and "pageProps" in json_data["props"]:
                            page_props = json_data["props"]["pageProps"]

                            # Try multiple JSON paths for company/line info

                            # Path 1: Traditional station data structure
                            if "station" in page_props:
                                station_data = page_props["station"]
                                if "company" in station_data:
                                    details.company_name = station_data["company"]
                                if "line" in station_data:
                                    details.line_name = station_data["line"]

                            # Path 2: lipFeature.TransitSearchInfo.Detail structure (more common)
                            if not details.company_name and "lipFeature" in page_props:
                                lip_feature = page_props["lipFeature"]
                                if "TransitSearchInfo" in lip_feature:
                                    transit_info = lip_feature["TransitSearchInfo"]
                                    if "Detail" in transit_info:
                                        detail = transit_info["Detail"]
                                        if "CompanyName" in detail:
                                            details.company_name = detail["CompanyName"]
                                        if "RailName" in detail:
                                            details.line_name = detail["RailName"]

                    except (json.JSONDecodeError, KeyError):
                        continue

                # Also try to extract from URL parameters which contain company and line info
                if "?" in station_url:
                    from urllib.parse import parse_qs, urlparse

                    parsed_url = urlparse(station_url)
                    params = parse_qs(parsed_url.query)

                    if "company" in params:
                        # URL decode the company name
                        from urllib.parse import unquote

                        details.company_name = unquote(params["company"][0])

                    if "line" in params:
                        # URL decode the line name
                        from urllib.parse import unquote

                        details.line_name = unquote(params["line"][0])

                # City extraction removed - Yahoo Transit pages don't contain reliable city/ward data
                # Based on comprehensive analysis, no city information is extractable from page text

                # Station codes, coordinates, and line colors removed - fields deleted from Station model

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
        # Yahoo uses prefecture codes: 1=Hokkaido, 13=Tokyo, 14=Kanagawa, etc.
        # Support both padded (/01/) and unpadded (/1/) formats
        prefecture_map = {}

        # Create mapping for both padded and unpadded codes
        code_to_name = {
            "1": "北海道",
            "2": "青森県",
            "3": "岩手県",
            "4": "宮城県",
            "5": "秋田県",
            "6": "山形県",
            "7": "福島県",
            "8": "茨城県",
            "9": "栃木県",
            "10": "群馬県",
            "11": "埼玉県",
            "12": "千葉県",
            "13": "東京都",
            "14": "神奈川県",
            "15": "新潟県",
            "16": "富山県",
            "17": "石川県",
            "18": "福井県",
            "19": "山梨県",
            "20": "長野県",
            "21": "岐阜県",
            "22": "静岡県",
            "23": "愛知県",
            "24": "三重県",
            "25": "滋賀県",
            "26": "京都府",
            "27": "大阪府",
            "28": "兵庫県",
            "29": "奈良県",
            "30": "和歌山県",
            "31": "鳥取県",
            "32": "島根県",
            "33": "岡山県",
            "34": "広島県",
            "35": "山口県",
            "36": "徳島県",
            "37": "香川県",
            "38": "愛媛県",
            "39": "高知県",
            "40": "福岡県",
            "41": "佐賀県",
            "42": "長崎県",
            "43": "熊本県",
            "44": "大分県",
            "45": "宮崎県",
            "46": "鹿児島県",
            "47": "沖縄県",
        }

        # Add both formats to the map
        for code, name in code_to_name.items():
            prefecture_map[f"/{code}/"] = name
            prefecture_map[f"/{code.zfill(2)}/"] = name  # Also support zero-padded

        for code, prefecture in prefecture_map.items():
            if code in url:
                return prefecture

        return "東京都"  # Default to Tokyo

    def _get_company_from_line(self, line_name: str) -> str:
        """Extract railway company from line name.

        Args:
            line_name: Railway line name

        Returns:
            Railway company name
        """
        if "JR" in line_name:
            return "JR東日本"
        elif "東京メトロ" in line_name:
            return "東京メトロ"
        elif "都営" in line_name:
            return "都営地下鉄"
        elif "小田急" in line_name:
            return "小田急電鉄"
        elif "京急" in line_name:
            return "京浜急行電鉄"
        else:
            return "その他"

    def _deduplicate_stations(self) -> list[Station]:
        """Remove duplicate stations based on name and prefecture.

        Returns:
            List of unique stations
        """
        seen: set[tuple[str, str | None]] = set()
        unique_stations = []

        for station in self.stations:
            key = (station.name, station.prefecture)
            if key not in seen:
                seen.add(key)
                unique_stations.append(station)

        return unique_stations


class StationSearcher:
    """Search engine for station data with enhanced fuzzy search capabilities."""

    def __init__(self, stations: list[Station]):
        """Initialize searcher with station data.

        Args:
            stations: List of stations to search
        """
        self.stations = stations
        self._build_search_index()

        # Import fuzzy search dependencies
        try:
            from fuzzywuzzy import fuzz, process  # type: ignore[import-untyped]

            self._fuzz = fuzz
            self._process = process
            self._fuzzy_available = True
        except ImportError:
            self._fuzzy_available = False

    def _build_search_index(self) -> None:
        """Build search index for faster lookups with Japanese text variants."""
        self.name_index: dict[str, list[Station]] = {}
        self.hiragana_index: dict[str, list[Station]] = {}
        self.katakana_index: dict[str, list[Station]] = {}
        self.romaji_index: dict[str, list[Station]] = {}
        self.prefecture_index: dict[str, list[Station]] = {}

        # Build comprehensive search terms for each station (use index as key)
        self.search_terms: dict[int, list[str]] = {}

        for i, station in enumerate(self.stations):
            # Index by original name
            if station.name not in self.name_index:
                self.name_index[station.name] = []
            self.name_index[station.name].append(station)

            # Build comprehensive search terms list
            search_terms = [station.name]

            # Index by hiragana name
            if station.name_hiragana:
                if station.name_hiragana not in self.hiragana_index:
                    self.hiragana_index[station.name_hiragana] = []
                self.hiragana_index[station.name_hiragana].append(station)
                search_terms.append(station.name_hiragana)

            # Index by katakana name
            if station.name_katakana:
                if station.name_katakana not in self.katakana_index:
                    self.katakana_index[station.name_katakana] = []
                self.katakana_index[station.name_katakana].append(station)
                search_terms.append(station.name_katakana)

            # Index by romaji name
            if station.name_romaji:
                if station.name_romaji not in self.romaji_index:
                    self.romaji_index[station.name_romaji] = []
                self.romaji_index[station.name_romaji].append(station)
                search_terms.append(station.name_romaji)

            # Add aliases to search terms
            if station.aliases:
                search_terms.extend(station.aliases)

            # Store all search terms for this station (use index as key)
            self.search_terms[i] = search_terms

            # Index by prefecture
            if station.prefecture:
                if station.prefecture not in self.prefecture_index:
                    self.prefecture_index[station.prefecture] = []
                self.prefecture_index[station.prefecture].append(station)

    def search_by_name(
        self, query: str, exact: bool = False, fuzzy_threshold: int = 70
    ) -> list[Station]:
        """Search stations by name with enhanced fuzzy matching across Japanese text formats.

        Args:
            query: Search query (can be kanji, hiragana, katakana, or romaji)
            exact: Whether to perform exact match
            fuzzy_threshold: Minimum fuzzy match score (0-100) for results

        Returns:
            List of matching stations sorted by relevance
        """
        if exact:
            # Check all indexes for exact matches
            results = []
            results.extend(self.name_index.get(query, []))
            results.extend(self.hiragana_index.get(query, []))
            results.extend(self.katakana_index.get(query, []))
            results.extend(self.romaji_index.get(query, []))

            # Remove duplicates while preserving order using station IDs
            seen_ids = set()
            unique_results = []
            for station in results:
                station_id = id(station)  # Use object id as unique identifier
                if station_id not in seen_ids:
                    unique_results.append(station)
                    seen_ids.add(station_id)
            return unique_results

        # Enhanced fuzzy search
        results = []
        query_lower = query.lower()

        # First pass: collect exact alias matches and all other matches separately
        exact_alias_matches = []
        all_other_matches = []

        for i, station in enumerate(self.stations):
            has_exact_alias = False
            best_other_score = 0

            # Check all search terms for this station using index
            search_terms = self.search_terms[i]

            # Check main station fields (name, hiragana, katakana, romaji)
            main_terms = [
                station.name,
                station.name_hiragana,
                station.name_katakana,
                station.name_romaji,
            ]
            main_terms = [t for t in main_terms if t]  # Remove None values

            # Check aliases
            aliases = station.aliases if station.aliases else []

            for term in search_terms:
                term_lower = term.lower()
                if query_lower == term_lower:
                    if term in aliases:
                        has_exact_alias = True
                        break  # Found exact alias match
                    else:
                        best_other_score = max(
                            best_other_score, 100
                        )  # Exact match on main field
                elif query_lower in term_lower:
                    best_other_score = max(best_other_score, 90)  # Substring match

            if has_exact_alias:
                exact_alias_matches.append((station, 100))
            elif best_other_score > 0:
                all_other_matches.append((station, best_other_score))

        # If we have exact alias matches, return only those
        # Otherwise return all other matches (exact name matches + substring matches)
        results_with_scores = []
        if exact_alias_matches:
            results_with_scores = exact_alias_matches
        else:
            results_with_scores = all_other_matches

        # Third pass: fuzzy matching if available and no matches found
        if not results_with_scores and self._fuzzy_available:
            # Create a flat list of all search terms with their stations
            all_terms = []
            term_to_stations: dict[str, list[Station]] = {}

            for i, station in enumerate(self.stations):
                for term in self.search_terms[i]:
                    all_terms.append(term)
                    if term not in term_to_stations:
                        term_to_stations[term] = []
                    term_to_stations[term].append(station)

            # Use fuzzywuzzy to find best matches
            fuzzy_matches = self._process.extract(
                query, all_terms, limit=20, scorer=self._fuzz.ratio
            )

            for match in fuzzy_matches:
                term, score = match[0], match[1]
                if score >= fuzzy_threshold:
                    for station in term_to_stations[term]:
                        results_with_scores.append((station, score))

        # Remove duplicates and sort by score using station IDs
        seen_station_ids: set[int] = set()
        scored_results: list[tuple[Station, int]] = []
        for station, score in results_with_scores:
            station_id = id(station)  # Use object id as unique identifier
            if station_id not in seen_station_ids:
                scored_results.append((station, score))
                seen_station_ids.add(station_id)

        # Sort by score (highest first) then by name
        scored_results.sort(key=lambda x: (-x[1], x[0].name))

        return [station for station, _score in scored_results]

    def search_by_prefecture(self, prefecture: str) -> list[Station]:
        """Search stations by prefecture.

        Args:
            prefecture: Prefecture name

        Returns:
            List of stations in the prefecture
        """
        return self.prefecture_index.get(prefecture, [])

    def get_all_prefectures(self) -> list[str]:
        """Get list of all prefectures in the database.

        Returns:
            List of prefecture names
        """
        return sorted([p for p in self.prefecture_index.keys() if p])

    def search_stations(
        self, query: str, limit: int = 10, fuzzy_threshold: int = 70
    ) -> list[Station]:
        """Search stations with limit and fuzzy matching.

        Args:
            query: Search query (can be in any Japanese text format)
            limit: Maximum number of results
            fuzzy_threshold: Minimum fuzzy match score (0-100)

        Returns:
            List of matching stations (up to limit) sorted by relevance
        """
        results = self.search_by_name(
            query, exact=False, fuzzy_threshold=fuzzy_threshold
        )
        return results[:limit]

    def fuzzy_search(
        self, query: str, limit: int = 10, threshold: int = 60
    ) -> list[tuple[Station, int]]:
        """Perform fuzzy search and return results with scores.

        Args:
            query: Search query
            limit: Maximum number of results
            threshold: Minimum fuzzy match score (0-100)

        Returns:
            List of (Station, score) tuples sorted by score
        """
        if not self._fuzzy_available:
            # Fallback to basic search
            stations = self.search_by_name(query, exact=False)
            return [(station, 100) for station in stations[:limit]]

        # Create comprehensive search terms list
        all_terms = []
        term_to_stations: dict[str, list[Station]] = {}

        for i, station in enumerate(self.stations):
            for term in self.search_terms[i]:
                all_terms.append(term)
                if term not in term_to_stations:
                    term_to_stations[term] = []
                term_to_stations[term].append(station)

        # Get fuzzy matches
        fuzzy_matches = self._process.extract(
            query, all_terms, limit=limit * 3, scorer=self._fuzz.ratio
        )

        # Build results with scores
        results: list[tuple[Station, int]] = []
        seen: set[int] = set()

        for match in fuzzy_matches:
            term, score = match[0], match[1]
            if score >= threshold:
                for station in term_to_stations[term]:
                    station_id = id(station)  # Use object id as unique identifier
                    if station_id not in seen:
                        results.append((station, score))
                        seen.add(station_id)

        # Sort by score and limit results
        results.sort(key=lambda x: -x[1])
        return results[:limit]

    def get_station_by_name(self, station_name: str) -> Station | None:
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
        prefecture: str | None = None,
        line: str | None = None,
        limit: int = 50,
    ) -> list[Station]:
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
            stations = [
                s
                for s in stations
                if s.line_name and line.lower() in s.line_name.lower()
            ]

        return stations[:limit]
