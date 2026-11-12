
import json
import time
import serial

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class MotionController(Node):

    def __init__(self):
        super().__init__('motion_controller')

        # Parámetros configurables
        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('wheel_separation', 0.16)
        self.declare_parameter('max_wheel_speed', 0.30)

        port = self.get_parameter('serial_port').value
        self.L = self.get_parameter('wheel_separation').value
        self.vmax = self.get_parameter('max_wheel_speed').value

        if self.L <= 0 or self.vmax <= 0:
            raise ValueError('Los parámetros físicos deben ser positivos')

        # Comunicación con la ESP32
        self.esp32 = serial.Serial(port, 115200, timeout=0.1)
        time.sleep(2)

        # Última orden recibida
        self.v = 0.0
        self.w = 0.0
        self.last_command = 0.0

        # Suscriptor de velocidad
        self.subscription = self.create_subscription(
            Twist,
            '/cmd_vel',
            self.receive_cmd_vel,
            10
        )

        # Enviar velocidades cada 100 ms
        self.timer = self.create_timer(0.1, self.send_motors)

        self.get_logger().info('Control de movimiento iniciado')

    def receive_cmd_vel(self, msg):
        self.v = msg.linear.x
        self.w = msg.angular.z
        self.last_command = time.monotonic()

    def send_motors(self):

        # Detener si no llegan comandos durante 0.5 s
        if time.monotonic() - self.last_command > 0.5:
            v = 0.0
            w = 0.0
        else:
            v = self.v
            w = self.w

        # Cinemática diferencial
        vleft = v - (self.L / 2) * w
        vright = v + (self.L / 2) * w

        # Convertir a porcentaje PWM
        m1 = round(vleft * 100 / self.vmax)
        m2 = round(vright * 100 / self.vmax)

        # Limitar a -100 ... 100
        m1 = max(-100, min(100, m1))
        m2 = max(-100, min(100, m2)) 

        # Enviar JSON por serial
        command = {'m1': m1, 'm2': m2}
        message = json.dumps(command) + '\n'

        self.esp32.write(message.encode())

    def stop(self):
        if self.esp32.is_open:
            self.esp32.write(b'{"m1":0,"m2":0}\n')
            self.esp32.close()


def main(args=None):
    rclpy.init(args=args)
    nodo = MotionController()

    try:
        rclpy.spin(nodo)
    except KeyboardInterrupt:
        pass
    finally:
        nodo.stop()
        nodo.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
