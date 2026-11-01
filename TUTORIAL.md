# CTD · Guía básica

Qué hace la app y cómo se usa. Si estás leyendo esto, probablemente quieres
registrar tus gastos y entender qué te dice la app.

> Esta guía es para leer. La ayuda **dentro** de la app es el recorrido guiado:
> aparece la primera vez que entras y puedes volver a abrirlo con el botón **?**
> de la cabecera, que además abre el paso que explica la pantalla donde estás.

---

## 1. La idea

CTD registra lo que entra y lo que sale, y te avisa **por quincenas** si te
alcanza.

No es un contador de gastos: es el que te avisa **antes** de quedarte sin plata.

---

## 2. Las seis pantallas

| Pestaña | Para qué sirve |
|---|---|
| **Inicio** | Lo esencial: cuánto tienes y cómo vas esta quincena o este mes |
| **Movs** | Todo lo registrado, editable — y los **fijos** (ingresos y gastos que se repiten), en la pestaña Fijos |
| **Agenda** | El calendario: qué se registró cada día y qué fijos vienen |
| **Plan** | Presupuestos y metas |
| **Datos** | Tendencias y comparaciones mes a mes |
| **Asesor** | Preguntas en español sobre **tus** números |

El botón redondo **+** (o **+ Nuevo movimiento** en escritorio) está siempre a
mano: abre el registro desde cualquier pantalla, también desde Inicio.

---

## 3. Primeros 5 minutos

### Regístrate

Al crear la cuenta te piden aceptar los términos y el tratamiento de datos. No
es burocracia: **las frases que escribes sí se envían a un modelo de IA** para
entenderlas. Está explicado en la pantalla `/datos`.

El audio de las notas de voz **se borra después de transcribirlo**; solo queda el
texto.

### Registrar: dictando o a mano

El botón de registrar abre dos caminos:

| Camino | Cuándo usarlo | Necesita internet |
|---|---|---|
| **Dictar o escribir** una frase | Lo de todos los días: "gasté 25 mil en un almuerzo" | Sí |
| **+ Ingreso / − Gasto** (formulario) | Cuando no quieres dictar, o no tienes señal | No |

Frases que entiende el primer camino:

```
gasté 25 mil en un almuerzo con los amigos
pagué el arriendo de 1.200.000
me llego el salario de 2.500.000
```

**Siempre revisa antes de guardar.** La app te muestra lo que entendió y tú
confirmas. Si el monto no estaba en tu texto, te lo pide a mano.

El formulario manual pide monto, cuenta y categoría. La cuenta es obligatoria:
el saldo de todas tus cuentas depende de ella.

### Si ya tienes el gasto en la cabeza y no en la frase

No pasa nada: abre el formulario manual y anótalo en dos toques. Es el mismo
registro que el dictado, solo que sin pasar por el intérprete.

---

## 4. Si te quedas sin internet

La app está pensada para usarse en la calle, donde la señal se va.

**Funciona sin conexión:**

- Registrar movimientos (ingreso o gasto) con el formulario manual.
- Registrar y editar fijos.
- Ver y corregir lo que ya registraste, y los saldos de tus cuentas.
- Elegir cuenta, categoría y método: se usan las copias guardadas en el
  teléfono de la última vez que hubo red.

**No funciona sin conexión:**

- Dictar o escribir una frase (lo interpreta el servidor).
- Agenda, Datos (análisis y tendencias), Asesor y el informe en PDF.

**Qué te dice la app:** arriba aparece un aviso **"Sin conexión"** que explica
esto mismo. Todo lo que registres se guarda en el dispositivo y se **envía solo**
cuando vuelve la red. Mientras tanto verás cuántos cambios faltan por enviar, y
un botón para reintentar si alguno se queda atascado.

Tu sesión **no se cierra** al quedarte sin red: sigues dentro de tu cuenta.

> Consejo: abre la app una vez con internet antes de salir (Inicio o Movs basta).
> Eso deja descargadas tus cuentas y categorías para poder registrar sin señal.

---

## 5. Los dos conceptos que importan

### Disponible y "cierra en"

**Disponible** es tu saldo real hoy: la suma de todas tus cuentas menos lo que
deben.

**Cierra en** es una proyección: si sigues al mismo ritmo, así vas a terminar el
periodo. Asume tu ritmo actual y los gastos fijos que faltan por vencer. **No
adivina ingresos**, así que si te pagan algo que no está registrado, ahí no lo
cuenta.

### Qué es una quincena

CTD razona en **quincenas** en los países donde se cobra dos veces al mes
(Colombia, México, Argentina). Si tu país no es de esos, razona **por mes**, y
por eso el texto y las fechas cambian solos.

Puedes cambiar el país en **Ajustes → País y moneda**, que también cambia el
formato de los números:

| País | Se ve así |
|---|---|
| Colombia | $1.800.000 |
| México | $1,800,000.00 |
| Estados Unidos | $1,800,000.00 |
| España | €1.800.000,00 |
| Perú | S/1,800,000.00 |

Que el número se vea distinto **no significa que valga distinto**: la app no
convierte entre monedas, cambia cómo se muestra.

---

## 6. Plan y Fijos: lo que puedes declarar

**Presupuestos** — un tope por categoría y mes. La app avisa cuando vas más
rápido de lo que el calendario permite, no solo cuando te pasaste.

> "Ya gastaste el 80% de Ocio y apenas vamos el día 12."

**Metas** — para qué quieres el dinero. CTD calcula cuánto ahorrar por mes.

**Fijos** (en **Movs › Fijos**) — lo que siempre entra o sale: arriendo,
internet, suscripción, el sueldo. Se declara con su frecuencia: cada mes, cada
15 días o cada semana. Sirven para que el motor separe lo fijo de lo variable y
no te diga "te alcanza" cuando no es cierto.

También se detectan solos: si registras "pagué el arriendo" y ya lo tienes
declarado, te pregunta **"¿es el mismo o es uno distinto?"**. Tú respondes, la
app no adivina.

---

## 7. Si te equivocaste

Toca el movimiento en **Movs** y lo editas. Corregir es normal y rápido: es
mejor que borrarlo y volver a escribirlo.

También puedes eliminarlo.

---

## 8. Tus datos son tuyos

**Ajustes → Respaldo y exportación**:

- **Excel** — gratis. Se abre en cualquier hoja de cálculo, con una hoja por
  cosa. Es el formato para revisar y para mandarle al contador.
- **JSON** — gratis. La copia técnica.
- **PDF** — de PRO. Es el único de pago, y no es una copia de tus datos: es el
  documento armado para enseñárselo a alguien.

El Excel se puede volver a subir y la app lo restaura **sin duplicar nada**, así
que puedes usarlo como tu copia de seguridad.

---

## 9. El asesor

Pregunta en español normal sobre tus propios números:

```
¿cómo voy este mes?
¿puedo comprar un celular de 2 millones este mes?
¿cuál es mi meta más alcanzable?
```

No inventa cifras: pide los datos y el backend los calcula. Si no alcanza,
te lo dice.

**Gratis son 5 consultas al día.** Si necesitas más, activa PRO.

---

## 10. Seguridad

- Activa **2FA** en Ajustes: te llega un código por correo.
- Exporta tu Excel de vez en cuando. Tus datos están en la nube.
- Si usas una red pública, no dejes sesión abierta en un computador compartido.

---

## 11. Instalarla en el teléfono

Abre la app en el navegador del celular y usa **"Instalar app"**. Se comporta
como una app normal, con icono propio, y **abre sin conexión**: la pantalla y
tus datos se cargan del teléfono. Lo que registres sin red se envía al volver la
señal (ver sección 4).

Cuando haya versión nueva aparece una cinta para actualizar.
