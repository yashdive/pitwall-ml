import fastf1
import pandas as pd

class FastF1Loader:
    def __init__(self, season: int, event: int | str, session_type: str, datasets: list[str]):
        self.season = season
        self.event = event
        self.session_type = session_type
        self.datasets = datasets
        self.allowed_datasets = ['laps', 'weather', 'telemetry']
        
        for dataset in datasets:
            if dataset not in self.allowed_datasets:
                raise ValueError(f"Dataset {dataset} not recognized. Available datasets: {self.allowed_datasets}")
        self.datasets = datasets
        
        
    
    def load_session(self):
        '''
        Load the session using FastF1
        '''
        try:
            session = fastf1.get_session(self.season, self.event, self.session_type)
            session.load(
                laps = "laps" in self.datasets,
                weather = "weather" in self.datasets,
                # telemetry = "telemetry" in self.datasets
            )
            return session
        except Exception as e:
            raise RuntimeError(f"Failed to load FastF1 session: {e}") from e
    
    def load_datasets(self, session):
        '''
        Load the requested datasets from the session into pandas DataFrames
        '''
        laps = pd.DataFrame()
        weather = pd.DataFrame()
        telemetry = pd.DataFrame()
        metadata = {
            "season": session._session_info['StartDate'].year,
            "Location": session._session_info['Meeting']['Location'],
            "event_name": session._session_info['Meeting']['Name'],
            "official_event_name": session._session_info['Meeting']['OfficialName'],
            "session_type": session._session_info["Type"],
        }
        for dataset in self.datasets:
            try:
                if dataset == 'laps':
                    laps = session.laps.copy()
                elif dataset == 'weather':
                    weather = session.weather_data.copy()     
                # elif dataset == 'telemetry':
                #     telemetry = session.telemetry.copy()               
            except Exception as e:
                raise RuntimeError(f"Failed to load dataset {dataset}: {e}") from e
        return {"laps": laps, "weather": weather, "metadata": metadata}