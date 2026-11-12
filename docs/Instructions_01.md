# Robótica móvil con ROS 2, Python y ESP32

Proyecto educativo para aprender robótica móvil utilizando ROS 2 Jazzy, Python, Raspberry Pi y ESP32.

El sistema permite controlar un robot de tracción diferencial mediante comandos de velocidad, manejarlo desde el teclado de otra computadora y visualizar una cámara USB en tiempo real a través de una página web.

**Repositorio:** https://github.com/CharlyMercury/robot-motion-ros2

## 1. Arquitectura del sistema

```text
Computadora / Mac
    |
    | Wi-Fi / Ethernet
    |
    +--- SSH ---> Raspberry Pi (Ubuntu 24.04)
    |                  |
    |                  +--- ROS 2 Jazzy
    |                  |       |
    |                  |       +--- /cmd_vel
    |                  |       |
    |                  |       +--- motion_controller
    |                  |                  |
    |                  |                  | USB / Serial
    |                  |                  v
    |                  |                ESP32
    |                  |                  |
    |                  |                Driver
    |                  |                  |
    |                  |             Motores DC
    |                  |
    +--- HTTP ---------+--- Cámara USB
         WebRTC/MJPEG
```

La Raspberry Pi procesa los comandos de ROS 2. La ESP32 recibe los valores de control por comunicación serial y acciona los motores. La cámara funciona como un servicio independiente.

## 2. Requisitos

| Componente | Requisito |
|---|---|
| Sistema operativo | Ubuntu 24.04 LTS ARM64 |
| ROS 2 | Jazzy Jalisco |
| Python | 3.12 |
| Computadora principal | Raspberry Pi |
| Microcontrolador | ESP32 con MicroPython |
| Driver | Puente H compatible |
| Comunicación | USB serial a 115200 baudios |
| Cámara | USB compatible con V4L2 |
| Red | Wi-Fi o Ethernet |

Se recomienda que la Raspberry Pi y la computadora utilizada para controlarla estén conectadas a la misma red local.

## 3. Preparar Ubuntu 24.04

### Verificar el sistema

```bash
cat /etc/os-release
uname -m
```

Resultados esperados:

```text
VERSION_ID="24.04"
VERSION_CODENAME=noble
aarch64
```

### Actualizar paquetes

```bash
sudo apt update
sudo apt upgrade -y
```

### Instalar herramientas

```bash
sudo apt install -y \
    git \
    curl \
    build-essential \
    software-properties-common \
    python3-pip \
    python3-venv \
    python3-serial \
    openssh-server \
    v4l-utils
```

Para evitar que Ubuntu ofrezca actualizaciones a una versión mayor:

```bash
sudo nano /etc/update-manager/release-upgrades
```

Configurar:

```ini
Prompt=never
```

Esto no desactiva las actualizaciones normales de seguridad de Ubuntu 24.04.

## 4. Instalar ROS 2 Jazzy

Si ROS 2 Jazzy ya está instalado, omite esta sección.

### Habilitar Universe

```bash
sudo add-apt-repository universe
```

### Configurar el repositorio de ROS 2

```bash
export ROS_APT_SOURCE_VERSION=$(
    curl -fsSL \
    https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest \
    | grep -F '"tag_name"' \
    | awk -F'"' '{print $4}'
)
```

Descargar:

```bash
curl -fL -o /tmp/ros2-apt-source.deb \
    "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.noble_all.deb"
```

Instalar el repositorio:

```bash
sudo dpkg -i /tmp/ros2-apt-source.deb
sudo apt update
```

### Instalar ROS-Base

```bash
sudo apt install -y ros-jazzy-ros-base
```

### Instalar herramientas de desarrollo

```bash
sudo apt install -y \
    python3-colcon-common-extensions \
    python3-rosdep \
    ros-dev-tools \
    python3-serial
```

### Configurar el entorno

```bash
source /opt/ros/jazzy/setup.bash
```

Verificar:

```bash
echo $ROS_DISTRO
```

Resultado:

```text
jazzy
```

Configurar carga automática:

```bash
echo 'source /opt/ros/jazzy/setup.bash' >> ~/.bashrc
```

Inicializar las herramientas de dependencias:

```bash
sudo rosdep init
rosdep update
```

Si `rosdep` ya está inicializado, solo actualiza su base de datos.

## 5. Clonar y compilar el proyecto

```bash
cd ~

git clone \
    https://github.com/CharlyMercury/robot-motion-ros2.git

cd robot-motion-ros2
```

Instalar dependencias:

```bash
source /opt/ros/jazzy/setup.bash

rosdep install \
    --from-paths src \
    --ignore-src \
    --rosdistro jazzy \
    -r -y
```

Compilar:

```bash
colcon build --symlink-install
```

Cargar el workspace:

```bash
source install/setup.bash
```

Verificar:

```bash
ros2 pkg executables robot_motion
```

Resultado esperado:

```text
robot_motion motion_controller
```

## 6. Acceder a la Raspberry Pi desde otra computadora

La Raspberry Pi puede trabajar sin monitor ni teclado. Una computadora con macOS, Windows o Linux puede administrarla mediante SSH.

### 6.1 Habilitar SSH en la Raspberry Pi

Ejecutar:

```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
```

Comprobar que el servicio está activo:

```bash
sudo systemctl status ssh
```

Debe aparecer:

```text
Active: active (running)
```

Si utilizas UFW y está activo, permite SSH:

```bash
sudo ufw status
sudo ufw allow OpenSSH
```

### 6.2 Obtener la dirección IP

En la Raspberry Pi:

```bash
hostname -I
```

Ejemplo:

```text
192.168.0.119
```

Esta dirección puede cambiar al reconectarse a la red.

También puedes consultar el nombre del dispositivo:

```bash
hostname
```

### 6.3 Conectarse desde macOS o Linux

Abrir Terminal en la computadora:

```bash
ssh usuario@192.168.0.119
```

Sustituir `usuario` por el usuario configurado en Ubuntu y utilizar la IP actual de la Raspberry Pi.

En la primera conexión, SSH puede solicitar confirmar la identidad del equipo. Verifica que corresponde a tu Raspberry Pi antes de aceptarla.

Después introduce la contraseña del usuario de Ubuntu.

Una vez conectado:

```bash
hostname
cat /etc/os-release
```

Los comandos ahora se ejecutan directamente en la Raspberry Pi, aunque estés utilizando la terminal de tu Mac.

Para salir:

```bash
exit
```

### 6.4 Acceder mediante raspberry.local o un nombre personalizado

Ubuntu puede anunciar su nombre en la red mediante mDNS utilizando Avahi.

Instalar y activar:

```bash
sudo apt install -y avahi-daemon

sudo systemctl enable --now avahi-daemon
```

Consultar el hostname:

```bash
hostname
```

Opcionalmente, asignar un nombre al robot:

```bash
sudo hostnamectl set-hostname robot-pi
```

Si se cambia el nombre, conviene cerrar y volver a abrir la sesión.

Desde la Mac:

```bash
ping robot-pi.local
```

Y conectarse:

```bash
ssh usuario@robot-pi.local
```

El dominio `.local` funciona cuando mDNS está disponible y la red permite su tráfico. Si no resuelve, utiliza la dirección IP.

### 6.5 Encontrar la Raspberry Pi si desconoces su IP

En macOS puedes comenzar con:

```bash
arp -a
```

Esto muestra dispositivos conocidos recientemente por tu computadora, aunque no necesariamente todos los que están conectados.

Otra opción es Nmap. Si utilizas Homebrew:

```bash
brew install nmap
```

Determina primero la subred local. Si corresponde a `192.168.0.0/24`, puedes escanearla con:

```bash
nmap -sn 192.168.0.0/24
```

Para buscar equipos con SSH activo:

```bash
nmap -p 22 --open 192.168.0.0/24
```

Utiliza la subred real de tu instalación y realiza estos escaneos únicamente en redes propias o autorizadas.

### 6.6 Acceder al video desde otra computadora

Con el servicio de cámara ejecutándose en la Raspberry Pi, abre desde tu Mac:

```text
http://192.168.0.119:8081
```

Sustituye la dirección por la IP actual.

Las rutas principales son:

| Ruta | Función |
|---|---|
| `/` | Visualización de la cámara |
| `/mjpeg` | Streaming MJPEG |
| `/health` | Estado del servicio |
| `/offer` | Negociación WebRTC |

SSH permite acceder a la terminal, mientras que esta dirección HTTP permite visualizar la cámara. No son el mismo servicio.

Para acceder a un escritorio gráfico completo se requiere Ubuntu Desktop y configurar por separado un servicio de escritorio remoto.

## 7. Conexión de la ESP32

El proyecto utiliza una ESP32 conectada a la Raspberry Pi mediante USB.

Los pines de control de motores previstos son:

| ESP32 | Driver |
|---|---|
| GPIO 25 | IN1 |
| GPIO 26 | IN2 |
| GPIO 32 | IN3 |
| GPIO 33 | IN4 |

La correspondencia exacta entre entradas, sentido de giro y motores depende del cableado del driver.

Identifica el puerto:

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

Ejemplo:

```text
/dev/ttyUSB0
```

Si hay problemas de permisos:

```bash
sudo usermod -aG dialout "$USER"
```

Cierra la sesión y vuelve a conectarte.

Comprueba:

```bash
groups
```

Debe aparecer `dialout`.

## 8. Instalar MicroPython en la ESP32

MicroPython permite ejecutar programas Python directamente en la ESP32.

Hay que distinguir dos operaciones:

- **Instalar MicroPython:** grabar el intérprete en la memoria flash del microcontrolador.
- **Subir el programa:** copiar archivos como `main.py` al sistema de archivos de MicroPython.

Si la ESP32 ya ejecuta MicroPython, no necesitas reinstalarlo para actualizar tu código.

### 8.1 Verificar si MicroPython está instalado

Instala primero `mpremote`, como se explica en la siguiente sección.

Después, con la ESP32 conectada:

```bash
mpremote connect /dev/ttyUSB0 repl
```

Si aparece el intérprete de MicroPython, normalmente con el indicador `>>>`, ya está instalado.

Puedes comprobarlo escribiendo:

```python
import sys
print(sys.implementation)
```

Si no responde como MicroPython, verifica el puerto y el tipo de firmware antes de intentar instalar otro.

### 8.2 Instalar el intérprete, cuando sea necesario

Descarga una versión estable de MicroPython compatible con tu modelo exacto de ESP32:

https://micropython.org/download/

Para placas ESP32 clásicas, la familia habitual es `ESP32_GENERIC`.

La instalación inicial del archivo `.bin` se realiza mediante `esptool`, utilizando la dirección de escritura indicada en las instrucciones oficiales de la placa.

**No utilices una imagen genérica de ESP32 en una ESP32-S3, C3 u otra variante sin comprobar su compatibilidad.**

Grabar el intérprete puede borrar el firmware anterior y sus archivos. Realiza un respaldo cuando corresponda.

## 9. Subir el código MicroPython a la ESP32

Para cargar los programas desde consola utilizaremos `mpremote`.

### 9.1 Instalar mpremote

En Ubuntu 24.04, crea un entorno virtual dedicado:

```bash
python3 -m venv ~/.venvs/mpremote
```

Instala:

```bash
~/.venvs/mpremote/bin/python -m pip install mpremote
```

Comprueba:

```bash
~/.venvs/mpremote/bin/mpremote --help
```

Para simplificar los siguientes comandos, activa el entorno:

```bash
source ~/.venvs/mpremote/bin/activate
```

Ahora puedes utilizar directamente `mpremote`.

### 9.2 Identificar la ESP32

```bash
mpremote connect list
```

Conectar:

```bash
mpremote connect /dev/ttyUSB0 repl
```

La ESP32 debe mostrar el intérprete de MicroPython. Sal del modo interactivo antes de utilizar otra herramienta que necesite el puerto.

### 9.3 Verificar el programa que se va a subir

El repositorio utiliza la siguiente ubicación:

```text
firmware/
└── esp32/
    └── main.py
```

**Estado del repositorio:** el archivo `firmware/esp32/main.py` publicado originalmente contiene un script que importa `serial` y se ejecuta desde la Raspberry Pi. Ese código no es firmware MicroPython para la ESP32.

Antes de utilizar las instrucciones de carga, sustituye su contenido por el programa MicroPython real que controla los GPIO y recibe los comandos JSON.

Para revisar el archivo:

```bash
cd ~/robot-motion-ros2
cat firmware/esp32/main.py
```

Un programa de control destinado a la ESP32 normalmente utilizará módulos de MicroPython como `machine`, `time` y `json`, además de la lógica para controlar el driver de motores.

### 9.4 Consultar los archivos de la ESP32

```bash
mpremote connect /dev/ttyUSB0 fs ls
```

Si ya existe un `main.py`, puedes respaldarlo primero:

```bash
mpremote connect /dev/ttyUSB0 \
    fs cp :main.py ./esp32_main_backup.py
```

Ejecuta el respaldo desde una carpeta donde quieras guardar la copia. Si el archivo aún no existe en la ESP32, este comando no será necesario.

### 9.5 Copiar main.py a la ESP32

Una vez que tengas el verdadero firmware MicroPython:

```bash
cd ~/robot-motion-ros2
```

Ejecuta:

```bash
mpremote connect /dev/ttyUSB0 \
    fs cp firmware/esp32/main.py :main.py
```

El prefijo `:` indica que el destino se encuentra dentro del sistema de archivos de la ESP32.

Comprueba:

```bash
mpremote connect /dev/ttyUSB0 fs ls
```

Debes encontrar `main.py`.

### 9.6 Reiniciar la ESP32

Con los motores desenergizados para esta primera prueba:

```bash
mpremote connect /dev/ttyUSB0 reset
```

MicroPython ejecuta automáticamente `main.py` al iniciar, después de `boot.py`, cuando esos archivos existen.

Para consultar la salida del programa:

```bash
mpremote connect /dev/ttyUSB0 repl
```

No abras simultáneamente el mismo puerto desde `mpremote` y desde el nodo de ROS 2.

### 9.7 Probar código antes de instalarlo

Durante el desarrollo puedes ejecutar un archivo MicroPython sin guardarlo permanentemente en la ESP32:

```bash
mpremote connect /dev/ttyUSB0 \
    run firmware/esp32/main.py
```

Este procedimiento es útil para realizar pruebas antes de copiar el programa como `main.py`.

Se recomienda probar primero el procesamiento de los comandos sin conectar la alimentación de los motores.

## 10. Protocolo de comunicación Raspberry Pi–ESP32

El nodo `motion_controller` utiliza comunicación serial a 115200 baudios.

Los comandos se envían como mensajes JSON, terminados con un salto de línea.

Ejemplo de avance:

```json
{"m1":50,"m2":50}
```

Ejemplo de reversa:

```json
{"m1":-50,"m2":-50}
```

Ejemplo de paro:

```json
{"m1":0,"m2":0}
```

`m1` y `m2` son valores de mando limitados entre -100 y 100.

La ESP32 debe implementar la interpretación de esos mensajes y convertirlos en señales de control de los motores.

El firmware también debe contar con un tiempo de espera que detenga los motores si dejan de recibirse comandos, incluso cuando la Raspberry Pi se desconecte o el programa falle.

## 11. Ejecutar el nodo robot_motion

Una vez que el firmware está instalado, conecta la ESP32 a la Raspberry Pi e identifica el puerto.

```bash
cd ~/robot-motion-ros2

source /opt/ros/jazzy/setup.bash
source install/setup.bash
```

Ejecutar:

```bash
ros2 run robot_motion motion_controller
```

Si necesitas otro puerto:

```bash
ros2 run robot_motion motion_controller \
    --ros-args \
    -p serial_port:=/dev/ttyACM0
```

Parámetros disponibles:

| Parámetro | Predeterminado |
|---|---|
| `serial_port` | `/dev/ttyUSB0` |
| `wheel_separation` | `0.16` m |
| `max_wheel_speed` | `0.30` m/s |

Los valores de dimensiones y velocidades deben ajustarse al robot real.

## 12. Control mediante teclado

Instala el paquete:

```bash
sudo apt update
sudo apt install ros-jazzy-teleop-twist-keyboard -y
```

### Terminal 1: controlador de motores

```bash
source /opt/ros/jazzy/setup.bash
source ~/robot-motion-ros2/install/setup.bash

ros2 run robot_motion motion_controller
```

### Terminal 2: teclado

```bash
source /opt/ros/jazzy/setup.bash

ros2 run teleop_twist_keyboard teleop_twist_keyboard \
    --ros-args \
    -p stamped:=false \
    -p speed:=0.10 \
    -p turn:=0.70 \
    -p repeat_rate:=10.0 \
    -p key_timeout:=0.8 \
    -r cmd_vel:=/cmd_vel
```

Control:

```text
       u    i    o
       j    k    l
       m    ,    .
```

| Tecla | Movimiento |
|---|---|
| `i` | Avanzar |
| `,` | Retroceder |
| `j` | Girar a la izquierda |
| `l` | Girar a la derecha |
| `k` | Detener |
| `u` / `o` | Avanzar girando |
| `m` / `.` | Retroceder girando |
| `q` / `z` | Incrementar / reducir velocidades |
| `Ctrl + C` | Terminar teleoperación |

Para verificar los mensajes:

```bash
ros2 topic echo /cmd_vel
```

El nodo espera mensajes de tipo `geometry_msgs/msg/Twist`.

## 13. Streaming de cámara

### Instalar dependencias

```bash
cd ~/robot-motion-ros2/services/camera_stream

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Identificar la cámara

```bash
v4l2-ctl --list-devices
```

### Iniciar streaming

```bash
python camera_stream.py \
    --device /dev/video0 \
    --width 640 \
    --height 480 \
    --fps 30 \
    --port 8081
```

Desde otra computadora en la misma red, abre:

```text
http://IP_RASPBERRY:8081
```

WebRTC es el método preferido de visualización. MJPEG queda disponible como alternativa.

El servicio no tiene autenticación y debe utilizarse en una red local de confianza.

## 14. Ejecutar el robot desde una Mac

El robot puede utilizarse sin monitor conectado a la Raspberry Pi.

### Terminal 1 de la Mac: conexión SSH y motores

```bash
ssh usuario@robot-pi.local
```

Dentro de la Raspberry Pi:

```bash
source /opt/ros/jazzy/setup.bash
source ~/robot-motion-ros2/install/setup.bash

ros2 run robot_motion motion_controller
```

### Terminal 2 de la Mac: conexión SSH y teclado

```bash
ssh usuario@robot-pi.local
```

Dentro de la Raspberry Pi:

```bash
source /opt/ros/jazzy/setup.bash

ros2 run teleop_twist_keyboard teleop_twist_keyboard \
    --ros-args \
    -p stamped:=false \
    -p speed:=0.10 \
    -p turn:=0.70 \
    -p repeat_rate:=10.0 \
    -p key_timeout:=0.8 \
    -r cmd_vel:=/cmd_vel
```

### Terminal 3 de la Mac: conexión SSH y cámara

```bash
ssh usuario@robot-pi.local
```

Dentro de la Raspberry Pi:

```bash
cd ~/robot-motion-ros2/services/camera_stream
source .venv/bin/activate
python camera_stream.py
```

### Navegador de la Mac

Abrir:

```text
http://robot-pi.local:8081
```

Si el nombre no resuelve, utiliza la IP.

Con esta configuración, la Mac permite controlar el movimiento por SSH y visualizar el entorno del robot mediante el navegador.

## 15. Actualizar el repositorio

Cuando existan nuevos cambios en GitHub:

```bash
cd ~/robot-motion-ros2

git pull origin main

source /opt/ros/jazzy/setup.bash

colcon build --symlink-install

source install/setup.bash
```

Si también se actualizó el firmware MicroPython:

```bash
source ~/.venvs/mpremote/bin/activate

mpremote connect /dev/ttyUSB0 \
    fs cp firmware/esp32/main.py :main.py
```

Este último comando debe ejecutarse únicamente cuando el archivo sea código MicroPython válido para la ESP32. Detén primero `motion_controller` y cualquier otro proceso que tenga abierto el puerto serial.

Si el firmware nuevo ya se copió y está listo para ejecutarse:

```bash
mpremote connect /dev/ttyUSB0 reset
```

Después puedes iniciar nuevamente el controlador de ROS 2.

## 16. Diagnóstico de problemas

| Problema | Qué revisar |
|---|---|
| Raspberry Pi no aparece en la red | Wi-Fi, IP, red de invitados o aislamiento de clientes |
| SSH rechaza conexión | Servicio SSH, dirección IP, usuario y firewall |
| `robot-pi.local` no resuelve | Avahi, mDNS o utilizar la IP |
| No aparece `/dev/ttyUSB0` | Cable USB, alimentación, controlador USB y puerto |
| Error `Permission denied` | Grupo `dialout` |
| `mpremote` no conecta | Puerto ocupado, MicroPython instalado y cable USB |
| El robot no responde | `/cmd_vel`, puerto serial, firmware y driver |
| Los motores giran al revés | Cableado y correspondencia de los canales |
| La cámara no abre | Dispositivo `/dev/videoX` y permisos |
| WebRTC no conecta | Probar `/mjpeg`, comprobar red y navegador |

Para revisar si el puerto serial está ocupado:

```bash
sudo fuser -v /dev/ttyUSB0
```

No ejecutes simultáneamente el controlador ROS 2, una herramienta de carga de firmware y un script de pruebas utilizando el mismo puerto.

## 17. Seguridad

Durante las primeras pruebas, mantén las ruedas levantadas y separa la alimentación de los motores de la alimentación de la Raspberry Pi y la ESP32, respetando las conexiones de tierra que requiera el driver.

Prueba primero comandos de velocidad cero y luego incrementa gradualmente el mando.

El sistema debe poder detenerse aunque falle la computadora que publica los comandos. El timeout implementado en `motion_controller` es una protección adicional, pero no sustituye el paro de seguridad en la ESP32 ni un medio físico de desconexión.

## Referencias

- [ROS 2 Jazzy — Instalación oficial](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)
- [ROS 2 Jazzy — Tutoriales](https://docs.ros.org/en/jazzy/Tutorials.html)
- [teleop_twist_keyboard](https://github.com/ros2/teleop_twist_keyboard)
- [MicroPython — Documentación de mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html)
- [MicroPython — Firmware para ESP32](https://micropython.org/download/)
- [Repositorio robot-motion-ros2](https://github.com/CharlyMercury/robot-motion-ros2)
