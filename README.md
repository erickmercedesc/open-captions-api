# CapService

Microservicio HTTP que recibe la URL de un video, genera subtítulos animados con [pycaps](https://github.com/francozanardi/pycaps) y notifica el resultado por webhook.

La API responde de inmediato con HTTP 202. Un worker independiente procesa la cola persistente (SQLite), así que un reinicio del proceso HTTP no pierde trabajos `queued`.

## API

### `POST /generate-captions`

Autenticación: `X-API-Key` o `Authorization: Bearer <API_KEY>`.

```json
{
  "video_url": "https://cdn.example.com/clip.mp4",
  "webhook_url": "https://hooks.example.com/captions",
  "template": "minimalist"
}
```

`template` es opcional. Si se omite, se usa `default` (plantilla oficial de pycaps).

Respuesta `202 Accepted`:

```json
{
  "job_id": "4d2c1a0e-8f1b-4c3a-9e2d-1a2b3c4d5e6f",
  "status": "queued"
}
```

Plantillas builtin de pycaps 0.3.0: `classic`, `default`, `explosive`, `fast`, `hype`, `line-focus`, `minimalist`, `model`, `neo-minimal`, `retro-gaming`, `vibrant`, `word-focus`.

### Webhook

Éxito:

```json
{
  "job_id": "...",
  "status": "completed",
  "output_url": "https://caps.example.com/outputs/<job-id>-<token>.mp4"
}
```

Error:

```json
{
  "job_id": "...",
  "status": "failed",
  "error": "The video exceeds the maximum allowed duration."
}
```

Los fallos del webhook se reintentan con espera progresiva. El video no se vuelve a procesar.

### Otros

- `GET /health` — sin autenticación
- `GET /jobs/{job_id}` — autenticado
- `GET /outputs/{job-id}-{token}.mp4` — token opaco, sin listar el disco

## Despliegue en EasyPanel

1. Cree un proyecto a partir de este repositorio.
2. Use el `Dockerfile` de la raíz.
3. Configure el comando:
   - Recomendado con dos servicios: `api` y `worker` (ver `docker-compose.yml`).
   - En un solo contenedor EasyPanel: comando `all`.
4. Monte un volumen persistente en `/data`.
5. Defina las variables de `.env.example`. `API_KEY` y `PUBLIC_BASE_URL` son obligatorias.
6. Publique el puerto `8000` y ponga `PUBLIC_BASE_URL` con el dominio HTTPS público.

El primer arranque puede descargar el modelo Whisper si no quedó cacheado en la imagen.

## Desarrollo local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
copy .env.example .env
python -m capservice api
python -m capservice worker
```

Pruebas:

```bash
pytest
```

La prueba de integración usa un clip corto en español (`tests/fixtures/spanish.mp4`) y la API real de pycaps 0.3.0 (`TemplateLoader`, `with_whisper_config(backend=WhisperBackend.FASTER)`, `pipeline.run()`). Requiere FFmpeg, Playwright Chromium y el modelo Whisper:

```bash
set RUN_PYCAPS_INTEGRATION=1
pytest -m integration
```
