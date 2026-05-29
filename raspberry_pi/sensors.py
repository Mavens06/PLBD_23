# sensors.py – Lecture du capteur agricole 4-en-1 RS485 (Modbus RTU).
# Le capteur mesure : pH, humidité, température et conductivité électrique (EC, en mS/cm).
# Aucune mesure N/P/K : ces grandeurs ne sont pas dans le périmètre du capteur.
# La liaison série est gérée via pyserial sur /dev/ttyUSB0 (ou /dev/ttyAMA0).
