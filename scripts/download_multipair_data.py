#!/usr/bin/env python3
"""
Download H1 data for all pairs in multi-pair strategy.

This script downloads 10+ years of hourly OHLC data for all currency pairs
needed for the 3,000 trade implementation.

Usage:
    python scripts/download_multipair_data.py
"""

import pandas as pd
from pathlib import Path
import json
from datetime import datetime, timedelta
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.Fxcm_downloader import download_fxcm_data


def load_pairs_from_config() -> list:
    """Load list of pairs from multi-pair config"""
    config_path = project_root / 'config' / 'h1_multipair_config.json'
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    return config['pairs_to_trade']


def format_pair_for_fxcm(pair: str) -> str:
    """Convert pair format to FXCM format (e.g., EURUSD -> EUR/USD)"""
    if '/' in pair:
        return pair
    return f"{pair[:3]}/{pair[3:]}"


def download_all_pairs():
    """Download H1 data for all pairs in config"""
    pairs = load_pairs_from_config()
    
    # Download parameters
    timeframe = '1H'
    start_date = '2015-01-01'
    end_date = '2026-02-25'
    
    output_dir = project_root / 'data' / 'raw'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*80)
    print("DOWNLOADING H1 DATA FOR MULTI-PAIR STRATEGY")
    print("="*80)
    print(f"\nPairs to download: {len(pairs)}")
    print(f"Timeframe:         {timeframe}")
    print(f"Period:            {start_date} to {end_date}")
    print(f"Output directory:  {output_dir}")
    print("\n" + "="*80 + "\n")
    
    successful = []
    failed = []
    
    for i, pair in enumerate(pairs, 1):
        pair_formatted = format_pair_for_fxcm(pair)
        output_file = output_dir / f"{pair.replace('/', '')}_{timeframe}.csv"
        
        print(f"[{i}/{len(pairs)}] Downloading {pair_formatted}...", end=' ')
        
        try:
            # Download from FXCM
            df = download_fxcm_data(
                symbol=pair_formatted,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
            
            if df is not None and len(df) > 0:
                # Save to CSV
                df.to_csv(output_file)
                print(f"✅ {len(df)} bars saved to {output_file.name}")
                successful.append(pair)
            else:
                print(f"❌ No data returned")
                failed.append(pair)
        
        except Exception as e:
            print(f"❌ Error: {e}")
            failed.append(pair)
    
    # Summary
    print("\n" + "="*80)
    print("DOWNLOAD SUMMARY")
    print("="*80)
    print(f"\n✅ Successful: {len(successful)}/{len(pairs)} pairs")
    print(f"❌ Failed:     {len(failed)}/{len(pairs)} pairs")
    
    if failed:
        print(f"\nFailed pairs:")
        for pair in failed:
            print(f"  - {pair}")
    
    print("\n" + "="*80)
    print("\nNext steps:")
    print("1. Validate downloaded data: python src/data/validator.py")
    print("2. Run multi-pair backtest: python deploy_multipair_h1.py")
    print("="*80 + "\n")


if __name__ == "__main__":
    download_all_pairs()
