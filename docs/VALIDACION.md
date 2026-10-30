# Validación ejecutada y límites de la entrega

Fecha local de los ensayos: 29 de octubre de 2026, America/Guayaquil (algunos archivos usan UTC y figuran el 30). Aplicación Django 5.2.18, PostgreSQL 16 y Python 3.13. La instalación documentada admite Python 3.12 o posterior; las versiones completas están en `requirements.lock`.

## Resultados comprobados

| Verificación | Resultado | Evidencia reproducible |
|---|---|---|
| Configuración Django de despliegue | Sin advertencias en `check --deploy` | `scripts/check.py` y log de pruebas |
| Esquema/migraciones | `makemigrations --check --dry-run` sin cambios | `scripts/check.py` |
| Suite backend/seguridad | 34 casos aprobados, sin errores (última ejecución en Docker) | `evidence/tests.json`, `test-run.log` |
| Reserva concurrente | 100 trabajadores, 100 pacientes, 1 confirmación y 99 conflictos | `evidence/concurrency.json` |
| Recorrido web | Login+MFA, cobertura, pago, confirmación, cancelación/reembolso, vínculo y paneles de roles aprobados | `evidence/browser.json` |
| Vista responsive | Escritorio 1440×1000 y móvil 390×844, sin desbordamiento raíz en las pantallas verificadas | `evidence/screenshots/` y browser-check |
| Errores JavaScript | Ninguno en el recorrido automatizado | `evidence/browser.json` |
| Rol SQL real de la web | No superusuario, sin CREATE en esquema, sin UPDATE/DELETE/TRUNCATE de auditoría | `evidence/runtime-permissions.json` |
| Integridad de auditoría | Cadena HMAC verificada | `manage.py verify_audit` |
| Backup/restore | pg_dump cifrado, pg_restore en base nueva, checksum y auditoría válidos, sesiones revocadas | `evidence/restore.json` |
| Supresión tras restaurar | Backup anterior a disociación: contacto y póliza permanecen disociados en la restaurada | `evidence/retention-restore.json` |
| Volumen | Se poblaron al menos 40.000 pacientes sintéticos, 150 profesionales, 20 centros, 5 aseguradoras | `runtime-permissions.json`; algún paciente adicional pertenece al ensayo de retención |
| Persistencia y consulta | Snapshot de tamaño/conexiones y EXPLAIN ANALYZE de consulta pública sin datos personales | `evidence/db-metrics.json`; no es medición del pico durante carga |

Los 34 casos incluyen positivos y negativos. No son 34 ataques diferentes: algunos verifican comportamiento funcional y otros distintos controles de un mismo riesgo. No se ejecutó una certificación, pentest independiente ni DAST exhaustivo.

## Mediciones de carga

Datos reales guardados en los JSON; no se han convertido los HTTP 429 en éxitos.

| Escenario | Peticiones | HTTP 200 | HTTP 429 | Errores de red | p95 |
|---|---:|---:|---:|---:|---:|
| 30 clientes, misma IP, ventana 8 s | 736 | 300 | 436 | 0 | 594,41 ms |
| Ráfaga 2.000, misma IP, ventana 10 s | 3.290 | 297 | 1.993 | 1.000 | 15.007,23 ms |
| 2.000 usuarios virtuales, rampa 30 s, pausa 30 s, ventana 50 s, IPs loopback distintas | 3.217 | 3.217 | 0 | 0 | 3.311,52 ms |

En el último escenario hubo un pico de **129 peticiones HTTP en curso**, no 2.000 peticiones simultáneas. El informe JSON registra 81,20 s de duración total y 39,62 peticiones/s usando ese tiempo de pared, que incluye las últimas pausas de los usuarios. Las muestras de RSS/CPU acumulada de los procesos web se guardan en el mismo archivo. Se usaron direcciones de origen TCP loopback distintas para representar clientes independientes; no se confió en cabeceras `X-Forwarded-For` ni se deshabilitó el rate limit.

**Conclusión de capacidad:** el escenario de búsqueda con 2.000 usuarios virtuales y pausas completó todas sus solicitudes; la ráfaga extrema no fue admitida sin fallos. No se estableció un SLO de latencia ni se probaron 2.000 reservas/pagos concurrentes, latencia de proveedores reales o alta disponibilidad. No es correcto afirmar «soporta cualquier carga de 2.000 usuarios». El límite por IP puede afectar usuarios tras un NAT compartido y debe calibrarse junto con cuotas por cuenta y controles de borde para producción.

El archivo `docs/capacidad.jmx` entrega un plan JMeter de 2.000 hilos, rampa de 120 segundos, tres iteraciones y pausa de 30 segundos. **No se ejecutó JMeter en este entorno.** Para ejecutarlo con JMeter instalado:

```bash
jmeter -n -t docs/capacidad.jmx -l evidence/jmeter.jtl -e -o evidence/jmeter-report
```

La prueba se dirige a HTTPS localhost y necesita aceptar el certificado de prueba en el almacén del cliente JMeter. Desde un solo IP verificará también la cuota; para medir admisión distribuida hacen falta generadores con sus propios IPs, sin falsificar cabeceras. Recoge asimismo CPU, RAM, conexiones y planes PostgreSQL; el JTL por sí solo no mide esos recursos del servidor.

## Continuidad y retención

La restauración se ejecutó en una base nueva sin borrar la base de la aplicación. Los tiempos y recuentos definitivos están en `evidence/restore.json`: en los ensayos observados con aproximadamente 40.000 cuentas se recuperó en pocos segundos, frente a RTO propuesto de 4 h, con copia recién creada frente a RPO propuesto de 1 h. La antigüedad de esa copia es una cota de ventana potencial de pérdida, no un cómputo de transacciones perdidas en un incidente real.

`retention_drill.py` crea exclusivamente una cuenta ficticia vencida, hace copia antes de disociarla, ejecuta mantenimiento y restaura después: comprueba que el contacto, póliza y acceso siguen disociados. Se reaplican marcadores de supresión de la base actual. Si se pierden a la vez el host, los marcadores y las claves, este procedimiento local no demuestra recuperación integral: los componentes deben custodiarse fuera del host.

El usuario web puede insertar y leer eventos de auditoría; el trigger bloquea su mutación y el rol no dispone de permisos SQL para alterarla. La purga de eventos vencidos se ejecuta con credenciales de propietario, bajo bloqueo y en una transacción, preservando un ancla HMAC del prefijo eliminado. Esta tarea separa permisos de base, pero ambos procesos siguen ejecutándose bajo el mismo usuario del sistema en la demo. El administrador de host es una frontera de confianza.

## Revisión visual

Se inspeccionaron capturas de escritorio, móvil, cita confirmada y panel operador. Se corrigieron la etiqueta pequeña y una posición absoluta del texto accesible de tabla que provocaba desbordamiento móvil. El recorrido posterior verificó el ancho del documento y la interacción. El detector mecánico también había marcado una familia tipográfica declarada que no se distribuía; se retiró para usar la pila del sistema sin red.

No había capacidad de subagentes para un revisor independiente: la revisión visual se realizó en el mismo proceso y no se presenta como auditoría externa.

## Límites y diferencias respecto de un despliegue productivo

| Elemento | Estado real |
|---|---|
| PostgreSQL en Docker | Compose entregado; **no se pudo ejecutar aquí**: no había CLI, daemon ni socket. Instalar el motor requiere contraseña administrativa. Se usó PostgreSQL 16 nativo aislado para verificar aplicación, migraciones, permisos y recuperación |
| Host redundante / réplica / balanceador | No implementados en una demo de un solo equipo. Los workers no equivalen a hosts independientes |
| WAF | Filtro de aplicación limitado, no ModSecurity/OWASP CRS ni WAF de borde |
| Secretos | Generados fuera de Git y archivos privados; rotación de claves de conectores disponible. No es Vault externo ni rotación automática de claves de datos/auditoría |
| Cifrado | Pólizas y secretos MFA cifrados, backups completos cifrados, TLS navegador→web. Sin cifrado transparente de volumen ni TLS de conexión loopback PostgreSQL |
| Cookies | Secure/HttpOnly/Strict, expiración/revocación comprobadas. Una cookie robada todavía vigente conserva riesgo de uso |
| Menores | Flujo de revisión y evidencia sintética; no acreditación de representación legal real |
| Cinco aseguradoras y PSP | Contratos, scopes, firmas y estados funcionales en simuladores locales. Sin contratos comerciales, red real, antifraude de proveedor ni conciliación bancaria |
| Notificaciones | Bandeja neutral; no SMS/correo/push real ni captura de una pantalla bloqueada del SO |
| Financiero | Conservación bloqueada hasta establecer el plazo aplicable; no se inventaron plazos fiscales |
| Copias predeterminadas | Cifradas y en directorio separado, pero en el mismo host. `BACKUP_DIR` permite otro disco; la clave y los marcadores también necesitan custodia externa |
| Retención de auditoría | Purga administrativa implementada y verificación con checkpoint; las pruebas corrientes verifican trigger/cadena, no un incidente de manipulación de administrador total |
| Disponibilidad a 2.000 | Escenario público con pausas medido; ráfaga extrema falló. No garantía para todos los flujos |
| Conformidad legal | Decisiones de diseño basadas en el informe. Sin dictamen ni certificación |

Estos límites deben decirse durante la defensa. El prototipo sí ejecuta la lógica de negocio y los controles señalados; los riesgos que necesitan infraestructura o terceros no se transforman en «resueltos» por escribir una etiqueta de seguridad.


## Actualización: Docker y códigos por inicio de sesión

Docker Desktop ya está operativo: PostgreSQL se ejecuta en el servicio Compose y la última suite pasó **34/34** sobre Docker. La limitación inicial de ausencia de Docker descrita arriba queda como antecedente histórico, resuelta para el arranque y estas pruebas. Las cuentas sintéticas ahora usan desafíos OTP de cinco minutos vinculados a la sesión previa; cada nuevo login genera otro código e invalida el pendiente anterior. El código se consume al entrar y su cifrado se elimina. Un MFA válido limpia los contadores de la cuenta; los fallos mantienen el límite. La consola simula la entrega del segundo factor; las cuentas nuevas con autenticador conservan TOTP estándar.

`evidence/mfa-reentry.json` verifica por HTTPS real con cookies Secure y CSRF: entrar, salir, crear otro desafío, rechazar el código viejo y aceptar el nuevo inmediatamente. `evidence/mfa-challenge-tests.log` contiene las 34 pruebas, incluidos expiración y rechazo de códigos de otra sesión. El desbloqueo local de paciente.a fue auditado.
