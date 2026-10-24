from pathlib import Path
import pandas as pd

from MoSIC import data

class ParquetWriter:
    def __init__(self, data: dict, raw_uri: str, compression: str = 'zstd'):
        self.data = data
        self.raw_uri = raw_uri
        self.compression = compression
        
    def write_data(self):
        '''
        Write the data to parquet files.

        '''
        season = self.data['metadata']['season']
        event = self.data['metadata']['event']
        session_type = self.data['metadata']['session_type']

        output_dir = Path(self.raw_uri) 
        laps_dir = Path(f"{output_dir}/laps/season={season}/event={event}/session_type={session_type}")
        weather_dir = Path(f"{output_dir}/weather/season={season}/event={event}/session_type={session_type}")
        metadata_dir = Path(f"{output_dir}/metadata/season={season}/event={event}/session_type={session_type}")
        
        for data_type in data.keys():
            if data[data_type] is not None or (isinstance(data[data_type],pd.DataFrame) and len(data[data_type]) > 0):
                if data_type == "laps":
                    laps_dir.mkdir(parents=True, exist_ok=True)
                    laps_df = pd.DataFrame(data[data_type])
                    laps_df.to_parquet(f"{laps_dir}/data.parquet", index=False, compression=self.compression)
                elif data_type == "weather":
                    weather_dir.mkdir(parents=True, exist_ok=True)
                    weather_df = pd.DataFrame(data[data_type])
                    weather_df.to_parquet(f"{weather_dir}/data.parquet", index=False, compression=self.compression)
                elif data_type == "metadata":
                    metadata_dir.mkdir(parents=True, exist_ok=True)
                    metadata_df = pd.DataFrame([data[data_type]])
                    metadata_df.to_csv(f"{metadata_dir}/data.csv", index=False)
            else:
                raise ValueError(f"No data found for {data_type} in season {season}, event {event}, session {session_type}.")
