# Semáforo Renal Tabasco

Aplicación académica de la UJAT con una calculadora pública del índice TyG y un espacio profesional separado para registrar evaluaciones y explorar patrones metabólico-musculares en pacientes en hemodiálisis. Construida con Python y Streamlit.

## Entrada pública para pacientes y visitantes

La dirección principal abre la calculadora pública, sin iniciar sesión. Solo solicita glucosa y triglicéridos en ayunas, ambos en mg/dL. No pide nombre, edad, correo, teléfono, creatinina ni un expediente. El resultado es numérico e informativo; no aplica a la población general los cortes de la cohorte de hemodiálisis ni presenta una clasificación diagnóstica.

Los valores se procesan en la sesión de Streamlit y no se escriben en la base de pacientes. Cada sesión comienza vacía y el botón **Borrar mis datos y comenzar de nuevo** elimina sus valores y resultado. La persona puede descargar un archivo de texto con su resultado o enviárselo por correo; la dirección es opcional y no se guarda. No se agregan valores clínicos a la dirección del navegador ni a los QR.

El botón **Acceso profesional** lleva a `?vista=profesional`. El acceso profesional sigue las reglas del modo configurado: demostración temporal o autenticación para datos persistentes. La vista pública funciona incluso si el almacenamiento profesional no está configurado.

## Acceso desde un código QR

1. Publica el sitio con una dirección HTTPS accesible desde internet.
2. Entra al espacio profesional y abre **Compartir calculadora**.
3. Introduce la dirección pública del sitio y pulsa **Generar código QR**. Opcionalmente configura `RENAL_PUBLIC_URL` para precargarla.
4. Descarga el PNG para imprimir o compartir. El enlace contiene `?vista=publica`, de modo que abre directamente la calculadora.
5. Pruébalo desde un teléfono con datos móviles antes de distribuirlo.

Una dirección de desarrollo como `http://127.0.0.1:8501` no permite acceder desde otros teléfonos. La aplicación rechaza direcciones locales para generar el QR. No se incluye un QR definitivo mientras el sitio no tenga una dirección pública. La generación del QR se realiza en el servidor, sin enviar el enlace a un servicio externo.

## Qué incluye

- Calculadora pública anónima con dos campos, explicación del resultado y reinicio de datos.
- Generación y descarga de QR para la dirección pública del sitio.
- Panel de inicio con indicadores, registros recientes y distribución de patrones por última evaluación de cada paciente.
- Expedientes con identificadores únicos: los homónimos no comparten seguimiento.
- Captura vacía de inicio; carga de ejemplos explícita y validación de valores, unidades y fecha.
- Cálculo de TyG e IMC, vista previa y confirmación separada de guardado.
- Prevención de duplicados exactos y confirmación de registros distintos en la misma fecha.
- Correcciones con control de revisión; archivo reversible y restauración.
- Gráficas con puntos, unidades, cortes de referencia y filtros por fecha.
- Reportes PDF y CSV completo, con datos originales, cortes, método y revisión.
- Modo demostración aislado por sesión con tres pacientes ficticios.
- Modo persistente con SQLite, cifrado de los datos de pacientes, autenticación y expedientes separados por cuenta.
- Administración de cuentas, respaldo consistente de SQLite y registro de actividad sin nombres ni valores clínicos.
- Diseño adaptable con colores, etiquetas textuales y estilos para pantallas pequeñas.
- Apariencia de día y de noche: sigue el modo del dispositivo y se puede cambiar en ⋮ › Settings › Theme. Los temas se definen en `.streamlit/config.toml`.
- Logo propio (riñón con semáforo) en `assets/logo.svg` y `assets/logo.png`.

## Ejecutar la demostración

Requiere Python 3.12. Desde la raíz del proyecto:

```sh
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

La dirección principal abre la calculadora pública. Para explorar el panel profesional, usa **Acceso profesional** o abre `http://localhost:8501/?vista=profesional`. El modo profesional predeterminado es `demo`. Solo utiliza datos ficticios: no escribe expedientes en disco ni exige credenciales y sus cambios desaparecen al terminar la sesión. El botón de reinicio vuelve a crear los ejemplos. La clave de este modo se genera al azar para cada sesión y sus credenciales internas nunca se usan en modo persistente.

## Publicar en Streamlit Community Cloud

1. En [share.streamlit.io](https://share.streamlit.io) pulsa **Create app** y elige este repositorio, la rama `main` y el archivo principal `app.py`.
2. En **Advanced settings** selecciona Python 3.12.
3. En **Secrets** pega el contenido de `.streamlit/secrets.toml.example` con tus valores. Para una demostración basta con `RENAL_MODE = "demo"`.
4. Pulsa **Deploy**. La dirección `https://<nombre>.streamlit.app` es la que debes usar para generar el QR.

> En Community Cloud el disco no es persistente: en modo `clinical` la base SQLite se pierde al reiniciarse la app. Para datos reales usa un servidor con volumen persistente.

## Activar almacenamiento persistente

Configura estas variables de entorno o las mismas entradas en `.streamlit/secrets.toml`. Hay un archivo de ejemplo; no guardes claves en Git.

| Variable | Uso |
| --- | --- |
| `RENAL_MODE` | `clinical` para habilitar autenticación y almacenamiento persistente. El nombre del modo no implica validación clínica. |
| `RENAL_DB_PATH` | Ruta del archivo SQLite; por defecto `data/renal.sqlite`. En hosting debe estar en un volumen persistente. |
| `RENAL_DB_KEY` | Clave Fernet que cifra los campos de pacientes y evaluaciones. Es obligatoria y debe mantenerse estable. |
| `RENAL_SETUP_TOKEN` | Token privado para crear la primera cuenta administradora desde la pantalla inicial. Se usa únicamente mientras no existan usuarios. |
| `RENAL_PUBLIC_URL` | Opcional. Dirección HTTPS definitiva del sitio para precargar el generador de QR. No puede ser una dirección local. |
| `RENAL_SMTP_HOST`, `RENAL_SMTP_PORT`, `RENAL_SMTP_USER`, `RENAL_SMTP_PASSWORD`, `RENAL_SMTP_FROM` | Opcionales. Permiten que **Enviar a mi correo** mande el resultado público directamente. Sin ellos, el botón abre la aplicación de correo de la persona con el resultado ya escrito. La dirección no se guarda y cada sesión puede enviar hasta tres correos. |

Genera los valores de forma local y guárdalos en el gestor de secretos del servidor:

```sh
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Tras configurar las variables, inicia la aplicación, pulsa **Acceso profesional**, introduce el token en la pantalla de configuración y crea un usuario administrador con una contraseña de al menos 12 caracteres. Elimina `RENAL_SETUP_TOKEN` del servidor tras completar el alta. No hay usuario ni contraseña predeterminados para este modo.

Los administradores crean/desactivan cuentas y descargan respaldos; los clínicos trabajan con sus propios expedientes. Un administrador tampoco puede abrir desde la interfaz los expedientes de otras cuentas. El respaldo incluye toda la base, con los datos de pacientes cifrados: su descarga está limitada a administradores. El acceso compartido a un expediente entre profesionales no está implementado.

Las contraseñas se almacenan mediante PBKDF2-SHA256 con sal individual y 600.000 iteraciones. Cinco intentos fallidos bloquean temporalmente el usuario durante diez minutos. La sesión requiere volver a iniciar sesión tras treinta minutos sin interacción. La desactivación de una cuenta se comprueba en cada interacción. Publica únicamente mediante HTTPS y mantén la clave fuera del archivo SQLite.

El cifrado protege los campos de pacientes y evaluaciones. Los identificadores aleatorios, fechas, cuentas, hashes de contraseña y metadatos de auditoría permanecen en SQLite para operar el sistema. No es cifrado completo de disco. Si pierdes la clave no podrás recuperar los campos cifrados; la aplicación rechaza una clave que no corresponda a la base existente.

## Respaldo y restauración

1. En **Administración → Preparar respaldo**, descarga una copia consistente de SQLite. Repite periódicamente según tu operación; no hay un servicio automático de respaldos incluido.
2. Custodia ese archivo y la clave `RENAL_DB_KEY` por separado.
3. Para restaurar, detén todas las instancias de la aplicación y conserva una copia del almacenamiento actual para poder revertir.
4. Utiliza una ruta nueva, copia allí el respaldo y apunta `RENAL_DB_PATH` a ese archivo. Usa la misma clave que protegía el respaldo. Usar una ruta nueva evita reutilizar archivos auxiliares WAL de una base anterior.
5. Reinicia e inicia sesión con una cuenta contenida en el respaldo. Comprueba los expedientes antes de reanudar la operación.

Usa una sola instancia de aplicación para este almacenamiento SQLite. Si necesitas múltiples réplicas o trabajo compartido entre profesionales, migra la persistencia a un servicio de base de datos y define los permisos de colaboración antes de habilitarlo. Un sistema de archivos efímero de hosting no conserva SQLite entre despliegues.

## Método y alcance académico

Versión del método: `cohorte-1.0`. La versión 2.0 corresponde a la aplicación, no a una nueva validación científica.

- TyG = ln(triglicéridos × glucosa / 2), con ambas concentraciones en mg/dL.
- La fórmula utilizada en la calculadora pública está descrita, entre otras publicaciones, en [el estudio de cohorte indexado como PMID 31687367](https://pubmed.ncbi.nlm.nih.gov/31687367/). Esta referencia describe el cálculo; no valida los cortes de la cohorte renal del prototipo.
- IMC = peso postdiálisis (kg) / talla (m)².
- Cortes conservados del prototipo: TyG **8.8** y creatinina prediálisis **8.5 mg/dL**.
- La igualdad pertenece al grupo superior. La clasificación utiliza valores completos; los reportes indican los cortes y la versión guardados en cada evaluación.
- Los nombres de los patrones describen la posición frente a los cortes; no constituyen diagnósticos ni implican ausencia de riesgo.

**Pendiente del equipo responsable del estudio:** referencia bibliográfica, tamaño y descripción de la cohorte, criterios de inclusión, fechas y validación externa. El repositorio original no aporta esos datos. No se ha inventado una cita ni se ha declarado validez clínica de la herramienta. La sección Metodología y los PDF hacen explícita esta limitación. Antes de utilizarla para decisiones clínicas se requiere revisión del equipo responsable.

Editar una evaluación recalcula con el método actual y aumenta su revisión; los cambios de identificación del paciente no alteran las identificaciones guardadas en reportes anteriores. El registro de actividad guarda autor, tipo de acción, recurso y fecha; no conserva una copia de todas las revisiones previas de los valores.

## Pruebas

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

La suite cubre fórmulas y límites, valores ausentes/no finitos, duplicados, separación entre cuentas, persistencia y cifrado, autenticación, revisión de ediciones, archivo/restauración, respaldos, contenido de exportaciones y recorridos de Streamlit. También comprueba la entrada pública sin base de datos, el aislamiento entre sesiones, el reinicio y la validación del formulario público, el rechazo de enlaces QR locales y la decodificación del QR generado. GitHub Actions ejecuta la suite al hacer push o abrir una propuesta de cambios.

## Estructura

```text
app.py                  Interfaz y navegación
renal/domain.py         Validaciones, fórmulas y método versionado
renal/storage.py        Persistencia, autorización y auditoría
renal/auth.py           Credenciales
renal/reports.py        Exportaciones PDF y CSV
renal/demo.py           Datos ficticios aislados
renal/public_view.py    Calculadora anónima y pantalla de compartir
renal/sharing.py        Enlace público y generación local del QR
renal/branding.py       Logo compartido por ambas vistas
renal/mailer.py         Envío opcional del resultado por correo
assets/theme.css        Diseño adaptable (claro y oscuro)
assets/logo.svg|png     Logo de la aplicación
tests/                  Pruebas de servicios e interfaz
```
