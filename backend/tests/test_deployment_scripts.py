"""Deployment config and archive tests need no Azure account or Docker daemon."""
import hashlib
import importlib.util
import json
import tarfile
import zipfile
from pathlib import Path

import pytest


def load_script(name):
    path = Path(__file__).resolve().parents[2] / 'scripts' / f'{name}.py'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cloud_configuration_generates_independent_secrets_without_printing_them(tmp_path, capsys):
    configure = load_script('configure_azure').configure
    files = [tmp_path / 'first.env', tmp_path / 'second.env']
    configurations = []
    for path in files:
        configure('imagevault.example.com', 'https://example.blob.core.windows.net/', path)
        configurations.append(dict(line.split('=', 1) for line in path.read_text().splitlines()))
    output = capsys.readouterr().out
    for values in configurations:
        assert values['APP_DOMAIN'] == 'imagevault.example.com'
        assert values['AZURE_STORAGE_ACCOUNT_URL'] == 'https://example.blob.core.windows.net'
        assert values['REGISTRATION_ENABLED'] == 'true'
        assert int(values['MAX_USER_STORAGE_BYTES']) == 2 * 1024**3
        secret_values = [values[key] for key in ('POSTGRES_PASSWORD', 'JWT_SECRET', 'REGISTRATION_CODE')]
        assert len(set(secret_values)) == 3
        for secret in secret_values:
            assert len(secret) >= 32 and all(c in '0123456789abcdef' for c in secret)
            assert secret not in output
    assert configurations[0]['JWT_SECRET'] != configurations[1]['JWT_SECRET']


def test_cloud_configuration_never_replaces_existing_secrets(tmp_path):
    destination = tmp_path / '.env'
    original = 'JWT_SECRET=existing-private-value\n'
    destination.write_text(original)
    with pytest.raises(FileExistsError):
        load_script('configure_azure').configure('imagevault.example.com', 'https://example.blob.core.windows.net', destination)
    assert destination.read_text() == original


@pytest.mark.parametrize('domain,url', [
    ('https://imagevault.example.com', 'https://example.blob.core.windows.net'),
    ('imagevault.example.com\nJWT_SECRET=injected', 'https://example.blob.core.windows.net'),
    ('imagevault.example.com', 'http://example.blob.core.windows.net'),
    ('imagevault.example.com', 'https://example.blob.core.windows.net/container'),
    ('imagevault.example.com', 'https://example.blob.core.windows.net?sig=secret'),
    ('imagevault.example.com', 'https://user:password@example.blob.core.windows.net'),
])
def test_invalid_cloud_configuration_creates_no_file(tmp_path, domain, url):
    destination = tmp_path / '.env'
    with pytest.raises(ValueError):
        load_script('configure_azure').configure(domain, url, destination)
    assert not destination.exists()


def test_release_archives_include_built_site_and_only_named_synthetic_samples(tmp_path, monkeypatch):
    script = load_script('package_release')
    tracked = ['README.md', '.env.example', 'frontend/package.json']
    sources = {
        'README.md': '# Demo\n', '.env.example': 'JWT_SECRET=REPLACE_ME\n',
        'frontend/package.json': json.dumps({'version': '1.2.1'}),
        'frontend/dist/index.html': '<html>Built site</html>',
        'frontend/dist/assets/app.js': 'console.log("fixture");',
        'demo-images/01-original.png': 'synthetic-test-sample',
        'demo-images/personal-photo.png': 'must-not-be-packaged',
        '.env': 'JWT_SECRET=private-runtime-value',
        'uploads/personal.png': 'private-upload',
    }
    for name, content in sources.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    monkeypatch.setattr(script.subprocess, 'check_output', lambda args, **_: (
        ('\0'.join(tracked) + '\0').encode() if args[1] == 'ls-files' else b'test-commit\n'
    ))
    output = tmp_path / 'output'
    script.package(tmp_path, output)
    expected = {*tracked, 'frontend/dist/index.html', 'frontend/dist/assets/app.js', 'demo-images/01-original.png'}
    with zipfile.ZipFile(output / 'imagevault-ai.zip') as archive:
        assert set(archive.namelist()) == expected
        assert archive.testzip() is None
    with tarfile.open(output / 'imagevault-ai.tar.gz') as archive:
        assert set(archive.getnames()) == expected
    for line in (output / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
    assert json.loads((output / 'release.json').read_text()) == {
        'version': '1.2.1', 'commit': 'test-commit', 'files': len(expected),
    }


@pytest.mark.parametrize('unsafe_path', ['.env', 'secrets/private.key', '../outside.txt'])
def test_release_refuses_tracked_secrets_and_path_traversal(tmp_path, monkeypatch, unsafe_path):
    script = load_script('package_release')
    dist = tmp_path / 'frontend/dist'
    dist.mkdir(parents=True)
    (dist / 'index.html').write_text('built site')
    monkeypatch.setattr(script.subprocess, 'check_output', lambda *_, **__: (unsafe_path + '\0').encode())
    with pytest.raises(RuntimeError):
        script.package(tmp_path, tmp_path / 'output')
    assert not (tmp_path / 'output').exists()
