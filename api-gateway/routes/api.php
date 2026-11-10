<?php

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Route;

function forwardToService(Request $request, string $baseUrl, string $targetPath)
{
    $headers = collect($request->headers->all())
        ->mapWithKeys(fn($value, $key) => [$key => $value[0]])
        ->except(['content-length', 'host'])
        ->toArray();

    $url = rtrim($baseUrl, '/') . '/' . ltrim($targetPath, '/');
    if ($request->getQueryString()) {
        $url .= '?' . $request->getQueryString();
    }

    $method = strtoupper($request->method());

    try {
        $pendingRequest = Http::withHeaders($headers)->timeout(30);

        $options = [];
        if (!in_array($method, ['GET', 'HEAD'])) {
            $options['json'] = $request->json()->all();
        }

        $response = $pendingRequest->send($method, $url, $options);

        return response($response->body(), $response->status())
            ->withHeaders($response->headers());

    } catch (\Illuminate\Http\Client\ConnectionException $e) {
        return response()->json([
            'error' => 'El microservicio destino no está disponible'
        ], 503, [], JSON_UNESCAPED_UNICODE);
    } catch (\Exception $e) {
        return response()->json([
            'error' => 'El microservicio destino no está disponible'
        ], 503, [], JSON_UNESCAPED_UNICODE);
    }
}

// Microservicios según tabla del README
$usersUrl       = env('USUARIOS_SERVICE_URL', 'http://ms-usuarios:3000');
$catalogoUrl    = env('CATALOGO_SERVICE_URL', 'http://ms-catalogo:8001');
$existenciasUrl = env('EXISTENCIAS_SERVICE_URL', 'http://ms-existencias:8002');
$analyticsUrl   = env('ANALYTICS_SERVICE_URL', 'http://ms-analitica:5000');
$notifUrl       = env('NOTIFICACIONES_SERVICE_URL', 'http://ms-notificaciones:5001');

// 1. ms-usuarios: Rutas Públicas (Token: No | Roles: Público)

Route::post('/usuarios/auth/login', fn(Request $r) => forwardToService($r, $usersUrl, '/api/usuarios/auth/login'));
Route::post('/auth/login', fn(Request $r) => forwardToService($r, $usersUrl, '/api/usuarios/auth/login'));

Route::post('/auth/recuperar-password', fn(Request $r) => forwardToService($r, $usersUrl, '/auth/recuperar-password'));
Route::post('/usuarios/auth/recuperar-password', fn(Request $r) => forwardToService($r, $usersUrl, '/auth/recuperar-password'));

Route::post('/auth/restablecer-password', fn(Request $r) => forwardToService($r, $usersUrl, '/auth/restablecer-password'));
Route::post('/usuarios/auth/restablecer-password', fn(Request $r) => forwardToService($r, $usersUrl, '/auth/restablecer-password'));

// 2. Rutas Protegidas por JWT

// --- A. Roles: Todos ---
Route::middleware('jwt.auth')->group(function () use ($usersUrl, $catalogoUrl, $existenciasUrl, $notifUrl) {
    // ms-usuarios
    Route::match(['GET', 'PUT', 'POST'], '/usuarios/auth/me', fn(Request $r) => forwardToService($r, $usersUrl, '/auth/me'));
    Route::match(['GET', 'PUT', 'POST'], '/auth/me', fn(Request $r) => forwardToService($r, $usersUrl, '/auth/me'));
    Route::match(['GET', 'PUT', 'POST'], '/auth/cambiar-password', fn(Request $r) => forwardToService($r, $usersUrl, '/auth/cambiar-password'));
    Route::match(['GET', 'PUT', 'POST'], '/auth/logout', fn(Request $r) => forwardToService($r, $usersUrl, '/auth/logout'));
    Route::get('/usuarios/roles', fn(Request $r) => forwardToService($r, $usersUrl, '/api/usuarios/roles'));

    // ms-catalogo (GET)
    Route::get('/catalogo/{path?}', fn(Request $r, $path = '') => forwardToService($r, $catalogoUrl, '/api/catalogo/' . $path))->where('path', '.*');

    // ms-existencias (GET)
    Route::get('/existencias/{path?}', fn(Request $r, $path = '') => forwardToService($r, $existenciasUrl, '/api/existencias/' . $path))->where('path', '.*');

    // ms-notificaciones (Todos los métodos)
    Route::any('/notifications/{path?}', fn(Request $r, $path = '') => forwardToService($r, $notifUrl, '/api/notifications/' . $path))->where('path', '.*');
});

// --- B. Roles: ADMIN, OPERADOR_BODEGA ---
Route::middleware('jwt.auth:ADMIN,OPERADOR_BODEGA')->group(function () use ($existenciasUrl) {
    Route::post('/existencias/movimientos', fn(Request $r) => forwardToService($r, $existenciasUrl, '/api/existencias/movimientos'));
    Route::post('/existencias/traslados', fn(Request $r) => forwardToService($r, $existenciasUrl, '/api/existencias/traslados'));
    Route::post('/existencias/devoluciones', fn(Request $r) => forwardToService($r, $existenciasUrl, '/api/existencias/devoluciones'));
    Route::post('/existencias/ordenes-compra/{id}/recepciones', fn(Request $r, $id) => forwardToService($r, $existenciasUrl, "/api/existencias/ordenes-compra/{$id}/recepciones"));
});

// --- C. Roles: ADMIN, ANALISTA ---
Route::middleware('jwt.auth:ADMIN,ANALISTA')->group(function () use ($analyticsUrl) {
    Route::any('/analytics/{path?}', fn(Request $r, $path = '') => forwardToService($r, $analyticsUrl, '/api/analytics/' . $path))->where('path', '.*');
});

// --- D. Roles: Exclusivo ADMIN ---
Route::middleware('jwt.auth:ADMIN')->group(function () use ($usersUrl, $catalogoUrl, $existenciasUrl) {
    Route::any('/usuarios/usuarios/{path?}', fn(Request $r) => forwardToService($r, $usersUrl, '/api/usuarios/usuarios/' . $path))->where('path', '.*');
    Route::match(['POST', 'PUT', 'DELETE'], '/catalogo/{path?}', fn(Request $r, $path = '') => forwardToService($r, $catalogoUrl, '/api/catalogo/' . $path))->where('path', '.*');
    Route::match(['POST', 'PUT', 'PATCH'], '/existencias/{path?}', fn(Request $r, $path = '') => forwardToService($r, $existenciasUrl, '/api/existencias/' . $path))->where('path', '.*');
});

// Error 404: La ruta no corresponde a ningún microservicio

Route::fallback(function () {
    return response()->json([
        'error' => 'La ruta no corresponde a ningún microservicio'
    ], 404, [], JSON_UNESCAPED_UNICODE);
});