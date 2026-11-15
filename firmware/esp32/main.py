
from machine import Pin, PWM
import sys
import json
import select
import time

# Entradas del ZK-BM1
in1 = PWM(Pin(25), freq=1000, duty_u16=0)
in2 = PWM(Pin(26), freq=1000, duty_u16=0)
in3 = PWM(Pin(32), freq=1000, duty_u16=0)
in4 = PWM(Pin(33), freq=1000, duty_u16=0)


def mover(a, b, velocidad):
    velocidad = max(-100, min(100, int(velocidad)))
    pwm = abs(velocidad) * 65535 // 100

    # Desactivar ambas entradas antes de cambiar
    a.duty_u16(0)
    b.duty_u16(0)
    time.sleep_ms(2)

    if velocidad > 0:
        a.duty_u16(pwm)
    elif velocidad < 0:
        b.duty_u16(pwm)


def detener():
    mover(in1, in2, 0)
    mover(in3, in4, 0)


# Escuchar el puerto USB serial
serial = select.poll()
serial.register(sys.stdin, select.POLLIN)

try:
    while True:
        if serial.poll(500):
            try:
                comando = json.loads(sys.stdin.readline())

                mover(in1, in2, comando["m1"])
                mover(in3, in4, comando["m2"])

            except Exception as e:
                detener()
                print("ERROR:", e)
        else:
            # Sin comandos durante 500 ms
            detener()
finally:
    detener()
