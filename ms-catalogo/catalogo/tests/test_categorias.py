from .base import PREFIJO, BaseAPITest

URL = f"{PREFIJO}/categorias"


class CategoriasTest(BaseAPITest):
    def test_admin_crea_categoria_principal(self):
        r = self.admin.post(URL, {"nombre": "Lácteos", "descripcion": "Leche y derivados"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(r.json()["categoria_padre_id"])
        self.assertTrue(r.json()["activo"])

    def test_crea_subcategoria(self):
        padre = self.crear_categoria("Alimentos")
        r = self.admin.post(URL, {"nombre": "Lácteos", "categoria_padre_id": padre.id}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["categoria_padre_id"], padre.id)

    def test_solo_admin_escribe(self):
        r = self.operador.post(URL, {"nombre": "X"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.interno.post(URL, {"nombre": "X"}, format="json").status_code, 403)

    def test_nombre_obligatorio_400(self):
        r = self.admin.post(URL, {"descripcion": "sin nombre"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "DATOS_INVALIDOS")

    def test_padre_inexistente_400(self):
        r = self.admin.post(URL, {"nombre": "X", "categoria_padre_id": 9999}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_padre_inactivo_400(self):
        padre = self.crear_categoria("Vieja", activo=False)
        r = self.admin.post(URL, {"nombre": "X", "categoria_padre_id": padre.id}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_nombre_duplicado_en_el_mismo_nivel_409(self):
        self.crear_categoria("Lácteos")
        r = self.admin.post(URL, {"nombre": "lácteos"}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_mismo_nombre_en_distinto_nivel_es_valido(self):
        padre = self.crear_categoria("Alimentos")
        self.crear_categoria("Otros")
        r = self.admin.post(URL, {"nombre": "Otros", "categoria_padre_id": padre.id}, format="json")
        self.assertEqual(r.status_code, 201)

    def test_lista_sin_padre_devuelve_principales(self):
        a = self.crear_categoria("Alimentos")
        self.crear_categoria("Lácteos", padre=a)
        self.crear_categoria("Aseo")
        nombres = [c["nombre"] for c in self.interno.get(URL).json()]
        self.assertEqual(nombres, ["Alimentos", "Aseo"])

    def test_lista_con_padre_devuelve_subcategorias(self):
        a = self.crear_categoria("Alimentos")
        self.crear_categoria("Lácteos", padre=a)
        self.crear_categoria("Aseo")
        r = self.operador.get(URL, {"padre_id": a.id})
        self.assertEqual([c["nombre"] for c in r.json()], ["Lácteos"])

    def test_lista_filtra_activas_por_defecto(self):
        self.crear_categoria("Activa")
        self.crear_categoria("Inactiva", activo=False)
        self.assertEqual(len(self.operador.get(URL).json()), 1)
        self.assertEqual(len(self.operador.get(URL, {"activo": "false"}).json()), 1)

    def test_parametros_invalidos_400(self):
        self.assertEqual(self.operador.get(URL, {"activo": "quizas"}).status_code, 400)
        self.assertEqual(self.operador.get(URL, {"padre_id": "abc"}).status_code, 400)

    def test_actualizar(self):
        c = self.crear_categoria("Lacteos")
        r = self.admin.put(f"{URL}/{c.id}", {"nombre": "Lácteos", "descripcion": "Leche"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["nombre"], "Lácteos")

    def test_mover_a_otro_padre(self):
        a = self.crear_categoria("Alimentos")
        c = self.crear_categoria("Lácteos")
        r = self.admin.put(f"{URL}/{c.id}", {"nombre": "Lácteos", "categoria_padre_id": a.id}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["categoria_padre_id"], a.id)

    def test_categoria_como_su_propio_padre_400(self):
        c = self.crear_categoria("Lácteos")
        r = self.admin.put(f"{URL}/{c.id}", {"nombre": "Lácteos", "categoria_padre_id": c.id}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "DATOS_INVALIDOS")

    def test_ciclo_con_descendiente_400(self):
        a = self.crear_categoria("A")
        b = self.crear_categoria("B", padre=a)
        c = self.crear_categoria("C", padre=b)
        r = self.admin.put(f"{URL}/{a.id}", {"nombre": "A", "categoria_padre_id": c.id}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_actualizar_inexistente_404(self):
        self.assertEqual(self.admin.put(f"{URL}/9999", {"nombre": "X"}, format="json").status_code, 404)

    def test_baja_logica(self):
        c = self.crear_categoria("Lácteos")
        self.assertEqual(self.admin.delete(f"{URL}/{c.id}").status_code, 204)
        c.refresh_from_db()
        self.assertFalse(c.activo)
        self.assertEqual(self.operador.get(URL).json(), [])

    def test_baja_con_productos_activos_409(self):
        c = self.crear_categoria("Lácteos")
        self.crear_producto(categoria=c)
        r = self.admin.delete(f"{URL}/{c.id}")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"], "CATEGORIA_EN_USO")

    def test_baja_con_subcategorias_activas_409(self):
        a = self.crear_categoria("Alimentos")
        self.crear_categoria("Lácteos", padre=a)
        self.assertEqual(self.admin.delete(f"{URL}/{a.id}").status_code, 409)

    def test_baja_ignora_productos_y_subcategorias_inactivos(self):
        a = self.crear_categoria("Alimentos")
        self.crear_categoria("Vieja", padre=a, activo=False)
        self.crear_producto(categoria=a, activo=False)
        self.assertEqual(self.admin.delete(f"{URL}/{a.id}").status_code, 204)

    def test_baja_solo_admin(self):
        c = self.crear_categoria("Lácteos")
        self.assertEqual(self.operador.delete(f"{URL}/{c.id}").status_code, 403)


class ReactivacionCategoriaTest(BaseAPITest):
    def test_put_sin_activo_conserva_el_estado(self):
        c = self.crear_categoria("Vieja", activo=False)
        self.assertFalse(self.admin.put(f"{URL}/{c.id}", {"nombre": "Vieja"}, format="json").json()["activo"])

    def test_put_reactiva(self):
        c = self.crear_categoria("Vieja", activo=False)
        r = self.admin.put(f"{URL}/{c.id}", {"nombre": "Vieja", "activo": True}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["activo"])

    def test_no_reactiva_subcategoria_con_padre_inactivo_400(self):
        padre = self.crear_categoria("Padre", activo=False)
        hija = self.crear_categoria("Hija", padre=padre, activo=False)
        r = self.admin.put(f"{URL}/{hija.id}", {"nombre": "Hija", "categoria_padre_id": padre.id, "activo": True},
                           format="json")
        self.assertEqual(r.status_code, 400)

    def test_editar_subcategoria_inactiva_con_padre_inactivo_es_valido(self):
        padre = self.crear_categoria("Padre", activo=False)
        hija = self.crear_categoria("Hija", padre=padre, activo=False)
        r = self.admin.put(f"{URL}/{hija.id}", {"nombre": "Hija 2", "categoria_padre_id": padre.id},
                           format="json")
        self.assertEqual(r.status_code, 200)

    def test_baja_por_put_aplica_la_misma_regla_que_delete(self):
        c = self.crear_categoria("Lácteos")
        self.crear_producto(categoria=c)
        r = self.admin.put(f"{URL}/{c.id}", {"nombre": "Lácteos", "activo": False}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"], "CATEGORIA_EN_USO")

    def test_baja_por_put_sin_dependencias(self):
        c = self.crear_categoria("Lácteos")
        r = self.admin.put(f"{URL}/{c.id}", {"nombre": "Lácteos", "activo": False}, format="json")
        self.assertFalse(r.json()["activo"])
