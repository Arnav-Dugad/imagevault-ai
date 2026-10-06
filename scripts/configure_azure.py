"""Generate private cloud configuration on the VM; never overwrite secrets."""
import argparse
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlparse


def configure(domain: str, storage_url: str, destination: Path) -> None:
    if not domain or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-.' for c in domain):
        raise ValueError('Domain must be a lowercase DNS hostname without a scheme')
    parsed = urlparse(storage_url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment or parsed.username or parsed.port
            or any(c.isspace() for c in storage_url)):
        raise ValueError('Storage URL must be an HTTPS account endpoint')
    values = {
        'APP_VERSION': json.loads((Path(__file__).resolve().parents[1] / 'frontend/package.json').read_text())['version'],
        'APP_DOMAIN': domain,
        'AZURE_STORAGE_ACCOUNT_URL': storage_url.rstrip('/'),
        'AZURE_STORAGE_CONTAINER': 'imagevault',
        'POSTGRES_PASSWORD': secrets.token_hex(32),
        'JWT_SECRET': secrets.token_hex(48),
        'REGISTRATION_CODE': secrets.token_hex(16),
        'REGISTRATION_ENABLED': 'true',
        'MAX_USER_STORAGE_BYTES': str(2 * 1024**3),
    }
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        handle.write(''.join(f'{key}={value}\n' for key, value in values.items()))
    print('Created private .env. Retrieve REGISTRATION_CODE on the VM to invite users.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', required=True)
    parser.add_argument('--storage-url', required=True)
    parser.add_argument('--output', type=Path, default=Path('.env'))
    args = parser.parse_args()
    configure(args.domain, args.storage_url, args.output)
