"""
Update GBPUSD H1 data to current date
Downloads recent data from OANDA and appends to existing file
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data.downloader import OandaDownloader
import pandas as pd
from datetime import datetime

def update_gbpusd_h1():
    """Download recent GBPUSD H1 data and append to existing file."""
    
    # File path
    data_file = 'data/raw/GBPUSD60.csv'
    
    # Read existing data to find last timestamp
    print("Reading existing data...")
    existing_data = pd.read_csv(
        data_file,
        names=['date', 'time', 'open', 'high', 'low', 'close', 'volume'],
        parse_dates=[['date', 'time']]
    )
    existing_data.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    
    last_timestamp = existing_data['timestamp'].max()
    print(f"Last timestamp in file: {last_timestamp}")
    print(f"Total existing bars: {len(existing_data)}")
    
    # Download from last timestamp to today
    start_date = (last_timestamp + pd.Timedelta(hours=1)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"\nDownloading from {start_date} to {end_date}...")
    
    downloader = OandaDownloader()
    new_data = downloader.download_data('GBPUSD', start_date, end_date, granularity='H1')
    
    if new_data.empty:
        print("No new data to download. File is up to date.")
        return
    
    print(f"Downloaded {len(new_data)} new bars")
    
    # Reset index to get timestamp column
    new_data = new_data.reset_index()
    
    # Combine with existing data
    print("Combining and deduplicating...")
    combined = pd.concat([existing_data, new_data], ignore_index=True)
    combined = combined.drop_duplicates(subset=['timestamp'], keep='last')
    combined = combined.sort_values('timestamp')
    
    print(f"Total bars after update: {len(combined)}")
    
    # Save back to CSV in original format (date,time,o,h,l,c,v)
    print(f"Saving to {data_file}...")
    
    # Split timestamp into date and time columns
    combined['date'] = combined['timestamp'].dt.strftime('%Y.%m.%d')
    combined['time'] = combined['timestamp'].dt.strftime('%H:%M')
    
    # Save without header
    combined[['date', 'time', 'open', 'high', 'low', 'close', 'volume']].to_csv(
        data_file,
        index=False,
        header=False
    )
    
    print(f"✓ Successfully updated {data_file}")
    print(f"  New bars added: {len(combined) - len(existing_data)}")
    print(f"  Date range: {combined['timestamp'].min()} to {combined['timestamp'].max()}")

if __name__ == "__main__":
    update_gbpusd_h1()
