# API Gateway

Único punto de entrada de PrediStock. Toda petición externa pasa por el Gateway, que valida el token, verifica los permisos del rol y reenvía la petición al microservicio correspondiente (RNF09).

| | |
|---|---|
| **Tecnología** | PHP / Laravel |
| **Base de datos** | No tiene |
| **Puerto local** | 8000 |

## Responsabilidades

1. **Validar el JWT** emitido por ms-usuarios: verifica la firma y la fecha de expiración, sin consultar ninguna base de datos.
2. **Autorizar** según el rol incluido en el token (tabla de abajo).
3. **Enrutar** la petición al microservicio según el prefijo de la ruta.
4. **Propagar la identidad** al microservicio en cabeceras: `X-Usuario-Id`, `X-Rol` y `X-Bodega-Id`.

El Gateway no tiene contrato OpenAPI propio porque no tiene lógica de negocio: sus rutas son las de los microservicios, documentadas en el contrato de cada uno.

## Tabla de enrutamiento y autorización

| Ruta | Método | Destino | Token | Roles permitidos |
|---|---|---|---|---|
| `/api/usuarios/auth/login`, `/auth/recuperar-password`, `/auth/restablecer-password` | POST | ms-usuarios:3000 | No | Público |
| `/api/usuarios/auth/me`, `/auth/cambiar-password`, `/auth/logout` | GET, PUT, POST | ms-usuarios:3000 | Sí | Todos |
| `/api/usuarios/usuarios/**` | Todos | ms-usuarios:3000 | Sí | ADMIN |
| `/api/usuarios/roles` | GET | ms-usuarios:3000 | Sí | Todos |
| `/api/catalogo/**` | GET | ms-catalogo:8001 | Sí | Todos |
| `/api/catalogo/**` | POST, PUT, DELETE | ms-catalogo:8001 | Sí | ADMIN |
| `/api/existencias/**` | GET | ms-existencias:8002 | Sí | Todos |
| `/api/existencias/movimientos`, `/traslados`, `/devoluciones`, `/ordenes-compra/{id}/recepciones` | POST | ms-existencias:8002 | Sí | ADMIN, OPERADOR_BODEGA (solo su bodega) |
| `/api/existencias/**` (resto de escrituras) | POST, PUT, PATCH | ms-existencias:8002 | Sí | ADMIN |
| `/api/analytics/**` | Todos | ms-analitica:5000 | Sí | ADMIN, ANALISTA |
| `/api/notifications/**` | Todos | ms-notificaciones:5001 | Sí | Todos |

La comunicación interna entre microservicios (por ejemplo, ms-existencias → ms-catalogo o ms-existencias → ms-notificaciones) se hace directamente por la red interna, sin pasar por el Gateway.

## Errores que responde el propio Gateway

| Código | Caso |
|---|---|
| 401 | Token ausente, inválido o vencido |
| 403 | El rol no tiene permiso para la ruta |
| 404 | La ruta no corresponde a ningún microservicio |
| 503 | El microservicio destino no está disponible |
