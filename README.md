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

Use un servicio **Compose** (no App). EasyPanel gestiona dominio, HTTPS y variables; el YAML solo define contenedores, build, healthchecks y el volumen.

1. En el proyecto, **New Service → Compose**.
2. Fuente **Git**: repositorio, rama, **Build Path** `/` y **Docker Compose File** `docker-compose.yml`.
3. En **Environment**, pegue `.env.example`, cambie `API_KEY` y `PUBLIC_BASE_URL`, y active **Create .env file**.
4. Despliegue. EasyPanel ejecuta `docker compose up --build -d`.
5. Añada un dominio hacia el servicio interno `api` y el puerto de contenedor `8000` (HTTP interno). No publique `ports` en el Compose ni apunte el dominio al `worker`.
6. Ponga `PUBLIC_BASE_URL` con la URL HTTPS pública de ese dominio y vuelva a desplegar.

Los datos (cola SQLite y MP4) viven en el volumen nombrado `capservice-data` montado en `/data`.

El primer build descarga Chromium y el modelo Whisper; puede tardar varios minutos.

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
