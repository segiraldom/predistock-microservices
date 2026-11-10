from locust import HttpUser, task, between

class AnalyticsLoadTestUser(HttpUser):
    # Tiempo de espera simulado entre consultas de usuario (1 a 3 segundos)
    wait_time = between(1, 3)

    @task(3)
    def test_get_segmentation(self):
        """Consulta frecuente desde el Dashboard de Inventarios."""
        self.client.get("/api/analytics/segmentation?warehouse_id=1")

    @task(3)
    def test_get_predictions(self):
        """Consulta de pronósticos de demanda."""
        self.client.get("/api/analytics/predictions?warehouse_id=1")

    @task(2)
    def test_get_suggestions(self):
        """Consulta de sugerencias de stock (quiebres y sobrestock)."""
        self.client.get("/api/analytics/suggestions?status=RIESGO_QUIEBRE")

    @task(1)
    def test_health_probe(self):
        self.client.get("/health")