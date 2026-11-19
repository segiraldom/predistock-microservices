from decimal import Decimal

from catalogo.models import ProductoProveedor

from .base import PREFIJO, BaseAPITest

URL = f"{PREFIJO}/productos"


class ProductosEscrituraTest(BaseAPITest):
    def test_admin_crea_producto(self):
        r = self.admin.post(URL, self.datos_producto(), format="json")
        self.assertEqual(r.status_code, 201)
        cuerpo = r.json()
        self.assertEqual(set(cuerpo), {"id", "codigo", "nombre", "descripcion", "categoria_id", "unidad_medida_id",
                                       "precio_venta", "costo", "es_perecedero", "activo"})
        self.assertTrue(cuerpo["activo"])
        self.assertTrue(cuerpo["es_perecedero"])
        self.assertEqual(cuerpo["precio_venta"], 4500)  # number, no string

    def test_es_perecedero_por_defecto_false(self):
        datos = self.datos_producto()
        del datos["es_perecedero"]
        self.assertFalse(self.admin.post(URL, datos, format="json").json()["es_perecedero"])

    def test_solo_admin_escribe(self):
        datos = self.datos_producto()
        for c in (self.operador, self.analista, self.interno):
            r = c.post(URL, datos, format="json")
            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.json()["error"], "SIN_PERMISO")

    def test_rol_administrador_se_normaliza(self):
        r = self.cliente("Administrador").post(URL, self.datos_producto(), format="json")
        self.assertEqual(r.status_code, 201)

    def test_codigo_duplicado_409(self):
        self.crear_producto(codigo="LAC-001")
        r = self.admin.post(URL, self.datos_producto(codigo="lac-001"), format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"], "CONFLICTO")

    def test_campos_obligatorios_400(self):
        r = self.admin.post(URL, {"codigo": "X"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "DATOS_INVALIDOS")
        for campo in ("nombre", "categoria_id", "unidad_medida_id", "precio_venta", "costo"):
            self.assertIn(campo, r.json()["mensaje"])

    def test_precios_negativos_400(self):
        self.assertEqual(self.admin.post(URL, self.datos_producto(costo=-1), format="json").status_code, 400)
        self.assertEqual(self.admin.post(URL, self.datos_producto(precio_venta=-5), format="json").status_code, 400)

    def test_categoria_inexistente_o_inactiva_400(self):
        self.assertEqual(self.admin.post(URL, self.datos_producto(categoria_id=9999), format="json").status_code, 400)
        inactiva = self.crear_categoria("Vieja", activo=False)
        self.assertEqual(self.admin.post(URL, self.datos_producto(categoria=inactiva), format="json").status_code, 400)

    def test_unidad_inexistente_400(self):
        self.assertEqual(self.admin.post(URL, self.datos_producto(unidad_medida_id=9999), format="json").status_code, 400)

    def test_actualizar(self):
        p = self.crear_producto()
        r = self.admin.put(f"{URL}/{p.id}", self.datos_producto(categoria=p.categoria, unidad=p.unidad_medida,
                                                                nombre="Leche deslactosada", costo=3500),
                           format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["nombre"], "Leche deslactosada")
        p.refresh_from_db()
        self.assertEqual(p.costo, Decimal("3500.00"))

    def test_actualizar_con_codigo_de_otro_409(self):
        self.crear_producto(codigo="A")
        b = self.crear_producto(codigo="B")
        r = self.admin.put(f"{URL}/{b.id}", self.datos_producto(categoria=b.categoria, unidad=b.unidad_medida,
                                                                codigo="A"), format="json")
        self.assertEqual(r.status_code, 409)

    def test_actualizar_inexistente_404(self):
        self.assertEqual(self.admin.put(f"{URL}/9999", self.datos_producto(), format="json").status_code, 404)

    def test_put_sin_activo_conserva_el_estado(self):
        p = self.crear_producto(activo=False)
        r = self.admin.put(f"{URL}/{p.id}", self.datos_producto(categoria=p.categoria, unidad=p.unidad_medida),
                           format="json")
        self.assertFalse(r.json()["activo"])

    def test_put_reactiva_producto(self):
        p = self.crear_producto(activo=False)
        r = self.admin.put(f"{URL}/{p.id}", {**self.datos_producto(categoria=p.categoria, unidad=p.unidad_medida),
                                              "activo": True}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["activo"])

    def test_put_da_de_baja_producto(self):
        p = self.crear_producto()
        r = self.admin.put(f"{URL}/{p.id}", {**self.datos_producto(categoria=p.categoria, unidad=p.unidad_medida),
                                              "activo": False}, format="json")
        self.assertFalse(r.json()["activo"])

    def test_no_reactiva_producto_de_categoria_inactiva_400(self):
        cat = self.crear_categoria("Vieja", activo=False)
        p = self.crear_producto(categoria=cat, activo=False)
        r = self.admin.put(f"{URL}/{p.id}", {**self.datos_producto(categoria=cat, unidad=p.unidad_medida),
                                              "activo": True}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_editar_producto_inactivo_de_categoria_inactiva_es_valido(self):
        cat = self.crear_categoria("Vieja", activo=False)
        p = self.crear_producto(categoria=cat, activo=False)
        r = self.admin.put(f"{URL}/{p.id}", self.datos_producto(categoria=cat, unidad=p.unidad_medida,
                                                                nombre="Corregido"), format="json")
        self.assertEqual(r.status_code, 200)

    def test_post_ignora_activo(self):
        r = self.admin.post(URL, {**self.datos_producto(), "activo": False}, format="json")
        self.assertTrue(r.json()["activo"])

    def test_baja_logica(self):
        p = self.crear_producto()
        self.assertEqual(self.admin.delete(f"{URL}/{p.id}").status_code, 204)
        p.refresh_from_db()
        self.assertFalse(p.activo)

    def test_baja_inexistente_404_y_solo_admin(self):
        self.assertEqual(self.admin.delete(f"{URL}/9999").status_code, 404)
        p = self.crear_producto()
        self.assertEqual(self.operador.delete(f"{URL}/{p.id}").status_code, 403)


class ProductoDetalleTest(BaseAPITest):
    """Contrato que consume ms-existencias: activo, es_perecedero, costo, codigo y nombre."""

    def test_detalle_sin_cabeceras(self):
        prov = self.crear_proveedor()
        p = self.crear_producto(es_perecedero=True)
        ProductoProveedor.objects.create(producto=p, proveedor=prov, precio_compra=3100, es_principal=True)
        r = self.interno.get(f"{URL}/{p.id}")
        self.assertEqual(r.status_code, 200)
        c = r.json()
        self.assertEqual((c["codigo"], c["nombre"], c["activo"], c["es_perecedero"]),
                         ("LAC-001", "Leche entera 1L", True, True))
        self.assertEqual(c["costo"], 3200)
        self.assertEqual(c["categoria"]["id"], p.categoria_id)
        self.assertEqual(c["unidad_medida"]["id"], p.unidad_medida_id)
        self.assertEqual(c["proveedores"], [{"proveedor_id": prov.id, "razon_social": "Lácteos del Eje S.A.S.",
                                             "precio_compra": 3100, "es_principal": True}])

    def test_detalle_de_producto_inactivo_devuelve_activo_false(self):
        p = self.crear_producto(activo=False)
        r = self.interno.get(f"{URL}/{p.id}")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["activo"])

    def test_detalle_inexistente_404_con_formato_de_error(self):
        r = self.interno.get(f"{URL}/9999")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json(), {"error": "NO_ENCONTRADO", "mensaje": "El producto 9999 no existe"})

    def test_ruta_inexistente_404_con_formato_de_error(self):
        r = self.interno.get(f"{PREFIJO}/no-existe")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "NO_ENCONTRADO")

    def test_metodo_no_permitido_405(self):
        r = self.admin.patch(f"{URL}/1", {}, format="json")
        self.assertEqual(r.status_code, 405)
        self.assertEqual(r.json()["error"], "METODO_NO_PERMITIDO")


class ProductosListaTest(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.alimentos = self.crear_categoria("Alimentos")
        self.lacteos = self.crear_categoria("Lácteos", padre=self.alimentos)
        self.aseo = self.crear_categoria("Aseo")
        self.unidad = self.crear_unidad("UND")
        self.leche = self.crear_producto(self.lacteos, self.unidad, "LAC-001", nombre="Leche entera 1L")
        self.arroz = self.crear_producto(self.alimentos, self.unidad, "ABA-001", nombre="Arroz 500g")
        self.jabon = self.crear_producto(self.aseo, self.unidad, "ASE-001", nombre="Jabón en barra")
        self.viejo = self.crear_producto(self.aseo, self.unidad, "ASE-999", nombre="Jabón viejo", activo=False)

    def ids(self, **params):
        r = self.operador.get(URL, params)
        self.assertEqual(r.status_code, 200)
        return sorted(p["codigo"] for p in r.json()["results"])

    def test_estructura_y_activos_por_defecto(self):
        r = self.operador.get(URL).json()
        self.assertEqual((r["total"], r["page"]), (3, 1))
        self.assertEqual(self.ids(), ["ABA-001", "ASE-001", "LAC-001"])

    def test_filtra_inactivos(self):
        self.assertEqual(self.ids(activo="false"), ["ASE-999"])

    def test_busqueda_parcial_por_nombre(self):
        self.assertEqual(self.ids(nombre="LECHE"), ["LAC-001"])
        self.assertEqual(self.ids(nombre="jab"), ["ASE-001"])

    def test_codigo_exacto(self):
        self.assertEqual(self.ids(codigo="abа-001".replace("а", "a")), ["ABA-001"])
        self.assertEqual(self.ids(codigo="ABA"), [])

    def test_categoria_incluye_subcategorias(self):
        self.assertEqual(self.ids(categoria_id=self.alimentos.id), ["ABA-001", "LAC-001"])
        self.assertEqual(self.ids(categoria_id=self.lacteos.id), ["LAC-001"])

    def test_por_proveedor(self):
        prov = self.crear_proveedor()
        ProductoProveedor.objects.create(producto=self.arroz, proveedor=prov, precio_compra=1)
        self.assertEqual(self.ids(proveedor_id=prov.id), ["ABA-001"])

    def test_filtros_combinados(self):
        self.assertEqual(self.ids(categoria_id=self.alimentos.id, nombre="arroz"), ["ABA-001"])

    def test_paginacion(self):
        r = self.operador.get(URL, {"page_size": 2}).json()
        self.assertEqual((r["total"], len(r["results"])), (3, 2))
        r = self.operador.get(URL, {"page_size": 2, "page": 2}).json()
        self.assertEqual((r["page"], len(r["results"])), (2, 1))

    def test_page_size_se_limita_a_100(self):
        self.assertEqual(self.operador.get(URL, {"page_size": 5000}).status_code, 200)

    def test_parametros_invalidos_400(self):
        self.assertEqual(self.operador.get(URL, {"page": 0}).status_code, 400)
        self.assertEqual(self.operador.get(URL, {"categoria_id": "x"}).status_code, 400)
        self.assertEqual(self.operador.get(URL, {"activo": "quizas"}).status_code, 400)

    def test_lista_sin_cabeceras(self):
        self.assertEqual(self.interno.get(URL).status_code, 200)


class AsociacionProveedorTest(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.producto = self.crear_producto()
        self.prov1 = self.crear_proveedor("1", "Proveedor Uno")
        self.prov2 = self.crear_proveedor("2", "Proveedor Dos")
        self.url = f"{URL}/{self.producto.id}/proveedores"

    def asociar(self, proveedor, precio=3100, **extra):
        return self.admin.post(self.url, {"proveedor_id": proveedor.id, "precio_compra": precio, **extra},
                               format="json")

    def test_asocia_proveedor(self):
        r = self.asociar(self.prov1, es_principal=True)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json(), {"proveedor_id": self.prov1.id, "razon_social": "Proveedor Uno",
                                    "precio_compra": 3100, "es_principal": True})

    def test_es_principal_por_defecto_false(self):
        self.assertFalse(self.asociar(self.prov1).json()["es_principal"])

    def test_solo_admin(self):
        r = self.operador.post(self.url, {"proveedor_id": self.prov1.id, "precio_compra": 1}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_asociacion_duplicada_409(self):
        self.asociar(self.prov1)
        self.assertEqual(self.asociar(self.prov1).status_code, 409)

    def test_un_solo_proveedor_principal(self):
        self.asociar(self.prov1, es_principal=True)
        self.asociar(self.prov2, es_principal=True)
        principales = ProductoProveedor.objects.filter(producto=self.producto, es_principal=True)
        self.assertEqual([a.proveedor_id for a in principales], [self.prov2.id])
        self.assertEqual(ProductoProveedor.objects.filter(producto=self.producto).count(), 2)

    def test_producto_o_proveedor_inexistente_404(self):
        self.assertEqual(self.admin.post(f"{URL}/9999/proveedores", {"proveedor_id": self.prov1.id,
                                         "precio_compra": 1}, format="json").status_code, 404)
        r = self.admin.post(self.url, {"proveedor_id": 9999, "precio_compra": 1}, format="json")
        self.assertEqual(r.status_code, 404)

    def test_proveedor_inactivo_400(self):
        inactivo = self.crear_proveedor("3", "Inactivo", activo=False)
        self.assertEqual(self.asociar(inactivo).status_code, 400)

    def test_datos_invalidos_400(self):
        self.assertEqual(self.admin.post(self.url, {"proveedor_id": self.prov1.id}, format="json").status_code, 400)
        self.assertEqual(self.asociar(self.prov1, precio=-1).status_code, 400)

    def test_aparece_en_detalle_y_filtra_la_lista(self):
        self.asociar(self.prov1, 3100, es_principal=True)
        self.asociar(self.prov2, 3300)
        detalle = self.interno.get(f"{URL}/{self.producto.id}").json()
        self.assertEqual(sorted(p["proveedor_id"] for p in detalle["proveedores"]), [self.prov1.id, self.prov2.id])
        r = self.operador.get(URL, {"proveedor_id": self.prov2.id}).json()
        self.assertEqual(r["total"], 1)

    def test_elimina_asociacion(self):
        self.asociar(self.prov1)
        r = self.admin.delete(f"{self.url}/{self.prov1.id}")
        self.assertEqual(r.status_code, 204)
        self.assertFalse(ProductoProveedor.objects.exists())
        self.assertEqual(self.admin.delete(f"{self.url}/{self.prov1.id}").status_code, 404)

    def test_elimina_asociacion_de_producto_inexistente_404(self):
        self.assertEqual(self.admin.delete(f"{URL}/9999/proveedores/{self.prov1.id}").status_code, 404)

    def test_elimina_asociacion_solo_admin(self):
        self.asociar(self.prov1)
        self.assertEqual(self.operador.delete(f"{self.url}/{self.prov1.id}").status_code, 403)

    def test_dar_de_baja_producto_conserva_asociaciones(self):
        self.asociar(self.prov1)
        self.admin.delete(f"{URL}/{self.producto.id}")
        self.assertEqual(ProductoProveedor.objects.count(), 1)
        self.assertEqual(len(self.interno.get(f"{URL}/{self.producto.id}").json()["proveedores"]), 1)


class SaludTest(BaseAPITest):
    def test_health(self):
        r = self.interno.get(f"{PREFIJO}/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok", "servicio": "ms-catalogo"})


class ActualizarAsociacionTest(BaseAPITest):
    """PUT /productos/{id}/proveedores/{proveedor_id}: precio y proveedor principal."""

    def setUp(self):
        super().setUp()
        self.producto = self.crear_producto()
        self.prov1 = self.crear_proveedor("1", "Proveedor Uno")
        self.prov2 = self.crear_proveedor("2", "Proveedor Dos")
        ProductoProveedor.objects.create(producto=self.producto, proveedor=self.prov1, precio_compra=3100,
                                         es_principal=True)
        ProductoProveedor.objects.create(producto=self.producto, proveedor=self.prov2, precio_compra=3300)
        self.base = f"{URL}/{self.producto.id}/proveedores"

    def principales(self):
        return list(ProductoProveedor.objects.filter(producto=self.producto, es_principal=True)
                    .values_list("proveedor_id", flat=True))

    def test_cambia_precio_y_conserva_principal(self):
        r = self.admin.put(f"{self.base}/{self.prov1.id}", {"precio_compra": 3000}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"proveedor_id": self.prov1.id, "razon_social": "Proveedor Uno",
                                    "precio_compra": 3000, "es_principal": True})

    def test_cambia_el_proveedor_principal(self):
        r = self.admin.put(f"{self.base}/{self.prov2.id}", {"precio_compra": 3300, "es_principal": True},
                           format="json")
        self.assertTrue(r.json()["es_principal"])
        self.assertEqual(self.principales(), [self.prov2.id])

    def test_quitar_principal_deja_al_producto_sin_principal(self):
        self.admin.put(f"{self.base}/{self.prov1.id}", {"precio_compra": 3100, "es_principal": False},
                       format="json")
        self.assertEqual(self.principales(), [])

    def test_marcar_principal_al_que_ya_lo_es(self):
        r = self.admin.put(f"{self.base}/{self.prov1.id}", {"precio_compra": 1, "es_principal": True},
                           format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.principales(), [self.prov1.id])

    def test_asociacion_inexistente_404(self):
        otro = self.crear_proveedor("3", "Sin asociar")
        self.assertEqual(self.admin.put(f"{self.base}/{otro.id}", {"precio_compra": 1}, format="json").status_code,
                         404)
        self.assertEqual(self.admin.put(f"{URL}/9999/proveedores/{self.prov1.id}", {"precio_compra": 1},
                                        format="json").status_code, 404)

    def test_datos_invalidos_400(self):
        self.assertEqual(self.admin.put(f"{self.base}/{self.prov1.id}", {}, format="json").status_code, 400)
        self.assertEqual(self.admin.put(f"{self.base}/{self.prov1.id}", {"precio_compra": -1},
                                        format="json").status_code, 400)

    def test_solo_admin(self):
        r = self.operador.put(f"{self.base}/{self.prov1.id}", {"precio_compra": 1}, format="json")
        self.assertEqual(r.status_code, 403)
