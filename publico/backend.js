// Lo genera servidor/publicar.sh: dirección del servidor del asistente ('' = no disponible)
// y la configuración visible de cada sitio autorizado (nunca su contexto).
window.ASISTENTE_BACKEND = "";
window.ASISTENTE_SITIOS = {
 "averan.github.io": {
  "modo": "contacto",
  "obligatorios": [
   "necesidad"
  ],
  "al_menos_uno": [
   "correo",
   "telefono",
   "otro"
  ],
  "confirmacion": "¡Gracias! Te contactaremos por {contacto} para coordinar la llamada o el Meet.",
  "nombre": "IA Local",
  "etiqueta": "Asistente IA Local",
  "avatar": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text x='8' y='.85em' font-size='80'>🤖</text></svg>",
  "saludo": "¡Hola! 👋 Soy un asistente de IA que funciona en un computador local, sin nube. ¿Quieres ver qué puede hacer la IA local por tu empresa?",
  "sugerencias": [
   "¿Qué es la IA local?",
   "¿Qué soluciones puedo probar?",
   "Quiero agendar un Meet"
  ],
  "no_disponible": "En este momento el asistente está apagado (corre en un computador local 😉). Vuelve a intentarlo más tarde.",
  "pie": "IA en un computador local · admite imágenes, PDF, Word, Excel y texto",
  "adjuntos": true,
  "color_principal": "",
  "color_cabecera": "",
  "color_acento": ""
 },
 "local-ia.andres-veran.workers.dev": {
  "modo": "contacto",
  "obligatorios": [
   "necesidad"
  ],
  "al_menos_uno": [
   "correo",
   "telefono",
   "otro"
  ],
  "confirmacion": "¡Gracias! Te contactaremos por {contacto} para coordinar la llamada o el Meet.",
  "nombre": "IA Local",
  "etiqueta": "Asistente IA Local",
  "avatar": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text x='8' y='.85em' font-size='80'>🤖</text></svg>",
  "saludo": "¡Hola! 👋 Soy un asistente de IA que funciona en un computador local, sin nube. ¿Quieres ver qué puede hacer la IA local por tu empresa?",
  "sugerencias": [
   "¿Qué es la IA local?",
   "¿Qué soluciones puedo probar?",
   "Quiero agendar un Meet"
  ],
  "no_disponible": "En este momento el asistente está apagado (corre en un computador local 😉). Vuelve a intentarlo más tarde.",
  "pie": "IA en un computador local · admite imágenes, PDF, Word, Excel y texto",
  "adjuntos": true,
  "color_principal": "",
  "color_cabecera": "",
  "color_acento": ""
 },
 "web-vercel-zeta-red.vercel.app": {
  "modo": "contacto",
  "obligatorios": [
   "nombre",
   "empresa",
   "correo",
   "necesidad"
  ],
  "al_menos_uno": [],
  "confirmacion": "Un socio de Faena te contactará en {correo} en menos de 48 horas hábiles.",
  "nombre": "Asistente Faena",
  "etiqueta": "Faena-Bot",
  "avatar": "https://web-vercel-zeta-red.vercel.app/img/faena-symbol.png",
  "saludo": "Hola, soy Faena-Bot. Te cuento cómo ayudamos a empresas tecnológicas a crecer con estructura, o te conecto con un socio de Faena. ¿Qué desafío tiene hoy tu empresa?",
  "sugerencias": [
   "¿Qué es un ejecutivo fraccional?",
   "¿Cómo trabajan?",
   "Quiero agendar una conversación"
  ],
  "no_disponible": "En este momento el asistente no está disponible. Escríbenos a **soporte@faenacs.com** y te responderemos en menos de 48 horas hábiles.",
  "pie": "Asistente virtual de Faena · admite imágenes, PDF, Word, Excel y texto",
  "adjuntos": true,
  "color_principal": "#2f5bff",
  "color_cabecera": "#0b1f33",
  "color_acento": "#1fc8e3"
 },
 "wodobox-web.andres-veran.workers.dev": {
  "modo": "ticket",
  "obligatorios": [
   "titulo",
   "descripcion",
   "nombre",
   "correo"
  ],
  "al_menos_uno": [],
  "confirmacion": "Tu número de ticket es **{id}**. La Mesa de Ayuda te contactará en {correo}.",
  "nombre": "Asistente",
  "etiqueta": "Wodobox-Bot",
  "avatar": "https://wodobox-web.andres-veran.workers.dev/img/wodobox-avatar.png",
  "saludo": "Hola, soy Wodobox-Bot de la Mesa de Ayuda. Puedo registrar un problema o pedir un servicio por ti (licencias, accesos, VPN, software, equipos). ¿Qué necesitas?",
  "sugerencias": [
   "Tengo un problema con un sistema",
   "Necesito una licencia (Power BI, Excel…)",
   "Quiero acceso a Jira o a la VPN",
   "Necesito instalar un software"
  ],
  "no_disponible": "En este momento el asistente no está disponible. Escribe a **contactoweb@wodobox.com** y la Mesa de Ayuda te responderá.",
  "pie": "Procesado en nuestro Mac Studio · imágenes, PDF, Word, Excel y texto",
  "adjuntos": true,
  "color_principal": "#ff375a",
  "color_cabecera": "#002b49",
  "color_acento": "#ff375a"
 }
};
