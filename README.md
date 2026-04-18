# Silo Labs

AI firmware generator for the Raspberry Pi Pico (RP2040). Describe what you want in natural
language; a multi-agent LangGraph pipeline emits pin assignments, clock configuration,
register writes, wiring, C code, and a Wokwi simulation — live, streamed over SSE.

## Canonical demo

> Read a BME280 over I2C and display the readings on an SSD1306 OLED.

## Architecture

- **Backend** (`backend/`): FastAPI + LangGraph + Claude (Sonnet 4.6 heavy, Haiku 4.5 light).
  Knowledge graph built from the RP2040 CMSIS SVD for authoritative register addresses.
  arm-none-eabi-gcc + pico-sdk compile; Wokwi CLI (or fixture) simulates.
- **Frontend** (`frontend/`): Next.js 15 + React 19 + Tailwind 4. Monaco, xterm.js,
  @xyflow/react, Three.js, Framer Motion. Zustand store driven by typed SSE events.

## Run locally

```bash
docker compose up
# backend:  http://localhost:8000
# frontend: http://localhost:3000
```

Environment (`backend/.env`):

```
ANTHROPIC_API_KEY=...
WOKWI_CLI_TOKEN=...   # optional; fixture used if absent
```

## Tests

```bash
cd backend && pytest tests/
cd frontend && npx tsc --noEmit
```

## Deploy

- Backend: `modal deploy backend/modal_app.py`
- Frontend: `vercel --prod` from `frontend/`
