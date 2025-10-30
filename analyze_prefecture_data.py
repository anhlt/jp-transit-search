#!/usr/bin/env python3
"""
Analyze current prefecture data and create mapping for prefecture IDs.
"""

import csv
from collections import Counter
from pathlib import Path

def analyze_prefecture_data():
    """Analyze existing prefecture data in stations.csv"""
    csv_path = Path("data/stations.csv")
    
    if not csv_path.exists():
        print(f"❌ {csv_path} not found")
        return
    
    prefecture_counts = Counter()
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            prefecture = row.get('prefecture', '').strip()
            if prefecture:
                prefecture_counts[prefecture] += 1
    
    print("Current Prefecture Distribution:")
    print("=" * 50)
    for prefecture, count in prefecture_counts.most_common():
        print(f"{prefecture}: {count} stations")
    
    return prefecture_counts

def create_prefecture_mapping():
    """Create standard prefecture ID mapping"""
    # JIS X 0401 prefecture codes (ISO 3166-2:JP)
    prefecture_mapping = {
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
        "沖縄県": "47"
    }
    
    print("\nPrefecture ID Mapping (JIS X 0401):")
    print("=" * 50)
    for name, code in prefecture_mapping.items():
        print(f"{code}: {name}")
    
    return prefecture_mapping

def test_mapping_against_data():
    """Test how well our mapping covers the existing data"""
    prefecture_counts = analyze_prefecture_data()
    prefecture_mapping = create_prefecture_mapping()
    
    print("\nMapping Coverage Analysis:")
    print("=" * 50)
    
    mapped = 0
    unmapped = 0
    
    for prefecture, count in prefecture_counts.items():
        if prefecture in prefecture_mapping:
            print(f"✅ {prefecture} ({count} stations) -> {prefecture_mapping[prefecture]}")
            mapped += count
        else:
            print(f"❌ {prefecture} ({count} stations) -> NO MAPPING")
            unmapped += count
    
    total = mapped + unmapped
    print(f"\nSummary:")
    print(f"Mapped: {mapped}/{total} stations ({mapped/total*100:.1f}%)")
    print(f"Unmapped: {unmapped}/{total} stations ({unmapped/total*100:.1f}%)")
    
    return prefecture_mapping

if __name__ == "__main__":
    mapping = test_mapping_against_data()
    
    print(f"\n🔍 Prefecture extraction from Yahoo Transit pages:")
    print("From our analysis, we found prefecture mentions in page text:")
    print("- Shinjuku: '東京都', '埼玉県' (multiple prefectures mentioned)")
    print("- Other pages may have prefecture info in breadcrumbs or structured data")
    print("\nRecommendation: Add prefecture_id field using JIS X 0401 codes")