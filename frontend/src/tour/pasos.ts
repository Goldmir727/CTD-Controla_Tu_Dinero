/**
 * El recorrido guiado: que se puede hacer en CTD, para quien acaba de entrar.
 *
 * Por que no es un documento: a un usuario nuevo no le sirve leer diez paginas
 * sobre una app que no conoce. Le sirve que le muestres un boton y le digas
 * "esto registra gastos, esto te dice si te alcanza". El texto largo queda en
 * TUTORIAL.md para cuando quiera leerlo con calma.
 *
 * Dos reglas que el recorrido respeta siempre:
 *  1. Se puede OMITIR en cualquier momento, y omitir no castiga: no vuelve a
 *     salir solo.
 *  2. Se puede volver a ver cuando se le olvide algo.
 */

export type Paso = {
  /** Selector CSS del elemento que se resalta. Vacio = tarjeta al centro. */
  selector?: string
  titulo: string
  texto: string
  /** Donde se pone la tarjeta respecto al elemento resaltado. */
  lado?: 'arriba' | 'abajo' | 'derecha' | 'izquierda'
}

export const PASOS: Paso[] = [
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
  },
  {
    selector: '[data-tour="quincena"]',
    titulo: 'Tu quincena, no tu mes',
    texto:
      'En Colombia se cobra dos veces al mes, y CTD razona en quincenas. ' +
      '"Cierra en" proyecta cómo vas al ritmo actual: asume tu ritmo y los fijos ' +
      'que faltan por vencer, pero no anticipa ingresos.',
    lado: 'abajo',
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
  },
  {
    selector: '[data-tour="perfil"]',
    titulo: 'Personal y Negocio, separados',
    texto:
      'Cada perfil lleva sus propias cuentas, categorías y saldos. Puedes tener ' +
      'los dos en la misma app sin que se mezclen los números.',
    lado: 'abajo',
  },
  {
    selector: '[data-tour="ajustes"]',
    titulo: 'Tus datos son tuyos',
    texto:
      'En Ajustes descargas tu Excel gratis (y se puede volver a subir sin ' +
      'duplicar nada), activas la verificación en dos pasos, y ves qué se está ' +
      'guardando de ti. El informe en PDF es lo único de PRO.',
    lado: 'abajo',
  },
  {
    titulo: 'Listo. Ya sabes lo básico',
    texto:
      'Puedes volver a ver esto cuando quieras desde Ajustes, en "Recorrido ' +
      'guiado". Si prefieres leer con calma, está TUTORIAL.md.',
  },
]