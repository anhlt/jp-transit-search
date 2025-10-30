#!/usr/bin/env python3
"""
Quick Start Script for Japanese Transit Search MCP Server

This script helps you quickly test the installation and generate sample CSV files.
Run this after installation to verify everything is working correctly.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

def print_banner():
    """Print welcome banner."""
    print("🚅" * 50)
    print("🌟 Japanese Transit Search MCP Server - Quick Start")
    print("🚅" * 50)
    print()

async def test_mcp_server():
    """Test MCP server functionality."""
    print("📡 Testing MCP Server...")
    
    try:
        from jp_transit_search.mcp.server import TransitMCPServer
        
        server = TransitMCPServer()
        print(f"✅ Server initialized with {len(server.station_searcher.stations)} stations")
        
        # Test search functionality
        result = await server._search_stations({"query": "東京", "limit": 3})
        print("✅ Station search working")
        
        # Test route search
        result = await server._search_route({
            "from_station": "新宿",
            "to_station": "東京",
            "departure_time": "09:00"
        })
        print("✅ Route search working")
        
        return True
        
    except Exception as e:
        print(f"❌ MCP Server test failed: {e}")
        return False

async def test_csv_operations():
    """Test CSV functionality using MCP server's sample data."""
    print("\n💾 Testing CSV Operations...")
    
    try:
        from jp_transit_search.mcp.server import TransitMCPServer
        
        # Use MCP server which has sample stations ready
        server = TransitMCPServer()
        stations = server.station_searcher.stations
        print(f"✅ Using {len(stations)} sample stations from MCP server")
        
        # Test CSV save via MCP server tools
        result = await server._save_stations_csv({"filename": "quickstart_test.csv"})
        print("✅ CSV save via MCP server working")
        
        # Test CSV load via MCP server tools
        result = await server._load_stations_csv({"filename": "quickstart_test.csv"})
        print("✅ CSV load via MCP server working")
        
        # Clean up test file
        Path("quickstart_test.csv").unlink()
        print("✅ Test file cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ CSV test failed: {e}")
        return False

async def generate_sample_csv():
    """Generate sample CSV files for user."""
    print("\n📊 Generating Sample CSV Files...")
    
    try:
        from jp_transit_search.mcp.server import TransitMCPServer
        
        server = TransitMCPServer()
        
        # Generate timestamped CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sample_stations_{timestamp}.csv"
        
        result = await server._save_stations_csv({"filename": filename})
        print(f"✅ Generated: {filename}")
        
        # Print CSV info
        csv_path = Path(filename)
        if csv_path.exists():
            size = csv_path.stat().st_size
            with open(csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            print(f"📄 File size: {size} bytes")
            print(f"📄 Lines: {len(lines)} (including header)")
            print(f"📄 Sample header: {lines[0].strip()}")
            
            if len(lines) > 1:
                print(f"📄 Sample data: {lines[1].strip()[:100]}...")
        
        return filename
        
    except Exception as e:
        print(f"❌ CSV generation failed: {e}")
        return None

def print_next_steps(csv_file):
    """Print next steps for the user."""
    print("\n🎉 Quick Start Complete!")
    print("\n📋 What You Can Do Next:")
    print(f"   1. Start MCP Server: uv run jp-transit-mcp")
    print(f"   2. View your CSV file: cat {csv_file}")
    print(f"   3. Run full tests: uv run pytest")
    print(f"   4. Try the Python API examples in README.md")
    print(f"   5. Integrate with MCP-compatible AI assistants")
    
    print("\n🔧 Available Commands:")
    print("   • uv run jp-transit-mcp           # Start MCP server")
    print("   • uv run jp-transit --help        # CLI help")
    print("   • uv run pytest -v               # Run tests")
    print("   • uv run python create_csv.py    # Generate more CSV files")
    
    print("\n📚 Documentation:")
    print("   • README.md - Full documentation")
    print("   • tests/ - Usage examples")
    print("   • src/jp_transit_search/ - Source code")

async def main():
    """Main quick start routine."""
    print_banner()
    
    # Test installation
    print("🔍 Checking Installation...")
    
    try:
        import jp_transit_search
        print("✅ Package imported successfully")
    except ImportError as e:
        print(f"❌ Package import failed: {e}")
        print("💡 Try: uv pip install -e .")
        sys.exit(1)
    
    # Run tests
    success_count = 0
    
    if await test_mcp_server():
        success_count += 1
    
    if await test_csv_operations():
        success_count += 1
    
    csv_file = await generate_sample_csv()
    if csv_file:
        success_count += 1
    
    # Summary
    print(f"\n📊 Quick Start Results: {success_count}/3 tests passed")
    
    if success_count == 3:
        print("🎉 All tests passed! Your installation is working perfectly.")
        print_next_steps(csv_file or "sample_stations.csv")
    else:
        print("⚠️  Some tests failed. Check the error messages above.")
        print("💡 Try running: uv sync && uv pip install -e .")

if __name__ == "__main__":
    asyncio.run(main())