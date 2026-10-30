# Acta de ejecución

Entorno: PostgreSQL 16 nativo aislado; Docker no disponible. Todos los datos son sintéticos.

- Suite de backend/seguridad: **30/30 aprobadas**.
- Concurrencia real: **1 confirmación y 99 conflictos de 100 contendientes**.
- Navegador: recorrido completo aprobado, escritorio y móvil, sin errores JavaScript.
- Restauración cifrada: checksum y cadena válidos; sesiones revocadas.
- Prueba de supresión: la restauración no reintroduce contacto ni póliza disociados.

Restauración final:

```json
{
  "staging_database": "restore_20261030_014456",
  "restored_rows": {
    "app_user": 40013,
    "app_appointment": 2,
    "app_payment": 2,
    "app_refund": 2,
    "app_coverage": 2,
    "app_audit": 94
  },
  "checksum_verified": true,
  "audit_verified": true,
  "sessions_revoked": true,
  "tombstones_applied": 2,
  "rto_seconds": 3.424,
  "backup_age_seconds_rpo_upper_bound": 4.012,
  "rto_target_seconds": 14400,
  "rpo_target_seconds": 3600,
  "within_rto": true,
  "within_rpo": true,
  "note": "Ensayo sobre base NUEVA; no simula pérdida del host ni alta disponibilidad.",
  "mode": "native-validation"
}
```

Carga y límites: consulta [VALIDACION.md](VALIDACION.md). Los dos escenarios de 2.000 usuarios permanecen separados; la ráfaga tuvo errores, el escenario con pausas no.

Los procesos de validación se detienen al entregar para liberar los puertos del arranque con Docker. Para repetir la demostración usa el README.


## Actualización posterior: MFA y Docker

Docker Desktop operativo. Suite actual: **34/34** aprobadas sobre PostgreSQL en Docker. Reingreso HTTPS con código distinto por login verificado (`evidence/mfa-reentry.json`); rechazo de código anterior, caducado o de otra sesión. Se conserva arriba el acta de los ensayos iniciales.
