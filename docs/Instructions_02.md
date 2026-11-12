# Teleop Web — Control remoto con GameSir y ROS 2

Módulo de teleoperación para controlar un robot móvil desde un navegador web utilizando un gamepad GameSir conectado a una computadora.

El control se conecta mediante USB o Bluetooth a una Mac. El navegador lee las palancas y botones, envía los comandos por WebSocket a la Raspberry Pi y un nodo de ROS 2 publica las velocidades en el tópico `/cmd_vel`.

No es necesario instalar ROS 2 en la Mac. Todo el procesamiento del robot se ejecuta en la Raspberry Pi.

**Proyecto:** [robot-motion-ros2](https://github.com/CharlyMercury/robot-motion-ros2)

## 1. Arquitectura

```text
Control GameSir
      |
      | USB / Bluetooth
      v
Mac (Chrome)
      |
      | Gamepad API
      v
Interfaz teleop_web
      |
      | WebSocket mediante túnel SSH
      | Red Wi-Fi del celular
      v
Raspberry Pi
      |
      | server.py
      v
Nodo web_teleop (ROS 2 Jazzy)
      |
      | geometry_msgs/msg/Twist
      v
    /cmd_vel
      |
      v
motion_controller
      |
      | JSON / USB serial
      v
     ESP32
      |
      v
Driver de motores
      |
      v
Robot móvil diferencial
```

El servicio web se comunica con ROS 2 mediante `rclpy`. No utiliza `rosbridge` y no requiere instalar paquetes de ROS 2 en el navegador.

## 2. Requisitos

### Hardware

- Raspberry Pi con Ubuntu 24.04 LTS.
- Robot móvil con ESP32 y driver de motores.
- Control GameSir compatible con macOS.
- Mac con Google Chrome.
- Celular con función de punto de acceso Wi-Fi.
- Conexión USB o Bluetooth para el gamepad.

### Software

| Componente | Uso |
|---|---|
| ROS 2 Jazzy | Comunicación del robot |
| `rclpy` | Nodo de teleoperación |
| `geometry_msgs` | Mensajes de velocidad |
| `aiohttp` | Servidor HTTP y WebSocket |
| Gamepad API | Lectura del GameSir desde el navegador |
| OpenSSH | Acceso remoto seguro |

## 3. Estructura del proyecto

El módulo se organiza de forma independiente del paquete de motores.

```text
robot-motion-ros2/
├── src/
│   └── robot_motion/
│       └── robot_motion/
│           └── motion_controller.py
│
└── services/
    ├── camera_stream/
    │   ├── camera_stream.py
    │   └── index.html
    │
    └── teleop_web/
        ├── server.py
        ├── index.html
        └── README.md
```

Archivos:

| Archivo | Descripción |
|---|---|
| `server.py` | Servidor WebSocket y nodo ROS 2 |
| `index.html` | Lectura de GameSir, calibración y estado |
| `README.md` | Instalación y uso |

Los archivos `server.py` e `index.html` corresponden al prototipo de teleoperación desarrollado para este proyecto. Deben crearse en la carpeta indicada antes de iniciar el módulo.

## 4. Configurar la red Wi-Fi

Para operar el robot fuera de una red doméstica se puede utilizar un celular como punto de acceso.

### 4.1 Activar el hotspot

En el celular:

1. Activar el punto de acceso personal.
2. Configurar el nombre y la contraseña de la red.
3. Conectar la Mac a esa red.
4. Conectar la Raspberry Pi a la misma red.

El control puede funcionar dentro de la red local sin utilizar datos móviles. La calidad de la comunicación dependerá de la cobertura Wi-Fi y de las restricciones del hotspot.

### 4.2 Obtener la IP de la Raspberry Pi

Desde la Raspberry:

```bash
hostname -I
```

Ejemplo:

```text
172.20.10.4
```

La dirección depende del punto de acceso.

### 4.3 Verificar la conexión desde la Mac

```bash
ping 172.20.10.4
```

Si hay respuesta, probar SSH:

```bash
ssh usuario@172.20.10.4
```

Sustituir `usuario` y la IP por los valores reales.

Si no es posible establecer la conexión, comprobar que el hotspot permita la comunicación entre dispositivos conectados.

## 5. Instalación del servicio en la Raspberry Pi

### 5.1 Actualizar paquetes

```bash
sudo apt update
```

### 5.2 Instalar dependencias

```bash
sudo apt install -y \
    python3-aiohttp \
    openssh-server
```

El módulo requiere una instalación funcional de ROS 2 Jazzy con `rclpy` y `geometry_msgs`.

### 5.3 Activar SSH

```bash
sudo systemctl enable --now ssh
```

Comprobar:

```bash
sudo systemctl status ssh
```

### 5.4 Crear la carpeta

```bash
cd ~/robot-motion-ros2

mkdir -p services/teleop_web
```

Colocar dentro de ella los archivos `server.py` e `index.html` del módulo.

### 5.5 Cargar ROS 2

```bash
source /opt/ros/jazzy/setup.bash
```

Comprobar:

```bash
echo $ROS_DISTRO
```

Debe indicar:

```text
jazzy
```

## 6. Conectar el GameSir a la Mac

El GameSir puede conectarse por USB o Bluetooth, según el modelo.

### Conexión USB

Conectar el control mediante un cable que permita transmisión de datos y comprobar que macOS lo reconozca.

### Conexión Bluetooth

1. Abrir Configuración del Sistema en macOS.
2. Entrar a Bluetooth.
3. Activar el modo de emparejamiento del GameSir.
4. Seleccionar el dispositivo cuando aparezca.
5. Confirmar la conexión.

Algunos controles GameSir tienen distintos modos de funcionamiento, como XInput, DInput o modos específicos para determinadas plataformas. El modo compatible depende del modelo.

No se debe asumir que todos los controles GameSir tienen la misma distribución de ejes y botones.

## 7. Iniciar el robot

Se utilizarán tres terminales.

### Terminal 1 — Control de motores

Conectarse a la Raspberry Pi mediante SSH:

```bash
ssh usuario@172.20.10.4
```

Cargar ROS 2 y el workspace:

```bash
source /opt/ros/jazzy/setup.bash
source ~/robot-motion-ros2/install/setup.bash
```

Ejecutar:

```bash
ros2 run robot_motion motion_controller
```

Este nodo recibe los comandos publicados en `/cmd_vel` y los envía a la ESP32 mediante serial.

Antes de ejecutarlo, comprobar que la ESP32 tiene cargado el firmware correcto y que ningún otro programa utiliza su puerto.

### Terminal 2 — Servidor de teleoperación

Abrir otra sesión SSH:

```bash
ssh usuario@172.20.10.4
```

Cargar ROS 2:

```bash
source /opt/ros/jazzy/setup.bash
```

Iniciar el servidor:

```bash
cd ~/robot-motion-ros2/services/teleop_web

python3 server.py
```

El servicio escucha en:

```text
127.0.0.1:8082
```

Por seguridad, el prototipo solo escucha conexiones locales en la Raspberry Pi. Se accede desde la Mac mediante un túnel SSH.

### Terminal 3 — Túnel SSH desde la Mac

Esta instrucción se ejecuta directamente en la terminal de macOS, no dentro de una sesión SSH previa.

```bash
ssh -N \
    -L 8082:127.0.0.1:8082 \
    usuario@172.20.10.4
```

La opción `-L` redirige el puerto 8082 de la Mac hacia el servicio de la Raspberry Pi.

Mantener esta terminal abierta durante el control remoto.

## 8. Abrir el panel de control

Desde Google Chrome en la Mac:

```text
http://localhost:8082
```

La página mostrará:

- Estado de conexión WebSocket.
- Identificación del gamepad.
- Selección del eje lineal.
- Selección del eje angular.
- Selección del botón de habilitación.
- Valores de ejes y botones.
- Velocidades enviadas al robot.

Se utiliza `localhost` porque el navegador trata esa dirección como un origen confiable para determinadas API de dispositivos.

No es necesario abrir el servidor en todas las interfaces de red.

## 9. Configurar los botones y palancas

Los índices iniciales son valores de referencia. Es necesario verificar cuáles utiliza el GameSir conectado.

| Función | Índice inicial |
|---|---|
| Eje de velocidad lineal | `1` |
| Eje de velocidad angular | `2` |
| Botón de habilitación | `4` |

### 9.1 Identificar el eje lineal

Mover verticalmente la palanca izquierda y observar los valores que muestra el diagnóstico.

Ejemplo:

```text
Ejes:
0:  0.00
1: -0.85
2:  0.00
3:  0.00
```

En este ejemplo, el eje `1` corresponde al movimiento vertical de la palanca.

Seleccionar ese número como eje lineal.

### 9.2 Identificar el eje angular

Mover horizontalmente la palanca derecha.

Ejemplo:

```text
Ejes:
0:  0.00
1:  0.00
2:  0.72
3:  0.00
```

Seleccionar el eje que cambie al mover esa palanca.

### 9.3 Configurar el botón de habilitación

Mantener presionado el botón que se utilizará para permitir el movimiento, preferentemente `LB` o `L1`.

La página mostrará el índice del botón presionado.

Seleccionar ese número como botón de habilitación.

Este botón funciona como un control de presencia del operador (*dead man's switch*): el programa solo debe ordenar movimiento mientras esté presionado.

### 9.4 Comprobar el sentido de movimiento

Las velocidades enviadas utilizan las convenciones de ROS 2:

| Valor | Movimiento esperado |
|---|---|
| `linear.x > 0` | Adelante |
| `linear.x < 0` | Atrás |
| `angular.z > 0` | Giro hacia la izquierda |
| `angular.z < 0` | Giro hacia la derecha |

Si alguna palanca tiene el sentido invertido, debe corregirse el signo de la conversión en `index.html` y volver a probar.

El selector actual permite elegir ejes, pero no incluye un interruptor para invertir su dirección.

## 10. Configuración de velocidad

El prototipo utiliza los siguientes valores:

| Parámetro | Valor |
|---|---|
| Velocidad lineal máxima | 0.12 m/s |
| Velocidad angular máxima | 0.8 rad/s |
| Zona muerta de las palancas | 12 % |
| Intervalo de envío desde el navegador | 50 ms |
| Publicación de ROS 2 | 20 Hz |
| Timeout de teleoperación | 300 ms |
| Timeout del controlador de motores | 500 ms |

La zona muerta evita enviar pequeños movimientos causados por desviaciones de las palancas cerca de su posición central.

Los valores enviados son proporcionales a la posición de las palancas y se limitan a los máximos configurados.

Para modificarlos, revisar las constantes `MAX_LINEAR` y `MAX_ANGULAR` en `server.py`, así como los factores de escala correspondientes en `index.html`.

## 11. Flujo de comunicación

El navegador obtiene la posición de las palancas mediante la Gamepad API.

El frontend genera mensajes JSON con la velocidad lineal, la angular y el estado del botón de habilitación.

Ejemplo:

```json
{
  "linear": 0.08,
  "angular": -0.25,
  "enabled": true
}
```

El servidor recibe el mensaje por WebSocket y actualiza las consignas del nodo `web_teleop`.

El nodo publica un mensaje `Twist` en:

```text
/cmd_vel
```

El nodo `motion_controller` calcula los valores de mando de cada rueda y envía un mensaje JSON a la ESP32.

Ejemplo del protocolo serial:

```json
{
  "m1": 45,
  "m2": 60
}
```

Los valores finales de `m1` y `m2` dependen de la velocidad lineal, la velocidad angular y los parámetros físicos configurados en `motion_controller`.

## 12. Verificación sin mover los motores

Antes de conducir el robot, realizar estas pruebas sin alimentación de los motores o con las ruedas levantadas.

### 12.1 Comprobar los nodos

```bash
ros2 node list
```

Deben aparecer los nodos en ejecución, incluidos:

```text
/web_teleop
/motion_controller
```

### 12.2 Comprobar el tópico

```bash
ros2 topic list
```

Verificar:

```text
/cmd_vel
```

### 12.3 Observar los comandos

```bash
ros2 topic echo /cmd_vel
```

Al presionar el botón de habilitación y mover una palanca deben aparecer mensajes de velocidad.

Sin habilitación, ambos valores deben regresar a cero:

```yaml
linear:
  x: 0.0
  y: 0.0
  z: 0.0
angular:
  x: 0.0
  y: 0.0
  z: 0.0
```

### 12.4 Verificar la frecuencia

```bash
ros2 topic hz /cmd_vel
```

La frecuencia esperada del prototipo es cercana a 20 Hz mientras el nodo esté funcionando correctamente.

Esta prueba no mide la latencia completa entre la palanca y el movimiento real de las ruedas.

## 13. Seguridad del control remoto

El módulo tiene varias medidas de protección.

**Botón de habilitación.** Sin mantener presionado el botón configurado, el navegador envía velocidades cero.

**Timeout de 300 ms.** Si el servidor deja de recibir comandos válidos, el nodo publica velocidades cero.

**Timeout de 500 ms en motion_controller.** El controlador de motores también deja de ordenar movimiento si no recibe mensajes de velocidad.

**Control de un operador.** El prototipo admite una conexión WebSocket de control activa a la vez.

**Acceso mediante SSH.** El puerto de teleoperación se mantiene limitado a la interfaz local y se utiliza un túnel para conectarse desde la Mac.

Estas medidas no sustituyen un interruptor físico de paro ni un timeout implementado directamente en el firmware de la ESP32.

### Pruebas obligatorias

Antes de colocar el robot en el piso:

1. Comprobar que las palancas estén centradas al conectar el control.
2. Verificar que soltar el botón de habilitación detenga los motores.
3. Desconectar el GameSir y confirmar que las consignas pasan a cero.
4. Cerrar la página web y comprobar el paro.
5. Interrumpir la conexión Wi-Fi y verificar el comportamiento de seguridad.
6. Comprobar el timeout de la ESP32 de manera independiente.

La pérdida de una conexión no debe provocar que el robot mantenga indefinidamente su última velocidad.

## 14. Utilizar el GameSir junto con la cámara

El sistema de cámara se ejecuta en otro proceso y utiliza el puerto 8081.

**Terminal de Raspberry Pi:**

```bash
cd ~/robot-motion-ros2/services/camera_stream
source .venv/bin/activate

python camera_stream.py \
    --device /dev/video0 \
    --width 640 \
    --height 480 \
    --fps 30
```

Desde la Mac puedes crear un túnel SSH para ambos servicios:

```bash
ssh -N \
    -L 8082:127.0.0.1:8082 \
    -L 8081:127.0.0.1:8081 \
    usuario@172.20.10.4
```

Si ya tienes otro túnel utilizando alguno de esos puertos, ciérralo antes de ejecutar el nuevo.

Abre dos pestañas:

| Dirección | Función |
|---|---|
| `http://localhost:8082` | GameSir y teleoperación |
| `http://localhost:8081/mjpeg` | Cámara del robot |

Este túnel permite acceder al stream MJPEG. Para WebRTC puede requerirse una ruta de red adicional para el transporte multimedia; el túnel HTTP no transporta automáticamente sus conexiones UDP.

La integración de ambos servicios en una sola interfaz es una ampliación posterior, no una característica implementada en el prototipo actual.

## 15. Problemas frecuentes

### El navegador no detecta el GameSir

Comprobar que macOS reconozca el control y que el navegador tenga el foco.

Presionar un botón después de abrir la página. Algunos navegadores no exponen los datos del gamepad hasta que el usuario interactúa con él.

Verificar también el modo de conexión del GameSir y probar otro navegador compatible.

### La página no abre

Comprobar que `server.py` se esté ejecutando en la Raspberry Pi.

Revisar el túnel SSH:

```bash
ssh -N \
    -L 8082:127.0.0.1:8082 \
    usuario@172.20.10.4
```

Abrir exactamente:

```text
http://localhost:8082
```

### WebSocket desconectado

Revisar la consola de `server.py` y comprobar que el túnel SSH siga abierto.

Si el servicio indica que el control está ocupado, comprobar que no exista otra pestaña o cliente conectado.

### Aparece un error de aiohttp

Instalar la dependencia en el Python del sistema que ejecuta ROS 2:

```bash
sudo apt update
sudo apt install -y python3-aiohttp
```

### El GameSir responde pero el robot no se mueve

Comprobar:

```bash
ros2 topic echo /cmd_vel
```

Si los mensajes cambian correctamente, revisar `motion_controller`, el puerto USB, la ESP32 y el driver de motores.

Si los mensajes permanecen en cero, revisar el índice del botón de habilitación, los ejes configurados y el foco de la página.

### El movimiento está invertido

Verificar el sentido de los ejes del control y la correspondencia entre los motores izquierdo y derecho.

No compensar un problema de cableado cambiando parámetros al azar. Realizar pruebas individuales para identificar el origen.

### El robot responde con retraso

Comprobar la cobertura del hotspot, la carga de CPU de la Raspberry Pi y si la transmisión de video está saturando la red.

Utilizar inicialmente 640 × 480 para la cámara y velocidades de movimiento bajas.

## 16. Subir el módulo a GitHub

Desde la Raspberry Pi:

```bash
cd ~/robot-motion-ros2
```

Después de crear o actualizar los archivos:

```bash
git add services/teleop_web/

git commit -m "Add GameSir web teleoperation documentation"

git push origin main
```

Si también agregaste `server.py` e `index.html`, quedarán incluidos en el commit.

## 17. Mejoras previstas

La siguiente versión del módulo puede incorporar un panel integrado con transmisión de cámara, indicadores de velocidad y estado de comunicación, calibración guardada por modelo de control y un botón visible de paro.

También sería conveniente agregar medición de latencia entre el navegador y la Raspberry Pi, autenticación del operador y registro de eventos de desconexión.

## Referencias

- [Gamepad API — MDN](https://developer.mozilla.org/es/docs/Web/API/Gamepad_API)
- [ROS 2 Jazzy](https://docs.ros.org/en/jazzy/)
- [aiohttp](https://docs.aiohttp.org/)
- [OpenSSH](https://www.openssh.com/)
- [Repositorio del proyecto](https://github.com/CharlyMercury/robot-motion-ros2)
