/*
  esp32_probe.ino — Firmware ESP32 : descente/remontée de la sonde (NEMA).

  La Raspberry Pi (Agribotics) pilote ce moteur pas-à-pas via USB série.
  Protocole texte à accusé de réception (la Pi BLOQUE jusqu'à "OK") :

      Pi → ESP32 : "DOWN\n"   → descend la sonde puis répond "OK\n"
      Pi → ESP32 : "UP\n"     → remonte la sonde puis répond "OK\n"
      Pi → ESP32 : "PING\n"   → "OK\n"  (test de présence)
      Erreur      :            "ERR ...\n"

  Côté Pi : raspberry_pi/robot/esp32_probe.py (Esp32ProbeController), activé par
  la variable .env  PROBE_SERIAL_PORT=/dev/serial/by-id/...  (cf. CLAUDE.md).

  ----------------------------------------------------------------------------
  CÂBLAGE (driver pas-à-pas type A4988 / DRV8825 / TMC2208) — À ADAPTER :
    ESP32 GPIO26 → STEP du driver
    ESP32 GPIO27 → DIR  du driver
    ESP32 GPIO25 → EN   du driver (enable, actif LOW sur A4988/DRV8825)
    GND ESP32    ↔ GND driver ↔ GND alim moteur (MASSE COMMUNE indispensable)
    Le NEMA est alimenté par une alim dédiée (ex. 12 V) via le driver, PAS par
    l'ESP32. Régler le courant (Vref) du driver pour ton NEMA.
  Brancher l'ESP32 sur un port USB de la Pi (il apparaît en /dev/ttyACM0 ou
  /dev/ttyUSB0 ; repérer le chemin stable via : ls -l /dev/serial/by-id/).
  ----------------------------------------------------------------------------
*/

// --- Broches (adapter à ton câblage) ---------------------------------------
const int PIN_STEP = 26;
const int PIN_DIR  = 27;
const int PIN_EN   = 25;            // enable driver (LOW = actif)

// --- Paramètres de mouvement (À CALIBRER au banc) --------------------------
const long STEPS_TRAVEL  = 2000;   // nombre de pas pour la course complète de la sonde
const int  STEP_DELAY_US = 600;    // demi-période d'un pas (µs) : + petit = + rapide
const bool DIR_DOWN_LEVEL = HIGH;  // niveau DIR pour DESCENDRE (inverser si à l'envers)
const bool HOLD_TORQUE    = true;  // true = garde le driver actif (maintient la position)

// --- Sécurité : empêcher deux descentes consécutives sans remontée ---------
bool probeIsDown = false;

void runSteps(bool down) {
  digitalWrite(PIN_EN, LOW);                          // active le driver
  digitalWrite(PIN_DIR, down ? DIR_DOWN_LEVEL : !DIR_DOWN_LEVEL);
  delayMicroseconds(50);                              // temps d'établissement DIR
  for (long i = 0; i < STEPS_TRAVEL; i++) {
    digitalWrite(PIN_STEP, HIGH);
    delayMicroseconds(STEP_DELAY_US);
    digitalWrite(PIN_STEP, LOW);
    delayMicroseconds(STEP_DELAY_US);
  }
  if (!HOLD_TORQUE) digitalWrite(PIN_EN, HIGH);       // relâche le couple si demandé
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_STEP, OUTPUT);
  pinMode(PIN_DIR, OUTPUT);
  pinMode(PIN_EN, OUTPUT);
  digitalWrite(PIN_STEP, LOW);
  digitalWrite(PIN_EN, HIGH);                         // driver inactif au repos
  Serial.println("READY");                            // signal de boot (la Pi l'ignore)
}

void loop() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  cmd.toUpperCase();
  if (cmd.length() == 0) return;

  if (cmd == "PING") {
    Serial.println("OK");
  } else if (cmd == "DOWN") {
    if (probeIsDown) { Serial.println("OK"); return; } // déjà en bas (idempotent)
    runSteps(true);
    probeIsDown = true;
    Serial.println("OK");
  } else if (cmd == "UP") {
    if (!probeIsDown) { Serial.println("OK"); return; }
    runSteps(false);
    probeIsDown = false;
    Serial.println("OK");
  } else {
    Serial.print("ERR unknown:");
    Serial.println(cmd);
  }
}
