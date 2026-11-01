/**
 * El recorrido: que se puede hacer en CTD, para quien acaba de entrar.
 *
 * Por que no es un documento: a un usuario nuevo no le sirve leer diez paginas
 * sobre una app que no conoce. Le sirve que le muestres un boton y le digas
 * "esto registra gastos, esto te dice si te alcanza".
 *
 * Ojo: TUTORIAL.md NO es la ayuda del usuario. Vive en la raiz del repo, no se
 * sirve desde dist y no tiene ruta, asi que nadie que use la app puede abrirlo.
 * La unica ayuda real es este recorrido, y el boton "?" lo abre en el paso que
 * explica la pantalla actual.
 *
 * Dos reglas que el recorrido respeta siempre:
 *  1. Se puede OMITIR en cualquier momento, y omitir no castiga: no vuelve a
 *     salir solo.
 *  2. Se puede volver a ver cuando se le olvide algo.
 *
 * Hay un paso dedicado a quedarse sin internet. No es un detalle tecnico: es la
 * duda que mas frena a alguien que registra en la calle, y si no se explica ahi
 * el usuario cierra la app pensando que perdio el gasto.
 *
 * El texto del paso de la quincena depende del pais: en Colombia y Mexico se
 * cobra dos veces al mes y el concepto existe; en Estados Unidos no, y ahi el
 * mismo texto seria mentira.
 */

export type ContextoPais = {
  pais: string
  nombre: string
  usaQuincena: boolean
}

export type Paso = {
  /** Selector CSS del elemento que se resalta. Vacio = tarjeta al centro. */
  selector?: string
  titulo: string
  /** Texto fijo, o funcion que recibe el pais del usuario. */
  texto: string | ((c: ContextoPais) => string)
  /** Donde se pone la tarjeta respecto al elemento resaltado. */
  lado?: 'arriba' | 'abajo' | 'derecha' | 'izquierda'
  /**
   * Pantalla donde este paso tiene sentido. Es lo que permite que el boton "?"
   * abra el tour EN el paso que explica lo que el usuario esta mirando, en vez
   * de siempre por el primero. '*' = sirve en cualquier pantalla.
   */
  ruta?: string
}

const QUINCENA = (c: ContextoPais) =>
  `Elegiste contar por quincenas: CTD parte el mes en dos (1 al 15 y 16 al final) ` +
  `porque es como te pagan. "Cierra en" proyecta cómo vas al ritmo actual: asume tu ` +
  `ritmo y los fijos que quedan por vencer, pero no anticipa ingresos.`

const SIN_QUINCENA = (c: ContextoPais) =>
  `CTD razona por mes completo. "Cierra en" proyecta cómo vas al ritmo actual: ` +
  `asume tu ritmo y los fijos que te tocan antes de que se termine el mes. Las ` +
  `proyecciones nunca anticipan ingresos. Si te pagan cada 15 días, puedes cambiarlo ` +
  `en Ajustes, en "Cómo cuentas el mes".`

export function pasosPara(pais: ContextoPais): Paso[] {
  const conQuincena = pais.usaQuincena
  return [
    {
      titulo: 'Esto es lo que puedes hacer',
      texto:
        'Registrar lo que entra y lo que sale, ver si te alcanza antes de ' +
        'quedarte sin plata, controlar presupuestos y metas, y preguntarle al ' +
        'asesor sobre tus números. Te lo mostramos en menos de un minuto. ' +
        'Puedes saltarlo cuando quieras y volver a verlo después.',
    },
    /*
 * `[data-tour="captura"]` esta en el boton flotante (movil) y en la pastilla
 * Capturar (escritorio, donde no hay flotante): los dos abren el panel de
 * registro. El texto no nombra el control a proposito, porque cambia segun el
 * ancho de pantalla y nombrar uno solo seria mentira en el otro.
 *
 * Se explican los DOS caminos: dictar y anotar a mano. Antes solo se hablaba de
 * la voz, y quien no podia o no queria dictar no sabia que el formulario manual
 * estaba detras del mismo boton.
 */
{
      selector: '[data-tour="captura"]',
      titulo: 'Registrar en dos toques',
      texto:
        'El botón de registrar abre dos caminos: dictarlo o escribirlo ("gasté 25 ' +
        'mil en un almuerzo"), o anotarlo a mano con + Ingreso / − Gasto. Los dos ' +
        'guardan en el mismo lugar, y siempre ves lo que se va a guardar antes de ' +
        'confirmar.',
      ruta: '*',
    },
    {
      titulo: 'Si te quedas sin internet',
      texto:
        'La app no deja de funcionar: puedes registrar movimientos y fijos, y ' +
        'editarlos, sin señal. Se guardan en este dispositivo y se envían solos ' +
        'cuando vuelve la red. Arriba verás un aviso con cuántos cambios faltan ' +
        'por enviar. Lo que sí necesita internet: dictar por voz, Agenda, Datos, ' +
        'Asesor y el informe en PDF.',
    },
    {
      selector: '[data-tour="quincena"]',
      titulo: conQuincena ? 'Tu quincena, no tu mes' : 'Cómo vas este mes',
      texto: conQuincena ? QUINCENA(pais) : SIN_QUINCENA(pais),
      lado: 'abajo',
      ruta: '/inicio',
    },
    {
      selector: '[data-tour="alerta"]',
      titulo: 'El aviso que llega a tiempo',
      texto:
        'Cuando vas más rápido que el calendario, te lo decimos antes de pasarte. ' +
        'No basta con "gastaste el 80%": importa si es el día 12 o el día 28.',
      lado: 'abajo',
    },
    {
      selector: '[data-tour="nav"]',
      titulo: 'Seis pantallas, seis oficios',
      texto:
        'Inicio para lo esencial, Movs para corregir lo que registraste y declarar ' +
        'lo que se repite (pestaña Fijos), Agenda para ver el mes y lo que viene, ' +
        'Plan para presupuestos y metas, Datos para ver tendencias, y Asesor para ' +
        'preguntar con tus propias cifras.',
      lado: 'abajo',
      ruta: '*',
    },
    {
      selector: '[data-tour="perfil"]',
      titulo: 'Personal y Negocio, separados',
      texto:
        'Cada perfil lleva sus propias cuentas, categorías y saldos. Puedes tener ' +
        'los dos en la misma app sin que se mezclen los números.',
      lado: 'abajo',
      ruta: '*',
    },
    {
      selector: '[data-tour="ajustes"]',
      titulo: 'Tus datos son tuyos',
      texto:
        'En Ajustes descargas tu Excel gratis (y se puede volver a subir sin ' +
        'duplicar nada), cambias el país si te mudaste, activas la verificación en ' +
        'dos pasos, y ves qué se está guardando de ti. El informe en PDF es lo ' +
        'único de PRO.',
      lado: 'abajo',
      ruta: '/config',
    },
    {
      titulo: 'Listo. Ya sabes lo básico',
      texto:
        'Puedes volver a ver esto cuando quieras con el botón ? de la cabecera, ' +
        'que abre el paso que explica la pantalla donde estás, o desde Ajustes, en ' +
        '"Recorrido guiado". Si algo te confunde, ese botón es la ayuda más rápida.',
    },
  ]
}

/**
 * Paso que mejor explica la pantalla que el usuario tiene abierta, para que el
 * boton "?" sea ayuda contextual y no siempre el primer paso.
 *
 * Gana el primer paso etiquetado con esa ruta; si ninguno, el primero marcado
 * como universal ('*'), que es el que explica que hace cada pantalla.
 */
export function indiceParaRuta(pasos: Paso[], ruta: string): number {
  const i = pasos.findIndex((p) => p.ruta === ruta)
  if (i >= 0) return i
  const j = pasos.findIndex((p) => p.ruta === '*')
  return j >= 0 ? j : 0
}