import pandas as pd
from pathlib import Path

data_path = Path('..') / 'ALOHA' / 'Receiver' / 'DATA'

stress_test_files = [
    data_path / 'noSen_10Hz_noALOHA',
    data_path / 'noSen_50Hz_noALOHA',
    data_path / 'noSen_100Hz_noALOHA',
]

data_header = [
    'node',
    'packet_number',
    'timestamp', 
    'temperature', 
    'humidity', 
    'time_of_measurement', 
    'warning', 
    'uninitialized',
    'rx_timestamp'
]

def load_data(filename) -> pd.DataFrame:
    if isinstance(filename, str):
        filename = data_path / filename

    data = pd.read_csv(
        filename,
        header=None
    )
    data.columns = data_header
    return data