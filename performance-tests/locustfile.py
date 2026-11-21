import random
from locust import HttpUser, task, between


class Pruebas_Cristian(HttpUser):
    """15 pruebas de rendimiento y seguridad sobre ms-usuarios, ms-analitica y API Gateway."""
    wait_time = between(1, 2)

    def on_start(self):
        self.auth_headers = {}
        self.operator_headers = {}
        self.operator_id = None

        # Prueba 1: Login ADMIN
        with self.client.post(
            "/api/usuarios/auth/login",
            json={"email": "admin@predistock.com", "password": "Admin2026*"},
            name="01. [Usuarios] POST /auth/login (Admin)",
            catch_response=True,
        ) as res:
            if res.status_code == 200:
                token = res.json().get("token")
                self.auth_headers = {"Authorization": f"Bearer {token}"}
                res.success()
            else:
                res.failure(f"Login admin fallido: {res.status_code}")

        # Prueba 2: Login OPERADOR_BODEGA
        with self.client.post(
            "/api/usuarios/auth/login",
            json={"email": "operador@predistock.com", "password": "Operador2026*"},
            name="02. [Usuarios] POST /auth/login (Operador)",
            catch_response=True,
        ) as res:
            if res.status_code == 200:
                body = res.json()
                self.operator_headers = {"Authorization": f"Bearer {body.get('token')}"}
                self.operator_id = body.get("user", {}).get("id")
                res.success()
            else:
                res.failure(f"Login operador fallido: {res.status_code}")

    # --- MICROSERVICIO DE USUARIOS ---
    @task(2)
    def test_03_get_profile(self):
        self.client.get(
            "/api/usuarios/auth/me",
            headers=self.auth_headers,
            name="03. [Usuarios] GET /auth/me",
        )

    @task(2)
    def test_04_list_users(self):
        self.client.get(
            "/api/usuarios/usuarios",
            headers=self.auth_headers,
            name="04. [Usuarios] GET /usuarios",
        )

    @task(1)
    def test_05_list_roles(self):
        self.client.get(
            "/api/usuarios/roles",
            headers=self.auth_headers,
            name="05. [Usuarios] GET /roles",
        )

    @task(1)
    def test_06_update_user_warehouse(self):
        if not self.operator_id:
            return
        self.client.put(
            f"/api/usuarios/usuarios/{self.operator_id}",
            json={"bodega_id": 1, "activo": True},
            headers=self.auth_headers,
            name="06. [Usuarios] PUT /usuarios/:id",
        )

    @task(1)
    def test_07_forgot_password_nonexistent(self):
        self.client.post(
            "/api/auth/recuperar-password",
            json={"email": "noexiste@predistock.com"},
            name="07. [Usuarios] POST /auth/recuperar-password",
        )

    @task(1)
    def test_08_login_invalid_credentials(self):
        with self.client.post(
            "/api/usuarios/auth/login",
            json={"email": "admin@predistock.com", "password": "ClaveIncorrecta123"},
            name="08. [Usuarios] POST /auth/login (401 esperado)",
            catch_response=True,
        ) as res:
            if res.status_code == 401:
                res.success()
            else:
                res.failure(f"Se esperaba 401 y respondió {res.status_code}")

    # --- MICROSERVICIO DE ANALÍTICA ML ---
    @task(3)
    def test_09_segmentation_central(self):
        self.client.get(
            "/api/analytics/segmentation?warehouse_id=1",
            headers=self.auth_headers,
            name="09. [Analitica] GET /segmentation (Bodega 1)",
        )

    @task(3)
    def test_10_segmentation_regional(self):
        bodega = random.choice([2, 3])
        self.client.get(
            f"/api/analytics/segmentation?warehouse_id={bodega}",
            headers=self.auth_headers,
            name="10. [Analitica] GET /segmentation (Bodegas 2-3)",
        )

    @task(3)
    def test_11_predictions_central(self):
        self.client.get(
            "/api/analytics/predictions?warehouse_id=1",
            headers=self.auth_headers,
            name="11. [Analitica] GET /predictions (Bodega 1)",
        )

    @task(3)
    def test_12_predictions_regional(self):
        bodega = random.choice([2, 3])
        self.client.get(
            f"/api/analytics/predictions?warehouse_id={bodega}",
            headers=self.auth_headers,
            name="12. [Analitica] GET /predictions (Bodegas 2-3)",
        )

    @task(3)
    def test_13_stock_suggestions(self):
        bodega = random.choice([1, 2, 3])
        self.client.get(
            f"/api/analytics/suggestions?warehouse_id={bodega}",
            headers=self.auth_headers,
            name="13. [Analitica] GET /suggestions",
        )

    # --- SEGURIDAD Y CONTROL DE ACCESO EN API GATEWAY ---
    @task(1)
    def test_14_gateway_unauthorized_401(self):
        with self.client.get(
            "/api/analytics/predictions?warehouse_id=1",
            name="14. [Gateway] GET sin token (401 esperado)",
            catch_response=True,
        ) as res:
            if res.status_code == 401:
                res.success()
            else:
                res.failure(f"Se esperaba 401 y respondió {res.status_code}")

    @task(1)
    def test_15_gateway_forbidden_403(self):
        with self.client.get(
            "/api/usuarios/usuarios",
            headers=self.operator_headers,
            name="15. [Gateway] GET /usuarios rol OPERADOR (403 esperado)",
            catch_response=True,
        ) as res:
            if res.status_code == 403:
                res.success()
            else:
                res.failure(f"Se esperaba 403 y respondió {res.status_code}")