import pandas as pd
from pathlib import Path

rx_data_path = Path('..') / 'ALOHA' / 'Receiver' / 'DATA'
tx_data_path = Path('..') / 'ALOHA' / 'Transmitter' / 'DATA'

stress_test_files = [
    rx_data_path / 'noSen_10Hz_noALOHA',
    rx_data_path / 'noSen_50Hz_noALOHA',
    rx_data_path / 'noSen_100Hz_noALOHA',
]

rx_aloha_files = [
    rx_data_path / 'wSen_50Hz_ALOHA',
    rx_data_path / 'noSen_50Hz_ALOHA'
]

tx_aloha_files = [
    tx_data_path / 'tx_sensor_aloha_50hz',
    tx_data_path / 'tx_nosensor_aloha_50hz'
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

tx_header = [
    'packet_number',
    'ack',
    'timestamp'
]

def load_rx_data(filename) -> pd.DataFrame:
    if isinstance(filename, str):
        filename = rx_data_path / filename

    data = pd.read_csv(
        filename,
        header=None
    )
    data.columns = data_header
    return data


def load_tx_data(filename) -> pd.DataFrame:
    if isinstance(filename, str):
        filename = rx_data_path / filename

    data = pd.read_csv(
        filename,
        header=None,
        sep=' '
    )
    data.columns = tx_header
    return data

