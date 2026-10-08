import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from single_instance import Instance


@unittest.skipUnless(os.name == 'nt', 'Windows app coordination')
class SingleInstanceTests(unittest.TestCase):
    def child(self, directory, script):
        return subprocess.run([sys.executable, '-c', script, str(directory)],
                              cwd=Path(__file__).parent, capture_output=True, text=True, timeout=10)

    def test_other_process_signals_without_becoming_primary(self):
        with tempfile.TemporaryDirectory() as folder:
            first = Instance(folder)
            try:
                self.assertTrue(first.primary)
                result = self.child(folder, 'import sys; from single_instance import Instance; x=Instance(sys.argv[1]); assert not x.primary; x.activate(); x.close()')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(first.requested())
                self.assertFalse(first.requested())
                other = Instance(Path(folder)/'isolated-test')
                try:self.assertTrue(other.primary)
                finally:other.close()
            finally:first.close()
            restarted = Instance(folder)
            try:self.assertTrue(restarted.primary)
            finally:restarted.close()

    def test_crash_does_not_leave_a_stale_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.child(folder, 'import sys, os; from single_instance import Instance; x=Instance(sys.argv[1]); assert x.primary; os._exit(0)')
            self.assertEqual(result.returncode, 0, result.stderr)
            restarted = Instance(folder)
            try:self.assertTrue(restarted.primary)
            finally:restarted.close()


if __name__ == '__main__':unittest.main()
