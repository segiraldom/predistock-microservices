from .base import PREFIJO, BaseAPITest

URL = f"{PREFIJO}/proveedores"
NUEVO = {"nit": "900123456-7", "razon_social": "Lácteos del Eje S.A.S.", "telefono": "+57 3001234567",
         "email": "ventas@lacteoseje.com", "ciudad": "Pereira"}


class ProveedoresTest(BaseAPITest):
    def test_admin_crea_proveedor(self):
        r = self.admin.post(URL, NUEVO, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()["activo"])
        self.assertEqual(r.json()["nit"], "900123456-7")

    def test_solo_nit_y_razon_social_son_obligatorios(self):
        r = self.admin.post(URL, {"nit": "1", "razon_social": "Mínimo"}, format="json")
        self.assertEqual(r.status_code, 201)

    def test_solo_admin_escribe(self):
        for c in (self.operador, self.analista, self.interno):
            self.assertEqual(c.post(URL, NUEVO, format="json").status_code, 403)

    def test_nit_duplicado_409(self):
        self.crear_proveedor(nit="900123456-7")
        r = self.admin.post(URL, NUEVO, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"], "CONFLICTO")

    def test_datos_invalidos_400(self):
        r = self.admin.post(URL, {"razon_social": "Sin NIT"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("nit", r.json()["mensaje"])
        r = self.admin.post(URL, {**NUEVO, "email": "no-es-correo"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_no_se_puede_crear_inactivo(self):
        r = self.admin.post(URL, {**NUEVO, "activo": False}, format="json")
        self.assertTrue(r.json()["activo"])

    def test_lista_filtros_y_activos_por_defecto(self):
        self.crear_proveedor("1", "Lácteos del Eje")
        self.crear_proveedor("2", "Aseo Total")
        self.crear_proveedor("3", "Lácteos viejos", activo=False)
        self.assertEqual(len(self.interno.get(URL).json()), 2)
        r = self.operador.get(URL, {"razon_social": "DEL EJE"})
        self.assertEqual([p["nit"] for p in r.json()], ["1"])
        self.assertEqual([p["nit"] for p in self.operador.get(URL, {"nit": "2"}).json()], ["2"])
        self.assertEqual([p["nit"] for p in self.operador.get(URL, {"activo": "false"}).json()], ["3"])

    def test_detalle_sin_cabeceras_como_hace_existencias(self):
        p = self.crear_proveedor(ciudad="Pereira")
        r = self.interno.get(f"{URL}/{p.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json()), {"id", "nit", "razon_social", "telefono", "email", "ciudad", "activo"})
        self.assertEqual(r.json()["razon_social"], "Lácteos del Eje S.A.S.")

    def test_detalle_de_proveedor_inactivo_devuelve_activo_false(self):
        p = self.crear_proveedor(activo=False)
        r = self.interno.get(f"{URL}/{p.id}")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["activo"])

    def test_detalle_inexistente_404(self):
        r = self.interno.get(f"{URL}/9999")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json(), {"error": "NO_ENCONTRADO", "mensaje": "El proveedor 9999 no existe"})

    def test_actualizar(self):
        p = self.crear_proveedor()
        r = self.admin.put(f"{URL}/{p.id}", {**NUEVO, "ciudad": "Manizales"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["ciudad"], "Manizales")

    def test_actualizar_con_nit_de_otro_409(self):
        self.crear_proveedor(nit="111")
        p = self.crear_proveedor(nit="222")
        r = self.admin.put(f"{URL}/{p.id}", {**NUEVO, "nit": "111"}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_actualizar_conservando_su_nit_es_valido(self):
        p = self.crear_proveedor(nit="900123456-7")
        self.assertEqual(self.admin.put(f"{URL}/{p.id}", NUEVO, format="json").status_code, 200)

    def test_put_sin_activo_conserva_el_estado(self):
        p = self.crear_proveedor(activo=False)
        self.assertFalse(self.admin.put(f"{URL}/{p.id}", NUEVO, format="json").json()["activo"])

    def test_put_reactiva_proveedor(self):
        p = self.crear_proveedor(activo=False)
        r = self.admin.put(f"{URL}/{p.id}", {**NUEVO, "activo": True}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["activo"])
        self.assertTrue(self.interno.get(f"{URL}/{p.id}").json()["activo"])

    def test_baja_logica(self):
        p = self.crear_proveedor()
        self.assertEqual(self.admin.delete(f"{URL}/{p.id}").status_code, 204)
        p.refresh_from_db()
        self.assertFalse(p.activo)

    def test_baja_inexistente_404(self):
        self.assertEqual(self.admin.delete(f"{URL}/9999").status_code, 404)

    def test_baja_solo_admin(self):
        p = self.crear_proveedor()
        self.assertEqual(self.operador.delete(f"{URL}/{p.id}").status_code, 403)
