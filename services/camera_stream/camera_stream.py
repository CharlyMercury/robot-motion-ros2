
from __future__ import annotations

import argparse
import asyncio
import logging
import threading
import time
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np
from aiohttp import web
from aiortc import (
    RTCConfiguration,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
)
from aiortc.mediastreams import MediaStreamError
from av import VideoFrame


LOG = logging.getLogger("camera_stream")
BASE_DIR = Path(__file__).resolve().parent

VIDEO_CLOCK = 90_000
RECONNECT_SECONDS = 2.0


class CameraSource:
    """Captura una cámara y comparte el último fotograma."""

    def __init__(
        self,
        device: str,
        width: int,
        height: int,
        fps: int,
        jpeg_quality: int,
    ):
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.jpeg_quality = jpeg_quality

        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None

        self.available = False
        self.opened = False
        self.last_error = ""
        self.last_frame_time = None
        self.sequence = 0

        self.frame = self._placeholder()
        self.jpeg = self._encode(self.frame)

    def _placeholder(self) -> np.ndarray:
        frame = np.zeros(
            (self.height, self.width, 3),
            dtype=np.uint8,
        )
        cv2.putText(
            frame,
            "Camara no disponible",
            (20, self.height // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        return frame

    def _encode(self, frame: np.ndarray) -> bytes:
        ok, buffer = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality],
        )
        return buffer.tobytes() if ok else b""

    def _update_frame(self, frame: np.ndarray) -> None:
        # El JPEG se codifica una vez y se comparte
        # entre todos los clientes MJPEG.
        jpeg = self._encode(frame)

        with self.lock:
            self.frame = frame
            if jpeg:
                self.jpeg = jpeg

            self.available = True
            self.last_error = ""
            self.last_frame_time = time.monotonic()
            self.sequence += 1

    def _set_offline(self, error: str) -> None:
        frame = self._placeholder()
        jpeg = self._encode(frame)

        with self.lock:
            self.available = False
            self.opened = False
            self.last_error = error
            self.frame = frame
            self.jpeg = jpeg
            self.sequence += 1

    def _open_camera(self) -> cv2.VideoCapture | None:
        # V4L2 es el backend preferido en Linux.
        for backend in (cv2.CAP_V4L2, cv2.CAP_ANY):
            cap = None

            try:
                cap = cv2.VideoCapture(self.device, backend)

                if not cap.isOpened():
                    cap.release()
                    continue

                cap.set(
                    cv2.CAP_PROP_FOURCC,
                    cv2.VideoWriter_fourcc(*"MJPG"),
                )
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                cap.set(cv2.CAP_PROP_FPS, self.fps)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                LOG.info(
                    "Camara abierta: %s | %.0fx%.0f | %.1f FPS",
                    self.device,
                    cap.get(cv2.CAP_PROP_FRAME_WIDTH),
                    cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
                    cap.get(cv2.CAP_PROP_FPS),
                )
                return cap

            except Exception:
                LOG.exception("Error abriendo %s", self.device)
                if cap is not None:
                    cap.release()

        return None

    def _capture_loop(self) -> None:
        while not self.stop_event.is_set():
            cap = self._open_camera()

            if cap is None:
                self._set_offline("No se pudo abrir la camara")
                LOG.warning("Reintentando en %.1f s", RECONNECT_SECONDS)
                self.stop_event.wait(RECONNECT_SECONDS)
                continue

            with self.lock:
                self.opened = True

            try:
                while not self.stop_event.is_set():
                    ok, frame = cap.read()

                    if not ok or frame is None:
                        self._set_offline("Sin fotogramas")
                        LOG.warning("Se perdio la captura")
                        break

                    if frame.shape[:2] != (
                        self.height,
                        self.width,
                    ):
                        frame = cv2.resize(
                            frame,
                            (self.width, self.height),
                        )

                    self._update_frame(frame)

            except Exception:
                LOG.exception("Error durante la captura")
                self._set_offline("Error de lectura")

            finally:
                cap.release()
                with self.lock:
                    self.opened = False

            if not self.stop_event.is_set():
                self.stop_event.wait(RECONNECT_SECONDS)

        LOG.info("Hilo de captura finalizado")

    def start(self) -> None:
        if self.thread is not None and self.thread.is_alive():
            return

        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._capture_loop,
            name="camera-capture",
            daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()

        if self.thread is not None:
            self.thread.join(timeout=3.0)
            if self.thread.is_alive():
                LOG.warning("La captura sigue bloqueada al cerrar")

    def get_frame(self) -> np.ndarray:
        with self.lock:
            return self.frame.copy()

    def get_jpeg(self) -> tuple[int, bytes]:
        with self.lock:
            return self.sequence, self.jpeg

    def get_status(self) -> dict:
        with self.lock:
            age = (
                None
                if self.last_frame_time is None
                else round(
                    time.monotonic() - self.last_frame_time, 2
                )
            )

            return {
                "device": self.device,
                "available": self.available,
                "opened": self.opened,
                "width": self.width,
                "height": self.height,
                "fps_requested": self.fps,
                "last_frame_age_seconds": age,
                "last_error": self.last_error,
            }


class CameraTrack(VideoStreamTrack):
    """Entrega fotogramas de la cámara a WebRTC."""

    kind = "video"

    def __init__(self, camera: CameraSource):
        super().__init__()
        self.camera = camera
        self.started_at = None
        self.frame_number = 0

    async def recv(self) -> VideoFrame:
        if self.readyState != "live":
            raise MediaStreamError

        now = time.monotonic()

        if self.started_at is None:
            self.started_at = now

        target = (
            self.started_at
            + self.frame_number / self.camera.fps
        )
        delay = target - now

        # Evitar ráfagas al recuperarse de un retraso.
        if delay < -0.25:
            self.started_at = (
                now - self.frame_number / self.camera.fps
            )
        elif delay > 0:
            await asyncio.sleep(delay)

        pts = round(
            self.frame_number
            * VIDEO_CLOCK
            / self.camera.fps
        )
        self.frame_number += 1

        frame = VideoFrame.from_ndarray(
            self.camera.get_frame(),
            format="bgr24",
        )
        frame.pts = pts
        frame.time_base = Fraction(1, VIDEO_CLOCK)

        return frame


async def index(request: web.Request) -> web.Response:
    html = (BASE_DIR / "index.html").read_text(
        encoding="utf-8"
    )
    return web.Response(text=html, content_type="text/html")


async def health(request: web.Request) -> web.Response:
    camera = request.app["camera"]
    status = camera.get_status()

    return web.json_response({
        "ok": status["available"],
        "service": "robot_camera_stream",
        "camera": status,
        "webrtc_clients": len(request.app["peers"]),
    })


async def offer(request: web.Request) -> web.Response:
    try:
        params = await request.json()
        if (
            not isinstance(params, dict)
            or params.get("type") != "offer"
            or not isinstance(params.get("sdp"), str)
        ):
            raise ValueError("Oferta SDP invalida")
    except (ValueError, TypeError):
        raise web.HTTPBadRequest(text="Oferta WebRTC invalida")

    # Sin servidores externos: pensado para red local.
    pc = RTCPeerConnection(
        configuration=RTCConfiguration(iceServers=[])
    )
    peers = request.app["peers"]
    peers.add(pc)

    @pc.on("connectionstatechange")
    async def connection_changed():
        LOG.info("WebRTC: %s", pc.connectionState)

        if pc.connectionState == "failed":
            await pc.close()

        if pc.connectionState == "closed":
            peers.discard(pc)

    try:
        remote = RTCSessionDescription(
            sdp=params["sdp"],
            type=params["type"],
        )
        await pc.setRemoteDescription(remote)

        pc.addTrack(CameraTrack(request.app["camera"]))

        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return web.json_response({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type,
        })

    except Exception:
        LOG.exception("Error negociando WebRTC")
        await pc.close()
        peers.discard(pc)
        raise web.HTTPBadRequest(
            text="No se pudo negociar la conexion WebRTC"
        )


async def mjpeg_stream(
    request: web.Request,
) -> web.StreamResponse:
    camera = request.app["camera"]

    response = web.StreamResponse(
        headers={
            "Content-Type":
                "multipart/x-mixed-replace; boundary=frame",
            "Cache-Control": "no-store",
        }
    )
    await response.prepare(request)

    last_sequence = -1

    try:
        while True:
            sequence, jpeg = camera.get_jpeg()

            if sequence != last_sequence and jpeg:
                packet = (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: "
                    + str(len(jpeg)).encode()
                    + b"\r\n\r\n"
                    + jpeg
                    + b"\r\n"
                )
                await response.write(packet)
                last_sequence = sequence

            await asyncio.sleep(
                max(0.01, 1.0 / (camera.fps * 2))
            )

    except (
        asyncio.CancelledError,
        ConnectionResetError,
        BrokenPipeError,
    ):
        pass

    return response


async def app_lifecycle(app: web.Application):
    camera = app["camera"]
    camera.start()

    try:
        yield
    finally:
        peers = list(app["peers"])

        await asyncio.gather(
            *(pc.close() for pc in peers),
            return_exceptions=True,
        )
        app["peers"].clear()

        await asyncio.to_thread(camera.stop)


def create_app(camera: CameraSource) -> web.Application:
    app = web.Application()

    app["camera"] = camera
    app["peers"] = set()

    app.cleanup_ctx.append(app_lifecycle)

    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    app.router.add_post("/offer", offer)
    app.router.add_get("/mjpeg", mjpeg_stream)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Streaming de una camara para robot movil"
    )

    parser.add_argument("--device", default="/dev/video0")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--jpeg-quality", type=int, default=80)

    args = parser.parse_args()

    if (
        args.width <= 0
        or args.height <= 0
        or args.fps <= 0
        or not 1 <= args.jpeg_quality <= 100
        or not 1 <= args.port <= 65535
    ):
        parser.error("Parametros de video o puerto invalidos")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    camera = CameraSource(
        device=args.device,
        width=args.width,
        height=args.height,
        fps=args.fps,
        jpeg_quality=args.jpeg_quality,
    )

    LOG.info("Servidor HTTP en puerto %s", args.port)

    web.run_app(
        create_app(camera),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
