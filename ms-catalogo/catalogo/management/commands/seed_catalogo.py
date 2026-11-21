"""
Siembra el catálogo de demostración (unidades, categorías, proveedores y 10 productos).

Usa los endpoints reales del servicio (cliente de pruebas de Django, en el mismo proceso y como
ADMIN), de modo que se aplican las mismas validaciones y reglas de unicidad que en producción.
Es idempotente: lo que ya existe (por código, NIT o nombre) se reutiliza y no se duplica.

    python manage.py seed_catalogo              # solo muestra qué haría
    python manage.py seed_catalogo --confirmo   # ejecuta
"""
from django.core.management.base import BaseCommand, CommandError
from django.test import Client

CABECERAS = {"X-Rol": "ADMIN", "X-Usuario-Id": "1"}
BASE = "/api/catalogo"

UNIDADES = [("UND", "Unidad"), ("KG", "Kilogramo"), ("LT", "Litro")]

# (nombre, descripción, padre o None)
CATEGORIAS = [
    ("Alimentos", "Alimentos y abarrotes", None),
    ("Lácteos", "Leche, yogur y quesos", "Alimentos"),
    ("Granos", "Arroz, lentejas y similares", "Alimentos"),
    ("Bebidas", "Gaseosas y jugos", None),
    ("Aseo", "Productos de aseo", None),
    ("Limpieza hogar", "Detergentes y desinfectantes", "Aseo"),
    ("Papelería", "Útiles y papelería", None),
]

# (NIT, razón social, teléfono, email, ciudad)
PROVEEDORES = [
    ("900100200-1", "Distribuidora Andina S.A.S.", "6015550101", "ventas@andina.example.com", "Bogotá"),
    ("900200300-2", "Lácteos del Valle Ltda.", "6025550102", "pedidos@lacteosvalle.example.com", "Cali"),
    ("900300400-3", "Aseo Total S.A.", "6045550103", "comercial@aseototal.example.com", "Medellín"),
    ("900400500-4", "Papelería y Suministros del Centro", "6015550104", "info@papelcentro.example.com", "Bogotá"),
]

# (código, nombre, categoría, unidad, precio_venta, costo, perecedero, [(NIT proveedor, precio_compra), ...])
# El primer proveedor de la lista es el principal. Los perfiles de rotación se definen en seed_existencias.
PRODUCTOS = [
    ("PRD-001", "Leche entera 1L", "Lácteos", "LT", "4200.00", "3100.00", True,
     [("900200300-2", "3100.00"), ("900100200-1", "3250.00")]),
    ("PRD-002", "Arroz blanco 500g", "Granos", "UND", "2800.00", "2000.00", False,
     [("900100200-1", "2000.00")]),
    ("PRD-003", "Gaseosa cola 1.5L", "Bebidas", "UND", "5600.00", "4100.00", False,
     [("900100200-1", "4100.00")]),
    ("PRD-004", "Yogur fresa 200g", "Lácteos", "UND", "2300.00", "1500.00", True,
     [("900200300-2", "1500.00")]),
    ("PRD-005", "Detergente líquido 1L", "Limpieza hogar", "UND", "9800.00", "7200.00", False,
     [("900300400-3", "7200.00"), ("900100200-1", "7500.00")]),
    ("PRD-006", "Jugo de naranja 1L", "Bebidas", "UND", "4700.00", "3300.00", False,
     [("900100200-1", "3300.00")]),
    ("PRD-007", "Lentejas 500g", "Granos", "UND", "3100.00", "2200.00", False,
     [("900100200-1", "2200.00")]),
    ("PRD-008", "Cuaderno 100 hojas", "Papelería", "UND", "6500.00", "4300.00", False,
     [("900400500-4", "4300.00")]),
    ("PRD-009", "Desinfectante 2L", "Limpieza hogar", "UND", "12900.00", "9400.00", False,
     [("900300400-3", "9400.00")]),
    ("PRD-010", "Queso campesino 500g", "Lácteos", "UND", "11800.00", "8600.00", True,
     [("900200300-2", "8600.00")]),
]


class Api:
    """Cliente mínimo sobre los endpoints del propio servicio."""

    def __init__(self):
        self.client = Client(raise_request_exception=False)

    def _resp(self, resp, esperado):
        if resp.status_code not in esperado:
            raise CommandError(f"{resp.status_code} {resp.content.decode()[:300]}")
        return resp.json() if resp.content else None

    def get(self, ruta, **params):
        return self._resp(self.client.get(f"{BASE}{ruta}", params, headers=CABECERAS), (200,))

    def post(self, ruta, datos):
        resp = self.client.post(f"{BASE}{ruta}", datos, content_type="application/json", headers=CABECERAS)
        return self._resp(resp, (201,))


class Command(BaseCommand):
    help = "Siembra el catálogo de demostración (unidades, categorías, proveedores y productos)."

    def add_arguments(self, parser):
        parser.add_argument("--confirmo", action="store_true", help="Ejecuta la siembra (sin esto solo la describe)")

    def handle(self, *args, **opciones):
        if not opciones["confirmo"]:
            self.stdout.write(
                f"[dry-run] Crearía (si no existen): {len(UNIDADES)} unidades, {len(CATEGORIAS)} categorías, "
                f"{len(PROVEEDORES)} proveedores y {len(PRODUCTOS)} productos con sus proveedores.\n"
                "Ejecute con --confirmo para aplicarlo.")
            return

        api = Api()
        creados = {"unidades": 0, "categorias": 0, "proveedores": 0, "productos": 0, "asociaciones": 0}

        unidades = {u["codigo"].upper(): u["id"] for u in api.get("/unidades-medida")}
        for codigo, nombre in UNIDADES:
            if codigo not in unidades:
                unidades[codigo] = api.post("/unidades-medida", {"codigo": codigo, "nombre": nombre})["id"]
                creados["unidades"] += 1

        categorias = {}
        for nombre, descripcion, padre in CATEGORIAS:
            padre_id = categorias[padre] if padre else None
            existentes = api.get("/categorias", padre_id=padre_id) if padre_id else api.get("/categorias")
            existente = next((c for c in existentes if c["nombre"].lower() == nombre.lower()), None)
            if existente is None:
                datos = {"nombre": nombre, "descripcion": descripcion}
                if padre_id:
                    datos["categoria_padre_id"] = padre_id
                existente = api.post("/categorias", datos)
                creados["categorias"] += 1
            categorias[nombre] = existente["id"]

        proveedores = {}
        for nit, razon, telefono, email, ciudad in PROVEEDORES:
            existentes = api.get("/proveedores", nit=nit)
            if existentes:
                proveedores[nit] = existentes[0]["id"]
                continue
            proveedores[nit] = api.post("/proveedores", {
                "nit": nit, "razon_social": razon, "telefono": telefono, "email": email, "ciudad": ciudad})["id"]
            creados["proveedores"] += 1

        for codigo, nombre, categoria, unidad, precio, costo, perecedero, provs in PRODUCTOS:
            existentes = api.get("/productos", codigo=codigo)["results"]
            if existentes:
                producto_id = existentes[0]["id"]
            else:
                producto_id = api.post("/productos", {
                    "codigo": codigo, "nombre": nombre, "categoria_id": categorias[categoria],
                    "unidad_medida_id": unidades[unidad], "precio_venta": precio, "costo": costo,
                    "es_perecedero": perecedero})["id"]
                creados["productos"] += 1
                for i, (nit, precio_compra) in enumerate(provs):
                    api.post(f"/productos/{producto_id}/proveedores", {
                        "proveedor_id": proveedores[nit], "precio_compra": precio_compra, "es_principal": i == 0})
                    creados["asociaciones"] += 1

        resumen = ", ".join(f"{v} {k}" for k, v in creados.items())
        self.stdout.write(self.style.SUCCESS(f"Catálogo sembrado. Creados ahora: {resumen}."))
        ids = {p["codigo"]: p["id"] for p in api.get("/productos", page_size=100)["results"]}
        self.stdout.write(f"Ids de producto: {ids}")
