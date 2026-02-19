<p align="center">
    <picture>
        <img width="256" height="256" alt="printbot" src="https://github.com/user-attachments/assets/00ff609c-27dd-4a9d-8b27-ad013f3a7364" />
    </picture>
</p>

## WhatsApp bot to handover print jobs to thermal and normal printers

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

### Example

<picture>
<img width="300" alt="whatsapp" src="https://github.com/user-attachments/assets/ba596156-2631-47d8-bbce-a830bc8fb22b" />
<img width="350" alt="thermal printer" src="https://github.com/user-attachments/assets/9e3e0fb9-988e-4998-80c2-9baab6600f48" />
</picture>

---

## ESP32 TCP to BLE Proxy

The thermal printer BLE range might be too small depending on the server location.

In order to mitigate this issue I embedded an ESP32 C3 on the thermal printer. This device will connect to the WIFI and to the thermal printer via BLE (actually any BLE device should work as well).

The ESP32 will then listen on port TCP 8000. Any data sent to the tcp server will be forwarded to the BLE device.

If the BLE connection is lost, the ESP32 will also stop the TCP Server. If the connection to the BLE device is not possible e.g.: device is off, the ESP32 will go automatically to deep sleep after a few retries.

**Required variables:**

Create a file named `secrets.h` in the `esp32-tcp-to-ble-proxy` folder (use `secrets.h.example` as reference)

| Variable | Description |
|----------|-------------|
| `WIFI_SSID` | Your WIFI SSID |
| `WIFI_PASSWORD` | Your WIFI Password |
| `BLE_MAC_ADDRESS` | The BLE MAC address of your device |
| `BLE_SERVICE_UUID` | The Service UUID Address of your device |
| `BLE_CHARACTERISTIC_UUID` | The Characteristic UUID of your device  |


> Remember to enable `USB CDC on Boot` if you are unable to see serial output.
