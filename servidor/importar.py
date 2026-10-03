#!/usr/bin/env python3
"""
Importa a la base del asistente las solicitudes de los proyectos anteriores:
  - tickets de Wodobox v3   (omlx-asistente-web-v3/tickets/tickets.db: tickets, comentarios, adjuntos)
  - contactos de web-vercel (web-vercel/servidor/datos/contactos.db: contactos, notas, adjuntos)

Las bases antiguas se abren SOLO en lectura y quedan intactas. Se conservan ids, fechas, estados,
conversaciones, notas y archivos (se verifica el SHA-256 de cada archivo). Es idempotente: las
solicitudes que ya existen en la base nueva se omiten.

Uso:  python3 importar.py [--v3 RUTA] [--faena RUTA] [--sitio-v3 DOMINIO]
"""
import argparse
import hashlib
import json
import os
import sqlite3

import solicitudes as sol

BASE = os.path.abspath(os.path.join(sol.ROOT, '..', '..'))
V3_DB = os.path.join(BASE, 'omlx-asistente-web-v3', 'tickets', 'tickets.db')
FAENA_DB = os.path.join(BASE, 'web-vercel', 'servidor', 'datos', 'contactos.db')
ESTADOS = {'en_curso': 'en_proceso'}  # estados antiguos -> nuevos


def solo_lectura(path):
    """Copia consistente en memoria de la base antigua (incluye lo que esté en su archivo -wal).
    La API de respaldo de SQLite solo lee la original; no la modifica."""
    if not os.path.isfile(path):
        raise SystemExit(f'No existe {path}')
    src, mem = sqlite3.connect(path), sqlite3.connect(':memory:')
    try:
        src.backup(mem)
    finally:
        src.close()
    mem.row_factory = sqlite3.Row
    return mem


def archivos(rows, campo_datos):
    out = []
    for a in rows:
        datos = bytes(a[campo_datos])
        if hashlib.sha256(datos).hexdigest() != a['sha256']:
            raise SystemExit(f'El archivo «{a["nombre"]}» no coincide con su SHA-256: se detiene la importación.')
        out.append({'nombre': a['nombre'], 'tipo': a['tipo'], 'datos': datos})
    return out


def importar_v3(dst, path, sitio):
    src = solo_lectura(path)
    n = na = nn = 0
    for t in src.execute('SELECT * FROM tickets ORDER BY num'):
        if dst.execute('SELECT 1 FROM solicitudes WHERE id = ?', (t['id'],)).fetchone():
            continue
        datos = {k: t[k] or '' for k in ('tipo', 'titulo', 'categoria', 'descripcion', 'nombre', 'correo', 'telefono',
                                          'prioridad', 'equipo', 'evidencias')}
        adj = archivos(src.execute('SELECT * FROM adjuntos WHERE ticket_id = ? ORDER BY num', (t['id'],)), 'contenido')
        notas = src.execute('SELECT fecha, texto FROM comentarios WHERE ticket_id = ? ORDER BY num', (t['id'],)).fetchall()
        dst.execute('BEGIN IMMEDIATE')
        try:
            sol.insertar(dst, t['id'], t['fecha'], ESTADOS.get(t['estado'], t['estado']), sitio, 'ticket', datos,
                         json.loads(t['conversacion'] or '[]'), t['ip'] or '', adj, t['actualizado'])
            for c in notas:
                dst.execute('INSERT INTO notas (solicitud_id, fecha, texto) VALUES (?, ?, ?)', (t['id'], c['fecha'], c['texto']))
            dst.execute('COMMIT')
        except Exception:
            dst.execute('ROLLBACK')
            raise
        n, na, nn = n + 1, na + len(adj), nn + len(notas)
    return n, na, nn


def importar_faena(dst, path):
    src = solo_lectura(path)
    n = na = nn = 0
    for c in src.execute('SELECT * FROM contactos ORDER BY id'):
        if dst.execute('SELECT 1 FROM solicitudes WHERE id = ?', (c['id'],)).fetchone():
            continue
        keys = c.keys()
        datos = {k: (c[k] if k in keys else '') or '' for k in ('nombre', 'empresa', 'cargo', 'correo', 'telefono', 'otro',
                                                                 'preferencia', 'interes', 'necesidad')}
        adj = archivos(src.execute('SELECT * FROM adjuntos WHERE contacto_id = ? ORDER BY id', (c['id'],)), 'datos')
        notas = src.execute('SELECT fecha, texto FROM notas WHERE contacto_id = ? ORDER BY id', (c['id'],)).fetchall()
        dst.execute('BEGIN IMMEDIATE')
        try:
            sol.insertar(dst, c['id'], c['fecha'], ESTADOS.get(c['estado'], c['estado']), c['sitio'] or '', 'contacto',
                         datos, json.loads(c['conversacion'] or '[]'), c['ip'] or '', adj)
            for x in notas:
                dst.execute('INSERT INTO notas (solicitud_id, fecha, texto) VALUES (?, ?, ?)', (c['id'], x['fecha'], x['texto']))
            dst.execute('COMMIT')
        except Exception:
            dst.execute('ROLLBACK')
            raise
        n, na, nn = n + 1, na + len(adj), nn + len(notas)
    return n, na, nn


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--v3', default=V3_DB, help='base de tickets de Wodobox v3')
    ap.add_argument('--faena', default=FAENA_DB, help='base de contactos de web-vercel')
    ap.add_argument('--sitio-v3', default='wodobox', help='sitio que se asigna a los tickets de la v3')
    args = ap.parse_args()
    dst = sol.connect()
    print(f'Destino: {sol.DB_PATH}')
    print('Tickets Wodobox v3:      %d solicitudes, %d archivos, %d notas importadas' % importar_v3(dst, args.v3, args.sitio_v3))
    print('Contactos web-vercel:    %d solicitudes, %d archivos, %d notas importadas' % importar_faena(dst, args.faena))
    tot = dst.execute('SELECT COUNT(*) FROM solicitudes').fetchone()[0]
    print(f'Total en la base nueva: {tot} solicitudes, '
          f'{dst.execute("SELECT COUNT(*) FROM adjuntos").fetchone()[0]} archivos, '
          f'{dst.execute("SELECT COUNT(*) FROM notas").fetchone()[0]} notas.')


if __name__ == '__main__':
    main()
