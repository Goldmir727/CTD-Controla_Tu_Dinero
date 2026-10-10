<template>
  <main class="page">
    <h2>Política de Tratamiento de Datos</h2>
    <p class="sub">Versión 1.0 · Septiembre 2026 · Ley 1581 de 2012 y Decreto 1377 de 2013 (Colombia)</p>
    <div class="card" style="margin-top: 12px; display: grid; gap: 12px">
      <div><strong>1. Responsable.</strong><p class="sub">CTD — Controla Tu Dinero, proyecto de finanzas personales. Contacto para tus derechos: contacto@ctd.app. Al registrarte aceptas esta política de forma previa, expresa e informada.</p></div>
      <hr class="divider" />
      <div><strong>2. Qué datos recogemos.</strong><p class="sub">Identificación y contacto que nos das (nombre, correo, moneda); credenciales protegidas (la contraseña se guarda con hash, nunca en claro); información financiera que tú registras (cuentas, saldos, movimientos, presupuestos, metas); datos técnicos mínimos (sesión, preferencias de tema, registros de seguridad como intentos de acceso).</p></div>
      <hr class="divider" />
      <div><strong>3. Para qué los usamos (finalidades).</strong><p class="sub">Operar tu cuenta y mostrarte tu información; autenticarte y proteger el acceso (incluido el 2FA por correo); calcular resúmenes, presupuestos y metas; enviarte códigos de seguridad y recuperación; hacer respaldos y atender tus solicitudes. Nunca vendemos tus datos ni los usamos para publicidad de terceros.</p></div>
      <hr class="divider" />
      <div><strong>4. Tus saldos son opcionales.</strong><p class="sub">Pedirte “cuánto dinero tienes hoy” tiene un único propósito: calcular tu DISPONIBLE inicial. Puedes dejarlo en 0 y usar CTD solo para ver tus ingresos y gastos del mes. Nada se comparte por registrarlo.</p></div>
      <hr class="divider" />
      <div><strong>5. Dónde se guardan y cómo se protegen.</strong><p class="sub">Infraestructura en la nube con cifrado en tránsito (HTTPS) y controles de acceso por usuario: cada cuenta solo ve sus datos. El historial de tus chats con el Asesor se guarda para darte continuidad y puedes borrarlo cuando quieras. Conservamos tu información mientras tu cuenta exista y hasta 5 años después de eliminarla por obligaciones legales, salvo que pidas supresión antes.</p></div>
      <hr class="divider" />
      <div><strong>6. Tus derechos (art. 8, Ley 1581).</strong><p class="sub">Conocer, actualizar, rectificar y suprimir tus datos; revocar tu autorización; presentar quejas ante la Superintendencia de Industria y Comercio. Escríbenos a contacto@ctd.app: respondemos consultas en 10 días hábiles y reclamos en 15 (Ley 1581, art. 14-15).</p></div>
      <hr class="divider" />
      <div><strong>7. Menores.</strong><p class="sub">CTD está dirigido a mayores de edad. Si eres menor, úsalo con tu representante legal.</p></div>
      <hr class="divider" />
      <div><strong>8. Cambios.</strong><p class="sub">Avisaremos en la app los cambios sustanciales antes de aplicarlos. La versión vigente siempre estará en esta página.</p></div>
    </div>
    <button class="btn-primary" style="margin-top: 16px" @click="$router.back()">Volver</button>
  </main>
</template>
