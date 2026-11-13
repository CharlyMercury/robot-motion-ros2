
import json
import math
import threading
import time
from pathlib import Path

import rclpy
from aiohttp import web, WSMsgType
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor


# ============================================================
# CONFIGURACION
# ============================================================

ROOT = Path(__file__).resolve().parent

TIMEOUT = 0.3

MAX_LINEAR = 0.12
MAX_ANGULAR = 0.8

HOST = "0.0.0.0"
PORT = 8082


# ============================================================
# ESTADO DEL OPERADOR
# ============================================================

class ControllerState:

    def __init__(self):
        self.ws = None


# ============================================================
# NODO ROS 2
# ============================================================

class WebTeleop(Node):

    def __init__(self):
        super().__init__("web_teleop")

        self.publisher = self.create_publisher(
            Twist,
            "/cmd_vel",
            10,
        )

        self.lock = threading.Lock()

        self.linear = 0.0
        self.angular = 0.0
        self.last_command = 0.0

        # Publicacion a 20 Hz
        self.timer = self.create_timer(
            0.05,
            self.publish_command,
        )

        self.get_logger().info(
            "Nodo web_teleop iniciado"
        )

    def set_command(self, linear, angular, enabled):

        # Asegurar tipos float
        linear = float(linear)
        angular = float(angular)

        with self.lock:

            if enabled:

                self.linear = float(
                    max(
                        -MAX_LINEAR,
                        min(MAX_LINEAR, linear),
                    )
                )

                self.angular = float(
                    max(
                        -MAX_ANGULAR,
                        min(MAX_ANGULAR, angular),
                    )
                )

            else:
                self.linear = 0.0
                self.angular = 0.0

            self.last_command = time.monotonic()

    def stop(self):
        self.set_command(0.0, 0.0, False)

    def publish_command(self):

        with self.lock:

            fresh = (
                time.monotonic() - self.last_command
                < TIMEOUT
            )

            linear = (
                float(self.linear)
                if fresh else 0.0
            )

            angular = (
                float(self.angular)
                if fresh else 0.0
            )

        msg = Twist()

        # Todos los campos numericos deben ser float
        msg.linear.x = float(linear)
        msg.linear.y = 0.0
        msg.linear.z = 0.0

        msg.angular.x = 0.0
        msg.angular.y = 0.0
        msg.angular.z = float(angular)

        self.publisher.publish(msg)


# ============================================================
# SERVIDOR HTTP
# ============================================================

async def index(request):
    return web.FileResponse(
        ROOT / "index.html"
    )


# ============================================================
# WEBSOCKET
# ============================================================

async def websocket_handler(request):

    app = request.app

    expected_origin = (
        f"{request.scheme}://{request.host}"
    )

    if request.headers.get("Origin") != expected_origin:
        raise web.HTTPForbidden(
            text="Origen no permitido"
        )

    state = app["controller_state"]

    # Un solo operador activo
    if state.ws is not None:
        raise web.HTTPConflict(
            text="Control ocupado"
        )

    ws = web.WebSocketResponse(
        heartbeat=2
    )

    # Reservar antes del primer await
    state.ws = ws

    node = app["node"]

    try:

        await ws.prepare(request)

        node.get_logger().info(
            "Operador WebSocket conectado"
        )

        async for message in ws:

            if message.type != WSMsgType.TEXT:
                continue

            try:

                data = json.loads(message.data)

                v = data["linear"]
                w = data["angular"]
                enabled = data["enabled"]

                # Validar estructura y tipos
                valid = (
                    type(v) in (int, float)
                    and type(w) in (int, float)
                    and type(enabled) is bool
                    and math.isfinite(v)
                    and math.isfinite(w)
                )

                if not valid:
                    continue

                # Conversion explicita
                linear = float(v)
                angular = float(w)

                node.set_command(
                    linear,
                    angular,
                    enabled,
                )

            except (
                ValueError,
                KeyError,
                TypeError,
            ):
                continue

    finally:

        # Detener el robot
        node.stop()

        # Publicar velocidad cero inmediatamente
        node.publish_command()

        node.get_logger().info(
            "Operador desconectado. Robot detenido."
        )

        if state.ws is ws:
            state.ws = None

    return ws


# ============================================================
# MAIN
# ============================================================

def main():

    rclpy.init()

    node = WebTeleop()

    executor = SingleThreadedExecutor()
    executor.add_node(node)

    ros_thread = threading.Thread(
        target=executor.spin,
        name="ros2-executor",
        daemon=True,
    )

    ros_thread.start()

    app = web.Application()

    app["node"] = node
    app["controller_state"] = ControllerState()

    app.router.add_get(
        "/",
        index,
    )

    app.router.add_get(
        "/ws",
        websocket_handler,
    )

    try:

        print(
            f"Servidor de teleoperacion: "
            f"http://{HOST}:{PORT}"
        )

        web.run_app(
            app,
            host=HOST,
            port=PORT,
            handle_signals=True,
        )

    finally:

        print("Cerrando servidor...")

        node.stop()
        node.publish_command()

        executor.shutdown()

        ros_thread.join(timeout=2.0)

        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()

        print("Servidor finalizado")


if __name__ == "__main__":
    main()
