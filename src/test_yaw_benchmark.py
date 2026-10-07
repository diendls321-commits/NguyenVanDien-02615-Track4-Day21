"""Check object association geometry and metric denominator semantics."""
import unittest
from types import SimpleNamespace

import numpy as np

from src.yaw_benchmark import matched_points, points_in_box


class BenchmarkTests(unittest.TestCase):
    def test_rotated_box_bottom_center(self):
        obj = SimpleNamespace(location=np.array([10., 2., 20.]),
                              dimensions=np.array([2., 2., 4.]), rotation_y=np.pi / 2)
        points = np.array([[10., 1., 21.8], [11.2, 1., 20.],
                           [10., 2.1, 20.], [10., -0.1, 20.], [np.nan, 1., 20.]])
        np.testing.assert_array_equal(points_in_box(points, obj), [True, False, False, False, False])

    def test_out_of_fov_remains_in_denominator(self):
        fixed = np.array([True, True, False])
        baseline = np.array([[5., 5.], [6., 6.], [7., 7.]])
        drift = np.array([[5., 5.], [np.nan, np.nan], [7., 7.]])
        bbox = [0., 0., 10., 10.]
        denominator = fixed.sum()
        self.assertEqual(int((matched_points(baseline, bbox) & fixed).sum()), 2)
        self.assertEqual(float((matched_points(drift, bbox) & fixed).sum() / denominator), 0.5)


if __name__ == "__main__":
    unittest.main()
