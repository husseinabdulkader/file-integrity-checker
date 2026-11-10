"""Create and compare SHA-256 file baselines for a local directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys


def safe_name(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or str(path) != name
            or '..' in path.parts or '\\' in name or ':' in name):
        raise ValueError(f'Unsupported relative path: {name!r}')


def regular_stat(path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ValueError(f'Links/reparse points are not supported: {path.name}')
    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
        raise ValueError(f'Unsupported filesystem object: {path.name}')
    return info


def fingerprint(path):
    before = regular_stat(path)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('Expected a regular file')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError('File replaced during scan')
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    after = regular_stat(path)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError('File changed during scan; retry with the directory idle')
    return {'sha256': digest.hexdigest(), 'size': after.st_size}


def snapshot(root):
    root = Path(root).absolute()
    for parent in [root, *root.parents]:
        regular_stat(parent)
    if not root.is_dir():
        raise ValueError('Scan root must be a directory')
    files = {}
    def walk(directory):
        for path in sorted(directory.iterdir()):
            info = regular_stat(path)
            if stat.S_ISDIR(info.st_mode):
                walk(path)
            else:
                name = path.relative_to(root).as_posix()
                safe_name(name)
                files[name] = fingerprint(path)
    walk(root)
    return {'version': 1, 'algorithm': 'sha256', 'files': files}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def load_baseline(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object)
    if (not isinstance(data, dict) or set(data) != {'version','algorithm','files'}
            or type(data['version']) is not int or data['version'] != 1
            or data['algorithm'] != 'sha256' or not isinstance(data['files'], dict)):
        raise ValueError('Invalid baseline schema')
    for name, record in data['files'].items():
        safe_name(name)
        if (not isinstance(record, dict) or set(record) != {'sha256','size'}
                or not isinstance(record['sha256'], str)
                or not re.fullmatch('[0-9a-f]{64}', record['sha256'])
                or type(record['size']) is not int or record['size'] < 0):
            raise ValueError(f'Invalid fingerprint: {name}')
    return data


def compare(baseline, current):
    old, new = baseline['files'], current['files']
    common = old.keys() & new.keys()
    changed = sorted(name for name in common if old[name] != new[name])
    return {'added': sorted(new.keys() - old.keys()),
            'modified': changed, 'removed': sorted(old.keys() - new.keys()),
            'unchanged_count': len(common) - len(changed)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['baseline','check'])
    parser.add_argument('directory', type=Path)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    try:
        if args.manifest.resolve().is_relative_to(args.directory.resolve()):
            raise ValueError('Store the baseline outside the scanned directory')
        if args.command == 'baseline':
            current = snapshot(args.directory)
            # Exclusive creation preserves an existing trusted baseline.
            with args.manifest.open('x', encoding='utf-8') as stream:
                json.dump(current, stream, indent=2)
                stream.write('\n')
            print(f'Baseline created for {len(current["files"])} files.')
            return 0
        baseline = load_baseline(args.manifest)
        report = compare(baseline, snapshot(args.directory))
        print(json.dumps(report, indent=2))
        return 1 if any(report[key] for key in ['added','modified','removed']) else 0
    except (OSError, ValueError, RecursionError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
