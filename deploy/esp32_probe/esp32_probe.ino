/*
  esp32_probe.ino — Firmware ESP32 : descente/remontée de la sonde (NEMA),
  PILOTÉ PAR LA RASPBERRY PI via USB série.

  Basé sur le sketch de test validé par Marius (rotation NEMA par durée), mais
  rendu COMMANDABLE : au lieu de bouger tout seul dans setup(), l'ESP32 attend
  des ordres sur le port série et confirme la fin RÉELLE du mouvement.

      Pi → ESP32 : "DOWN\n"   → descend la sonde (TRAVEL_MS) puis répond "OK\n"
      Pi → ESP32 : "UP\n"     → remonte la sonde (TRAVEL_MS) puis répond "OK\n"
      Pi → ESP32 : "PING\n"   → "OK\n"  (test de présence)
      Pi → ESP32 : "OFF\n"    → coupe le driver si EN_PIN est câblé
      Erreur      :            "ERR ...\n"

  Côté Pi : raspberry_pi/robot/esp32_probe.py (Esp32ProbeController), activé par
  PROBE_SERIAL_PORT dans le .env. La Pi BLOQUE jusqu'à "OK" (timeout
  PROBE_SERIAL_TIMEOUT, qui DOIT être > TRAVEL_MS).

  ----------------------------------------------------------------------------
  CÂBLAGE (inchangé par rapport à ton test) :
    ESP32 GPIO26 → STEP du driver
    ESP32 GPIO27 → DIR  du driver
    EN du driver : optionnel. Si EN_PIN = -1, laisser le driver activé en
                   matériel (EN à GND / jumper enable). Pour économiser
                   l'énergie après la remontée, câbler EN sur une GPIO ESP32
                   et mettre ce numéro dans EN_PIN (LOW = activé, HIGH = off).
    GND ESP32 ↔ GND driver ↔ GND alim moteur (MASSE COMMUNE indispensable).
    NEMA alimenté par une alim dédiée via le driver (PAS par l'ESP32).
  Brancher l'ESP32 en USB sur la Pi (repérer le port : ls -l /dev/serial/by-id/).
  ----------------------------------------------------------------------------
*/

// --- Broches (identiques à ton sketch) -------------------------------------
#define STEP_PIN 26
#define DIR_PIN  27
#define EN_PIN   33            // GPIO EN driver (LOW = activé, HIGH = off)

// --- Cadence des pas (identique à ton sketch : 200 pas/tour, "rpm" 100) -----
const int steps_per_rev   = 200;                               // NEMA 17 (1.8°/pas)
const int rpm             = 100;
const int pulse_delay_us  = 60000000 / (steps_per_rev * rpm);  // = 3000 µs

// --- Course de la sonde : DURÉE de rotation (à CALIBRER) --------------------
// Ton test faisait 10 000 ms ; pour la sonde, règle ce temps sur la course
// réelle (descente complète). PROBE_SERIAL_TIMEOUT (.env Pi) doit être > ce temps.
const unsigned long TRAVEL_MS = 10000;

// Niveau DIR pour DESCENDRE (ton 1er sens = HIGH). Inverser si la sonde monte.
const bool DIR_DOWN_LEVEL = HIGH;

bool probeIsDown = false;       // évite une 2e descente sans remontée (idempotent)

void motorEnable() {
  if (EN_PIN >= 0) {
    digitalWrite(EN_PIN, LOW);                       // LOW = driver activé
    delay(10);                                       // réveil driver avant STEP
  }
}

void motorDisable() {
  if (EN_PIN >= 0) {
    digitalWrite(STEP_PIN, LOW);
    digitalWrite(EN_PIN, HIGH);                      // HIGH = driver off
  }
}

// Fait tourner le moteur pendant TRAVEL_MS dans le sens demandé (ta logique).
void runMove(bool down) {
  motorEnable();
  digitalWrite(DIR_PIN, down ? DIR_DOWN_LEVEL : !DIR_DOWN_LEVEL);
  delayMicroseconds(50);                          // établissement DIR
  unsigned long startTime = millis();
  while (millis() - startTime < TRAVEL_MS) {
    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(pulse_delay_us);
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(pulse_delay_us);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  digitalWrite(STEP_PIN, LOW);
  if (EN_PIN >= 0) {
    pinMode(EN_PIN, OUTPUT);
    motorDisable();                                // repos = driver off
  }
  Serial.println("READY");                         // signal de boot (la Pi l'ignore)
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
    if (!probeIsDown) { runMove(true); probeIsDown = true; }   // idempotent
    Serial.println("OK");
  } else if (cmd == "UP") {
    if (probeIsDown) { runMove(false); probeIsDown = false; }
    motorDisable();                                          // économie d'énergie
    Serial.println("OK");
  } else if (cmd == "ON") {
    motorEnable();
    Serial.println("OK");
  } else if (cmd == "OFF") {
    motorDisable();
    Serial.println("OK");
  } else {
    Serial.print("ERR unknown:");
    Serial.println(cmd);
  }
}
