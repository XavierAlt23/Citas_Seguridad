# Consulta Clara — demo local defendible

Implementación del documento **Informe_ESPE_Formato_Corregido.docx**, incluido el contenido de sus siete figuras. Aplicación Django local con HTTPS, PostgreSQL 16 en Docker, cinco aseguradoras y pasarela simuladas. Los flujos guardan datos y ejecutan controles reales.

La guía para exponer está en **[DEMO_Y_DEFENSA.md](DEMO_Y_DEFENSA.md)**. La trazabilidad completa está en **[docs/MATRIZ_CUMPLIMIENTO.md](docs/MATRIZ_CUMPLIMIENTO.md)**. Consulta los límites y resultados en **[docs/VALIDACION.md](docs/VALIDACION.md)**.

## Arranque en Linux / macOS

Requisitos: Python 3.12 o posterior, Docker Engine/Desktop con Compose v2 y puertos locales 8443 y 55432 libres. La primera instalación necesita internet; la aplicación ya preparada funciona sin servicios externos. No se necesita Node.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python scripts/setup.py
bash scripts/run.sh
```

Si usas `uv`, puedes sustituir las primeras dos líneas por:

```bash
uv venv .venv
uv pip sync --python .venv/bin/python requirements.lock
```

Abre **https://localhost:8443**. El certificado local se puede registrar como confiable en Brave/Chromium para tu usuario de Linux:

```bash
.venv/bin/python scripts/trust_local_https.py
```

El asistente requiere `certutil` (`libnss3-tools`) o la copia local preparada en este equipo. Confía únicamente en el certificado servidor de esta demo (`P,,` en NSS), sin instalar una CA ni desactivar validación TLS. Si el navegador conserva una advertencia anterior, reinícialo. Para retirar solo esta confianza ejecuta el mismo comando con `--uninstall`. Si regeneras el certificado, ejecuta otra vez el asistente. Las cookies son Secure; utiliza siempre la URL HTTPS con el puerto 8443.

`setup.py` crea secretos aleatorios privados, arranca PostgreSQL con Compose, espera su healthcheck, migra como propietario, concede permisos mínimos al rol de la aplicación, genera 20 centros, 150 profesionales y horarios futuros, y crea las cuentas de ensayo. Repetirlo agrega horarios sin borrar citas ni reemplazar contraseñas.

Las contraseñas de las 13 cuentas sintéticas están **solo en `.local/access.md`** (archivo privado, fuera de Git). Para el segundo factor de una cuenta sembrada:

```bash
.venv/bin/python manage.py demo_code paciente.a
```

Primero ingresa usuario y contraseña en la web; después ejecuta el comando. Cada inicio crea un desafío nuevo con un código distinto al anterior. El código vence a los cinco minutos, se consume al entrar y queda vinculado a ese acceso; iniciar de nuevo invalida cualquier desafío pendiente anterior. Ejecutar el comando dos veces en el mismo acceso pendiente muestra el mismo código de ese acceso. Las cuentas nuevas no sembradas conservan MFA con aplicación autenticadora/QR (TOTP estándar de 30 segundos). La entrega por consola simula el canal de entrega del OTP para la demo: no es SMS/correo real ni una ruta HTTP.

Si bloqueas una cuenta sintética durante la exposición, el operador local puede ejecutar `.venv/bin/python manage.py demo_unlock paciente.a`; el desbloqueo queda auditado y no habilita recuperación de cuentas reales.

## Cuentas de ensayo

| Usuario | Ámbito |
|---|---|
| `paciente.a`, `paciente.b` | Cada paciente ve sus citas y pólizas |
| `medico.a`, `medico.b` | Cada profesional ve su agenda asignada |
| `recepcion.a`, `recepcion.b` | Centros 01 y 02, respectivamente |
| `seguro.1` … `seguro.5` | Una aseguradora por cuenta |
| `operador.a`, `operador.b` | Métricas, auditoría, revisión independiente y cambios de rol con doble aprobación |

No compartas una sesión entre actores: usa perfiles diferentes del navegador o cierra sesión antes de cambiar de cuenta.

## Operación y pruebas

```bash
# Volumen del informe, sin crear 40.000 contraseñas utilizables
.venv/bin/python manage.py seed_scale

# Comprobaciones y pruebas en una base test_consultas separada
.venv/bin/python scripts/check.py

# Integridad de auditoría y tareas de retención
.venv/bin/python manage.py verify_audit
.venv/bin/python manage.py maintenance
.venv/bin/python scripts/audit_retention.py

# Renovar claves de los conectores simulados (después reinicia la aplicación)
.venv/bin/python scripts/rotate_integrations.py

# Copia cifrada y restauración no destructiva en una NUEVA base restore_...
.venv/bin/python scripts/backup.py backup
.venv/bin/python scripts/backup.py restore-drill

# Ensayo con cuenta ficticia vencida: la copia no debe resucitar sus datos
.venv/bin/python scripts/retention_drill.py

# Carga acotada, solo contra este localhost
.venv/bin/python scripts/load.py --users 30 --seconds 10

# Tamaño, conexiones y plan de consulta público (solo lectura)
.venv/bin/python scripts/db_metrics.py

# Ráfaga extrema desde una misma IP (es esperable que active 429)
.venv/bin/python scripts/load.py --users 2000 --seconds 10

# 2.000 usuarios virtuales con pausas, orígenes TCP locales distintos
.venv/bin/python scripts/load.py --users 2000 --seconds 50 --ramp 30 --think 30 --distinct-ips
```

`run.sh` ejecuta mantenimiento cada minuto, auditoría con retención y copia cada hora. Los fallos se muestran en consola; no se silencian como si hubiera copia. Para un destino separado configura `BACKUP_DIR=/ruta/a/otro/disco` antes del arranque. El destino predeterminado `.local/backups` está cifrado pero **sigue en el mismo host**. Las copias locales rotan tras 24 horas; conserva la clave de descifrado en otro lugar seguro si trasladas copias. La restauración elimina sesiones, reaplica las disociaciones registradas desde la copia y ejecuta retención antes de dejar lista la base restaurada. El ensayo no cambia la conexión de la aplicación ni borra su base principal.

Con la aplicación arrancada puedes ejecutar opcionalmente la prueba visual:

```bash
.venv/bin/python -m playwright install chromium
.venv/bin/python scripts/browser_check.py
```

El script prefiere Brave si está disponible y, en otro caso, Chromium de Playwright. Necesita dependencias nativas del navegador. Usa únicamente cuentas de ensayo y genera una cita cancelada, un reembolso y un vínculo ficticio verificado. Evidencia: `evidence/browser.json` y `evidence/screenshots/`.

## Detener y volver a iniciar

Ctrl+C detiene la aplicación y el planificador. La base se mantiene en Docker:

```bash
docker compose stop db
docker compose up -d --wait db
bash scripts/run.sh
```

No uses `docker compose down -v` para detener: elimina el volumen de datos. No borres `.env`, `.local/backup.key` ni las claves de campo si necesitas descifrar datos existentes. El repositorio no contiene esos secretos.

## Estructura

| Ruta | Contenido |
|---|---|
| `app/models.py` | Entidades, relaciones y restricciones de base |
| `app/services.py` | Reservas, pagos, cobertura y cancelación transaccionales |
| `app/security.py`, `app/waf.py` | Cifrado, firmas, nonce, tasa, auditoría y filtro de entrada |
| `app/views.py` | Rutas, autenticación/MFA y autorización por rol y objeto |
| `app/tests.py` | Casos negativos, positivos y 100 contendientes reales |
| `compose.yaml` | PostgreSQL persistente, puerto solo loopback, healthcheck |
| `scripts/` | Preparación, ejecución, pruebas, carga y continuidad |
| `docs/INFORME_EXTRAIDO.md` | Texto íntegro del DOCX para consultar sin Word |

## Estado del entorno de construcción

El entorno donde se creó el proyecto no disponía de Docker Engine/CLI. Se validó contra PostgreSQL 16 aislado usando los mismos modelos y migraciones; `compose.yaml` es la vía de despliegue entregada y debe ejecutarse con Docker en la máquina de la defensa. La alternativa `setup.py --existing-postgres` y `backup.py --native` existe solo para reproducir esa validación, no sustituye el requisito de Docker en la presentación.

Los procesos aislados de validación se detienen al entregar para dejar libres los puertos del arranque con Docker. Los datos locales de ensayo y evidencias se conservan. El esquema DDL de la aplicación se puede revisar en `docs/ESQUEMA.sql`.

No se garantiza protección frente a todo ataque. La evidencia cubre escenarios identificados en el informe; producción requiere proveedores reales, segregación de infraestructura, gestión externa de secretos, revisión independiente, monitoreo y validación de capacidad.
