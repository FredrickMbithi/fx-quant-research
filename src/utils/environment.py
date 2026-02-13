import sys
import pandas as pd
import numpy as np
import scipy
import statsmodels
import sklearn
import yaml
import  requests


def log_environment():
    """
    Returns dictionary containing Python and critical dependancy versions.
    Used for:
        - Backtest reproducibility
        - Debugging environment drift
        - Audit logging
    """
    return {
        "python": sys.version,
        "python": sys.version,
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "statsmodels": statsmodels.__version__,
        "sklearn": sklearn.__version__,
        "pyyaml": yaml.__version__,
        "requests": requests.__version__,
    }

if __name__== "__main__":
    from pprint import pprint
    pprint(log_environment)