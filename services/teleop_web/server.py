
import asyncio
import json
import logging
import math
import os
import threading
import time
from pathlib import Path

import rclpy
from aiohttp import (
    web,
    WSMsgType,
    WSCloseCode,
    ClientSession,
    ClientTimeout,
    ClientError,
)
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor


# ============================================================
# CONFIGURACION GENERAL
# ============================================================

ROOT = Path(__file__).resolve().parent

HOST = "0.0.0.0"
PORT = 8082

# Servicio independiente de camara
CAMERA_BASE_URL = os.getenv(
    "CAMERA_BASE_URL",
    "http://127.0.0.1:8081",
).rstrip("/")

# Seguridad de movimiento
TIMEOUT = 0.3

# Limites de velocidad del robot
MAX_LINEAR = 0.12
MAX_ANGULAR = 0.8

# Frecuencia de publicacion ROS 2: 20 Hz
PUBLISH_PERIOD = 0.05

LOG = logging.getLogger("teleop_web")


# ============================================================
# ESTADO DEL OPERADOR WEBSOCKET
# ============================================================

class ControllerState:
    """
    Almacena la conexion del operador activo.

    Solo se permite un operador a la vez.
    """

    def __init__(self):
        self.ws = None


# ============================================================
# ESTADO DEL PROXY DE CAMARA
# ============================================================

class CameraProxyState:
    """
    Mantiene una sesion HTTP compartida para comunicarse
    con el servicio camera_stream.
    """

    def __init__(self):
        self.session = None


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

        # Publicar comandos cada 50 ms
        self.timer = self.create_timer(
            PUBLISH_PERIOD,
            self.publish_command,
        )

        self.get_logger().info(
            "Nodo web_teleop iniciado"
        )

    def set_command(self, linear, angular, enabled):
        """
        Recibe velocidades del navegador.

        Limita los valores y garantiza el tipo float
        requerido por geometry_msgs/Twist.
        """

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
        """
        Solicita velocidad cero.
        """

        self.set_command(
            0.0,
            0.0,
            False,
        )

    def publish_command(self):
        """
        Publica Twist en /cmd_vel.

        Si transcurren mas de 300 ms sin comandos,
        publica velocidades cero.
        """

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

        msg.linear.x = float(linear)
        msg.linear.y = 0.0
        msg.linear.z = 0.0

        msg.angular.x = 0.0
        msg.angular.y = 0.0
        msg.angular.z = float(angular)

        self.publisher.publish(msg)


# ============================================================
# INTERFAZ WEB
# ============================================================

async def index(request):
    """
    Entrega el dashboard unificado.

    El archivo index.html contiene:
    - Visualizacion de camara
    - Control GameSir
    - Configuracion de ejes
    - Diagnostico
    """

    return web.FileResponse(
        ROOT / "index.html"
    )


# ============================================================
# WEBSOCKET DE TELEOPERACION
# ============================================================

async def websocket_handler(request):

    app = request.app

    # Validar origen de la conexion
    expected_origin = (
        f"{request.scheme}://{request.host}"
    )

    if request.headers.get("Origin") != expected_origin:
        raise web.HTTPForbidden(
            text="Origen no permitido"
        )

    state = app["controller_state"]

    # Impedir operadores simultaneos
    if state.ws is not None:
        raise web.HTTPConflict(
            text="Control ocupado por otro operador"
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

                linear = data["linear"]
                angular = data["angular"]
                enabled = data["enabled"]

                # Validar datos recibidos
                valid = (
                    type(linear) in (int, float)
                    and type(angular) in (int, float)
                    and type(enabled) is bool
                    and math.isfinite(linear)
                    and math.isfinite(angular)
                )

                if not valid:
                    continue

                # Convertir siempre a float
                node.set_command(
                    float(linear),
                    float(angular),
                    enabled,
                )

            except (
                ValueError,
                KeyError,
                TypeError,
            ):
                continue

    finally:

        # Detener el robot al perder la conexion
        node.stop()

        # Publicar inmediatamente velocidad cero
        node.publish_command()

        node.get_logger().info(
            "Operador desconectado. Robot detenido."
        )

        if state.ws is ws:
            state.ws = None

    return ws


# ============================================================
# CICLO DE VIDA DEL PROXY DE CAMARA
# ============================================================

async def camera_proxy_lifecycle(app):
    """
    Crea una unica sesion HTTP reutilizable.

    Evita abrir una nueva sesion para cada peticion.
    """

    state = app["camera_proxy"]

    timeout = ClientTimeout(
        total=None,
        sock_connect=5,
    )

    state.session = ClientSession(
        timeout=timeout
    )

    LOG.info(
        "Proxy de camara: %s",
        CAMERA_BASE_URL,
    )

    try:
        yield

    finally:

        await state.session.close()
        state.session = None

        LOG.info("Proxy de camara cerrado")


# ============================================================
# PROXY: ESTADO DE LA CAMARA
# ============================================================

async def camera_health(request):
    """
    GET /camera/health

    Consulta:
    camera_stream:8081/health
    """

    session = request.app["camera_proxy"].session

    try:

        async with session.get(
            CAMERA_BASE_URL + "/health",
            timeout=ClientTimeout(total=3),
        ) as response:

            body = await response.read()

            return web.Response(
                body=body,
                status=response.status,
                headers={
                    "Content-Type": "application/json",
                    "Cache-Control": "no-store",
                },
            )

    except (ClientError, asyncio.TimeoutError):

        LOG.warning(
            "Servicio de camara no disponible"
        )

        return web.json_response(
            {
                "ok": False,
                "service": "camera_proxy",
                "error": "Camara no disponible",
            },
            status=503,
        )


# ============================================================
# PROXY: NEGOCIACION WEBRTC
# ============================================================

async def camera_offer(request):
    """
    POST /camera/offer

    Reenvia la oferta SDP al servicio de camara.
    La comunicacion de video WebRTC se establece
    directamente entre navegador y camera_stream.
    """

    session = request.app["camera_proxy"].session

    try:

        params = await request.json()

        if (
            not isinstance(params, dict)
            or params.get("type") != "offer"
            or not isinstance(params.get("sdp"), str)
        ):
            raise ValueError("Oferta invalida")

    except (
        ValueError,
        TypeError,
    ):
        raise web.HTTPBadRequest(
            text="Oferta WebRTC invalida"
        )

    try:

        async with session.post(
            CAMERA_BASE_URL + "/offer",
            json=params,
            timeout=ClientTimeout(total=15),
        ) as response:

            body = await response.read()

            content_type = (
                "application/json"
                if response.status == 200
                else "text/plain"
            )

            return web.Response(
                body=body,
                status=response.status,
                content_type=content_type,
            )

    except (ClientError, asyncio.TimeoutError):

        LOG.exception(
            "Error comunicando con WebRTC de camara"
        )

        raise web.HTTPBadGateway(
            text="Servicio WebRTC no disponible"
        )


# ============================================================
# PROXY: STREAMING MJPEG
# ============================================================

async def camera_mjpeg(request):
    """
    GET /camera/mjpeg

    Retransmite el flujo MJPEG del servicio
    camera_stream sin decodificar las imagenes.

    No utiliza OpenCV ni consume otra captura.
    """

    session = request.app["camera_proxy"].session

    try:

        upstream = await session.get(
            CAMERA_BASE_URL + "/mjpeg",
            timeout=ClientTimeout(
                total=None,
                sock_connect=5,
                sock_read=None,
            ),
        )

    except (ClientError, asyncio.TimeoutError):

        LOG.warning(
            "No se pudo conectar con MJPEG"
        )

        raise web.HTTPBadGateway(
            text="Streaming MJPEG no disponible"
        )

    if upstream.status != 200:

        status = upstream.status
        upstream.close()

        LOG.warning(
            "Servicio MJPEG devolvio HTTP %s",
            status,
        )

        raise web.HTTPBadGateway(
            text="Error del servicio de camara"
        )

    response = web.StreamResponse(
        headers={
            "Content-Type":
                "multipart/x-mixed-replace; boundary=frame",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        }
    )

    try:

        await response.prepare(request)

        async for chunk in upstream.content.iter_chunked(
            32768
        ):

            await response.write(chunk)

    except (
        asyncio.CancelledError,
        ConnectionResetError,
        BrokenPipeError,
        ClientError,
    ):
        # El navegador cerro el video o cambio a WebRTC
        pass

    finally:

        upstream.close()

    return response


# ============================================================
# APAGADO DEL SERVIDOR WEB
# ============================================================

async def on_shutdown(app):
    """
    Cierra el WebSocket activo y detiene el robot
    antes de apagar el servidor.
    """

    state = app["controller_state"]
    node = app["node"]

    node.stop()
    node.publish_command()

    if state.ws is not None:

        await state.ws.close(
            code=WSCloseCode.GOING_AWAY,
            message=b"Servidor apagado",
        )


# ============================================================
# CONFIGURACION AIOHTTP
# ============================================================

def create_app(node):

    app = web.Application()

    # Objetos registrados antes de iniciar aiohttp
    app["node"] = node

    app["controller_state"] = ControllerState()
    app["camera_proxy"] = CameraProxyState()

    # Inicializar/cerrar conexion HTTP con camara
    app.cleanup_ctx.append(
        camera_proxy_lifecycle
    )

    # Cerrar conexiones durante el apagado
    app.on_shutdown.append(
        on_shutdown
    )

    # --------------------------------------------------------
    # INTERFAZ Y CONTROL
    # --------------------------------------------------------

    app.router.add_get(
        "/",
        index,
    )

    app.router.add_get(
        "/ws",
        websocket_handler,
    )

    # --------------------------------------------------------
    # SERVICIO DE CAMARA
    # --------------------------------------------------------

    app.router.add_get(
        "/camera/health",
        camera_health,
    )

    app.router.add_post(
        "/camera/offer",
        camera_offer,
    )

    app.router.add_get(
        "/camera/mjpeg",
        camera_mjpeg,
    )

    return app


# ============================================================
# MAIN
# ============================================================

def main():

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    # --------------------------------------------------------
    # INICIALIZAR ROS 2
    # --------------------------------------------------------

    rclpy.init()

    node = WebTeleop()

    executor = SingleThreadedExecutor()
    executor.add_node(node)

    # Ejecutar ROS 2 en un hilo independiente
    ros_thread = threading.Thread(
        target=executor.spin,
        name="ros2-executor",
        daemon=True,
    )

    ros_thread.start()

    # --------------------------------------------------------
    # CREAR APLICACION WEB
    # --------------------------------------------------------

    app = create_app(node)

    LOG.info(
        "Servidor de teleoperacion: http://%s:%s",
        HOST,
        PORT,
    )

    LOG.info(
        "Servicio de camara: %s",
        CAMERA_BASE_URL,
    )

    # --------------------------------------------------------
    # INICIAR SERVIDOR
    # --------------------------------------------------------

    try:

        web.run_app(
            app,
            host=HOST,
            port=PORT,
            handle_signals=True,
        )

    finally:

        LOG.info(
            "Cerrando servidor de teleoperacion"
        )

        # Detener robot
        node.stop()
        node.publish_command()

        # Detener ROS 2
        executor.shutdown(timeout_sec=2.0)

        ros_thread.join(timeout=2.0)

        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()

        LOG.info(
            "Servidor finalizado correctamente"
        )


if __name__ == "__main__":
    main()
