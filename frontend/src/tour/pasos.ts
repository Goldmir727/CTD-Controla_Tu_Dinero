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
  `En ${c.nombre} se cobra dos veces al mes, y CTD razona en quincenas. ` +
  `"Cierra en" proyecta cómo vas al ritmo actual: asume tu ritmo y los fijos que ` +
  `quedan por vencer, pero no anticipa ingresos.`

const SIN_QUINCENA = (c: ContextoPais) =>
  `En ${c.nombre} no se cobra por quincena, así que CTD razona por mes: te dice ` +
  `cómo vas contra el presupuesto del mes y qué fijos te tocan antes de que se ` +
  `termine. Las proyecciones nunca anticipan ingresos.`

export function pasosPara(pais: ContextoPais): Paso[] {
  const conQuincena = pais.usaQuincena
  return [
    {
      titulo: 'Esto es lo que puedes hacer',
      texto:
        'Registrar un gasto hablando, ver si te alcanza antes de quedarte sin ' +
        'plata, controlar presupuestos y metas, y preguntarle al asesor sobre tus ' +
        'números. Te lo mostramos en cuarenta segundos. Puedes saltarlo cuando quieras.',
    },
    {
      selector: '[data-tour="capturar"]',
      titulo: 'Registra lo que gastaste, hablándolo',
      texto:
        'Escribe "gasté 25 mil en un almuerzo" o dictalo. La app te muestra lo que ' +
        'entendió y tú confirmas antes de que se guarde nada. Si el monto no ' +
        'estaba en tu frase, te lo pide a mano.',
      ruta: '/movimientos',
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
      titulo: 'Cinco pantallas, cinco oficios',
      texto:
        'Inicio para lo esencial, Movs para corregir lo que registraste, Plan para ' +
        'presupuestos, metas y gastos fijos, Datos para ver tendencias, y Asesor ' +
        'para preguntar.',
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
        'Puedes volver a ver esto cuando quieras con el botón ? de la cabecera, o ' +
        'desde Ajustes, en "Recorrido guiado".',
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