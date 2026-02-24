"""
Data Loader Test Suite
======================

Tests for:
- UTC normalization
- Lookahead bias prevention
- Duplicate handling
- Data integrity validation
- Missing bar handling
- OHLC relationship validation
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from pathlib import Path
import tempfile
import sys

# Add source to path (adjust as needed)
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data.loader import FXDataLoader, MissingBarHandler
from data.validator import (
    check_missing_bars, check_extreme_spikes, 
    check_volume_anomalies, validate_full_suite
)


class TestFXDataLoader:
    """Test FXDataLoader core functionality."""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary directory for test data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def sample_ohlc_data(self):
        """Create sample OHLC data."""
        dates = pd.date_range('2023-01-01', '2023-12-31', freq='D', tz='UTC')
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)
        
        return pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': prices + np.abs(np.random.randn(len(dates))),
            'low': prices - np.abs(np.random.randn(len(dates))),
            'close': prices + np.random.randn(len(dates)) * 0.1,
            'volume': np.random.randint(1000000, 10000000, len(dates))
        })
    
    def test_loader_initialization(self, temp_data_dir):
        """Test loader initializes correctly."""
        loader = FXDataLoader(temp_data_dir)
        assert loader.data_path == Path(temp_data_dir)
        assert loader.timezone == 'UTC'
    
    def test_loader_invalid_path(self):
        """Test loader raises error for invalid path."""
        with pytest.raises(ValueError, match="Data path does not exist"):
            FXDataLoader('/nonexistent/path')
    
    def test_timestamp_normalization_naive(self, temp_data_dir, sample_ohlc_data):
        """Test UTC normalization of naive timestamps."""
        # Save sample data
        csv_path = Path(temp_data_dir) / 'EURUSD.csv'
        sample_ohlc_data.to_csv(csv_path, index=False)
        
        loader = FXDataLoader(temp_data_dir)
        df = loader.load('EURUSD')
        
        # Check all timestamps are UTC
        assert df.index.tz == pytz.UTC
        assert all(ts.tzinfo == pytz.UTC for ts in df.index)
    
    def test_timestamp_normalization_aware(self, temp_data_dir, sample_ohlc_data):
        """Test conversion of timezone-aware timestamps to UTC."""
        # Convert to different timezone
        sample_ohlc_data['timestamp'] = pd.to_datetime(
            sample_ohlc_data['timestamp']
        ).dt.tz_convert('US/Eastern')
        
        csv_path = Path(temp_data_dir) / 'EURUSD.csv'
        sample_ohlc_data.to_csv(csv_path, index=False)
        
        loader = FXDataLoader(temp_data_dir)
        df = loader.load('EURUSD')
        
        assert df.index.tz == pytz.UTC
    
    def test_no_lookahead_bias(self, temp_data_dir, sample_ohlc_data):
        """CRITICAL: Ensure loaded data has no future timestamps."""
        csv_path = Path(temp_data_dir) / 'EURUSD.csv'
        sample_ohlc_data.to_csv(csv_path, index=False)
        
        loader = FXDataLoader(temp_data_dir)
        df = loader.load('EURUSD')
        
        now = pd.Timestamp.now(tz=pytz.UTC)
        
        # No timestamp should be in the future
        assert (df.index <= now).all(), "Data contains future timestamps (lookahead bias!)"
    
    def test_data_sorted_chronologically(self, temp_data_dir, sample_ohlc_data):
        """Test data is sorted by timestamp after loading."""
        # Shuffle data
        shuffled = sample_ohlc_data.sample(frac=1)
        
        csv_path = Path(temp_data_dir) / 'EURUSD.csv'
        shuffled.to_csv(csv_path, index=False)
        
        loader = FXDataLoader(temp_data_dir)
        df = loader.load('EURUSD')
        
        # Check monotonic increasing
        assert df.index.is_monotonic_increasing
        # Check equals sorted version
        assert df.index.equals(df.index.sort_values())
    
    def test_duplicate_handling(self, temp_data_dir, sample_ohlc_data):
        """Test duplicate timestamps are handled (keep last)."""
        # Add duplicate row
        dup_row = sample_ohlc_data.iloc[0].copy()
        dup_row['close'] = dup_row['close'] * 1.1  # Modify slightly
        sample_ohlc_data = pd.concat(
            [sample_ohlc_data, pd.DataFrame([dup_row])],
            ignore_index=True
        )
        
        csv_path = Path(temp_data_dir) / 'EURUSD.csv'
        sample_ohlc_data.to_csv(csv_path, index=False)
        
        loader = FXDataLoader(temp_data_dir)
        df = loader.load('EURUSD')
        
        # No duplicates in result
        assert not df.index.duplicated().any()
        # Close should be the modified value (last occurrence)
        first_date = sample_ohlc_data['timestamp'].min()
        assert df.loc[first_date, 'close'] == dup_row['close']
    
    def test_date_range_filtering(self, temp_data_dir, sample_ohlc_data):
        """Test loading with date range filter."""
        csv_path = Path(temp_data_dir) / 'EURUSD.csv'
        sample_ohlc_data.to_csv(csv_path, index=False)
        
        loader = FXDataLoader(temp_data_dir)
        df = loader.load('EURUSD', start_date='2023-06-01', end_date='2023-06-30')
        
        assert df.index.min() >= pd.Timestamp('2023-06-01', tz=pytz.UTC)
        assert df.index.max() <= pd.Timestamp('2023-06-30', tz=pytz.UTC)
    
    def test_validation_detects_nan_values(self, temp_data_dir, sample_ohlc_data):
        """Test validation fails with NaN in OHLCV."""
        sample_ohlc_data.loc[0, 'close'] = np.nan
        
        csv_path = Path(temp_data_dir) / 'EURUSD.csv'
        sample_ohlc_data.to_csv(csv_path, index=False)
        
        loader = FXDataLoader(temp_data_dir)
        
        with pytest.raises(ValueError, match="NaN in OHLCV"):
            loader.load('EURUSD')
    
    def test_validation_detects_invalid_ohlc(self, temp_data_dir, sample_ohlc_data):
        """Test validation fails with invalid OHLC relationships."""
        # Make high < low
        sample_ohlc_data.loc[0, 'high'] = 50
        sample_ohlc_data.loc[0, 'low'] = 100
        
        csv_path = Path(temp_data_dir) / 'EURUSD.csv'
        sample_ohlc_data.to_csv(csv_path, index=False)
        
        loader = FXDataLoader(temp_data_dir)
        
        with pytest.raises(ValueError, match="High < Low"):
            loader.load('EURUSD')
    
    def test_validation_detects_non_positive_prices(self, temp_data_dir, sample_ohlc_data):
        """Test validation fails with zero or negative prices."""
        sample_ohlc_data.loc[0, 'close'] = 0
        
        csv_path = Path(temp_data_dir) / 'EURUSD.csv'
        sample_ohlc_data.to_csv(csv_path, index=False)
        
        loader = FXDataLoader(temp_data_dir)
        
        with pytest.raises(ValueError, match="non-positive"):
            loader.load('EURUSD')


class TestMissingBarHandler:
    """Test missing bar detection and handling."""
    
    @pytest.fixture
    def complete_data(self):
        """Create complete daily data."""
        dates = pd.date_range('2023-01-01', '2023-12-31', freq='D', tz='UTC')
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)
        
        return pd.DataFrame({
            'open': prices,
            'high': prices + 1,
            'low': prices - 1,
            'close': prices,
            'volume': 1000000
        }, index=dates)
    
    @pytest.fixture
    def data_with_gaps(self, complete_data):
        """Create data with gaps."""
        # Remove weekends (common for FX)
        return complete_data[complete_data.index.dayofweek < 5]
    
    def test_no_gaps_detected_when_none_exist(self, complete_data):
        """Test no false positives on complete data."""
        report = check_missing_bars(complete_data, expected_freq='D')
        
        assert not report['has_gaps']
        assert report['coverage'] > 0.99
        assert report['passed']
    
    def test_gaps_detected_correctly(self, data_with_gaps):
        """Test gaps are detected."""
        report = check_missing_bars(data_with_gaps, expected_freq='D')
        
        assert report['has_gaps']
        assert report['missing_count'] > 0
        # Weekends should be ~40% of data
        assert 0.5 < report['coverage'] < 0.8
    
    def test_forward_fill_strategy(self, data_with_gaps):
        """Test forward fill strategy."""
        filled, report = MissingBarHandler.check_and_fill(
            data_with_gaps, 
            expected_freq='D',
            strategy='forward_fill'
        )
        
        # Filled data should have complete index
        expected_index = pd.date_range(
            data_with_gaps.index.min(),
            data_with_gaps.index.max(),
            freq='D',
            tz='UTC'
        )
        assert len(filled) == len(expected_index)
        
        # No NaN values
        assert not filled.isna().any().any()
    
    def test_interpolate_strategy(self, data_with_gaps):
        """Test interpolation strategy."""
        filled, report = MissingBarHandler.check_and_fill(
            data_with_gaps,
            expected_freq='D',
            strategy='interpolate'
        )
        
        # Filled data should have complete index
        expected_index = pd.date_range(
            data_with_gaps.index.min(),
            data_with_gaps.index.max(),
            freq='D',
            tz='UTC'
        )
        assert len(filled) == len(expected_index)
        
        # Values should be interpolated (not same as adjacent)
        # (except at endpoints)


class TestDataValidator:
    """Test data validation functions."""
    
    @pytest.fixture
    def clean_data(self):
        """Create clean sample data."""
        dates = pd.date_range('2023-01-01', '2023-12-31', freq='D', tz='UTC')
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)
        
        return pd.DataFrame({
            'open': prices,
            'high': prices + np.abs(np.random.randn(len(dates))),
            'low': prices - np.abs(np.random.randn(len(dates))),
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, len(dates))
        }, index=dates)
    
    def test_extreme_spike_detection(self, clean_data):
        """Test detection of extreme price moves."""
        # Inject a spike
        clean_data.loc[clean_data.index[100], 'close'] *= 1.5
        
        report = check_extreme_spikes(clean_data, threshold=3)
        
        assert report['has_spikes']
        assert len(report['spike_indices']) > 0
    
    def test_volume_anomaly_detection(self, clean_data):
        """Test detection of low-volume bars."""
        # Set one bar to very low volume
        clean_data.loc[clean_data.index[50], 'volume'] = 1000
        
        report = check_volume_anomalies(clean_data, percentile=5)
        
        assert report['has_anomalies']
        assert report['anomaly_count'] >= 1
    
    def test_full_validation_suite_passes_clean_data(self, clean_data):
        """Test complete validation on clean data."""
        report = validate_full_suite(clean_data, symbol='EURUSD')
        
        assert report['passed']
        assert report['status'] == 'PASS'
        assert report['checks']['ohlc_sanity']['passed']
        assert report['checks']['missing_bars']['passed']


class TestLookaheadBiasPrevention:
    """Critical tests for preventing lookahead bias."""
    
    def test_loader_rejects_future_data(self):
        """CRITICAL: Loader must reject future timestamps."""
        # Create data with future dates
        dates = pd.date_range(
            end=pd.Timestamp.now(tz=pytz.UTC) + timedelta(days=10),
            periods=100,
            freq='D',
            tz=pytz.UTC
        )
        
        df = pd.DataFrame({
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.5,
            'volume': 1000000
        }, index=dates)
        
        loader = FXDataLoader('.')
        
        # Should raise ValueError for future data
        with pytest.raises(ValueError, match="future timestamps"):
            loader.validate(df)
    
    def test_no_information_leakage_in_features(self):
        """Test that feature calculation doesn't leak future info."""
        # This is more of an integration test
        # In real trading, this would test strategy backtesting
        # to ensure indicators don't use future data
        pass
    
    def test_timestamp_edge_cases(self):
        """Test edge cases in timestamp handling."""
        # Test boundaries (very old data, very recent data)
        very_old = pd.Timestamp('1970-01-01', tz=pytz.UTC)
        very_new = pd.Timestamp.now(tz=pytz.UTC)
        
        dates = pd.date_range(very_old, very_new, periods=100, tz=pytz.UTC)
        
        df = pd.DataFrame({
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.5,
            'volume': 1000000
        }, index=dates)
        
        loader = FXDataLoader('.')
        # Should not raise for valid historical data
        loader.validate(df)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
