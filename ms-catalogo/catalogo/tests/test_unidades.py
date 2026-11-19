from .base import PREFIJO, BaseAPITest

URL = f"{PREFIJO}/unidades-medida"


class UnidadesTest(BaseAPITest):
    def test_admin_crea_unidad(self):
        r = self.admin.post(URL, {"codigo": "PACA6", "nombre": "Paca x 6 unidades"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(set(r.json()), {"id", "codigo", "nombre"})

    def test_solo_admin_escribe(self):
        for c in (self.operador, self.analista, self.interno):
            r = c.post(URL, {"codigo": "X", "nombre": "X"}, format="json")
            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.json()["error"], "SIN_PERMISO")

    def test_codigo_duplicado_409_sin_distinguir_mayusculas(self):
        self.crear_unidad("UND")
        r = self.admin.post(URL, {"codigo": "und", "nombre": "Otra"}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"], "CONFLICTO")

    def test_datos_invalidos_400_con_formato_de_error(self):
        r = self.admin.post(URL, {"codigo": "ESTE-CODIGO-ES-DEMASIADO-LARGO", "nombre": "X"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "DATOS_INVALIDOS")
        self.assertIn("codigo", r.json()["mensaje"])

    def test_lista_visible_para_cualquier_rol(self):
        self.crear_unidad("UND")
        self.crear_unidad("KG", "Kilogramo")
        self.assertEqual(len(self.operador.get(URL).json()), 2)
        self.assertEqual(len(self.interno.get(URL).json()), 2)

    def test_actualizar(self):
        u = self.crear_unidad("UND")
        r = self.admin.put(f"{URL}/{u.id}", {"codigo": "UND", "nombre": "Unidad suelta"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["nombre"], "Unidad suelta")

    def test_actualizar_a_codigo_de_otra_409(self):
        self.crear_unidad("UND")
        kg = self.crear_unidad("KG", "Kilogramo")
        r = self.admin.put(f"{URL}/{kg.id}", {"codigo": "UND", "nombre": "Kilogramo"}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_actualizar_inexistente_404(self):
        r = self.admin.put(f"{URL}/9999", {"codigo": "X", "nombre": "X"}, format="json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "NO_ENCONTRADO")

    def test_eliminar_unidad_sin_uso(self):
        u = self.crear_unidad("UND")
        self.assertEqual(self.admin.delete(f"{URL}/{u.id}").status_code, 204)
        self.assertEqual(self.admin.get(URL).json(), [])

    def test_eliminar_unidad_en_uso_409(self):
        u = self.crear_unidad("CAJA", "Caja")
        self.crear_producto(unidad=u, codigo="A")
        self.crear_producto(unidad=u, codigo="B")
        r = self.admin.delete(f"{URL}/{u.id}")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"], "UNIDAD_EN_USO")
        self.assertEqual(r.json()["mensaje"], "La unidad CAJA está asignada a 2 productos y no puede eliminarse")

    def test_operador_no_elimina(self):
        u = self.crear_unidad("UND")
        self.assertEqual(self.operador.delete(f"{URL}/{u.id}").status_code, 403)
