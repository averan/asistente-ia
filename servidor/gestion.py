#!/usr/bin/env python3
"""
Página de gestión de las solicitudes del asistente (tickets y contactos de todos los sitios).

Escucha en 127.0.0.1:5205 (ADMIN_PORT en .env) y acepta dos tipos de acceso:
- Desde este Mac: Host localhost y sin cabeceras de Cloudflare.
- Desde internet, solo si está configurado Cloudflare Access (ACCESS_TEAM y ACCESS_AUD en .env): el túnel
  con nombre publica GESTION_HOST y cada petición debe traer un JWT de Access válido (firma RS256 con las
  claves del equipo, audiencia, emisor y vigencia). Sin esa configuración, el acceso remoto queda cerrado.
Rechaza cualquier otro Host (DNS rebinding) y exige una cabecera propia en los cambios (CSRF).

server.py la arranca automáticamente; también se puede usar sola:
    python3 servidor/gestion.py
"""
import base64
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlsplit

import solicitudes

ROOT = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(ROOT, 'gestion.html')
INLINE_TYPES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}  # el resto se descarga, nunca se muestra
FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">💬</text></svg>').encode()
LOCAL = 'este Mac'

# ---------- Cloudflare Access (acceso desde internet) ----------
ACCESS = {'team': '', 'aud': '', 'host': ''}
_certs = {'t': 0.0, 'keys': {}}
_certs_lock = threading.Lock()
SHA256_INFO = bytes.fromhex('3031300d060960864801650304020105000420')  # DigestInfo de PKCS#1 v1.5 para SHA-256


def configure_access(team, aud, host):
    ACCESS.update(team=(team or '').strip(), aud=(aud or '').strip(), host=(host or '').strip().lower())


def _b64(s):
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def _access_keys(force=False):
    """Claves públicas del equipo de Access ({kid: (n, e)}), en caché 1 h. force: volver a pedirlas
    (rotación de claves), como máximo una vez por minuto."""
    with _certs_lock:
        age = time.time() - _certs['t']
        if _certs['keys'] and age < 3600 and not (force and age > 60):
            return _certs['keys']
        url = f"https://{ACCESS['team']}.cloudflareaccess.com/cdn-cgi/access/certs"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.load(r)
        _certs['keys'] = {k['kid']: (int.from_bytes(_b64(k['n']), 'big'), int.from_bytes(_b64(k['e']), 'big'))
                          for k in data.get('keys', []) if k.get('kty') == 'RSA' and k.get('kid')}
        _certs['t'] = time.time()
        return _certs['keys']


def _rsa_sha256_ok(n, e, signed, sig):
    """Verificación RSASSA-PKCS1-v1_5 con SHA-256 (RS256), solo con la biblioteca estándar."""
    k = (n.bit_length() + 7) // 8
    if len(sig) != k or k < 128:
        return False
    em = pow(int.from_bytes(sig, 'big'), e, n).to_bytes(k, 'big')
    t = SHA256_INFO + hashlib.sha256(signed).digest()
    return hmac.compare_digest(em, b'\x00\x01' + b'\xff' * (k - len(t) - 3) + b'\x00' + t)


def access_user(token):
    """Correo del usuario si el JWT de Cloudflare Access es válido para esta aplicación; None si no."""
    if not (ACCESS['team'] and ACCESS['aud'] and token):
        return None
    try:
        h64, p64, s64 = token.split('.')
        header, payload = json.loads(_b64(h64)), json.loads(_b64(p64))
        if header.get('alg') != 'RS256':
            return None
        keys = _access_keys()
        if header.get('kid') not in keys:
            keys = _access_keys(force=True)
        n, e = keys[header['kid']]
        if not _rsa_sha256_ok(n, e, f'{h64}.{p64}'.encode(), _b64(s64)):
            return None
        aud = payload.get('aud')
        now = time.time()
        if ACCESS['aud'] not in (aud if isinstance(aud, list) else [aud]):
            return None
        if payload.get('iss') != f"https://{ACCESS['team']}.cloudflareaccess.com":
            return None
        if not (float(payload.get('nbf', 0)) - 30 <= now < float(payload['exp']) + 30):
            return None
        email = payload.get('email')
        return email if isinstance(email, str) and '@' in email else None
    except (ValueError, KeyError, TypeError, OSError):
        return None


def make_handler(port):
    allowed_hosts = {f'localhost:{port}', f'127.0.0.1:{port}'}

    class AdminHandler(BaseHTTPRequestHandler):
        server_version = 'AsistenteGestion'
        sys_version = ''

        def log_message(self, fmt, *args):
            pass

        def send(self, status, body, ctype='application/json; charset=utf-8', extra=None):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(data)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy', "frame-ancestors 'none'")
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(data)

        def fail(self, status, message):
            self.send(status, {'error': {'message': message}})

        def identify(self):
            """Quién pide: LOCAL (este Mac), el correo validado por Cloudflare Access, o None (403)."""
            host = (self.headers.get('Host') or '').lower()
            via_cf = self.headers.get('Cf-Ray') or self.headers.get('Cf-Connecting-Ip')
            if host in allowed_hosts and not via_cf:
                self.user = LOCAL
            elif ACCESS['host'] and host == ACCESS['host']:
                self.user = access_user(self.headers.get('Cf-Access-Jwt-Assertion'))
            else:
                self.user = None
            if not self.user:
                self.fail(403, 'Acceso no permitido')
            return bool(self.user)

        def do_GET(self):
            if not self.identify():
                return
            url = urlsplit(self.path)
            path = unquote(url.path)
            if path in ('/', '/index.html'):
                with open(PAGE, 'rb') as f:
                    return self.send(200, f.read(), 'text/html; charset=utf-8')
            if path == '/favicon.svg':
                return self.send(200, FAVICON, 'image/svg+xml')
            if path == '/api/yo':
                return self.send(200, {'usuario': self.user, 'remoto': self.user != LOCAL})
            db = solicitudes.connect()
            try:
                if path == '/api/solicitudes':
                    q = {k: v[0] for k, v in parse_qs(url.query).items()}
                    filas = solicitudes.listar(db, q.get('estado', ''), q.get('texto', '').strip(), q.get('sitio', ''), q.get('modo', ''))
                    return self.send(200, {'solicitudes': [dict(r) for r in filas], **solicitudes.resumen(db)})
                if path.startswith('/api/solicitudes/'):
                    return self.send(200, solicitudes.obtener(db, path.rsplit('/', 1)[1]))
                if path.startswith('/api/adjuntos/') and path.rsplit('/', 1)[1].isdigit():
                    found = solicitudes.leer_adjunto(db, path.rsplit('/', 1)[1])
                    if not found:
                        return self.fail(404, 'Archivo no encontrado')
                    nombre, tipo, data = found
                    inline = tipo in INLINE_TYPES and 'descargar' not in url.query
                    safe = ''.join(c if c.isalnum() or c in '._- ' else '_' for c in nombre) or 'archivo'
                    return self.send(200, data, tipo if inline else 'application/octet-stream', {
                        'Content-Disposition': f"{'inline' if inline else 'attachment'}; filename=\"{safe}\"; filename*=UTF-8''{quote(nombre)}",
                        'Content-Security-Policy': "default-src 'none'; img-src 'self'; sandbox",
                    })
                self.fail(404, 'No encontrado')
            except solicitudes.Error as e:
                self.fail(404, str(e))
            finally:
                db.close()

        def do_POST(self):
            if not self.identify():
                return
            if self.headers.get('X-Gestion') != '1':  # impide peticiones de otros sitios (CSRF)
                return self.fail(403, 'Acceso no permitido')
            path = unquote(urlsplit(self.path).path)
            if not path.startswith('/api/solicitudes/'):
                return self.fail(404, 'No encontrado')
            try:
                args = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
                assert isinstance(args, dict)
            except (ValueError, AssertionError):
                return self.fail(400, 'Petición no válida')
            db = solicitudes.connect()
            try:
                sid = path.rsplit('/', 1)[1]
                autor = '' if self.user == LOCAL else self.user
                self.send(200, solicitudes.actualizar(db, sid, args.get('estado'), args.get('nota'), autor))
                print(f'{time.strftime("%H:%M:%S")}  GESTIÓN {sid}  {self.user}'
                      + (f'  estado → {args.get("estado")}' if args.get('estado') else '') + ('  + nota' if args.get('nota') else ''), flush=True)
            except solicitudes.Error as e:
                self.fail(400, str(e))
            finally:
                db.close()

    return AdminHandler


def start(port, background=True):
    srv = ThreadingHTTPServer(('127.0.0.1', port), make_handler(port))
    srv.daemon_threads = True
    if background:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == '__main__':
    port = int(os.environ.get('ADMIN_PORT', 5205))
    print(f'Gestión de solicitudes en http://localhost:{port}  (acceso remoto solo con Cloudflare Access configurado)')
    try:
        start(port, background=False).serve_forever()
    except KeyboardInterrupt:
        pass
