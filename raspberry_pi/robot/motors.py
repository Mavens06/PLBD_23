import time

class MotorDriver:
    def move_to(self, point: str) -> str:
        print(f"[MOTOR] Navigating to point {point}...")
        time.sleep(2) # Simulate transit time
        print(f"[MOTOR] Reached point {point}.")
        return f'Move to {point}'

    def lower_arm(self) -> None:
        print("[MOTOR] Lowering robotic arm for sensor reading...")
        time.sleep(1)
        print("[MOTOR] Arm is now down in the soil.")

    def raise_arm(self) -> None:
        print("[MOTOR] Raising robotic arm...")
        time.sleep(1)
        print("[MOTOR] Arm is fully raised and secured.")
