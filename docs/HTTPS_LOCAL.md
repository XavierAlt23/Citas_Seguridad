# HTTPS local sin advertencia en Brave

La aplicación ya servía HTTPS. La advertencia provenía de un certificado autofirmado que el navegador no tenía registrado como confiable.

Se registró exclusivamente `.local/tls-cert.pem` como **servidor SSL confiable** en el almacén NSS del usuario, con el nombre `Consulta Clara - localhost HTTPS` y atributos `P,,`. No se instaló una autoridad certificadora y no se añadieron opciones para ignorar errores de certificados. El asistente comprueba vigencia y SAN: solo admite `localhost` y direcciones loopback.

```bash
.venv/bin/python scripts/trust_local_https.py
.venv/bin/python scripts/https_check.py
```

Resultado verificado: HTTPS 200, TLS 1.3, contexto seguro y `ignore_https_errors=False` en Brave. La evidencia se conserva en `evidence/https-trusted.json`. La aplicación y la base Docker siguen ejecutándose; no se cambiaron sesiones ni credenciales.

Abre https://localhost:8443. Si una ventana abierta conserva la advertencia anterior, reinicia Brave para recargar su confianza. La instalación afecta a este usuario del equipo; otro equipo debe registrar su propio certificado. No equivale a un certificado público.

Para retirar únicamente la confianza de la demo:

```bash
.venv/bin/python scripts/trust_local_https.py --uninstall
```

Las herramientas NSS se descargaron de los repositorios Ubuntu y se extrajeron bajo `.local/https-tools`, sin instalar paquetes globales ni modificar el almacén de certificados del sistema.

Referencia oficial: [Chromium, gestión de certificados Linux](https://chromium.googlesource.com/chromium/src/+/HEAD/docs/linux/cert_management.md). Chromium admite `P,,` para confiar en un certificado servidor autofirmado; cuando existe `~/.pki/nssdb`, utiliza ese almacén compartido.
