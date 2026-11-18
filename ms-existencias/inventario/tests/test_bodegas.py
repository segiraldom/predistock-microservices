from .base import PREFIJO, BaseAPITest

URL = f"{PREFIJO}/bodegas"
NUEVA = {"codigo": "BOD-MZL", "nombre": "Bodega Manizales", "region": "Centro", "ciudad": "Manizales"}


class BodegasTest(BaseAPITest):
    def test_admin_crea_bodega(self):
        r = self.admin.post(URL, NUEVA, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()["activa"])

    def test_rol_administrador_se_normaliza(self):
        r = self.cliente("Administrador").post(URL, NUEVA, format="json")
        self.assertEqual(r.status_code, 201)

    def test_operador_no_puede_crear(self):
        r = self.operador.post(URL, NUEVA, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["error"], "SIN_PERMISO")

    def test_codigo_duplicado_409(self):
        self.crear_bodega("BOD-MZL")
        r = self.admin.post(URL, {**NUEVA, "codigo": "bod-mzl"}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_datos_faltantes_400_con_formato_de_error(self):
        r = self.admin.post(URL, {"codigo": "X"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "DATOS_INVALIDOS")
        self.assertIn("nombre", r.json()["mensaje"])

    def test_listado_filtra_activas_y_region(self):
        self.crear_bodega("B1", region="Centro")
        self.crear_bodega("B2", region="Norte")
        self.crear_bodega("B3", region="Centro", activa=False)
        self.assertEqual(len(self.operador.get(URL).json()), 2)
        self.assertEqual(len(self.operador.get(URL, {"region": "centro"}).json()), 1)
        self.assertEqual(len(self.operador.get(URL, {"activa": "false"}).json()), 1)

    def test_parametro_booleano_invalido_400(self):
        self.assertEqual(self.operador.get(URL, {"activa": "quizas"}).status_code, 400)

    def test_actualizar_y_desactivar(self):
        b = self.crear_bodega()
        r = self.admin.put(f"{URL}/{b.id}", {**NUEVA, "nombre": "Central", "activa": False}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["nombre"], "Central")
        self.assertFalse(r.json()["activa"])

    def test_actualizar_con_codigo_de_otra_bodega_409(self):
        self.crear_bodega("B1")
        b2 = self.crear_bodega("B2")
        r = self.admin.put(f"{URL}/{b2.id}", {**NUEVA, "codigo": "B1"}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_bodega_inexistente_404(self):
        r = self.operador.get(f"{URL}/999")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json(), {"error": "NO_ENCONTRADO", "mensaje": "La bodega 999 no existe"})


class GeneralesTest(BaseAPITest):
    def test_health(self):
        r = self.client.get(f"{PREFIJO}/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_ruta_inexistente_responde_json(self):
        r = self.client.get(f"{PREFIJO}/no-existe")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "NO_ENCONTRADO")
