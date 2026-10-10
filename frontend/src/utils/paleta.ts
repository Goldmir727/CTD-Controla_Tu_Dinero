/** Paleta de la marca, replicada de styles/tokens.css.
 *  Se mantiene tambien en backend/app/services/tema.py para que los PDF de
 *  reportlab usen exactamente los mismos colores que la pantalla.
 *  Si cambias un valor aqui, cambialo tambien alla. */

export const PALETA = [
  '#16B98B', // verde marca
  '#050B3B', // navy
  '#5CF2C0', // mint claro
  '#D89A27', // ambar
  '#8CA0B8', // gris azulado
  '#E25555', // rojo
  '#0A1763', // navy 2
  '#7C4DFF', // violeta (para series extra)
  '#00B4D8', // cian
  '#F4A261' // durazno
] as const

export const TEMA = {
  navy: '#050B3B',
  navy2: '#0A1763',
  mint: '#00FFAB',
  mintDark: '#16B98B',
  mintDim: '#5CF2C0',
  danger: '#E25555',
  warning: '#D89A27',
  ink: '#10202F',
  inkSoft: '#6B7A87',
  line: '#E2E8F0',
  bg: '#F7F9FA',
  surface: '#FFFFFF'
} as const

/** Colores de eje/texto segun el tema claro u oscuro. */
export function coloresTexto(oscuro: boolean): { texto: string; suave: string; linea: string; superficie: string } {
  return oscuro
    ? { texto: '#FFFFFF', suave: '#B9C2E0', linea: '#1B2560', superficie: '#0B1340' }
    : { texto: '#10202F', suave: '#6B7A87', linea: '#E2E8F0', superficie: '#FFFFFF' }
}

/** Un color estable por indice (cicla la paleta) para que un grafico con dos
 *  consultas distintas conserve el color de cada categoria. */
export function colorPorIndice(i: number): string {
  return PALETA[i % PALETA.length] as string
}
