<template>
  <main class="page">
    <h2>Términos y Condiciones</h2>
    <p class="sub">Versión 1.0 · Septiembre 2026 · CTD — Controla Tu Dinero</p>
    <div class="card" style="margin-top: 12px; display: grid; gap: 12px">
      <div><strong>1. Objeto y aceptación.</strong><p class="sub">CTD es una aplicación web progresiva (PWA) de finanzas personales para registrar, organizar y visualizar ingresos, gastos, presupuestos y metas. Al crear tu cuenta aceptas estos Términos.</p></div>
      <hr class="divider" />
      <div><strong>2. Tu cuenta.</strong><p class="sub">Debes registrarte con un correo válido al que tengas acceso (sirve para verificación y recuperación). Eres responsable de tu contraseña y de no compartir tu sesión. Puedes cerrar sesión cuando quieras y solicitar la eliminación de tu cuenta escribiendo a contacto@ctd.app.</p></div>
      <hr class="divider" />
      <div><strong>3. Tu información financiera la pones tú.</strong><p class="sub">Los saldos, movimientos, presupuestos y metas los registras manualmente. CTD calcula a partir de lo que ingresas: si los datos son incompletos, los resultados también. Puedes dejar tu saldo inicial en 0 y usar solo el registro mensual de ingresos y gastos.</p></div>
      <hr class="divider" />
      <div><strong>4. Esto no es asesoría financiera.</strong><p class="sub">Los resúmenes, pronósticos, ritmos de gasto y mensajes (“puedes gastar…”, “necesitas ahorrar…”) son estimaciones informativas generadas con tus datos. No constituyen asesoría profesional de inversión, crédito o impuestos. Las decisiones siempre son tuyas.</p></div>
      <hr class="divider" />
      <div><strong>5. Uso correcto.</strong><p class="sub">Prohibido usar CTD para actividades ilícitas, intentar vulnerar su seguridad, automatizar accesos abusivos o registrar datos de terceros sin su consentimiento.</p></div>
      <hr class="divider" />
      <div><strong>6. Disponibilidad.</strong><p class="sub">CTD se ofrece “tal cual”. La app abre sin conexión, pero tus cifras se consultan al servidor en el momento: sin internet no se ven saldos ni movimientos. Exporta tu información desde Ajustes para tener una copia propia.</p></div>
      <hr class="divider" />
      <div><strong>7. Privacidad.</strong><p class="sub">El tratamiento de tus datos se rige por nuestra <a href="#" @click.prevent="$router.push('/datos')">Política de Tratamiento de Datos</a> (Ley 1581 de 2012).</p></div>
      <hr class="divider" />
      <div><strong>8. Propiedad y cambios.</strong><p class="sub">La marca, el diseño y el código de CTD son de sus titulares. Podemos actualizar estos Términos; los cambios importantes se avisarán en la app y seguir usándola implica aceptarlos.</p></div>
      <hr class="divider" />
      <div><strong>9. Ley aplicable.</strong><p class="sub">Se rigen por las leyes de la República de Colombia. Contacto: contacto@ctd.app.</p></div>
    </div>
    <button class="btn-primary" style="margin-top: 16px" @click="$router.back()">Volver</button>
  </main>
</template>
