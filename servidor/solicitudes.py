#!/usr/bin/env python3
"""
Base de datos del asistente (SQLite): solicitudes de todos los sitios.

Cada sitio trabaja en uno de dos modos (ver sitios/<dominio>.md):
  - contacto: el visitante deja sus datos para que lo contacten (FAE-0001…)
  - ticket:   mesa de ayuda, incidentes y solicitudes de servicio (TCK-0001…)

La usan server.py (registrar las solicitudes que los visitantes validan en el chat),
gestion.py (página de gestión, solo en este Mac) e importar.py. También se puede usar sola:
    python3 solicitudes.py listar          (todas, las más recientes primero)
    python3 solicitudes.py ver TCK-0001    (detalle con archivos y conversación)

Ruta de la base: ASISTENTE_DB (variable de entorno) o datos/asistente.db junto a este archivo.
"""
import hashlib
import json
import os
import re
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('ASISTENTE_DB') or os.path.join(ROOT, 'datos', 'asistente.db')

# campo -> largo máximo (unión de los campos de contacto y de ticket)
CAMPOS = {
    # persona
    'nombre': 120, 'empresa': 160, 'cargo': 120, 'correo': 200, 'telefono': 60, 'otro': 200, 'preferencia': 120,
    # modo contacto
    'interes': 200, 'necesidad': 4000,
    # modo ticket
    'tipo': 60, 'titulo': 200, 'categoria': 200, 'descripcion': 4000, 'prioridad': 60, 'equipo': 120, 'evidencias': 600,
}
MODOS = ('contacto', 'ticket')
ESTADOS = {'nuevo': 'Nuevo', 'contactado': 'Contactado', 'en_proceso': 'En proceso', 'resuelto': 'Resuelto', 'cerrado': 'Cerrado'}
PREFIJO_RE = re.compile(r'^[A-Z]{2,5}$')

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS solicitudes (
    id           TEXT PRIMARY KEY,          -- TCK-0001 / FAE-0001 (prefijo por sitio)
    fecha        TEXT NOT NULL,             -- ISO local
    actualizado  TEXT,
    estado       TEXT NOT NULL DEFAULT 'nuevo',
    sitio        TEXT,                      -- dominio de la página donde se hizo la solicitud
    modo         TEXT NOT NULL DEFAULT 'contacto',
    {', '.join(f'{c} TEXT' for c in CAMPOS)},
    conversacion TEXT,                      -- JSON [{{rol, texto, adjuntos}}]
    ip           TEXT
);
CREATE TABLE IF NOT EXISTS adjuntos (       -- archivos que el visitante adjuntó en la conversación
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    solicitud_id TEXT NOT NULL REFERENCES solicitudes(id),
    nombre       TEXT NOT NULL,
    tipo         TEXT NOT NULL,             -- tipo MIME verificado por el servidor
    tamano       INTEGER NOT NULL,
    sha256       TEXT NOT NULL,
    datos        BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS notas (          -- historial de gestión (cambios de estado y notas)
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    solicitud_id TEXT NOT NULL REFERENCES solicitudes(id),
    fecha        TEXT NOT NULL,
    texto        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_adjuntos_solicitud ON adjuntos(solicitud_id);
CREATE INDEX IF NOT EXISTS idx_notas_solicitud ON notas(solicitud_id);
"""


class Error(Exception):
    """Error que se muestra tal cual en la página de gestión."""


def ahora():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


def connect(path=DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    existentes = {r[1] for r in db.execute('PRAGMA table_info(solicitudes)')}
    for col in CAMPOS:  # columnas agregadas en versiones posteriores
        if col not in existentes:
            db.execute(f'ALTER TABLE solicitudes ADD COLUMN {col} TEXT')
    return db


def siguiente_id(db, prefijo):
    if not PREFIJO_RE.match(prefijo):
        raise Error(f'Prefijo no válido: {prefijo}')
    ultimo = db.execute('SELECT MAX(CAST(SUBSTR(id, ?) AS INTEGER)) FROM solicitudes WHERE id LIKE ?',
                        (len(prefijo) + 2, prefijo + '-%')).fetchone()[0] or 0
    return f'{prefijo}-{ultimo + 1:04d}'


def insertar(db, sid, fecha, estado, sitio, modo, datos, conversacion, ip, archivos=(), actualizado=None):
    """Inserta una solicitud completa (con su id ya decidido). Debe llamarse dentro de una transacción."""
    db.execute(
        f'INSERT INTO solicitudes (id, fecha, actualizado, estado, sitio, modo, {", ".join(CAMPOS)}, conversacion, ip) '
        f'VALUES (?, ?, ?, ?, ?, ?, {", ".join("?" * len(CAMPOS))}, ?, ?)',
        (sid, fecha, actualizado or fecha, estado, sitio, modo, *(datos.get(k, '') for k in CAMPOS),
         json.dumps(conversacion, ensure_ascii=False), ip))
    for a in archivos:
        db.execute('INSERT INTO adjuntos (solicitud_id, nombre, tipo, tamano, sha256, datos) VALUES (?, ?, ?, ?, ?, ?)',
                   (sid, a['nombre'], a['tipo'], len(a['datos']), hashlib.sha256(a['datos']).hexdigest(), a['datos']))


def crear(db, datos, conversacion, ip, sitio='', modo='contacto', prefijo='FAE', archivos=()):
    """Registra una solicitud validada con sus archivos [{nombre, tipo, datos(bytes)}] y devuelve (id, fecha).
    Todo va en una sola transacción: o se guarda completa o no se guarda nada."""
    if modo not in MODOS:
        raise Error(f'Modo no válido: {modo}')
    fecha = ahora()
    db.execute('BEGIN IMMEDIATE')
    try:
        sid = siguiente_id(db, prefijo)
        insertar(db, sid, fecha, 'nuevo', sitio, modo, datos, conversacion, ip, archivos)
        db.execute('COMMIT')
    except Exception:
        db.execute('ROLLBACK')
        raise
    return sid, fecha


def listar(db, estado='', texto='', sitio='', modo=''):
    sql = ('SELECT id, fecha, estado, sitio, modo, nombre, empresa, cargo, correo, telefono, otro, preferencia, '
           'interes, tipo, titulo, prioridad, equipo, '
           '(SELECT COUNT(*) FROM adjuntos a WHERE a.solicitud_id = solicitudes.id) AS adjuntos FROM solicitudes WHERE 1=1')
    args = []
    for col, val in (('estado', estado), ('sitio', sitio), ('modo', modo)):
        if val:
            sql += f' AND {col} = ?'
            args.append(val)
    if texto:
        cols = ('id', 'nombre', 'empresa', 'correo', 'telefono', 'otro', 'interes', 'necesidad', 'titulo', 'descripcion',
                'categoria', 'equipo', 'sitio')
        sql += ' AND (' + ' OR '.join(f'{c} LIKE ?' for c in cols) + ')'
        args += [f'%{texto}%'] * len(cols)
    return db.execute(sql + ' ORDER BY fecha DESC, id DESC LIMIT 500', args).fetchall()


def resumen(db):
    """Conteo por estado y lista de sitios (para los filtros de la gestión)."""
    return {
        'conteo': {r[0]: r[1] for r in db.execute('SELECT estado, COUNT(*) FROM solicitudes GROUP BY estado')},
        'sitios': [r[0] for r in db.execute("SELECT DISTINCT sitio FROM solicitudes WHERE sitio <> '' ORDER BY sitio")],
    }


def obtener(db, sid):
    r = db.execute('SELECT * FROM solicitudes WHERE id = ?', (sid.upper(),)).fetchone()
    if not r:
        raise Error(f'No existe la solicitud {sid}.')
    out = dict(r)
    out['conversacion'] = json.loads(r['conversacion'] or '[]')
    out['notas'] = [dict(n) for n in db.execute('SELECT fecha, texto FROM notas WHERE solicitud_id = ? ORDER BY id', (r['id'],))]
    out['adjuntos'] = [dict(a) for a in db.execute(
        'SELECT id, nombre, tipo, tamano, sha256 FROM adjuntos WHERE solicitud_id = ? ORDER BY id', (r['id'],))]
    return out


def leer_adjunto(db, adjunto_id):
    """(nombre, tipo, bytes) de un archivo adjunto, o None si no existe."""
    row = db.execute('SELECT nombre, tipo, datos FROM adjuntos WHERE id = ?', (int(adjunto_id),)).fetchone()
    return (row['nombre'], row['tipo'], bytes(row['datos'])) if row else None


def actualizar(db, sid, estado=None, nota=None, autor=''):
    """Cambia el estado y/o agrega una nota. Cada cambio queda en el historial (con su autor si viene de internet)."""
    actual = obtener(db, sid)
    nota = (nota or '').strip()[:2000]
    if estado and estado not in ESTADOS:
        raise Error('Estado no válido.')
    if not (estado and estado != actual['estado']) and not nota:
        raise Error('Cambia el estado o escribe una nota.')
    fecha = ahora()
    firma = f' — {autor}' if autor else ''
    db.execute('BEGIN IMMEDIATE')
    try:
        if estado and estado != actual['estado']:
            db.execute('UPDATE solicitudes SET estado = ?, actualizado = ? WHERE id = ?', (estado, fecha, actual['id']))
            db.execute('INSERT INTO notas (solicitud_id, fecha, texto) VALUES (?, ?, ?)',
                       (actual['id'], fecha, f'Estado: {ESTADOS.get(actual["estado"], actual["estado"])} → {ESTADOS[estado]}' + firma))
        if nota:
            db.execute('INSERT INTO notas (solicitud_id, fecha, texto) VALUES (?, ?, ?)', (actual['id'], fecha, nota + firma))
            db.execute('UPDATE solicitudes SET actualizado = ? WHERE id = ?', (fecha, actual['id']))
        db.execute('COMMIT')
    except Exception:
        db.execute('ROLLBACK')
        raise
    return obtener(db, sid)


def _vacio(v):
    return not v or str(v).lower().startswith('no informad')


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'listar'
    db = connect()
    if cmd == 'listar':
        filas = listar(db)
        if not filas:
            return print(f'No hay solicitudes todavía ({DB_PATH}).')
        for r in filas:
            medio = ' / '.join(v for v in (r['correo'], r['telefono'], r['otro']) if not _vacio(v))
            asunto = r['titulo'] if r['modo'] == 'ticket' else r['interes']
            print(f"{r['id']}  {r['fecha'][:16].replace('T', ' ')}  {r['estado']:<10}  "
                  f"{r['nombre'] or '(sin nombre)'} <{medio}>  [{asunto or '-'}]"
                  + (f"  📎 {r['adjuntos']}" if r['adjuntos'] else '') + f"  · {r['sitio'] or '-'}")
        return print(f'\n{len(filas)} solicitud(es) · {DB_PATH}')
    if cmd == 'ver' and len(sys.argv) > 2:
        try:
            s = obtener(db, sys.argv[2])
        except Error as e:
            return print(e)
        for k in ('id', 'fecha', 'estado', 'sitio', 'modo', *CAMPOS, 'ip'):
            if not _vacio(s.get(k)) or k in ('id', 'estado', 'sitio', 'modo'):
                print(f'{k:>12}: {s.get(k) or "-"}')
        for a in s['adjuntos']:
            print(f"  📎 {a['nombre']}  ({a['tipo']}, {a['tamano']} bytes)")
        for n in s['notas']:
            print(f"  📝 {n['fecha'][:16].replace('T', ' ')}  {n['texto']}")
        print('\nConversación:')
        for m in s['conversacion']:
            print(f"  [{m.get('rol')}] {m.get('texto')}\n")
        return None
    print(__doc__)


if __name__ == '__main__':
    main()
