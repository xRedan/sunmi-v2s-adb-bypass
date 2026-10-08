"""Package verified public tool files only. No device access or local-data inclusion."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def package(tools, target):
    tools = tools.resolve()
    target = target.resolve()
    if target.is_relative_to(tools):
        raise RuntimeError('The output archive must be outside the tool directory.')
    manifest_path = tools / 'tools-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    selected = []
    for relative, record in sorted(manifest['files'].items()):
        name = PurePosixPath(relative)
        if name.is_absolute() or '..' in name.parts or '\\' in relative or ':' in relative:
            raise RuntimeError('Unsafe manifest path: ' + relative)
        path = (tools / relative).resolve()
        if not path.is_relative_to(tools) or not path.is_file():
            raise RuntimeError('Missing or unsafe public tool file: ' + relative)
        if path.stat().st_size != record['size'] or sha256(path) != record['sha256']:
            raise RuntimeError('Tool integrity mismatch: ' + relative)
        selected.append((relative, path))
    selected.append(('tools-manifest.json', manifest_path))
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + '.partial')
    try:
        with zipfile.ZipFile(partial, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for relative, path in selected:
                item = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                item.compress_type = zipfile.ZIP_DEFLATED
                item.external_attr = 0o644 << 16
                archive.writestr(item, path.read_bytes())
        partial.replace(target)
    except Exception:
        if partial.exists():
            partial.unlink()
        raise
    return {'filename': target.name, 'sha256': sha256(target), 'size': target.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools', type=Path, default=ROOT / '.tools')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/sunmi-v2s-tools-windows.zip')
    parser.add_argument('--update-lock', action='store_true', help='Record a reviewed bundle update in tools.lock.json.')
    args = parser.parse_args()
    record = package(args.tools, args.output)
    if args.update_lock:
        lock_path = ROOT / 'tools.lock.json'
        lock = json.loads(lock_path.read_text(encoding='utf-8'))
        lock['bundle'] = record
        lock_path.write_text(json.dumps(lock, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
