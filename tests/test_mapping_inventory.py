import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import mapping_inventory


class MappingInventoryTests(unittest.TestCase):
    def test_runtime_modes_and_current_ardour_actions_are_included(self):
        rows = {(r['zone'], r['button']): r for r in mapping_inventory.inventory()}
        self.assertEqual(rows[8, 10]['actions']['normal'], [('monitor', 'selected', ['input'])])
        self.assertEqual(rows[0, 4]['actions']['monitor'], [('monitor', 'toggle', [1])])
        self.assertTrue(rows[0, 4]['mapped'])
        self.assertEqual(rows[0, 1]['actions']['normal'], [('eq', 'browse_track', [1])])
        self.assertEqual(rows[13, 0]['actions']['browse'], [('eq', 'open', [0])])
        self.assertEqual(rows[13, 0]['actions']['eq'], [('eq', 'filter', [0])])
        self.assertEqual(rows[0x19, 6]['actions']['normal'],
                         [('osc', '/access_action', ['EditorEditing/undo'])])
        self.assertEqual(rows[0x1b, 10]['actions']['nudge'][-1],
                         ('osc', '/access_action', ['Editor/nudge-backward']))
        self.assertFalse(rows[0x1c, 12]['mapped'])

    def test_check_detects_drift_without_rewriting_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'docs').mkdir()
            with patch.object(mapping_inventory, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(mapping_inventory.main(['--check']), 1)
                self.assertEqual(list((root / 'docs').iterdir()), [])
                self.assertEqual(mapping_inventory.main([]), 0)
                self.assertEqual(mapping_inventory.main(['--check']), 0)
                changed = root / 'docs/mapping-backlog.md'
                changed.write_text('stale\n')
                self.assertEqual(mapping_inventory.main(['--check']), 1)
                self.assertEqual(changed.read_text(), 'stale\n')


if __name__ == '__main__':
    unittest.main()
