"""
FX Trading Session Tagger
Classifies bars into ASIA, LONDON, or NY sessions based on UTC hour
"""

import pandas as pd
import numpy as np
from typing import Literal

SessionType = Literal['ASIA', 'LONDON', 'NY']


class SessionTagger:
    """
    Tag FX bars with trading session information.
    
    Session definitions (UTC):
    - ASIA:   00:00 - 08:00 UTC (Tokyo, Singapore, Hong Kong)
    - LONDON: 08:00 - 16:00 UTC (London, Frankfurt)
    - NY:     16:00 - 24:00 UTC (New York)
    """
    
    SESSIONS = {
        'ASIA': (0, 8),
        'LONDON': (8, 16),
        'NY': (16, 24)
    }
    
    def __init__(self):
        """Initialize the session tagger."""
        pass
    
    @staticmethod
    def tag_session(timestamp: pd.Timestamp) -> SessionType:
        """
        Determine the trading session for a single timestamp.
        
        Args:
            timestamp: pandas Timestamp (must be UTC or naive)
        
        Returns:
            Session name: 'ASIA', 'LONDON', or 'NY'
        """
        hour = timestamp.hour
        
        if 0 <= hour < 8:
            return 'ASIA'
        elif 8 <= hour < 16:
            return 'LONDON'
        else:  # 16 <= hour < 24
            return 'NY'
    
    @staticmethod
    def tag_sessions(df: pd.DataFrame) -> pd.Series:
        """
        Tag all bars in a DataFrame with session information.
        
        Args:
            df: DataFrame with DatetimeIndex or 'timestamp' column
        
        Returns:
            pd.Series with session labels ('ASIA', 'LONDON', 'NY')
        """
        # Get timestamps
        if isinstance(df.index, pd.DatetimeIndex):
            timestamps = df.index
        elif 'timestamp' in df.columns:
            timestamps = df['timestamp']
        else:
            raise ValueError("DataFrame must have DatetimeIndex or 'timestamp' column")
        
        # Vectorized hour extraction
        hours = timestamps.hour
        
        # Vectorized session assignment
        sessions = np.full(len(hours), '', dtype=object)
        sessions[(hours >= 0) & (hours < 8)] = 'ASIA'
        sessions[(hours >= 8) & (hours < 16)] = 'LONDON'
        sessions[(hours >= 16) & (hours < 24)] = 'NY'
        
        return pd.Series(sessions, index=df.index, dtype='category')
    
    @staticmethod
    def get_session_stats(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate statistics by session.
        
        Args:
            df: DataFrame with 'session' column
        
        Returns:
            DataFrame with session statistics
        """
        if 'session' not in df.columns:
            raise ValueError("DataFrame must have 'session' column")
        
        stats = df.groupby('session').agg({
            'close': ['count', 'mean', 'std'],
            'volume': ['mean', 'sum']
        })
        
        # Add volatility if high/low available
        if 'high' in df.columns and 'low' in df.columns:
            df['range'] = df['high'] - df['low']
            range_stats = df.groupby('session')['range'].agg(['mean', 'std'])
            stats = pd.concat([stats, range_stats], axis=1)
        
        return stats
    
    @staticmethod
    def filter_session(df: pd.DataFrame, session: SessionType) -> pd.DataFrame:
        """
        Filter DataFrame to include only bars from specified session.
        
        Args:
            df: DataFrame with 'session' column
            session: Session to filter ('ASIA', 'LONDON', 'NY')
        
        Returns:
            Filtered DataFrame
        """
        if 'session' not in df.columns:
            raise ValueError("DataFrame must have 'session' column")
        
        return df[df['session'] == session].copy()
    
    @staticmethod
    def is_session_overlap(timestamp: pd.Timestamp) -> bool:
        """
        Check if timestamp is near session boundary (within 30 minutes).
        Useful for filtering out volatile transition periods.
        
        Args:
            timestamp: pandas Timestamp
        
        Returns:
            True if near session boundary (7:30-8:30 or 15:30-16:30 UTC)
        """
        hour = timestamp.hour
        minute = timestamp.minute
        
        # London open (8:00 UTC +/- 30 min)
        if (hour == 7 and minute >= 30) or (hour == 8 and minute < 30):
            return True
        
        # NY open (16:00 UTC +/- 30 min)
        if (hour == 15 and minute >= 30) or (hour == 16 and minute < 30):
            return True
        
        return False


def add_session_tags(df: pd.DataFrame, inplace: bool = False) -> pd.DataFrame:
    """
    Convenience function to add session tags to a DataFrame.
    
    Args:
        df: DataFrame with datetime index or 'timestamp' column
        inplace: If True, modify df in place; otherwise return copy
    
    Returns:
        DataFrame with added 'session' column
    """
    if not inplace:
        df = df.copy()
    
    tagger = SessionTagger()
    df['session'] = tagger.tag_sessions(df)
    
    return df


if __name__ == "__main__":
    # Example usage
    import pandas as pd
    from datetime import datetime, timedelta
    
    # Create sample hourly data
    start = datetime(2024, 1, 1, 0, 0)
    timestamps = [start + timedelta(hours=i) for i in range(72)]  # 3 days
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'close': np.random.randn(72).cumsum() + 1.25,
        'high': np.random.randn(72).cumsum() + 1.26,
        'low': np.random.randn(72).cumsum() + 1.24,
        'volume': np.random.randint(1000, 10000, 72)
    })
    
    df = df.set_index('timestamp')
    
    # Tag sessions
    df = add_session_tags(df)
    
    print("Sample data with session tags:")
    print(df.head(24))
    
    print("\nSession distribution:")
    print(df['session'].value_counts())
    
    print("\nSession statistics:")
    tagger = SessionTagger()
    print(tagger.get_session_stats(df))
