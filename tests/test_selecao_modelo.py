import sys
from pathlib import Path
import unittest
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.selecao_modelo import bootstrap_pareado


class TestBootstrap(unittest.TestCase):
    def test_pairing_identical_predictions(self):
        y = np.array([0, 0, 1, 1])
        p = np.array([.1, .2, .7, .8])
        result, samples = bootstrap_pareado(y, p, p, 20, 42)
        np.testing.assert_array_equal(samples.delta_brier, np.zeros(20))
        np.testing.assert_array_equal(samples.delta_auc, np.zeros(20))
        self.assertEqual(result['brier']['percentile_interval_95'], [0, 0])

    def test_direction_reproducibility_and_invalid_input(self):
        y = np.array([0, 0, 1, 1])
        a, b = np.full(4, .5), np.array([.1, .2, .7, .8])
        result, first = bootstrap_pareado(y, a, b, 30, 42)
        _, second = bootstrap_pareado(y, a, b, 30, 42)
        np.testing.assert_array_equal(first, second)
        self.assertTrue((first.delta_brier < 0).all())
        self.assertTrue((first.delta_auc > 0).all())
        with self.assertRaises(ValueError):
            bootstrap_pareado(np.zeros(4), a, b)


if __name__ == '__main__':
    unittest.main()
