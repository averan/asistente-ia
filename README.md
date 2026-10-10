# asistente-ia

Asistente de IA **independiente de cualquier página web**: se integra en cualquier sitio con una
línea y responde con el modelo que corre en este Mac (oMLX). Cada sitio tiene su propia
personalidad, colores y modo de trabajo, configurados en el servidor.

```
Cualquier sitio ──<script src="https://asistente-ia.faenabot.stream/embed.js">──► Cloudflare Workers (widget)
      └── chat / solicitudes (CORS) ──► túnel fijo (api.faenabot.stream) ──► servidor del Mac (:5204) ──► oMLX
                                                   ├─ sitios/<dominio>.md  (configuración + contexto de cada sitio)
                                                   └─ datos/asistente.db   (solicitudes de todos los sitios)
Gestión: http://localhost:5205 en el Mac · https://gestion.faenabot.stream desde internet (Cloudflare Access)
```

Documentación de la solución (diagrama, servicios del servidor :5204, pruebas con curl y operación): [docs/arquitectura.html](docs/arquitectura.html).
Probar los servicios: `./docs/probar-servicios.sh` (en el Mac) o `./docs/probar-servicios.sh --publico` (por api.faenabot.stream); no crea solicitudes reales.

```
publico/     Lo que publica Cloudflare (Worker con despliegue desde Git; directorio publico)
  embed.js       la línea que se pega en cada sitio
  asistente.js   widget de chat (adjuntos, solicitudes, modo «no disponible»)
  asistente.css  estilos; los colores de cada sitio llegan desde el servidor
  backend.js     dirección del servidor + configuración visible de los sitios (la genera publicar.sh)
servidor/    Corre en el Mac; nunca se publica
  server.py        servidor del asistente (CORS, prompt en el servidor, límites, archivos)
  solicitudes.py   base de datos (tickets y contactos, archivos con SHA-256, notas)
  gestion.py/.html página de gestión (Mac, o internet con Cloudflare Access) con visor de archivos
  publicar.sh      conecta el asistente: servidor + túnel + backend.js (vigila el túnel)
  servicio.sh      lo deja como servicio del Mac (launchd): arranque automático y reinicio
  importar.py      importa los datos de los proyectos anteriores (se usó una vez)
  reglas/          reglas comunes por modo (contacto.md, ticket.md)
  sitios/          un archivo por sitio (no se suben a GitHub, salvo las plantillas)
```

## Stack

| Capa | Tecnología |
|---|---|
| Widget (navegador) | JavaScript sin framework, CSS con variables, streaming con `fetch`; pdf.js, mammoth y SheetJS para leer archivos |
| Publicación | Cloudflare Workers (static assets, despliegue desde GitHub, `wrangler.jsonc`), Cloudflare DNS/Registrar (`faenabot.stream`) |
| Conexión | `cloudflared`: túnel fijo con nombre (`api.` y `gestion.faenabot.stream`); Cloudflare Access para la gestión |
| Servidor | Python 3.9 solo con la biblioteca estándar; API compatible con OpenAI |
| Datos | SQLite (solicitudes, archivos con SHA-256, notas); Markdown por sitio; `.env` |
| IA | oMLX con modelos MLX cuantizados a 4 bits, en el mismo Mac (Apple silicon) |
| Operación | bash, launchd, caffeinate, git, curl |

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
terminal o la app, y se reinicia solo si el servidor o el túnel dejan de responder (lo revisa cada minuto).

```bash
cd ~/oMLX_archivos/asistente-ia      # o usar la ruta completa desde cualquier carpeta
./servidor/servicio.sh instalar      # una sola vez (arranca al iniciar sesión)
./servidor/servicio.sh detener       # bajar: los sitios muestran «no disponible» (hasta «iniciar» o el próximo inicio de sesión)
./servidor/servicio.sh iniciar       # subir: responde en ~8 segundos con el túnel fijo
./servidor/servicio.sh reiniciar     # vuelve a conectar el servidor y el túnel
./servidor/servicio.sh estado        # ¿está corriendo? ¿qué túnel usa?
./servidor/servicio.sh log           # registro en vivo (Ctrl+C solo cierra la vista)
./servidor/servicio.sh desinstalar   # bajarlo y que deje de arrancar al iniciar sesión
```

O a mano, en una terminal: primero `servicio.sh detener` (usan el mismo puerto) y luego `./servidor/publicar.sh`
(Ctrl+C para desconectarlo). Con el servicio abajo tampoco funciona la gestión, y estos comandos no inician ni detienen
oMLX. Registro: `~/Library/Logs/asistente-ia.log` (también en la app Consola); los inicios de sesión en la gestión se
ven en Cloudflare, en Zero Trust → Logs → Access.

En ambos casos arranca el servidor y el túnel. Con el **túnel fijo** (`TUNEL_CONFIG` en `servidor/.env`, ver
`.env.example`) la dirección es siempre `https://api.faenabot.stream`, y `publico/backend.js` solo se vuelve a subir
si cambia la configuración visible de algún sitio. Sin túnel fijo usa uno gratuito (trycloudflare), cuya dirección
cambia en cada arranque y se publica en `backend.js`. Cuando el Mac no está disponible, todos los sitios muestran su
aviso «no disponible» (con su nombre y colores, que `backend.js` guarda). Requisitos: oMLX en marcha con el modelo cargado.

**Gestión:** http://localhost:5205 en el Mac, o https://gestion.faenabot.stream desde internet (solo los correos
autorizados en Cloudflare Access, con un código que llega al correo) — tickets y contactos de todos los sitios,
filtros por sitio, modo y estado, detalle con la conversación, visor de archivos, cambio de estado y notas. También:
`python3 servidor/solicitudes.py listar` y `python3 servidor/solicitudes.py ver TCK-0017`.

## Direcciones y túnel de Cloudflare

| Dirección | Qué es | Acceso |
|---|---|---|
| `faenabot.stream` | Página de FaenaBot con demo (Workers) | Pública |
| `asistente-ia.faenabot.stream` | Widget: `embed.js`, `asistente.js`, `backend.js` (Workers) | Pública |
| `api.faenabot.stream` | Servidor del asistente, :5204 en el Mac (túnel fijo) | Solo sitios autorizados (CORS) |
| `gestion.faenabot.stream` | Gestión, :5205 en el Mac (túnel fijo) | Cloudflare Access: correo + código |
| `wodobox-web.faenabot.stream`, `local-ia.faenabot.stream` | Páginas de Wodobox e IA Local (Workers) | Públicas |

El túnel con nombre `faenabot` une el Mac con Cloudflare sin abrir puertos. Su configuración está fuera del repo, en
`~/.cloudflared/` (`cert.pem` y `<id>.json` son secretos):

```yaml
# ~/.cloudflared/faenabot.yml
tunnel: <id-del-túnel>
credentials-file: /Users/<usuario>/.cloudflared/<id-del-túnel>.json
ingress:
  - hostname: api.faenabot.stream
    service: http://127.0.0.1:5204
  - hostname: gestion.faenabot.stream
    service: http://127.0.0.1:5205
  - service: http_status:404
```

Se creó con `cloudflared tunnel login`, `cloudflared tunnel create faenabot` y `cloudflared tunnel route dns faenabot
<dirección>` para cada dirección (crea los CNAME). Para agregar otra: `route dns`, su regla en `faenabot.yml` antes del
404 y `servicio.sh reiniciar`. En `servidor/.env`: `TUNEL_CONFIG`, `TUNEL_URL`, `GESTION_HOST`, `ACCESS_TEAM`, `ACCESS_AUD`.

**Cloudflare Access** (Zero Trust, plan Free): equipo `faenabot`; inicio de sesión con One-time PIN (Integrations →
Identity providers); aplicación «Gestión asistente» en `gestion.faenabot.stream` (solo One-time PIN, autenticación
instantánea, sesión de 24 h); política «Equipo» (Allow, Include → Emails). Para agregar o quitar personas: Access
controls → Policies → Equipo → Configure. Para cortar una sesión abierta: My Team → Users → Revoke session.

## Seguridad

- La API key de oMLX nunca sale del Mac (`servidor/.env`, fuera de git).
- El prompt lo pone el servidor; el navegador no puede cambiarlo.
- Solo responden los sitios con archivo en `sitios/` (CORS); solo `https://` salvo `localhost` para pruebas.
- Límites de mensajes y solicitudes por visitante, de generaciones simultáneas y de tokens; solo se usa el modelo ya
  cargado en oMLX; el chat no puede usar herramientas.
- Archivos: se verifica el tipo real por su contenido; en la gestión solo las imágenes se muestran directamente.
- La gestión acepta conexiones desde este Mac o, desde internet, solo con una sesión de Cloudflare Access: el servidor
  verifica en cada petición la firma del acceso (RS256, audiencia, emisor y vigencia) y sin `ACCESS_TEAM`/`ACCESS_AUD`
  el acceso remoto queda cerrado. Los cambios hechos desde internet quedan firmados con el correo de quien los hizo,
  y todos exigen una cabecera propia (CSRF).
