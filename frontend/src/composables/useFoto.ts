/** Foto a data-URL JPEG cuadrada liviana (avatares y metas). */
export function archivoADataURL(f: File, max = 256): Promise<string> {
  return new Promise((res, rej) => {
    if (!f.type.startsWith('image/')) {
      rej(new Error('El archivo no es una imagen.'))
      return
    }
    const url = URL.createObjectURL(f)
    const img = new Image()
    img.onload = () => {
      try {
        const lado = Math.min(img.width, img.height)
        const sx = (img.width - lado) / 2
        const sy = (img.height - lado) / 2
        const s = Math.min(1, max / lado)
        const c = document.createElement('canvas')
        c.width = Math.round(lado * s)
        c.height = Math.round(lado * s)
        c.getContext('2d')!.drawImage(img, sx, sy, lado, lado, 0, 0, c.width, c.height)
        URL.revokeObjectURL(url)
        res(c.toDataURL('image/jpeg', 0.82))
      } catch (e) {
        rej(e)
      }
    }
    img.onerror = () => rej(new Error('No se pudo leer la imagen.'))
    img.src = url
  })
}
