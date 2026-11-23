import random
import uuid
from gevent.lock import Semaphore
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


# =====================================================================================
# Pruebas de Sebastian (ms-catalogo y ms-existencias)
# =====================================================================================

# Datos compartidos por todos los usuarios virtuales. Se preparan una sola vez y no
# tocan las bodegas de demostración: las escrituras van a la bodega PERF-B1.
_PERF = {"listo": False, "bodega_id": None, "producto_id": 2, "categoria_id": None, "unidad_id": None}
_PERF_LOCK = Semaphore()


def _lista(body):
    """Las listas llegan como arreglo simple o dentro de 'results'."""
    return body if isinstance(body, list) else (body or {}).get("results", [])


class Pruebas_Sebastian(HttpUser):
    """15 pruebas de rendimiento sobre ms-catalogo y ms-existencias (RNF06: respuestas < 2 s).

    Las pruebas 6, 14 y 15 escriben datos: usan prefijo PERF- o la bodega PERF-B1.
    """
    wait_time = between(1, 2)

    def on_start(self):
        self.auth_headers = {}
        res = self.client.post(
            "/api/usuarios/auth/login",
            json={"email": "admin@predistock.com", "password": "Admin2026*"},
            name="00. [Setup] POST /auth/login (Admin)",
        )
        if res.status_code == 200:
            self.auth_headers = {"Authorization": f"Bearer {res.json().get('token')}"}
        self._preparar_datos()

    def _preparar_datos(self):
        """Crea una vez la bodega PERF-B1 con stock del producto 2 y busca categoría y unidad."""
        with _PERF_LOCK:
            if _PERF["listo"] or not self.auth_headers:
                return
            h = self.auth_headers
            # 201 = creada ahora; 409 = ya existía de una corrida anterior (ambos son correctos)
            with self.client.post(
                "/api/existencias/bodegas",
                json={"codigo": "PERF-B1", "nombre": "Bodega de pruebas de rendimiento", "region": "Pruebas"},
                headers=h, name="00. [Setup] POST /bodegas", catch_response=True,
            ) as r:
                if r.status_code in (201, 409):
                    r.success()
                else:
                    r.failure(f"Se esperaba 201 o 409 y respondió {r.status_code}")
            if r.status_code == 201:
                _PERF["bodega_id"] = r.json()["id"]
            else:  # ya existía (409): se busca por código
                lista = self.client.get("/api/existencias/bodegas", headers=h, name="00. [Setup] GET /bodegas")
                for b in _lista(lista.json()):
                    if b.get("codigo") == "PERF-B1":
                        _PERF["bodega_id"] = b["id"]
            if _PERF["bodega_id"] is None:
                return
            with self.client.post(
                "/api/existencias/stock",
                json={"producto_id": _PERF["producto_id"], "bodega_id": _PERF["bodega_id"], "stock_minimo": "0"},
                headers=h, name="00. [Setup] POST /stock", catch_response=True,
            ) as s:
                if s.status_code in (201, 409):
                    s.success()
                else:
                    s.failure(f"Se esperaba 201 o 409 y respondió {s.status_code}")
            self.client.post(
                "/api/existencias/movimientos",
                json={"producto_id": _PERF["producto_id"], "bodega_id": _PERF["bodega_id"],
                      "tipo": "ENTRADA", "cantidad": "100000"},
                headers=h, name="00. [Setup] POST /movimientos (stock inicial)",
            )
            cats = self.client.get("/api/catalogo/categorias", headers=h, name="00. [Setup] GET /categorias")
            unis = self.client.get("/api/catalogo/unidades-medida", headers=h, name="00. [Setup] GET /unidades-medida")
            if _lista(cats.json()):
                _PERF["categoria_id"] = _lista(cats.json())[0]["id"]
            if _lista(unis.json()):
                _PERF["unidad_id"] = _lista(unis.json())[0]["id"]
            _PERF["listo"] = True

    # --- MICROSERVICIO DE CATÁLOGO ---
    @task(3)
    def test_01_list_products(self):
        self.client.get(
            "/api/catalogo/productos?page=1&page_size=10",
            headers=self.auth_headers,
            name="01. [Catalogo] GET /productos (paginado)",
        )

    @task(2)
    def test_02_filter_products(self):
        self.client.get(
            "/api/catalogo/productos?nombre=Leche",
            headers=self.auth_headers,
            name="02. [Catalogo] GET /productos?nombre=",
        )

    @task(3)
    def test_03_product_detail(self):
        self.client.get(
            f"/api/catalogo/productos/{random.randint(1, 10)}",
            headers=self.auth_headers,
            name="03. [Catalogo] GET /productos/:id",
        )

    @task(1)
    def test_04_list_categories(self):
        self.client.get(
            "/api/catalogo/categorias",
            headers=self.auth_headers,
            name="04. [Catalogo] GET /categorias",
        )

    @task(1)
    def test_05_list_suppliers(self):
        self.client.get(
            "/api/catalogo/proveedores",
            headers=self.auth_headers,
            name="05. [Catalogo] GET /proveedores",
        )

    @task(1)
    def test_06_create_product(self):
        if not (_PERF["categoria_id"] and _PERF["unidad_id"]):
            return
        self.client.post(
            "/api/catalogo/productos",
            json={
                "codigo": f"PERF-{uuid.uuid4().hex[:10]}",
                "nombre": "Producto de prueba de rendimiento",
                "categoria_id": _PERF["categoria_id"],
                "unidad_medida_id": _PERF["unidad_id"],
                "precio_venta": "1000.00",
                "costo": "600.00",
            },
            headers=self.auth_headers,
            name="06. [Catalogo] POST /productos",
        )

    # --- MICROSERVICIO DE EXISTENCIAS ---
    @task(3)
    def test_07_stock_by_warehouse(self):
        self.client.get(
            f"/api/existencias/stock?bodega_id={random.choice([1, 2, 3])}",
            headers=self.auth_headers,
            name="07. [Existencias] GET /stock?bodega_id=",
        )

    @task(2)
    def test_08_stock_below_minimum(self):
        self.client.get(
            "/api/existencias/stock?bajo_minimo=true",
            headers=self.auth_headers,
            name="08. [Existencias] GET /stock?bajo_minimo=true",
        )

    @task(3)
    def test_09_kardex(self):
        self.client.get(
            f"/api/existencias/movimientos?producto_id={random.randint(1, 10)}&bodega_id=1&page_size=20",
            headers=self.auth_headers,
            name="09. [Existencias] GET /movimientos (kardex)",
        )

    @task(1)
    def test_10_lots(self):
        self.client.get(
            "/api/existencias/lotes?bodega_id=1",
            headers=self.auth_headers,
            name="10. [Existencias] GET /lotes",
        )

    @task(2)
    def test_11_report_stock(self):
        self.client.get(
            "/api/existencias/reportes/existencias",
            headers=self.auth_headers,
            name="11. [Existencias] GET /reportes/existencias",
        )

    @task(2)
    def test_12_report_valuation(self):
        self.client.get(
            "/api/existencias/reportes/valorizacion",
            headers=self.auth_headers,
            name="12. [Existencias] GET /reportes/valorizacion",
        )

    @task(1)
    def test_13_pending_orders(self):
        self.client.get(
            "/api/existencias/ordenes-compra?estado=PENDIENTE",
            headers=self.auth_headers,
            name="13. [Existencias] GET /ordenes-compra?estado=PENDIENTE",
        )

    @task(2)
    def test_14_stock_entry(self):
        if not _PERF["bodega_id"]:
            return
        self.client.post(
            "/api/existencias/movimientos",
            json={"producto_id": _PERF["producto_id"], "bodega_id": _PERF["bodega_id"],
                  "tipo": "ENTRADA", "cantidad": "5"},
            headers=self.auth_headers,
            name="14. [Existencias] POST /movimientos (entrada)",
        )

    @task(3)
    def test_15_concurrent_exits(self):
        """Muchas salidas sobre el mismo saldo: 201 o 409 (stock insuficiente) son respuestas correctas."""
        if not _PERF["bodega_id"]:
            return
        with self.client.post(
            "/api/existencias/movimientos",
            json={"producto_id": _PERF["producto_id"], "bodega_id": _PERF["bodega_id"],
                  "tipo": "SALIDA", "cantidad": "1"},
            headers=self.auth_headers,
            name="15. [Existencias] POST /movimientos (salidas concurrentes)",
            catch_response=True,
        ) as res:
            if res.status_code in (201, 409):
                res.success()
            else:
                res.failure(f"Se esperaba 201 o 409 y respondió {res.status_code}")