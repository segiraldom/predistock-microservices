<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class JwtAuthenticate
{
    private function base64UrlDecode(string $input): string
    {
        $remainder = strlen($input) % 4;
        if ($remainder) {
            $input .= str_repeat('=', 4 - $remainder);
        }
        return base64_decode(strtr($input, '-_', '+/'));
    }

    private function base64UrlEncode(string $input): string
    {
        return rtrim(strtr(base64_encode($input), '+/', '-_'), '=');
    }

    private function normalizeRole(string $role): string
    {
        $clean = strtoupper(trim($role));
        $clean = str_replace([' ', '-'], '_', $clean);
        if ($clean === 'ADMINISTRADOR') return 'ADMIN';
        if ($clean === 'OPERADOR_DE_BODEGA') return 'OPERADOR_BODEGA';
        return $clean;
    }

    /**
     * Valida JWT y opcionalmente autoriza roles pasados como parámetros:
     * middleware('jwt.auth:ADMIN,OPERADOR_BODEGA')
     */
    public function handle(Request $request, Closure $next, ...$allowedRoles): Response
    {
        $authHeader = $request->header('Authorization');

        // Error 401: Token ausente
        if (!$authHeader || !str_starts_with($authHeader, 'Bearer ')) {
            return response()->json([
                'error' => 'Token ausente, inválido o vencido'
            ], 401, [], JSON_UNESCAPED_UNICODE);
        }

        $token = trim(substr($authHeader, 7));
        $token = trim($token, '"\'');

        try {
            $parts = explode('.', $token);
            if (count($parts) !== 3) {
                throw new \Exception('Formato de token inválido.');
            }

            [$headerB64, $payloadB64, $signatureB64] = $parts;

            // 1. Validar firma criptográfica HMAC-SHA256 en memoria
            $secret = env('JWT_SECRET', 'password_2026');
            $expectedSignature = $this->base64UrlEncode(
                hash_hmac('sha256', "$headerB64.$payloadB64", $secret, true)
            );

            if (!hash_equals($expectedSignature, $signatureB64)) {
                throw new \Exception('Firma inválida.');
            }

            // 2. Decodificar payload
            $payload = json_decode($this->base64UrlDecode($payloadB64), true);
            if (!$payload || !isset($payload['sub'])) {
                throw new \Exception('Payload corrupto.');
            }

            // 3. Validar expiración (exp)
            if (isset($payload['exp']) && time() >= (int) $payload['exp']) {
                throw new \Exception('Token vencido.');
            }

            // 4. Normalizar rol del usuario
            $userRole = isset($payload['rol']) ? $this->normalizeRole($payload['rol']) : '';

            // 5. Autorización RBAC (Error 403 si el rol no tiene permiso)
            if (!empty($allowedRoles)) {
                $normalizedAllowed = array_map(fn($r) => $this->normalizeRole($r), $allowedRoles);
                if (!in_array($userRole, $normalizedAllowed)) {
                    return response()->json([
                        'error' => 'El rol no tiene permiso para la ruta'
                    ], 403, [], JSON_UNESCAPED_UNICODE);
                }
            }

            // 6. Propagar identidad en las cabeceras exactas requeridas
            $request->headers->set('X-Usuario-Id', (string) $payload['sub']);
            $request->headers->set('X-Rol', (string) ($payload['rol'] ?? ''));
            $request->headers->set('X-Bodega-Id', (string) ($payload['bodega_id'] ?? ''));

        } catch (\Exception $e) {
            // Error 401: Token inválido o vencido
            return response()->json([
                'error' => 'Token ausente, inválido o vencido'
            ], 401, [], JSON_UNESCAPED_UNICODE);
        }

        return $next($request);
    }
}