"""
imu.py — Driver minimal du gyroscope MPU6500/MPU6050 (I2C 0x68) du PiCar-Pro.

Sert UNIQUEMENT à l'asservissement des rotations : on intègre la vitesse
angulaire de l'axe Z (lacet) pendant le virage et on s'arrête quand l'angle
cible est atteint — la précision ne dépend plus des batteries ni du sol.

Driver volontairement minimal (smbus2, 3 registres) :
  0x6B PWR_MGMT_1   : 0x00 → réveil
  0x1B GYRO_CONFIG  : 0x00 → pleine échelle ±250 °/s (131 LSB par °/s)
  0x47 GYRO_ZOUT_H  : vitesse angulaire Z, 16 bits signés

Le biais du gyro (dérive à l'arrêt) est calibré à l'init, robot IMMOBILE.
"""

from __future__ import annotations

import time


def _log(msg: str) -> None:
    print(f"  [robot:imu] {msg}", flush=True)


class GyroZ:
    """Lecture du taux de lacet (°/s) du MPU6500, biais compensé."""

    PWR_MGMT_1 = 0x6B
    GYRO_CONFIG = 0x1B
    GYRO_ZOUT_H = 0x47
    LSB_PER_DPS = 131.0     # pleine échelle ±250 °/s

    def __init__(self, bus: int = 1, address: int = 0x68,
                 calibration_s: float = 1.0) -> None:
        from smbus2 import SMBus
        self._addr = address
        self._bus = SMBus(bus)
        self._bus.write_byte_data(self._addr, self.PWR_MGMT_1, 0x00)
        time.sleep(0.05)
        self._bus.write_byte_data(self._addr, self.GYRO_CONFIG, 0x00)
        time.sleep(0.05)
        self._bias_dps = 0.0
        self._bias_dps = self._calibrate(calibration_s)
        _log(f"gyroscope prêt (biais {self._bias_dps:+.2f} °/s)")

    def _read_raw_dps(self) -> float:
        hi, lo = self._bus.read_i2c_block_data(self._addr, self.GYRO_ZOUT_H, 2)
        raw = (hi << 8) | lo
        if raw >= 32768:
            raw -= 65536
        return raw / self.LSB_PER_DPS

    def _calibrate(self, seconds: float) -> float:
        """Moyenne du taux à l'arrêt = biais. Le robot doit être IMMOBILE."""
        total, n = 0.0, 0
        end = time.monotonic() + max(0.2, seconds)
        while time.monotonic() < end:
            total += self._read_raw_dps()
            n += 1
            time.sleep(0.005)
        return total / n if n else 0.0

    def rate_dps(self) -> float:
        """Vitesse angulaire Z en °/s, biais déduit (signe = sens de rotation)."""
        return self._read_raw_dps() - self._bias_dps

    def close(self) -> None:
        try:
            self._bus.close()
        except Exception:
            pass
