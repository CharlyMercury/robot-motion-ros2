import serial
import json
import time

esp32 = serial.Serial("/dev/ttyUSB0", 115200, timeout=1)
time.sleep(2)

def mover(m1, m2, duration=2):
    command = {"m1": m1, "m2": m2}
    message = json.dumps(command) + "\n"

    for _ in range(int(duration)*10):
        esp32.write(message.encode())
        time.sleep(0.1)


try:
    # movimiento hacia adelante
    mover(50, 50, 5)

    # movimiento en resersa
    mover(-50, -50, 5)

    # giro
    mover(50, -50, 5)

finally:
    mover(0,0,0.2)
    esp32.close()
