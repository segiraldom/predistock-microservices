# ms-usuarios/tests/locustfile.py
from locust import HttpUser, task, between

class UsersLoadTestUser(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        """Genera sesión previa para probar endpoints autenticados."""
        self.auth_token = None
        payload = {"email": "admin@predistock.com", "password": "Admin2026*"}
        with self.client.post("/api/v1/auth/login", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                self.auth_token = response.json().get("token")
                response.success()
            else:
                response.failure(f"Error login: {response.text}")

    @task(4)
    def test_list_roles(self):
        """Consulta frecuente de catálogo de roles."""
        self.client.get("/api/v1/roles", name="/api/v1/roles")

    @task(3)
    def test_login_concurrente(self):
        """Estrés de validación criptográfica Bcrypt en Login."""
        payload = {"email": "admin@predistock.com", "password": "Admin2026*"}
        self.client.post("/api/v1/auth/login", json=payload, name="/api/v1/auth/login")

    @task(3)
    def test_get_profile(self):
        """Consulta de perfil autenticado con cabeceras de contexto."""
        if self.auth_token:
            headers = {"Authorization": f"Bearer {self.auth_token}", "X-User-Id": "1"}
            self.client.get("/api/v1/auth/me", headers=headers, name="/api/v1/auth/me")

    @task(1)
    def test_health(self):
        self.client.get("/health", name="/health")