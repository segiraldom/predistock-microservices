import os
import time
import json
import hmac
import hashlib
import base64
import requests
import pandas as pd
from app.config import Config
from app.pipeline.seeder import generate_mock_historical_data


def _generate_service_jwt() -> str:
    """Genera un JWT efímero (60s) firmado con JWT_SECRET para consultar el API Gateway."""
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        return ""

    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

    now = int(time.time())
    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8"))
    payload = b64url(json.dumps({
        "sub": 0,
        "rol": "ANALISTA",
        "bodega_id": None,
        "iat": now,
        "exp": now + 60
    }).encode("utf-8"))

    signature = b64url(
        hmac.new(secret.encode("utf-8"), f"{header}.{payload}".encode("utf-8"), hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"


class DataCollector:
    def __init__(self):
        base = Config.EXISTENCIAS_SERVICE_URL.rstrip("/")
        self.history_endpoint = f"{base}/existencias/movimientos/historico"
        self.stock_endpoint = f"{base}/existencias/stock"

    def _auth_headers(self) -> dict:
        token = _generate_service_jwt()
        return {"Authorization": f"Bearer {token}"} if token else {}

    def get_historical_movements(self) -> pd.DataFrame:
        """Extrae el historial consolidado de movimientos desde ms-existencias vía Gateway."""
        try:
            response = requests.get(self.history_endpoint, headers=self._auth_headers(), timeout=3)
            if response.status_code == 200:
                payload = response.json()
                records = payload if isinstance(payload, list) else payload.get("data", payload.get("results", []))
                if records:
                    return pd.DataFrame(records)
        except requests.RequestException:
            print("[INFO] ms-existencias (/historico) no disponible. Usando datos sintéticos locales.")

        return generate_mock_historical_data()

    def get_current_stock_map(self) -> dict:
        """
        Consulta GET /api/existencias/stock vía Gateway y construye:
        {(producto_id, bodega_id): cantidad_actual}
        """
        try:
            response = requests.get(self.stock_endpoint, headers=self._auth_headers(), timeout=3)
            if response.status_code == 200:
                payload = response.json()
                records = payload if isinstance(payload, list) else payload.get("data", payload.get("results", []))
                stock_map = {}
                for item in records:
                    pid = item.get("producto_id") or item.get("product_id")
                    wid = item.get("bodega_id") or item.get("warehouse_id")
                    qty = item.get("cantidad") if item.get("cantidad") is not None else item.get("quantity", 0)
                    if pid is not None and wid is not None:
                        stock_map[(int(pid), int(wid))] = int(qty)
                if stock_map:
                    return stock_map
        except requests.RequestException:
            print("[INFO] ms-existencias (/stock) no disponible. Usando stock de respaldo por defecto.")

        return {}