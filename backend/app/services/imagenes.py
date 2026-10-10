"""Validación de imágenes data-URL (avatares, metas)."""
from fastapi import HTTPException


def validar_imagen(imagen_url: str | None, max_chars: int = 700_000) -> None:
    if imagen_url is None or imagen_url == "":
        return
    ok = imagen_url.startswith(
        ("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,")
    )
    if not ok and not imagen_url.startswith(("http://", "https://")):
        raise HTTPException(422, "Imagen inválida: usa JPG/PNG/WebP o una URL http(s)")
    if len(imagen_url) > max_chars:
        raise HTTPException(422, "Imagen muy pesada")
