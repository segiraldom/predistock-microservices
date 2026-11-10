# ms-analitica/tests/locustfile.py
from locust import HttpUser, task, between

class AnalyticsLoadTestUser(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        """Si la prueba apunta al Gateway (puerto 8000), genera token de autenticación"""
        self.auth_headers = {}
        # Detectar si estamos apuntando al API Gateway
        if "8000" in str(self.host):
            payload = {"email": "admin@predistock.com", "password": "Admin2026*"}
            with self.client.post("/api/usuarios/auth/login", json=payload, catch_response=True) as res:
                if res.status_code == 200:
                    token = res.json().get("token")
                    self.auth_headers = {"Authorization": f"Bearer {token}"}
                    res.success()
                else:
                    res.failure(f"Fallo de login en Gateway: {res.status_code}")

    @task(4)
    def test_get_segmentation(self):
        """Consulta clusters K-Means por bodega"""
        self.client.get(
            "/api/analytics/segmentation?warehouse_id=1",
            headers=self.auth_headers,
            name="/api/analytics/segmentation"
        )

    @task(3)
    def test_get_predictions(self):
        """Consulta proyecciones de demanda Random Forest"""
        self.client.get(
            "/api/analytics/predictions?warehouse_id=1",
            headers=self.auth_headers,
            name="/api/analytics/predictions"
        )

    @task(3)
    def test_get_suggestions(self):
        """Consulta sugerencias de stock"""
        self.client.get(
            "/api/analytics/suggestions?warehouse_id=1",
            headers=self.auth_headers,
            name="/api/analytics/suggestions"
        )

    @task(1)
    def test_health(self):
        """Solo se consulta si se prueba directo al microservicio en el puerto 5000"""
        if "8000" not in str(self.host):
            self.client.get("/health", name="/health")