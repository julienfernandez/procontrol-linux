"""Capture orchestration with a synthetic dumpcap; never opens a network socket."""
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FAKE = '''#!/usr/bin/python3
import os, signal, struct, sys, time
if '--version' in sys.argv:
 print('dumpcap SYNTHETIC TEST'); sys.exit(0)
if os.environ.get('PROCONTROL_TEST_FAIL'):
 print('Synthetic failure',file=sys.stderr); sys.exit(1)
assert sys.argv[sys.argv.index('-w')+1] == '-'
assert '-P' in sys.argv
seconds=float(sys.argv[sys.argv.index('-a')+1].split(':')[1])
def finish(*args):
 print('Packets captured: 1 (SYNTHETIC)',file=sys.stderr,flush=True)
 sys.exit(0)
signal.signal(signal.SIGINT,finish)
frame=bytes.fromhex('ffffffffffff020000000001885f')+b'SYNTHETIC ONLY'
sys.stdout.buffer.write(struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,262144,1))
sys.stdout.buffer.write(struct.pack('<IIII',1700000000,0,len(frame),len(frame))+frame)
sys.stdout.buffer.flush()
print('File: -',file=sys.stderr,flush=True)
time.sleep(seconds)
finish()
'''


class CaptureTests(unittest.TestCase):
    def setUp(self):
        interfaces = [p.name for p in Path('/sys/class/net').glob('*')
                      if (p / 'type').read_text().strip() == '1' and not (p / 'wireless').exists()]
        if not interfaces or not shutil.which('ip') or not shutil.which('flock'):
            self.skipTest('Linux Ethernet sysfs, ip et flock requis ; aucun accès réseau effectué')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for file in ('tools/capture.sh', 'tools/inspect_pcap.py', 'docs/experiment-template.md'):
            target = self.root / file
            target.parent.mkdir(exist_ok=True, parents=True)
            shutil.copyfile(ROOT / file, target)
        (self.root / 'bin').mkdir()
        fake = self.root / 'bin/dumpcap'
        fake.write_text(FAKE)
        fake.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.root / 'bin') + ':' + os.environ['PATH'],
                        PROCONTROL_CAPTURE_BACKEND='dumpcap', PROCONTROL_AUTH='none')
        self.cmd = ['bash', str(self.root / 'tools/capture.sh'), interfaces[0]]

    def test_native_duration_and_summary(self):
        result = subprocess.run(self.cmd + ['duration', '1'], env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = next(p for p in (self.root / 'captures').iterdir() if p.is_dir())
        self.assertIn('Trames : 1', (folder / 'summary.txt').read_text())
        self.assertIn('duration:1', (folder / 'metadata.txt').read_text())
        self.assertIn('capture_exit_code=0', (folder / 'metadata.txt').read_text())
        self.assertEqual(subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=folder, capture_output=True).returncode, 0)

    def test_capture_failure_is_reported(self):
        result = subprocess.run(self.cmd + ['failure', '1'], env=dict(self.env, PROCONTROL_TEST_FAIL='1'), capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Échec capture', result.stderr)

    def test_no_duplicate_and_clean_interrupt(self):
        proc = subprocess.Popen(self.cmd + ['interrupt', '30'], env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, start_new_session=True)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stderr, selectors.EVENT_READ)
                self.assertTrue(selector.select(5), 'No synthetic capture start')
                self.assertIn('File: -', proc.stderr.readline())
            other = subprocess.run(self.cmd + ['duplicate', '1'], env=self.env, capture_output=True, text=True, timeout=5)
            self.assertEqual(other.returncode, 2)
            self.assertIn('déjà lancée', other.stderr)
            os.killpg(proc.pid, signal.SIGINT)
            out, err = proc.communicate(timeout=5)
            self.assertEqual(proc.returncode, 0, err)
            self.assertIn('Trames : 1', out)
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()


if __name__ == '__main__':
    unittest.main()
