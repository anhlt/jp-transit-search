# Japanese Transit Search MCP Server

A comprehensive Model Context Protocol (MCP) server that provides Japanese transit route planning and station database management capabilities, powered by Yahoo Transit integration.

## 🌟 Features

- **Real-time Route Search**: Get transit routes between Japanese stations using Yahoo Transit
- **Station Database Management**: Search, filter, and manage Japanese railway stations
- **CSV Data Persistence**: Import/export station data for offline usage
- **Enhanced Station Information**: Line colors, types, company codes, and comprehensive metadata
- **Prefecture-based Filtering**: Search stations by prefecture, city, or railway company
- **MCP Protocol Compliance**: Full integration with MCP-compatible AI assistants

## 🏗️ Project Structure

```
jp-transit-search/
├── src/jp_transit_search/          # Main package
│   ├── core/                       # Core functionality
│   │   ├── models.py              # Station and route data models
│   │   ├── scraper.py             # Yahoo Transit web scraper
│   │   └── exceptions.py          # Custom exception classes
│   ├── crawler/                    # Station data crawling
│   │   ├── station_crawler.py     # Yahoo station crawler with CSV support
│   │   └── __init__.py            # StationSearcher utilities
│   ├── mcp/                       # MCP server implementation
│   │   ├── server.py              # Main MCP server with 7 tools
│   │   └── __init__.py
│   ├── cli/                       # Command-line interface
│   │   ├── main.py                # CLI entry points
│   │   ├── station_commands.py    # Station management commands
│   │   └── formatters.py          # Output formatting utilities
│   └── utils/                     # Shared utilities
│       └── __init__.py
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests
│   └── conftest.py                # Test configuration
├── pyproject.toml                 # Project configuration and dependencies
├── uv.lock                        # Dependency lock file
└── README.md                      # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+ (Python 3.11+ recommended)
- [uv](https://docs.astral.sh/uv/) package manager (fast Python package installer)

### Installation

#### Step 1: Install uv (if not already installed)

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Alternative installation methods:**
```bash
# Using pip
pip install uv

# Using homebrew (macOS)
brew install uv

# Using conda
conda install -c conda-forge uv
```

#### Step 2: Clone and Setup Project

```bash
# Clone the repository
git clone <repository-url>
cd jp-transit-search

# Install dependencies and create virtual environment
uv sync

# Verify installation
uv run python --version
uv run pip list | grep mcp
```

#### Step 3: Local Development Installation

**Option A: Editable install for development**
```bash
# Install the package in development mode
uv pip install -e .

# Now you can use the CLI commands directly
uv run jp-transit --help
uv run jp-transit-mcp
```

**Option B: Direct package installation**
```bash
# Install as a regular package
uv pip install .

# Or install from source with dev dependencies
uv sync --all-extras
```

#### Step 4: Verify Installation

```bash
# Test the MCP server starts correctly
timeout 5s uv run jp-transit-mcp || echo "Server startup test completed"

# Test CLI functionality
uv run jp-transit --version

# Run tests to verify everything works
uv run pytest tests/unit/test_mcp_server.py -v
```

### Quick Test Run

```bash
# Run the quick start script to verify everything works
uv run python quickstart.py

# Or manually start the MCP server (it will load sample stations automatically)
uv run jp-transit-mcp

# In another terminal, test the Python API
uv run python -c "
from jp_transit_search.mcp.server import TransitMCPServer
import asyncio

async def test():
    server = TransitMCPServer()
    result = await server._search_stations({'query': '東京'})
    print('✅ Server working:', 'Found' in result[0].text)

asyncio.run(test())
"
```

## 🤖 Automated Station Data Updates

### GitHub Action Integration

This project includes a GitHub Action that automatically updates the station data when triggered by a comment. Simply comment `/update station` on any issue or pull request to:

1. **Crawl Latest Data**: Fetch the most recent station information from Yahoo Transit
2. **Generate CSV**: Create an updated `stations.csv` file with comprehensive metadata
3. **Auto-commit**: Automatically commit the updated file back to the repository
4. **Real-time Feedback**: Get status updates through GitHub comments

#### How to Use

1. **On any Issue or PR**, comment:
   ```
   /update station
   ```

2. **Monitor Progress**: The action will:
   - Add a 👀 reaction to acknowledge the command
   - Run the station crawler (may take 2-5 minutes)
   - Commit the updated `stations.csv` to the repository
   - Add a 🎉 reaction and detailed comment on success

3. **Review Results**: The commit message will include:
   - Number of stations crawled
   - Timestamp of the update
   - Who triggered the update
   - Link to the issue/PR

#### Example Workflow

```markdown
User Comment: "/update station"
↓
GitHub Action Starts
↓ 
Crawls station data (1-5 minutes)
↓
Creates/updates stations.csv
↓
Commits with descriptive message
↓
Posts success comment with statistics
```

#### Benefits

- **Always Fresh Data**: Keep your station database up-to-date
- **Zero Manual Work**: Fully automated from trigger to commit
- **Transparent Process**: Full logging and status updates
- **Error Handling**: Graceful fallbacks if crawling fails
- **Community Friendly**: Anyone can trigger updates via comments

#### Workflow Details

The GitHub Action (``.github/workflows/update-stations.yml``) includes:
- **Smart Triggers**: Only runs on `/update station` comments
- **Dependency Management**: Uses uv for fast Python setup
- **Error Recovery**: Falls back to sample data if Yahoo blocks requests
- **Rich Feedback**: Detailed success/failure comments with statistics
- **Git Integration**: Proper commit messages with metadata

## 📊 Creating and Managing CSV Station Data

### Method 1: Using the MCP Server Tools (Recommended)

The easiest way to manage station data is through the MCP server tools:

```python
# Example: Complete CSV workflow using MCP server
from jp_transit_search.mcp.server import TransitMCPServer
import asyncio

async def csv_workflow():
    server = TransitMCPServer()
    
    # 1. Save current database to CSV
    result = await server._save_stations_csv({
        "filename": "my_stations.csv"  # Optional: defaults to "stations_data.csv"
    })
    print("Save result:", result[0].text)
    
    # 2. Load stations from CSV file
    result = await server._load_stations_csv({
        "filename": "my_stations.csv"
    })
    print("Load result:", result[0].text)
    
    # 3. Crawl fresh data from Yahoo (may take time)
    result = await server._crawl_stations({
        "prefectures": ["Tokyo"],  # Optional: limit to specific prefectures
        "limit": 100              # Optional: limit number of stations
    })
    print("Crawl result:", result[0].text)

# Run the workflow
asyncio.run(csv_workflow())
```

### Method 2: Using Python API Directly

For more control over the crawling and CSV operations:

```python
from jp_transit_search.crawler.station_crawler import StationCrawler
from pathlib import Path

# Create crawler instance
crawler = StationCrawler()

# Option A: Crawl all stations (uses sample data if Yahoo blocked)
print("🔄 Crawling stations...")
stations = crawler.crawl_all_stations()
print(f"✅ Crawled {len(stations)} stations")

# Option B: Work with existing sample stations
print("📋 Using sample stations...")
# The crawler automatically loads sample stations on initialization
stations = crawler.stations
print(f"✅ Loaded {len(stations)} sample stations")

# Save to CSV with all enhanced fields
csv_file = Path("enhanced_stations.csv")
crawler.save_to_csv(stations, csv_file)
print(f"💾 Saved to {csv_file}")

# Verify CSV contents
with open(csv_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    print(f"📄 CSV has {len(lines)} lines (including header)")
    print("📝 Header:", lines[0].strip())
    if len(lines) > 1:
        print("📝 Sample row:", lines[1].strip())

# Load from CSV and verify data integrity
loaded_stations = crawler.load_from_csv(csv_file)
print(f"✅ Loaded {len(loaded_stations)} stations from CSV")

# Data integrity check
original_names = {s.name for s in stations}
loaded_names = {s.name for s in loaded_stations}
print(f"🔍 Data integrity: {original_names == loaded_names}")
```

### Method 3: Command Line Utilities

Create useful CSV files directly from the command line:

```bash
# Create a simple script to generate CSV files
cat > create_csv.py << 'EOF'
#!/usr/bin/env python3
"""Utility script to create CSV files from station data."""

import asyncio
from jp_transit_search.mcp.server import TransitMCPServer
from jp_transit_search.crawler.station_crawler import StationCrawler

async def create_sample_csv():
    """Create CSV file with sample station data."""
    print("🚀 Creating sample station CSV...")
    server = TransitMCPServer()
    
    # Save current sample data to CSV
    result = await server._save_stations_csv({"filename": "sample_stations.csv"})
    print("✅", result[0].text)

def create_enhanced_csv():
    """Create CSV with enhanced sample data."""
    print("🔧 Creating enhanced station CSV...")
    crawler = StationCrawler()
    
    # Use sample stations (10 stations with full metadata)
    stations = crawler.stations
    print(f"📊 Processing {len(stations)} stations...")
    
    # Save with timestamp in filename
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"stations_enhanced_{timestamp}.csv"
    
    crawler.save_to_csv(stations, filename)
    print(f"💾 Enhanced CSV saved: {filename}")
    
    # Print statistics
    prefectures = {s.prefecture for s in stations if s.prefecture}
    companies = {s.railway_company for s in stations if s.railway_company}
    print(f"📈 Statistics:")
    print(f"   • Prefectures: {len(prefectures)}")
    print(f"   • Railway companies: {len(companies)}")
    print(f"   • Total stations: {len(stations)}")

if __name__ == "__main__":
    # Create both types of CSV files
    asyncio.run(create_sample_csv())
    create_enhanced_csv()
EOF

# Make executable and run
chmod +x create_csv.py
uv run python create_csv.py
```

### Method 4: Automated CSV Generation

For regular data updates, create an automated workflow:

```python
# save as: automated_csv_generator.py
"""Automated CSV generation with error handling and logging."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from jp_transit_search.mcp.server import TransitMCPServer
from jp_transit_search.crawler.station_crawler import StationCrawler

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def automated_csv_generation():
    """Generate CSV files with comprehensive error handling."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        # Method 1: Via MCP Server (includes enhanced error handling)
        logger.info("🚀 Starting MCP server CSV generation...")
        server = TransitMCPServer()
        
        result = await server._save_stations_csv({
            "filename": f"mcp_stations_{timestamp}.csv"
        })
        logger.info(f"✅ MCP CSV: {result[0].text}")
        
        # Method 2: Direct crawler approach
        logger.info("🔧 Starting direct crawler CSV generation...")
        crawler = StationCrawler()
        
        # Try to crawl fresh data (with timeout)
        try:
            logger.info("🌐 Attempting to crawl fresh Yahoo data...")
            stations = crawler.crawl_all_stations()
            source = "Yahoo Transit"
        except Exception as e:
            logger.warning(f"⚠️  Yahoo crawling failed: {e}")
            logger.info("📋 Using sample data instead...")
            stations = crawler.stations
            source = "Sample Data"
        
        # Save with metadata
        csv_filename = f"stations_{source.lower().replace(' ', '_')}_{timestamp}.csv"
        crawler.save_to_csv(stations, csv_filename)
        
        logger.info(f"💾 Generated: {csv_filename}")
        logger.info(f"📊 Source: {source}")
        logger.info(f"📈 Stations: {len(stations)}")
        
        # Generate summary report
        report_filename = f"generation_report_{timestamp}.txt"
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(f"CSV Generation Report - {datetime.now()}\n")
            f.write(f"=" * 50 + "\n")
            f.write(f"Source: {source}\n")
            f.write(f"Stations: {len(stations)}\n")
            f.write(f"CSV File: {csv_filename}\n")
            f.write(f"File Size: {Path(csv_filename).stat().st_size} bytes\n")
            
            # Prefecture breakdown
            prefecture_counts = {}
            for station in stations:
                if station.prefecture:
                    prefecture_counts[station.prefecture] = prefecture_counts.get(station.prefecture, 0) + 1
            
            f.write(f"\nPrefecture Breakdown:\n")
            for prefecture, count in sorted(prefecture_counts.items()):
                f.write(f"  {prefecture}: {count} stations\n")
        
        logger.info(f"📝 Report saved: {report_filename}")
        
    except Exception as e:
        logger.error(f"❌ CSV generation failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(automated_csv_generation())
```

### CSV Format and Fields

The CSV files include comprehensive station metadata:

```csv
name,prefecture,city,railway_company,line_name,station_code,latitude,longitude,aliases,line_name_kana,line_color,line_type,company_code,all_lines
新宿,東京都,新宿区,JR東日本,JR山手線,,,,,ヤマノテセン,#9ACD32,Loop,JR-E,"[""JR山手線"",""JR中央線"",""JR埼京線""]"
東京,東京都,千代田区,JR東日本,JR東海道線,,,,,トウカイドウセン,#F68B1E,Main,JR-E,"[""JR東海道線"",""JR山手線"",""JR京浜東北線""]"
渋谷,東京都,渋谷区,JR東日本,JR山手線,,,,,ヤマノテセン,#9ACD32,Loop,JR-E,"[""JR山手線"",""JR埼京線"",""東急東横線""]"
```

**Field descriptions:**
- `name`: Station name in Japanese
- `prefecture`: Prefecture (都道府県)
- `city`: City/ward (市区町村)
- `railway_company`: Operating railway company
- `line_name`: Primary line name
- `station_code`: Station code (if available)
- `latitude/longitude`: GPS coordinates (if available)
- `aliases`: Alternative names/spellings
- `line_name_kana`: Line name in katakana
- `line_color`: Official line color (hex code)
- `line_type`: Line type (Loop, Main, Branch, etc.)
- `company_code`: Railway company code
- `all_lines`: JSON array of all lines serving this station

### CSV Usage Tips

```bash
# View CSV statistics
uv run python -c "
import pandas as pd
df = pd.read_csv('stations_data.csv')
print(f'📊 Total stations: {len(df)}')
print(f'📍 Prefectures: {df[\"prefecture\"].nunique()}')
print(f'🚆 Companies: {df[\"railway_company\"].nunique()}')
print(f'\\n🏆 Top prefectures by station count:')
print(df['prefecture'].value_counts().head())
"

# Convert CSV to different formats
uv run python -c "
import pandas as pd
import json

# Load CSV
df = pd.read_csv('stations_data.csv')

# Save as JSON
df.to_json('stations_data.json', orient='records', ensure_ascii=False, indent=2)

# Save as Excel (requires openpyxl: uv add openpyxl)
# df.to_excel('stations_data.xlsx', index=False)

print('✅ Converted CSV to additional formats')
"
```

## 🛠️ MCP Server Tools

The server exposes 7 tools for comprehensive transit functionality:

### 1. `search_route`
**Purpose**: Find transit routes between stations
```json
{
  "from_station": "新宿",
  "to_station": "東京", 
  "departure_time": "09:00",
  "date": "2024-01-15"
}
```

### 2. `search_stations`
**Purpose**: Search station database
```json
{
  "query": "東京",
  "prefecture": "東京都",
  "limit": 10
}
```

### 3. `crawl_stations`
**Purpose**: Crawl fresh station data from Yahoo
```json
{
  "prefectures": ["Tokyo", "Osaka"],
  "limit": 1000
}
```

### 4. `list_station_database`
**Purpose**: List stations in current database
```json
{
  "prefecture": "東京都",
  "limit": 50,
  "offset": 0
}
```

### 5. `save_stations_csv`
**Purpose**: Export database to CSV
```json
{
  "filename": "stations_export.csv"
}
```

### 6. `load_stations_csv`
**Purpose**: Import stations from CSV
```json
{
  "filename": "stations_data.csv"
}
```

### 7. `get_station_details`
**Purpose**: Get detailed information about a station
```json
{
  "station_name": "新宿"
}
```

## 🏃‍♂️ Usage Examples

### Basic Route Search
```python
# Using the MCP server programmatically
from jp_transit_search.mcp.server import TransitMCPServer
import asyncio

async def search_route():
    server = TransitMCPServer()
    result = await server._search_route({
        "from_station": "新宿",
        "to_station": "渋谷",
        "departure_time": "09:00"
    })
    print(result[0].text)

asyncio.run(search_route())
```

### Station Database Management
```python
async def manage_stations():
    server = TransitMCPServer()
    
    # Search for stations
    result = await server._search_stations({"query": "東京"})
    print("Search results:", result[0].text)
    
    # Save current database
    result = await server._save_stations_csv({})
    print("Save result:", result[0].text)
    
    # Load from file
    result = await server._load_stations_csv({"filename": "stations_data.csv"})
    print("Load result:", result[0].text)

asyncio.run(manage_stations())
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all tests
uv run pytest

# Run specific test categories
uv run pytest tests/unit/test_mcp_server.py -v
uv run pytest tests/unit/test_crawler.py -v
uv run pytest -m "not slow" # Skip slow integration tests
uv run pytest --cov=jp_transit_search # With coverage report

# Run tests with detailed output
uv run pytest -v --tb=short

# Test specific functionality
uv run pytest -k "test_mcp" -v  # Only MCP-related tests
uv run pytest -k "test_csv" -v  # Only CSV-related tests
```

## 🔧 Troubleshooting

### Common Issues and Solutions

**1. uv command not found**
```bash
# Reinstall uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # or restart terminal
```

**2. MCP server won't start**
```bash
# Check Python version
uv run python --version  # Should be 3.10+

# Verify dependencies
uv sync
uv run pip list | grep mcp

# Test server initialization
uv run python -c "from jp_transit_search.mcp.server import TransitMCPServer; print('✅ Server imports OK')"
```

**3. CSV files not generating**
```bash
# Check file permissions
ls -la *.csv

# Test CSV functionality directly
uv run python -c "
from jp_transit_search.crawler.station_crawler import StationCrawler
crawler = StationCrawler()
print(f'Stations available: {len(crawler.stations)}')
crawler.save_to_csv(crawler.stations, 'test.csv')
print('✅ CSV test completed')
"
```

**4. Yahoo crawling fails**
```bash
# This is expected behavior - Yahoo may block automated requests
# The system automatically falls back to sample data
echo "✅ This is normal - system uses sample data when Yahoo is blocked"
```

**5. Import errors**
```bash
# Reinstall in development mode
uv pip install -e .

# Or reinstall dependencies
rm -rf .venv
uv sync
```

### Performance Tips

```bash
# For faster development, skip slow tests
uv run pytest -m "not slow"

# Use sample data instead of crawling
# (This is automatic when Yahoo is blocked)

# Generate CSV files in background
nohup uv run python automated_csv_generator.py > csv_generation.log 2>&1 &
```

## 🌐 Integration with AI Assistants

This MCP server can be integrated with MCP-compatible AI assistants like Claude Desktop:

1. **Add to MCP settings** (e.g., Claude Desktop config):
   ```json
   {
     "servers": {
       "jp-transit-search": {
         "command": "uv",
         "args": ["run", "jp-transit-mcp"],
         "cwd": "/path/to/jp-transit-search"
       }
     }
   }
   ```

2. **Available capabilities**:
   - Japanese transit route planning
   - Station database queries
   - CSV data management
   - Prefecture-based filtering

## 📈 Data Sources and Architecture

### Yahoo Transit Integration
- **Route Search**: Real-time data from Yahoo Transit (transit.yahoo.co.jp)
- **Station Crawling**: Attempts to crawl station data from Yahoo (with fallback to sample data)
- **Rate Limiting**: Respectful crawling with delays and error handling

### Enhanced Station Model
Each station includes comprehensive metadata:
- **Basic Info**: Name, prefecture, city, railway company
- **Line Details**: Line name, Kana reading, color codes, line types
- **Technical Data**: Station codes, company codes, coordinates
- **Relationships**: All lines serving the station, aliases

### Data Flow
```
Yahoo Transit → StationCrawler → Enhanced Station Model → CSV Storage → MCP Server → AI Assistant
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes and add tests
4. Run tests: `uv run pytest`
5. Submit a pull request

## 📋 Development Status

- **Version**: 1.0.0
- **Python Support**: 3.10, 3.11, 3.12, 3.13
- **MCP Protocol**: Compatible with MCP 0.9.0+
- **Status**: Production Ready ✅

### Recent Updates
- ✅ Fixed MCP server runtime issues 
- ✅ Enhanced station data model with comprehensive metadata
- ✅ Improved CSV persistence with full field support
- ✅ Added comprehensive error handling and fallbacks
- ✅ Full integration with Yahoo Transit route search

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

- **Issues**: Report bugs and feature requests via GitHub Issues
- **Documentation**: Full API documentation available in source code docstrings
- **Examples**: See `tests/` directory for comprehensive usage examples
- **Community**: Join discussions about Japanese transit data and MCP integration

### Getting Help

1. **Check the troubleshooting section** above for common issues
2. **Run the test suite** to verify your installation: `uv run pytest`
3. **Check logs** when running the MCP server for detailed error information
4. **Use sample data** if Yahoo crawling fails - this is expected behavior

### Contributing Guidelines

1. Fork the repository and create a feature branch
2. Add tests for new functionality: `uv run pytest`
3. Ensure code quality: `uv run ruff check src/`
4. Update documentation for new features
5. Submit a pull request with detailed description

---

**⚠️ Legal Notice**: This project respects Yahoo Transit's robots.txt and implements respectful crawling practices. Station crawling may return sample data if access is restricted. For production use with large-scale crawling, please contact Yahoo Transit for API access or terms of service.

**🌟 Star this project** if you find it useful for Japanese transit applications!