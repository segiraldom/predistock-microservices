import requests
import pandas as pd
from app.config import Config
from app.pipeline.seeder import generate_mock_historical_data

class DataCollector:
    def __init__(self):
        self.endpoint = f"{Config.EXISTENCIAS_SERVICE_URL}/movimientos/historico"

    def get_historical_movements(self) -> pd.DataFrame:
        """Extrae el historial consolidado de movimientos de todas las bodegas."""
        try:
            response = requests.get(self.endpoint, timeout=3)
            if response.status_code == 200:
                data = response.json().get('data', [])
                if data:
                    return pd.DataFrame(data)
        except requests.RequestException:
            # Fallback para pruebas locales autónomas si existencias no está levantado
            print("[INFO] ms-existencias no disponible. Usando datos sintéticos locales.")
            return generate_mock_historical_data()

        return generate_mock_historical_data()