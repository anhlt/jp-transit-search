# Enhanced Station Crawling Features

## Resume-able Crawling System

The station crawler now supports resumable crawling with detailed progress tracking and CSV-based deduplication.

### Key Features

🔄 **Resumable Operations**: Interrupted crawls can be resumed from the last checkpoint
📊 **Progress Tracking**: Real-time statistics on stations found, duplicates filtered, and crawling speed
💾 **Periodic Checkpointing**: Automatic saves every 50 stations to prevent data loss
🔍 **Smart Deduplication**: Uses existing CSV data to avoid duplicate station entries
⚡ **Enhanced Error Handling**: Continues crawling even when individual sources fail

### Usage Examples

#### Basic Crawling
```bash
# Start a new crawl
jp-transit stations crawl

# Specify output file and timeout
jp-transit stations crawl --output my_stations.csv --timeout 60
```

#### Resumable Crawling
```bash
# Resume from interrupted crawl
jp-transit stations crawl --resume

# Resume with custom state file
jp-transit stations crawl --resume --state-file my_crawl_state.json
```

### Progress Display

The crawler shows detailed real-time progress:

```
Prefecture: 東京都 | Line: JR山手線 | Stations: 1,247 | Filtered: 23
Found: 1,247 | Duplicates: 23 | Time: 15:42 | Errors: 2
```

- **Prefecture/Line**: Current location being crawled
- **Stations**: Total unique stations found
- **Filtered**: Duplicate stations detected and skipped
- **Time**: Elapsed crawling time
- **Errors**: Failed requests (with automatic retries)

### File Management

#### Output Files
- **CSV File**: `data/stations.csv` (default) - Station data in CSV format
- **State File**: `data/crawl_state.json` (default) - Resume state tracking

#### Resume Behavior
- Loads existing stations from CSV for deduplication
- Reads previous crawling state from JSON file
- Skips already completed prefectures and railway lines
- Appends new stations to existing CSV file
- Automatically cleans up state file on successful completion

### Technical Implementation

#### Progress Tracking
```python
class CrawlingProgress:
    - stations_found: int
    - duplicates_filtered: int  
    - prefectures_completed: int
    - lines_completed: int
    - current_prefecture: str
    - current_line: str
    - errors: int
    - start_time: datetime
```

#### Checkpoint System
- Saves progress every 50 stations (configurable)
- Tracks completed prefectures and railway lines
- Preserves crawling state across interruptions
- Supports graceful interruption with Ctrl+C

#### Deduplication Strategy
Uses `(station_name, prefecture)` as unique key:
1. Loads existing stations from CSV into memory
2. Checks each new station against existing set
3. Only adds truly new stations to output
4. Tracks duplicate count for statistics

### Error Recovery

The enhanced crawler handles various failure scenarios:

- **Network timeouts**: Automatic retry with exponential backoff
- **Parsing errors**: Skip problematic pages and continue  
- **Interrupted crawls**: Resume from last successful checkpoint
- **Duplicate detection**: Smart filtering prevents data corruption

This makes the crawler much more robust for large-scale station data collection operations.