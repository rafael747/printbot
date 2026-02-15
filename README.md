# Printbot

WhatsApp bot handover print jobs to thermal and normal printers

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Quickstart

### 1. Install dependencies with uv

From the project root:

```bash
uv sync
```

This installs all dependencies from `pyproject.toml` into a virtual environment. Use `uv run` to run commands in that environment.

### 2. Create an `.env` file

Create a file named `.env` in the project root (use .env.example as reference)

**Required variables:**

| Variable | Description |
|----------|-------------|
| `WA_PHONE_ID` | WhatsApp Business API phone number ID |
| `WA_TOKEN` | WhatsApp Business API access token |
| `WA_VERIFY_TOKEN` | Random string used to verify the webhook with Meta |
| `PRINTER_ADDR` | Printer IP (network) or Bluetooth address |
| `PRINTER_PORT` | Printer port (network or Bluetooth) |
| `CUPS_PRINTER_NAME` | Name of the CUPS printer for scanning/printing |
| `WHITELISTED_NUMBERS` | Comma-separated list of WhatsApp numbers allowed to use the bot |

### 3. Run the project

Start the FastAPI app in development mode:

```bash
uv run fastapi dev
```

The server will start (default: http://127.0.0.1:8000).

**Note:** For WhatsApp webhooks to work, your server must be reachable from the internet (e.g. via ngrok or a deployed host). Point your WhatsApp app webhook URL to `https://your-host/printbot`.
