"""Versiones de los documentos legales.

Viven aqui, y no en api/v1/auth.py, porque los necesita tanto el router como
schemas/auth.py. Ponerlas en el router generaba import circular.

Por que importa: `user_out` compara la version guardada contra la vigente para
decidir si hay que volver a pedir consentimiento. Con la 1.1 (envío de datos a
Groq) eso es obligatorio bajo la Ley 1581.
"""

TERMINOS_VERSION = "1.0"
# 1.0 -> 1.1: se aviso que el Asesor y la captura por voz envian datos a un
# proveedor externo (Groq, USA), que eso es tratamiento transfactivo bajo la
# Circular 008 de la SIC, y que el audio se transcribe y se descarta.
DATOS_VERSION = "1.1"