# Habilidad de generación de imágenes

[English](README.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [Español](README.es.md)

[![validate](https://github.com/hjm-al/image-generation/actions/workflows/validate.yml/badge.svg)](https://github.com/hjm-al/image-generation/actions/workflows/validate.yml)

Una habilidad independiente de Codex para generar y editar imágenes mediante APIs de Images compatibles con OpenAI. Gestiona la preparación de prompts, la carga segura de credenciales, la normalización de respuestas, la escritura de archivos locales, la detección de formatos, las dimensiones y los metadatos.

## Funciones

- Genera imágenes con `POST /images/generations`.
- Edita imágenes con multipart oficial o JSON al estilo de los servicios de retransmisión.
- Construye la dirección artística a partir de un contrato de estilo por capas, en lugar de adjetivos vagos.
- Etiqueta varias referencias con roles ordenados como `Image 1`, `Image 2`, etc.
- Registra hashes, formatos, dimensiones y presencia de canal alfa de las imágenes de origen.
- Valida el tamaño de las máscaras, la semántica del canal alfa PNG, los píxeles transparentes y las dimensiones.
- Distingue canales alfa PNG totalmente opacos, totalmente transparentes, parcialmente transparentes e imposibles de analizar.
- Rechaza `background=transparent` con salida JPEG antes de realizar la solicitud.
- Acepta `b64_json`, `b64`, `url` y campos de imagen anidados habituales.
- Publica cada conjunto de imágenes y su archivo JSON sidecar juntos, sin sobrescribir archivos existentes.
- Detecta las firmas PNG, JPEG, WebP y GIF y registra las dimensiones reales.
- Conserva las imágenes válidas cuando otras candidatas de la misma respuesta están malformadas.
- Prevalida trabajos JSONL, rechaza conflictos de rutas y actualiza un manifiesto de recuperación después de cada trabajo.
- Escribe un archivo JSON sidecar con los detalles de la solicitud, los hashes de archivos, las advertencias de entrega y la forma de la respuesta.
- Realiza un seguimiento de las revisiones reutilizables de prompts mediante eventos de calidad codificados, hashes de prompts y comprobaciones de regresión.
- Ejecuta pruebas sin conexión y sin realizar solicitudes de red.

## Requisitos

- Python 3.10 o posterior.
- No se necesitan paquetes de terceros; los asistentes, el ejecutor por lotes, el registro de calidad y las pruebas usan solo la biblioteca estándar de Python.
- Solo las solicitudes facturables de generación o edición requieren acceso a la red y credenciales del proveedor.

## Coste y comportamiento de red

- `--dry-run` muestra la solicitud prevista sin leer la clave de API, usar la red ni generar costes.
- La suite de pruebas y todos los comandos de `quality_log.py` funcionan sin conexión.
- `generate`, `edit` y un lote sin `--dry-run` llaman al proveedor configurado y pueden generar costes.
- Cada elemento del lote realiza una solicitud a la API; `n` es el número de imágenes solicitadas dentro de esa solicitud. El asistente nunca reintenta ni cambia de modelo automáticamente.

## Instalación

Clona el repositorio y después copia su contenido al directorio de habilidades de Codex:

```powershell
git clone https://github.com/hjm-al/image-generation.git
$source = Join-Path $PWD "image-generation"
$target = Join-Path $HOME ".codex\skills\image-generation"
New-Item -ItemType Directory -Force $target | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force
```

En Codex, invócala explícitamente con `$image-generation`; se trata de una referencia a la habilidad, no de una expansión de variables de PowerShell. Codex también puede seleccionarla a partir de su descripción.

## Actualización o eliminación

Actualiza el clon y la habilidad instalada:

```powershell
git -C .\image-generation pull --ff-only
$source = Join-Path $PWD "image-generation"
$target = Join-Path $HOME ".codex\skills\image-generation"
New-Item -ItemType Directory -Force $target | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force
```

Esto copia los archivos actuales, pero no elimina los archivos retirados upstream. Para una instalación limpia, revisa y guarda los cambios locales antes de reemplazar el directorio instalado. Para eliminar la habilidad:

```powershell
$target = Join-Path $HOME ".codex\skills\image-generation"
Remove-Item -LiteralPath $target -Recurse -Force
```

## Configuración

Establece la clave solo en el entorno del proceso actual:

```powershell
$env:IMAGE_API_KEY = "your-key"
$env:IMAGE_API_BASE_URL = "https://api.openai.com/v1"
$env:IMAGE_MODEL = "gpt-image-1"
```

Variables de entorno compatibles:

| Variable | Obligatoria | Finalidad |
|---|---:|---|
| `IMAGE_API_KEY` | Sí | Token Bearer, o la variable indicada por `--api-key-env` |
| `IMAGE_API_BASE_URL` | No | Raíz de la API; valor predeterminado `https://api.openai.com/v1` |
| `IMAGE_MODEL` | No | Modelo predeterminado; valor de reserva `gpt-image-1` |

Elimina la clave después de usarla:

```powershell
Remove-Item Env:IMAGE_API_KEY -ErrorAction SilentlyContinue
```

## Generación

```powershell
python .\scripts\image_api.py generate `
  --prompt "A quiet editorial photo of a ceramic cup on a windowsill, overcast daylight, no text or watermark" `
  --output .\outputs\cup.png `
  --size 1024x1024 `
  --quality high
```

Previsualiza la solicitud sin una clave ni una llamada de red:

```powershell
python .\scripts\image_api.py generate `
  --prompt "A minimal studio portrait with a warm gray background" `
  --output .\outputs\portrait.png `
  --dry-run
```

## Dirección artística

Cuando el estilo sea central para el encargo, define un medio principal y las propiedades observables que controlan los bordes, el renderizado, la superficie, la paleta, la luz, la composición y los sistemas gráficos opcionales. Para el trabajo de imagen a imagen, mantén separado el contrato de conservación del contrato de cambio de estilo.

La guía incluye direcciones fotográficas, de ilustración, impresión, cartel, interfaz, 3D, técnicas y de estilo mixto, además de alternativas para palabras de estilo vagas. Consulta [references/art-directions.md](references/art-directions.md).

## Edición

Transporte multipart oficial:

```powershell
python .\scripts\image_api.py edit `
  --image .\inputs\source.png `
  --image-role "product and framing reference" `
  --prompt "Keep the subject unchanged; replace the background with pale sand-colored plaster." `
  --output .\outputs\edited.png
```

Transporte JSON utilizado por algunos servicios de retransmisión compatibles:

```powershell
python .\scripts\image_api.py edit `
  --image .\inputs\source.png `
  --image-role "product and framing reference" `
  --prompt "Keep the subject unchanged; replace the background with pale sand-colored plaster." `
  --output .\outputs\edited.png `
  --transport json
```

Repite `--image` y `--image-role` juntos para usar varias referencias. El número de roles debe coincidir con el número de imágenes. Las máscaras multipart deben ser de 4 MB o menos, coincidir con las dimensiones de la primera imagen de origen, contener un canal alfa real e incluir al menos un píxel transparente. Los metadatos PNG `tRNS` se informan por separado y no se tratan como un canal alfa.

## Procesamiento por lotes

Crea un archivo JSONL con un trabajo por línea. Las rutas relativas se resuelven desde el directorio del archivo JSONL:

```jsonl
{"id":"hero","prompt":"Editorial product photo of a steel kettle, side light, no text","output":"outputs/hero.png","output_format":"png","size":"1024x1536"}
{"id":"room-edit","operation":"edit","prompt":"Keep the product; replace the room with warm plaster","images":["inputs/source.png"],"image_roles":["product and framing reference"],"output":"outputs/room-edit.png","output_format":"png"}
```

Prevalida sin leer la clave de API ni realizar una llamada de red:

```powershell
python .\scripts\image_batch.py .\jobs.jsonl --dry-run
```

Después de revisar el número de trabajos y el plan de solicitudes:

```powershell
python .\scripts\image_batch.py .\jobs.jsonl --manifest .\outputs\manifest.json
```

Los trabajos por lotes se ejecutan de forma secuencial y nunca reintentan ni cambian de modelo automáticamente. Un trabajo fallido no detiene los siguientes. El manifiesto se actualiza de forma atómica después de cada elemento. Consulta [references/batch-jsonl.md](references/batch-jsonl.md) para ver el contrato completo de campos.

## Ciclo de calidad de prompts

La habilidad puede mantener un registro de revisión local y de solo añadido para prompts reutilizables. Los archivos JSON sidecar de la API siguen siendo la fuente de verdad sobre las solicitudes y la entrega; los eventos de calidad capturan la revisión subjetiva. Cada evento exitoso registra características positivas y cualquier defecto observable de `C1` a `C9`. Los fallos de infraestructura usan `C10` y nunca se convierten en evidencia para editar prompts.

Genera un hash normalizado del prompt:

```powershell
python .\scripts\quality_log.py hash --prompt .\prompts\theme.txt
```

Valida eventos y versiones registradas de prompts:

```powershell
python .\scripts\quality_log.py validate `
  --events .\quality\events.jsonl `
  --versions .\quality\prompt-versions.json `
  --root .
```

Resume los defectos y comprueba si toca realizar una revisión:

```powershell
python .\scripts\quality_log.py digest --events .\quality\events.jsonl
python .\scripts\quality_log.py due `
  --events .\quality\events.jsonl `
  --versions .\quality\prompt-versions.json `
  --ledger .\quality\reviews.json
```

El prompt predeterminado solo cambia después de que se repita la evidencia: al menos 3 apariciones del mismo defecto en un tema, o 4 apariciones en al menos 2 temas para cambiar la plantilla compartida. Consulta [references/quality-loop.md](references/quality-loop.md) para ver el esquema de eventos, el registro de versiones, las reglas de comparación controlada y el libro de revisiones.

Todos los comandos de registro de calidad funcionan sin conexión. Cualquier generación de imágenes adicional utilizada para comparar versiones de prompts es facturable y requiere indicar el número de solicitudes y obtener confirmación.

## Contrato de salida

Para `outputs\result.png`, el asistente también escribe `outputs\result.png.json`. El sidecar incluye:

- endpoint y modelo;
- prompt exacto;
- opciones de solicitud sin secretos;
- rutas, tamaños en bytes, hashes SHA-256, formatos y dimensiones de las imágenes de entrada;
- rutas, tamaños en bytes, hashes SHA-256, formatos, detección de alfa y dimensiones de las imágenes finales;
- estado alfa (`opaque`, `transparent`, `partial`, `unknown`, `chunk_only` o `none`);
- recuentos devueltos, publicados y solicitados;
- `delivery_ready`, `warnings` y `errors` por candidata;
- nombres de campos de la respuesta y marcas de tiempo.

Si el proveedor devuelve un formato diferente, el asistente cambia la extensión de salida al formato detectado en lugar de escribir bytes con una etiqueta incorrecta.

`delivery_ready` es más estricto que el éxito del proveedor: pasa a false cuando falla cualquier candidata, el número de imágenes difiere de `n`, no se cumple un tamaño fijo solicitado, un fondo transparente no tiene canal alfa, el canal alfa es totalmente opaco o no se puede verificar la transparencia. Los archivos de imagen y su sidecar se preparan primero y se publican como un conjunto; si falla el sidecar, no queda una entrega parcial de imágenes.

## Notas de compatibilidad

- El endpoint oficial de edición de OpenAI usa datos de formulario multipart.
- Algunos servicios de retransmisión implementan ediciones JSON con `images[].image_url`; usa `--transport json` solo con esos servicios.
- Las URL de imágenes firmadas se descargan sin la clave de API. Si un proveedor exige descargas autenticadas, solicita una respuesta base64.
- Los nombres de modelos, tamaños, valores de calidad y formatos de respuesta específicos de cada proveedor son responsabilidad del proveedor.

## Desarrollo y verificación

```powershell
python -m unittest discover -s tests -v
python -m py_compile .\scripts\image_api.py .\scripts\image_batch.py .\scripts\quality_log.py
```

Las pruebas no llaman a servicios externos ni generan costes. CI comprueba Python 3.10 y 3.12. Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para el desarrollo y las Pull Requests.

## Contribuciones

Usa las plantillas de Issue y Pull Request, no incluyas comprobaciones reales del proveedor en las pruebas automatizadas y ejecuta los comandos de verificación sin conexión antes de abrir una Pull Request. La participación se rige por [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Seguridad

- No confirmes `.env`, claves de API, imágenes de referencia privadas ni trabajos generados para clientes.
- No pases secretos con `--api-key`; usa variables de entorno.
- Revisa el prompt antes de enviar material confidencial a una API de terceros.
- Informa de vulnerabilidades según [SECURITY.md](SECURITY.md), no en una Issue pública.

## Licencia

MIT. Las fuentes de diseño upstream revisadas y las revisiones exactas se enumeran en [ATTRIBUTIONS.md](ATTRIBUTIONS.md).
