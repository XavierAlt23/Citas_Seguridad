# Trazabilidad del informe a implementación y pruebas

Fuente: DOCX original completo, tablas y siete figuras. El texto íntegro se conserva en `INFORME_EXTRAIDO.md`. «Implementado» se refiere a la demo sintética; no convierte una integración simulada en un proveedor contratado.

## Requisitos S01–S14

| ID | Implementación / demostración | Ubicación | Prueba / límite |
|---|---|---|---|
| S01 | Búsqueda pública, reserva, cancelación, copago, reembolso y cobertura | `views.py`, `services.py`, plantillas | P06/P07/P08; cupo único en PostgreSQL |
| S02 | Identidad/contacto mínimos al crear cuenta para confirmar; horarios públicos | `RegisterForm`, `home`, `booking` | P01/P09; no se valida identidad civil real |
| S03 | Póliza opcional del titular y respuesta limitada de elegibilidad | `Policy`, `Coverage`, `partner_coverage` | P02/P05; datos sintéticos, no verificaciones comerciales |
| S04 | Sin historia clínica en este módulo, profesional sin dato de pago | Esquema y panel profesional | P01/P07; el sistema clínico permanece fuera del alcance |
| S05 | No se solicitan religión, ingresos, empleador, GPS ni contactos | Registro y esquema | P01; no hay permisos de geolocalización/cámara/micrófono |
| S06 | Evidencia ficticia, vínculo pendiente y operador verificador | `Representation`, `DependentForm` | P03; no es verificación legal de parentesco |
| S07 | Cinco claves independientes; scope, HMAC, timestamp y nonce | `security.py`, `integration`, adaptador local | P05/P06; adaptador en proceso, sin fallos/latencia de red externa |
| S08 | Filtro por aseguradora y por objeto en cada solicitud | `api_policy`, `partner_coverage`, panel | P02/P05 |
| S09 | Bandeja con plantilla neutral única | `Notice`, panel paciente | P10; sin entrega SMS/push real |
| S10 | MFA, cookie Secure/HttpOnly/Strict, sesión de servidor revocable y expirable | Login/MFA/logout y settings | P04/P09; cookie robada vigente conserva riesgo de uso |
| S11 | PSP sintético, solo importe/moneda/estado/referencia; firma de evento | `Payment`, `Refund`, `apply_payment` | P01/P06; no hay tarjetas ni pagos monetarios reales |
| S12 | Cuentas individuales, lecturas/cambios/exportación/denegaciones auditados | `Audit`, middleware, seguridad | P11; trigger y permisos, no resistencia a administrador total del host |
| S13 | BD en Compose, web local, backups cifrados, scheduler y ensayo en otra base | Compose y `scripts/` | P12; host único local y réplica no implementada |
| S14 | Finalidad sin IA/publicidad, exportación/cierre, disociación/retención, legal hold y marcadores para restauración | Aviso, `maintenance`, `audit_retention`, `backup` | P14; financiero conservado hasta definir plazo aplicable; custodia de copias externas requiere política propia |

## Riesgos R01–R20 y su defensa

La puntuación P×I inherente y la residual de las Tablas 5.2/5.3 permanecen como estimaciones del informe. La demo agrega evidencia específica y no sustituye una nueva valoración formal.

| Riesgo | Activo / escenario | Prevención | Detección y corrección | Evidencia |
|---|---|---|---|---|
| R01 | Fuga de expediente excesivamente recolectado | No hay expediente en agenda | Inspección de esquema/formulario | P01 |
| R02 | Seguro A accede a pacientes de B | Filtro por tenant, póliza y beneficiario | Denegación auditada | P02/P05 |
| R03 | Representación falsa de menor | Vínculo pendiente hasta revisión independiente | Actor y fecha de validación | P03 y navegador |
| R04 | Robo/reutilización de sesión | MFA, TLS, cookie protegida, sin token por URL | Revocación y expiración | P04/P09 |
| R05 | Robo de tarjetas | No almacenar ni recibir PAN/CVV | Revisión de DDL y contratos | P01/P06 |
| R06 | Acciones no atribuibles | Cuentas individuales, cadena HMAC | Verificación y panel de auditoría | P11 |
| R07 | Caída/corrupción/ransomware | Proceso de backup cifrado y permisos mínimos | Restauración nueva, checksum y RTO/RPO | P12; aislamiento de host sigue pendiente |
| R08 | IA/publicidad obligatoria | No hay datos/función/casilla de esa finalidad | Aviso y exportación de datos | P01/P14 |
| R09 | Aviso expone salud | Plantilla neutra | Prueba de contenido sin especialidad/póliza | P10; push no integrado |
| R10 | Socio malicioso/replay | Firma+scope+organización+beneficiario+tiempo+nonce | Rechazos auditados; idempotencia de pago | P05/P06 |
| R11 | BOLA sobre cita | Propietario/agenda/centro antes de devolver objeto | 403, intento atribuible | P07 |
| R12 | Doble reserva | Bloqueo de franja y restricción única parcial | Conflicto de negocio; expiración de retenciones | P08, 100 contendientes |
| R13 | Fuerza bruta/credential stuffing | Argon2id, MFA, cuotas de usuario e IP | Alertas y bloqueo temporal | P09 |
| R14 | Agotamiento de API | 300/min/IP, límites de cuerpo, consultas y workers, timeouts DB | HTTP 429, métricas y carga | `load-*.json`; no defensa de DDoS de red |
| R15 | SQL injection | ORM parametrizado y rol sin DDL/superusuario | WAF complementario y prueba de integridad | P13 |
| R16 | Webhook falso confirma pago | HMAC del cuerpo/metadatos; importe/moneda/evento/estado | Rechazo, sin cambio de orden | P06 |
| R17 | Empleado ajeno consulta salud | Ausencia clínica y agenda asignada | Auditoría de lectura/denegación | P01/P07 |
| R18 | Secretos en código/logs | Generación aleatoria, archivos 0600, Git ignore, sin access log con tokens | Inspección estática y auditoría de acciones | Custodia local, no Vault ni rotación automática de claves de campo |
| R19 | Retención infinita/resurrección desde backup | Disociación, legal hold, purga acotada y tombstones | Job de vencimiento y restauración con supresiones | P14 y restore-drill |
| R20 | Escalamiento por función | Rol+ámbito, doble operador para cambiar permisos de personal | Sesiones revocadas y evento atribuible | Tests R20; no interfaz de promoción de pacientes |

## Plan P01–P14

| Prueba del informe | Ejecución entregada | Evidencia |
|---|---|---|
| P01 | Esquema sin datos prohibidos y cifrado de póliza | Tests y modelos |
| P02 | Acceso cruzado de póliza rechazado; acceso propio permitido | Tests API |
| P03 | Sin evidencia no se crea solicitud; sin revisión no se reserva; aprobado sí | Tests positivos/negativos + navegador |
| P04 | Sesión revocada/caducada no autentica | Tests de sesión |
| P05 | Scope, firma, beneficiario, organización, tiempo y nonce | Tests de contratos reales del endpoint |
| P06 | Webhook falso/monto incorrecto/replay no duplica ni confirma indebidamente | Tests de pago y DB |
| P07 | Paciente, centro y profesional ajeno reciben 403 | Tests y recorrido manual |
| P08 | Barrera, 100 hilos/usuarios, exactamente una confirmación | `concurrency.json` |
| P09 | Límite de intentos, alerta, contraseña+MFA real y no reutilización TOTP | `tests.json` |
| P10 | Texto neutral exacto | Test; bandeja en navegador, sin simulación de push del SO |
| P11 | Dos actores distintos; mutación de auditoría denegada; cadena íntegra | Test + `verify_audit` |
| P12 | Copia cifrada y pg_restore en base nueva, checksum, cadena, sesiones y tiempos | `restore.json`; no destrucción del host |
| P13 | Entradas SQL y XSS, escape de contenido desde DB, CSP, CSRF y WAF | Tests; no se presenta como DAST exhaustivo |
| P14 | Cuenta vencida disociada; legal hold respetado; marcadores de supresión | Tests + maintenance y restore |

## Figuras y tablas del documento

| Referencia | Implementación / explicación |
|---|---|
| Fig. 2.1 | Búsqueda, reserva/cancelación, cobertura, pago y agenda por actor; auditoría solo operador, más restrictiva que la flecha a recepción del dibujo |
| Fig. 2.2 | Flujo funcional completo y confirmación atómica después de PSP |
| Fig. 3.1 | BD de agenda sin clínica y conectores con propósito limitado |
| Fig. 4.1 | PWA, TLS, filtro WAF de aplicación, API, permisos, DB, auditoría y copias; WAF de borde y host redundante quedan fuera del despliegue local |
| Fig. 4.2 | Contratos seguros de seguro/PSP y plantilla neutral |
| Fig. 4.3 / Tabla 4.3 | Todas las entidades originales representadas; adicionales para nonce, cuota, reembolso, revisión, legal hold y supresión |
| Fig. 5.1 | BOLA reproducible con UUID conocido y 403 auditado |
| Tabla 3.2 | Plazos operativos implementados donde son definidos; financiero bajo conservación, sin inventar obligación tributaria |
| Tabla 4.4 | Dataset 40.000/150/20/5, concurrencia100, carga2000 y recuperación medida; no promesa de alta disponibilidad local |
| Tablas 5.1–5.3 | Modelo de amenaza, controles por riesgo y residual condicionado |
| Tabla 6.1 | Correspondencia ATT&CK conservada abajo |
| Tabla 7.1 / §7.1 | Casos comprobables y límites de aceptación explícitos |

## MITRE ATT&CK del capítulo 6

| Técnica | Riesgo | Control demostrado |
|---|---|---|
| T1110.004 Credential Stuffing | R13 | MFA y límites por cuenta/IP |
| T1078 Valid Accounts | R04/R17 | Revocación y permisos por objeto/ámbito |
| T1539 Steal Web Session Cookie | R04 | HttpOnly/Secure, TLS, expiración; riesgo de cookie vigente robada reconocido |
| T1199 Trusted Relationship | R10 | Claves de socio distintas y solicitudes propias |
| T1552.001 Credentials In Files | R18 | Secretos fuera de Git, archivos privados; no equivalencia con Vault |
| T1499.003 Application Exhaustion Flood | R14 | Cuotas, tamaño, timeout, mediciones de carga |
| T1485 Data Destruction | R07 | Backup cifrado y restauración en base nueva; host aislado aún necesario |
| T1098 Account Manipulation | R20 | Doble revisión, scope y revocación de sesión |

## Referencias de implementación consultadas

Documentación oficial consultada mediante Context7: [Django 5.2, contraseñas](https://docs.djangoproject.com/en/5.2/topics/auth/passwords/), [transacciones y bloqueos](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update), [restricciones](https://docs.djangoproject.com/en/5.2/ref/models/constraints/), [despliegue seguro](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/), [Docker Compose](https://docs.docker.com/compose/), [Playwright Python](https://playwright.dev/python/). Las referencias jurídicas y académicas del documento original se conservan en él y no se presentan como una auditoría legal realizada durante la implementación.
