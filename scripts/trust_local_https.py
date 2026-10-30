"""Trust only this localhost server certificate in the current user's NSS store."""
import argparse
from datetime import datetime, timezone
import ipaddress
from pathlib import Path
import shutil
import subprocess
import sys
from cryptography import x509
from cryptography.hazmat.primitives import hashes

ROOT = Path(__file__).resolve().parent.parent
NICKNAME = 'Consulta Clara - localhost HTTPS'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uninstall', action='store_true', help='Retira solo la confianza de esta demo.')
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        raise SystemExit('Este asistente configura NSS en Linux. En otros sistemas importa el certificado local con el gestor de certificados del navegador.')
    certutil = shutil.which('certutil')
    bundled = ROOT / '.local/https-tools/extracted/usr/bin/certutil'
    if not certutil and bundled.is_file(): certutil = str(bundled)
    if not certutil:
        raise SystemExit('Falta certutil. Instala libnss3-tools y vuelve a ejecutar este asistente.')
    old_store = Path.home() / '.pki/nssdb'
    new_store = Path.home() / '.local/share/pki/nssdb'
    store = old_store if (old_store/'cert9.db').exists() else new_store
    database = 'sql:' + str(store)
    if not (store/'cert9.db').exists():
        if args.uninstall: return
        store.mkdir(parents=True, exist_ok=True, mode=0o700)
        subprocess.run([certutil, '-N', '--empty-password', '-d', database], check=True)
    exists = subprocess.run([certutil, '-L', '-d', database, '-n', NICKNAME], capture_output=True).returncode == 0
    if args.uninstall:
        if exists: subprocess.run([certutil, '-D', '-d', database, '-n', NICKNAME], check=True)
        print('Retirada la confianza de Consulta Clara; los demás certificados no se modificaron.')
        return
    path = ROOT / '.local/tls-cert.pem'
    cert = x509.load_pem_x509_certificate(path.read_bytes())
    now = datetime.now(timezone.utc)
    if not cert.not_valid_before_utc <= now < cert.not_valid_after_utc:
        raise SystemExit('El certificado no está vigente. Revisa el reloj o renueva el certificado antes de confiar en él.')
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    dns = set(san.get_values_for_type(x509.DNSName))
    ips = set(san.get_values_for_type(x509.IPAddress))
    if dns != {'localhost'} or not ips.issubset({ipaddress.ip_address('127.0.0.1'), ipaddress.ip_address('::1')}):
        raise SystemExit('Solo se permite confiar en el certificado de localhost y sus direcciones loopback.')
    try:
        if cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
            raise SystemExit('Se esperaba un certificado de servidor, no una autoridad certificadora.')
    except x509.ExtensionNotFound:
        pass
    if exists:
        prior = subprocess.run([certutil, '-L', '-a', '-d', database, '-n', NICKNAME], check=True, capture_output=True).stdout
        prior_cert = x509.load_pem_x509_certificate(prior)
        if prior_cert.fingerprint(hashes.SHA256()) != cert.fingerprint(hashes.SHA256()):
            (ROOT/'.local/previous-trusted-server.pem').write_bytes(prior)
            subprocess.run([certutil, '-D', '-d', database, '-n', NICKNAME], check=True)
    # P = trusted SSL peer, not C = CA allowed to issue certificates for other sites.
    subprocess.run([certutil, '-A', '-d', database, '-n', NICKNAME, '-t', 'P,,', '-i', str(path)], check=True)
    subprocess.run([certutil, '-V', '-d', database, '-n', NICKNAME, '-u', 'V'], check=True)
    print('Certificado HTTPS de localhost confiable en el almacén NSS de tu usuario.')
    print('No se instaló una CA ni se desactivó la validación de certificados.')
    print('Abre https://localhost:8443. Si Brave conserva el aviso anterior, reinícialo para recargar la confianza.')

if __name__ == '__main__': main()
