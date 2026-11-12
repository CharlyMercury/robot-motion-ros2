
import json
import math
import threading
import time
from pathlib import Path

import rclpy
from aiohttp import web, WSMsgType
from geometry_msgs.msg import Twist
from rclpy.node import Node


ROOT = Path(__file__).resolve().parent
TIMEOUT = 0.3
MAX_LINEAR = 0.12
MAX_ANGULAR = 0.8


class WebTeleop(Node):
    def __init__(self):
        super().__init__("web_teleop")

        self.publisher = self.create_publisher(
            Twist, "/cmd_vel", 10
        )

        self.lock = threading.Lock()
        self.linear = 0.0
        self.angular = 0.0
        self.last_command = 0.0

        self.create_timer(0.05, self.publish_command)

    def set_command(self, linear, angular, enabled):
        with self.lock:
            self.linear = (
                max(-MAX_LINEAR, min(MAX_LINEAR, linear))
                if enabled else 0.0
            )
            self.angular = (
                max(-MAX_ANGULAR, min(MAX_ANGULAR, angular))
                if enabled else 0.0
            )
            self.last_command = time.monotonic()

    def stop(self):
        self.set_command(0.0, 0.0, False)

    def publish_command(self):
        with self.lock:
            fresh = (
                time.monotonic() - self.last_command < TIMEOUT
            )

            linear = self.linear if fresh else 0.0
            angular = self.angular if fresh else 0.0

        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = angular
        self.publisher.publish(msg)


async def index(request):
    return web.FileResponse(ROOT / "index.html")


async def websocket_handler(request):
    app = request.app

    # Impedir conexiones WebSocket desde otras páginas.
    if request.headers.get("Origin") != (
        f"http://{request.host}"
    ):
        raise web.HTTPForbidden()

    # Solo un operador a la vez.
    if app["controller"] is not None:
        raise web.HTTPConflict(text="Control ocupado")

    ws = web.WebSocketResponse(heartbeat=2)
    await ws.prepare(request)

    app["controller"] = ws
    node = app["node"]

    try:
        async for message in ws:
            if message.type != WSMsgType.TEXT:
                continue

            try:
                data = json.loads(message.data)

                v = data["linear"]
                w = data["angular"]
                enabled = data["enabled"]

                if not (
                    type(v) in (int, float)
                    and type(w) in (int, float)
                    and type(enabled) is bool
                    and math.isfinite(v)
                    and math.isfinite(w)
                ):
                    continue

                node.set_command(v, w, enabled)

            except (ValueError, KeyError, TypeError):
                continue

    finally:
        node.stop()
        app["controller"] = None

    return ws


def main():
    rclpy.init()
    node = WebTeleop()

    ros_thread = threading.Thread(
        target=rclpy.spin,
        args=(node,),
        daemon=True,
    )
    ros_thread.start()

    app = web.Application()
    app["node"] = node
    app["controller"] = None

    app.router.add_get("/", index)
    app.router.add_get("/ws", websocket_handler)

    try:
        # Solo conexiones locales: acceder desde
        # la Mac mediante un túnel SSH.
        web.run_app(
            app,
            host="127.0.0.1",
            port=8082,
        )
    finally:
        node.stop()
        node.publish_command()
        rclpy.shutdown()
        ros_thread.join(timeout=2)
        node.destroy_node()


if __name__ == "__main__":
    main()
