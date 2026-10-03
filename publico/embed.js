/*
 * Asistente IA — se integra en cualquier página con una sola línea, antes de </body>:
 *
 *   <script src="https://asistente-ia.pages.dev/embed.js" defer></script>
 *
 * Todo lo del sitio (nombre, saludo, colores, modo contacto o ticket, datos obligatorios y lo
 * que sabe el asistente) se configura en el servidor, en sitios/<dominio>.md. Un sitio sin
 * ese archivo no está autorizado y el asistente no aparece (queda un aviso en la consola).
 *
 * Opcional, antes de la línea: window.ASISTENTE = { greeting: '…', suggestions: […] } para
 * sobrescribir valores visibles solo en esa página (window.FAENA_BOT también se acepta).
 * Abrirlo desde un botón propio: <button onclick="asistenteIA.open()">Hablar con el asistente</button>
 */
(() => {
  if (window.__asistenteIA) return; // evita cargarlo dos veces si se pega el código repetido
  window.__asistenteIA = true;

  const base = new URL('.', document.currentScript?.src || location.href).href; // carpeta de este archivo
  const local = /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?\/$/.test(new URL(base).origin + '/');
  const override = window.ASISTENTE || window.FAENA_BOT || {};

  const load = src => new Promise((ok, ko) => {
    const s = Object.assign(document.createElement('script'), { src, async: false });
    s.onload = ok;
    s.onerror = () => ko(new Error('no se pudo cargar ' + src));
    document.head.append(s);
  });
  const css = Object.assign(document.createElement('link'), { rel: 'stylesheet', href: base + 'asistente.css' });
  document.head.append(css);

  // Configuración del servidor (claves de sitios/<dominio>.md) -> opciones del widget
  const fromServer = c => ({
    mode: c.modo, assistantName: c.nombre, modelLabel: c.etiqueta, avatar: c.avatar, greeting: c.saludo,
    suggestions: c.sugerencias, unavailableMessage: c.no_disponible, footnote: c.pie, attachments: c.adjuntos,
    contactConfirmation: c.confirmacion, contactRequired: c.obligatorios, contactAnyOf: c.al_menos_uno,
  });
  const theme = c => {
    const vars = [['--oa-principal', c.color_principal], ['--oa-cabecera', c.color_cabecera], ['--oa-acento', c.color_acento]]
      .filter(([, v]) => /^#[0-9a-fA-F]{3,8}$/.test(v || '')).map(([k, v]) => `${k}: ${v};`).join(' ');
    if (vars) document.head.append(Object.assign(document.createElement('style'), { textContent: `.oa-root { ${vars} }` }));
  };

  const notAuthorized = () => console.warn(
    `Asistente IA: este sitio (${location.host}) no está autorizado. Crea su archivo en servidor/sitios/${location.host.replace(':', '_')}.md`);

  (async () => {
    try {
      await load(base + 'backend.js');
      // backend.js (lo genera servidor/publicar.sh) trae la dirección del túnel hacia el Mac;
      // al probar con los archivos servidos desde localhost se usa el servidor local.
      const backend = (window.ASISTENTE_BACKEND || (local ? 'http://localhost:5204' : '')).replace(/\/+$/, '');
      // Configuración del sitio: la del servidor (al día) o, si está apagado, la que trae backend.js
      const saved = (window.ASISTENTE_SITIOS || {})[location.host] || null;
      let server = null, offline = !backend;
      if (backend) {
        try {
          const res = await fetch(backend + '/api/config', { credentials: 'omit' });
          if (res.status === 403) return notAuthorized();
          if (!res.ok) throw new Error('HTTP ' + res.status);
          server = await res.json();
        } catch {
          offline = true; // servidor apagado o túnel caído: el asistente aparece como «no disponible»
        }
      }
      if (!server) {
        if (!saved) return notAuthorized(); // ni el servidor ni backend.js conocen este sitio
        server = saved;
      }
      window.OMLX_ASSISTANT = {
        baseUrl: backend,
        unavailable: offline,
        tickets: { endpoint: '/api/solicitudes' },
        maxTokens: 1024, temperature: 0.4, enableThinking: false, maxFileMB: 10,
        ...(server ? fromServer(server) : {}),
        ...override,
      };
      if (server) theme(server);
      await load(base + 'asistente.js');
    } catch (e) {
      console.warn('Asistente IA:', e.message);
    }
  })();
})();
