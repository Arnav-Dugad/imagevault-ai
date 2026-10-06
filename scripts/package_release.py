"""Package tracked source and the built web app; exclude credentials and runtime data."""
import argparse
import hashlib
import json
import subprocess
import tarfile
import zipfile
from pathlib import Path


def package(root: Path, output: Path) -> list[Path]:
    dist = root / 'frontend/dist'
    if not (dist / 'index.html').is_file():
        raise RuntimeError('Run npm ci && npm run build in frontend before packaging')
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    paths = []
    for name in tracked:
        if not name:
            continue
        path = Path(name)
        if (path.name.startswith('.env') and path.name != '.env.example') or path.suffix in {'.pem', '.key'}:
            raise RuntimeError(f'Refusing to package possible secret: {name}')
        if path.is_absolute() or '..' in path.parts or (root / path).is_symlink():
            raise RuntimeError(f'Unsafe release entry: {name}')
        paths.append(path)
    paths.extend(path.relative_to(root) for path in dist.rglob('*') if path.is_file())
    paths = sorted(set(paths))
    output.mkdir(parents=True, exist_ok=True)
    tar_path, zip_path = output / 'imagevault-ai.tar.gz', output / 'imagevault-ai.zip'
    with tarfile.open(tar_path, 'w:gz') as archive:
        for path in paths:
            archive.add(root / path, arcname=path.as_posix(), recursive=False)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(root / path, path.as_posix())
    (output / 'SHA256SUMS').write_text(''.join(
        f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n'
        for path in (tar_path, zip_path)
    ))
    metadata = {
        'version': json.loads((root / 'frontend/package.json').read_text())['version'],
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip(),
        'files': len(paths),
    }
    (output / 'release.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return [tar_path, zip_path, output / 'SHA256SUMS', output / 'release.json']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('release-dist'))
    args = parser.parse_args()
    for artifact in package(Path(__file__).resolve().parents[1], args.output.resolve()):
        print(artifact.name)
