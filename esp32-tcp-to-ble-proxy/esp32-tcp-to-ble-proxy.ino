#include <WiFi.h>
#include <NimBLEDevice.h>
#include "secrets.h"

#define LED_BUILTIN 8

// --- Configuration ---
const char* ssid = WIFI_SSID;
const char* password = WIFI_PASSWORD;
const int port = 8000;

// Replace with your specific BLE device details
const char* targetMacAddress = BLE_MAC_ADDRESS; // Target BT Address
const char* serviceUUID      = BLE_SERVICE_UUID; 
const char* charUUID         = BLE_CHARACTERISTIC_UUID;

// Control commands
const uint8_t STATUS_CMD[] = {0x10, 0x04, 0x01};
const int maxRetries = 5;

WiFiServer server(port);
NimBLEClient*  pClient  = nullptr;
NimBLERemoteCharacteristic* pRemoteChar = nullptr;
int retries = 0;

// Function to connect to your specific BLE device
bool connectToBLEDevice() {
  NimBLEAddress addr(targetMacAddress, BLE_ADDR_PUBLIC);
  pClient = NimBLEDevice::createClient();
  digitalWrite(LED_BUILTIN, HIGH); //HIGH actually turns off the LED

  if (pClient->connect(addr)) {
    NimBLERemoteService* pService = pClient->getService(serviceUUID);
    if (pService) {
      pRemoteChar = pService->getCharacteristic(charUUID);
      if (pRemoteChar && pRemoteChar->canWrite()) {
        Serial.println("Connected to BLE Device and Characteristic found!");
        server.begin();
        digitalWrite(LED_BUILTIN, LOW); //LOW actually lights up the LED
        retries = 0;
        return true;
      }
    }
  }
  Serial.print("BLE Connection failed. Retrying...");
  Serial.println(retries);
  server.end();
  NimBLEDevice::deleteClient(pClient);
  retries += 1;
  if(retries >= maxRetries){
    Serial.println("Could not connect to printer, entering deep sleep...");
    delay(100);
    esp_deep_sleep_start();
  }
  return false;
}

void setup() {
  Serial.begin(9600);
  // Status LED
  pinMode(LED_BUILTIN, OUTPUT);
  delay(500);
  digitalWrite(LED_BUILTIN, HIGH); //HIGH actually turns off the LED

  // 1. WiFi Setup
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nWiFi Connected. IP: " + WiFi.localIP().toString());

  // 2. BLE Setup
  NimBLEDevice::init("ESP32C3_Bridge_Client");
  NimBLEDevice::setMTU(517);
  connectToBLEDevice();
}

void loop() {
  // Auto-reconnect BLE if connection drops
  if (!pClient->isConnected()) {
    connectToBLEDevice();
    delay(5000);
    return;
  }

  WiFiClient tcpClient = server.available();
  if (tcpClient) {
    while (tcpClient.connected() && pClient->isConnected()) {
      if (tcpClient.available()) {
        uint8_t buffer[1024]; 
        int bytesRead = tcpClient.read(buffer, sizeof(buffer));
        Serial.print("Bytes read from client: ");
        Serial.println(bytesRead);

        // Check for control requests
        if(memmem(buffer, bytesRead, STATUS_CMD, sizeof(STATUS_CMD))){
          Serial.println("Sending Printer OK status");
          tcpClient.write((uint8_t)1);
        }

        // Send to printer
        int mtuSize = pClient->getMTU() - 3;
        int sentBytes = 0;

        while (sentBytes < bytesRead) {
          int chunkSize = min(mtuSize, bytesRead - sentBytes);
           // Forward chunk to the printer's TX characteristic
          pRemoteChar->writeValue(&buffer[sentBytes], chunkSize, true);
          sentBytes += chunkSize;
          Serial.print("Bytes forwarded to BLE: ");
          Serial.println(chunkSize);
          delay(10); 
        }
      }
    }
    tcpClient.stop();
  }
}
