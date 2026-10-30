# Revisión de seguridad de la implementación

Revisión sobre código y pruebas del prototipo; no es pentest externo ni certificación. Se aplicaron las guías locales de validación de backend, frontend, base y seguridad. El informe original y las figuras son la referencia de alcance.

## Controles con evidencia

- Autenticación completa solo tras contraseña y MFA; cookie emitida por el login real comprobada. El código TOTP no se acepta dos veces y se limita por usuario.
- Autorización en servidor por propietario, profesional, centro y aseguradora; pruebas de acceso cruzado y de función prohibida.
- Orden, moneda, monto y transición de estado validados en webhook; claves por socio, firma del cuerpo y metadatos, ventana temporal y nonce con unicidad PostgreSQL.
- Operación idempotente ligada al contenido. La clave repetida con otro contenido se rechaza; pago repetido no emite otro aviso ni reembolso.
- Reservas y pagos transaccionales, bloqueo de franja en orden consistente y restricción única parcial en PostgreSQL; prueba de 100 hilos.
- Consultas ORM parametrizadas; filtros de entrada y límites de tamaño; escape de plantilla y CSP; CSRF en todas las mutaciones de navegador, con excepción exclusiva de los endpoints firmados.
- Rol SQL web sin superusuario ni DDL; auditoría sin UPDATE/DELETE/TRUNCATE, trigger append-only y cadena HMAC comprobada.
- No existe historia clínica ni formulario de tarjetas; referencias de póliza y secretos MFA cifrados. Avisos neutrales y exportación propia auditada.
- Copia cifrada restaurada en otra base, sesiones invalidadas y disociación reaplicada desde marcadores. Caso de copia anterior a supresión comprobado.
- Privilegios de personal requieren dos operadores distintos y revocan sesiones del afectado. Un paciente no puede promoverse desde el panel.

## Límites relevantes para el riesgo residual

| Relevancia | Hallazgo confirmado | Tratamiento |
|---|---|---|
| Operativa / bloqueo del entorno | No hay Docker CLI/daemon/socket; sudo pide contraseña | Compose y arranque preparados; ejecutar Docker en la máquina de defensa. Validación aquí sobre PostgreSQL 16 aislado |
| Alta fuera del alcance local | Un host y una instancia DB siguen siendo punto único de fallo | Réplica, balanceador, disco/host de backup externo y simulacro de pérdida de infraestructura antes de uso real |
| Alta frente a compromiso de host | Claves, owner de DB, procesos y copias predeterminadas comparten usuario/host | Vault/KMS, custodias separadas, usuario de scheduler distinto, backup y anclaje externos |
| Media de disponibilidad | La ráfaga de 2.000 solicitudes tuvo timeouts y 429; cuotas por IP afectan NAT compartido | Calibrar con SLO, cuotas de cuenta, generadores distribuidos y defensa de borde; no declarar éxito del escenario |
| Media de sesión | Cookie robada vigente sigue siendo credencial portadora | TLS/HttpOnly/SameSite, expiración, MFA y revocación; protección del dispositivo y reautenticación adicional en producción |
| De integración | Los adaptadores no simulan latencia/fallas de un socio remoto, antifraude comercial ni conciliación real | Contratos, allowlist de destinos, timeout, reintentos con presupuesto, circuit breaker y webhook real antes de sustituir los simuladores |
| De privacidad y legitimación | Evidencia de parentesco sintética; plazos fiscales no determinados | Validación real con responsable competente; financiero conservado y legal hold, sin fingir verificación civil |
| De cobertura de pruebas | WAF acotado y pruebas propias; sin pentest exhaustivo/DAST independiente | Revisión externa, análisis de dependencias continuo y pruebas ampliadas antes de tratar datos reales |

No se encontró en los escenarios ejecutados acceso cruzado permitido, confirmación por webhook falso ni sobreventa del cupo. Esa afirmación se limita a las pruebas guardadas; no certifica ausencia universal de vulnerabilidades. No se reescribieron las estimaciones residuales del informe como si fueran mediciones.
