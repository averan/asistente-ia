# asistente-ia

Asistente de IA **independiente de cualquier página web**: se integra en cualquier sitio con una
línea y responde con el modelo que corre en este Mac (oMLX). Cada sitio tiene su propia
personalidad, colores y modo de trabajo, configurados en el servidor.

```
Cualquier sitio ──<script src="https://asistente-ia.faenabot.stream/embed.js">──► Cloudflare Workers (widget)
      └── chat / solicitudes (CORS) ──► túnel ──► servidor del Mac (:5204) ──► oMLX
                                                   ├─ sitios/<dominio>.md  (configuración + contexto de cada sitio)
                                                   └─ datos/asistente.db   (solicitudes de todos los sitios)
Gestión (solo este Mac): http://localhost:5205
```

Documentación de la solución (diagrama, servicios del servidor :5204 y operación): [docs/arquitectura.html](docs/arquitectura.html).

```
publico/     Lo que publica Cloudflare (Worker con despliegue desde Git; directorio publico)
  embed.js       la línea que se pega en cada sitio
  asistente.js   widget de chat (adjuntos, solicitudes, modo «no disponible»)
  asistente.css  estilos; los colores de cada sitio llegan desde el servidor
  backend.js     dirección del túnel + configuración visible de los sitios (la genera publicar.sh)
servidor/    Corre en el Mac; nunca se publica
  server.py        servidor del asistente (CORS, prompt en el servidor, límites, archivos)
  solicitudes.py   base de datos (tickets y contactos, archivos con SHA-256, notas)
  gestion.py/.html página de gestión local con visor de archivos
  publicar.sh      conecta el asistente: servidor + túnel + backend.js (vigila el túnel)
  servicio.sh      lo deja como servicio del Mac (launchd): arranque automático y reinicio
  importar.py      importa los datos de los proyectos anteriores (se usó una vez)
  reglas/          reglas comunes por modo (contacto.md, ticket.md)
  sitios/          un archivo por sitio (no se suben a GitHub, salvo las plantillas)
```

## Dos modos

| Modo | Para qué | Numeración |
|---|---|---|
| `contacto` | El visitante pregunta y deja sus datos para que lo contacten (Faena, IA Local) | FAE-0001… |
| `ticket` | Mesa de ayuda: incidentes y solicitudes de servicio con prioridad, equipo y evidencias (Wodobox) | TCK-0001… |

## Agregar un sitio nuevo

1. **Crea su archivo** a partir de una plantilla. El nombre es el dominio exacto (`www.ejemplo.com` y `ejemplo.com`
   son distintos). Crear el archivo **autoriza** el sitio, sin reiniciar nada:
   ```bash
   cp servidor/sitios/_plantilla-contacto.md servidor/sitios/www.ejemplo.com.md   # o _plantilla-ticket.md
   ```
   Arriba (entre `---`) va la configuración: modo, nombre, saludo, sugerencias (separadas por `|`), colores, avisos,
   datos obligatorios. Abajo, lo que sabe el asistente de esa empresa. Los cambios se aplican en la siguiente consulta.
2. **Pega una línea** antes de `</body>` en el sitio:
   ```html
   <script src="https://asistente-ia.faenabot.stream/embed.js" defer></script>
   ```
   (WordPress: plugin WPCode → footer; Shopify: `theme.liquid`; Wix/Squarespace: código personalizado del pie.)

Nada más: el widget pide al servidor la configuración de su sitio. Un sitio sin archivo no muestra el asistente
(deja un aviso en la consola). Opcional: `window.ASISTENTE = { greeting: '…' }` antes de la línea sobrescribe valores
visibles solo en esa página, y `<button onclick="asistenteIA.open()">` abre el asistente desde un botón propio.

## Conectar el asistente

Como **servicio del Mac** (recomendado): arranca solo al iniciar sesión, sigue funcionando aunque se cierre la
terminal o la app, y se reinicia solo si falla o si el túnel de Cloudflare expira (lo revisa cada minuto).

```bash
./servidor/servicio.sh instalar      # una sola vez
./servidor/servicio.sh estado        # ¿está corriendo? ¿qué túnel usa?
./servidor/servicio.sh log           # consultas recibidas y avisos (Ctrl+C para salir del registro)
./servidor/servicio.sh reiniciar     # túnel nuevo
./servidor/servicio.sh detener       # lo pausa (los sitios muestran «no disponible») hasta «iniciar» o el próximo inicio de sesión
./servidor/servicio.sh iniciar       # lo vuelve a encender
./servidor/servicio.sh desinstalar   # lo detiene y deja de arrancar al iniciar sesión
```

O a mano, en una terminal: `./servidor/publicar.sh` (Ctrl+C para desconectarlo).

En ambos casos arranca el servidor y el túnel, y sube `publico/backend.js` con la nueva dirección → Cloudflare se
actualiza solo (~1 min). Al detenerse, todos los sitios muestran su aviso de «no disponible» (con su nombre y colores,
que `backend.js` guarda aunque el Mac esté apagado). Requisitos: oMLX en marcha con el modelo cargado.

**Gestión:** http://localhost:5205 (solo este Mac) — tickets y contactos de todos los sitios, filtros por sitio, modo y
estado, detalle con la conversación, visor de archivos, cambio de estado y notas. También:
`python3 servidor/solicitudes.py listar` y `python3 servidor/solicitudes.py ver TCK-0017`.

## Seguridad

- La API key de oMLX nunca sale del Mac (`servidor/.env`, fuera de git).
- El prompt lo pone el servidor; el navegador no puede cambiarlo.
- Solo responden los sitios con archivo en `sitios/` (CORS); solo `https://` salvo `localhost` para pruebas.
- Límites de mensajes y solicitudes por visitante, de generaciones simultáneas y de tokens; solo se usa el modelo ya
  cargado en oMLX; el chat no puede usar herramientas.
- Archivos: se verifica el tipo real por su contenido; en la gestión solo las imágenes se muestran directamente.
- La gestión solo acepta conexiones desde este Mac y exige una cabecera propia para los cambios.
