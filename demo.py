"""Reproduce CLI scenarios using disposable copies of the fictional sample files."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def run_demo():
    samples = ROOT / 'samples'
    originals = {p.name: p.read_bytes() for p in samples.iterdir() if p.is_file()}
    scratch = ROOT / 'local-results'
    scratch.mkdir(exist_ok=True)
    outcomes = []
    with tempfile.TemporaryDirectory(prefix='demo-', dir=scratch) as temporary:
        temporary = Path(temporary).resolve()
        if temporary.parent != scratch.resolve():
            raise ValueError('Temporary directory is outside the expected workspace')
        for case in ('unchanged', 'modified', 'added', 'removed', 'renamed',
                     'overwrite_prevented', 'malformed_baseline'):
            folder = temporary / case
            folder.mkdir()
            target = folder / 'samples'
            shutil.copytree(samples, target)
            manifest = folder / 'baseline.json'
            command = [sys.executable, str(ROOT / 'integrity.py')]

            def execute(action):
                return subprocess.run(command + [action, str(target), str(manifest)],
                                      capture_output=True, text=True)

            created = execute('baseline')
            if created.returncode != 0:
                raise RuntimeError(f'{case}: baseline creation failed')
            baseline_bytes = manifest.read_bytes()
            expected = {'added': [], 'modified': [], 'removed': [], 'unchanged_count': 2}
            if case == 'modified':
                with (target / 'settings.txt').open('a', encoding='utf-8') as stream:
                    stream.write('\nreviewed_change=true\n')
                expected.update(modified=['settings.txt'], unchanged_count=1)
            elif case == 'added':
                (target / 'new.txt').write_text('Fictional added file.\n', encoding='utf-8')
                expected['added'] = ['new.txt']
            elif case == 'removed':
                (target / 'notes.txt').unlink()
                expected.update(removed=['notes.txt'], unchanged_count=1)
            elif case == 'renamed':
                (target / 'notes.txt').rename(target / 'renamed-notes.txt')
                expected.update(added=['renamed-notes.txt'], removed=['notes.txt'], unchanged_count=1)
            elif case == 'malformed_baseline':
                manifest.write_text('{invalid JSON', encoding='utf-8')

            action = 'baseline' if case == 'overwrite_prevented' else 'check'
            result = execute(action)
            error_case = case in ('overwrite_prevented', 'malformed_baseline')
            expected_code = 2 if error_case else (0 if case == 'unchanged' else 1)
            if result.returncode != expected_code:
                raise AssertionError(f'{case}: expected exit {expected_code}, got {result.returncode}')
            record = {'case': case, 'exit_code': result.returncode}
            if error_case:
                if result.stdout or not result.stderr.startswith('Error:'):
                    raise AssertionError(f'{case}: invalid error output')
                record['error_reported'] = True
                if case == 'overwrite_prevented':
                    if manifest.read_bytes() != baseline_bytes:
                        raise AssertionError('Existing baseline was modified')
                    record['baseline_preserved'] = True
            else:
                actual = json.loads(result.stdout)
                if actual != expected:
                    raise AssertionError(f'{case}: unexpected report {actual}')
                record['report'] = actual
            outcomes.append(record)
    if originals != {p.name: p.read_bytes() for p in samples.iterdir() if p.is_file()}:
        raise AssertionError('Original sample files changed')
    return {'sample_files_preserved': True, 'scenarios_passed': len(outcomes), 'results': outcomes}


if __name__ == '__main__':
    print(json.dumps(run_demo(), indent=2))
