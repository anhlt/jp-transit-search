#!/usr/bin/env python3
"""Update existing stations CSV to include prefecture IDs."""

import csv
from pathlib import Path

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

def update_csv_prefecture_ids(csv_path: Path):
    """Update CSV file to include prefecture IDs."""
    
    # Read existing data
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        for row in reader:
            # Update prefecture_id if it's empty
            if not row.get('prefecture_id') and row.get('prefecture'):
                prefecture = row['prefecture']
                prefecture_id = PREFECTURE_ID_MAPPING.get(prefecture)
                if prefecture_id:
                    row['prefecture_id'] = prefecture_id
                    print(f"Updated {row['name']} ({prefecture}) -> ID: {prefecture_id}")
            
            rows.append(row)
    
    # Write updated data back
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Updated {len(rows)} stations in {csv_path}")

if __name__ == "__main__":
    csv_path = Path("data/stations.csv")
    if csv_path.exists():
        update_csv_prefecture_ids(csv_path)
    else:
        print(f"CSV file not found: {csv_path}")