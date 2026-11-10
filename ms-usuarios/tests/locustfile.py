# ms-usuarios/tests/locustfile.py
from locust import HttpUser, task, between

class GatewayLoadTestUser(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        """Inicia sesión a través del Gateway y almacena el JWT"""
        self.auth_token = None
        payload = {"email": "admin@predistock.com", "password": "Admin2026*"}
        with self.client.post("/api/usuarios/auth/login", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                self.auth_token = response.json().get("token")
                response.success()
            else:
                response.failure(f"Error login: {response.status_code} - {response.text}")

    @task(4)
    def test_list_roles(self):
        """Consulta de catálogo de roles protegida por JWT"""
        if self.auth_token:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            self.client.get("/api/usuarios/roles", headers=headers, name="/api/usuarios/roles")

    @task(3)
    def test_get_profile(self):
        """Consulta de perfil propio autenticado (/me)"""
        if self.auth_token:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            self.client.get("/api/auth/me", headers=headers, name="/api/auth/me")

    @task(3)
    def test_analytics_segmentation(self):
        """Consulta de analítica a través del Gateway (RBAC ADMIN)"""
        if self.auth_token:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            self.client.get(
                "/api/analytics/segmentation?warehouse_id=1",
                headers=headers,
                name="/api/analytics/segmentation"
            )

    @task(2)
    def test_login_concurrente(self):
        """Prueba de concurrencia en login público"""
        payload = {"email": "admin@predistock.com", "password": "Admin2026*"}
        self.client.post("/api/usuarios/auth/login", json=payload, name="/api/usuarios/auth/login")