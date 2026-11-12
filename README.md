# Robótica móvil con ROS 2 y Python

Este proyecto busca acercar a jóvenes y estudiantes universitarios a la robótica móvil mediante actividades prácticas de programación, electrónica y control de movimiento. El propósito es que comprendan cómo funciona un robot, desde el envío de instrucciones hasta el accionamiento de sus motores, utilizando herramientas que también se emplean en proyectos profesionales.

El desarrollo utiliza **ROS 2 y Python** para controlar un robot móvil de tracción diferencial. Actualmente cuenta con un paquete llamado `robot_motion`, que recibe comandos de velocidad mediante el tópico `/cmd_vel`, calcula las velocidades correspondientes a cada rueda y envía las instrucciones por comunicación serial a una ESP32.

A través de este proyecto, los estudiantes aprenden a crear nodos de ROS 2, trabajar con tópicos y mensajes, aplicar conceptos de cinemática diferencial y establecer comunicación entre una computadora y un microcontrolador. También conocen aspectos básicos de seguridad, como detener los motores cuando dejan de recibirse instrucciones.

El proyecto está pensado para desarrollarse de manera progresiva, comenzando con movimientos básicos y avanzando hacia la integración de sensores, odometría, simulación y navegación autónoma.

La intención es que los estudiantes puedan construir, programar, probar y mejorar su propio robot, comprendiendo el funcionamiento de cada componente en lugar de limitarse a ejecutar código previamente desarrollado.
