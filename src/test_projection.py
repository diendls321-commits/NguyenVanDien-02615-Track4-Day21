"""Geometry checks for CP2: python -m unittest src.test_projection -v."""
import unittest

import numpy as np

from starter.datasets import load_frame
from starter.kitti_io import KittiCalib
from starter.projection import cam_to_image, velo_to_cam


class ProjectionTests(unittest.TestCase):
    def test_synthetic_reference_point(self):
        frame = load_frame("data/synthetic", "000000")
        camera = velo_to_cam(np.array([[10., 0., 0.]]), frame["calib"])
        uv, depth, mask = cam_to_image(camera, frame["calib"].P2, frame["image"].shape)
        self.assertAlmostEqual(float(depth[0]), 9.73, delta=0.02)
        np.testing.assert_allclose(uv[0], [614., 175.], atol=2.)
        self.assertTrue(mask[0])

    def test_rectification_and_translation(self):
        rotation = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
        transform = np.column_stack((np.eye(3), [1., 2., 3.]))
        calib = KittiCalib(np.zeros((3, 4)), rotation, transform)
        np.testing.assert_allclose(velo_to_cam(np.array([[4., 5., 6.]]), calib), [[-7., 5., 9.]])

    def test_invalid_depth_and_image_boundaries(self):
        projection = np.column_stack((np.eye(3), np.zeros(3)))
        points = np.array([[1., 1., 1.], [0., 0., 1.], [4., 1., 1.],
                           [1., 3., 1.], [-1., 1., 1.], [1., 1., -1.],
                           [0., 0., 0.1], [np.nan, 1., 1.], [1., np.inf, 1.]])
        uv, depth, mask = cam_to_image(points, projection, (3, 4, 3))
        np.testing.assert_array_equal(mask, [True, True, False, False, False, False, False, False, False])
        np.testing.assert_allclose(uv, [[1., 1.], [0., 0.]])
        np.testing.assert_allclose(depth, [1., 1.])

    def test_homogeneous_scale_and_empty_input(self):
        projection = np.array([[10., 0., 0., 2.], [0., 10., 0., 4.], [0., 0., 1., 1.]])
        uv, depth, mask = cam_to_image(np.array([[1., 2., 3.]]), projection, (20, 20))
        np.testing.assert_allclose(uv, [[3., 6.]])
        np.testing.assert_allclose(depth, [3.])
        self.assertTrue(mask[0])
        for points, matrix in [(np.empty((0, 3)), projection), (np.array([[1., 2., 3.]]), np.zeros((3, 4)))]:
            uv, depth, mask = cam_to_image(points, matrix, (20, 20))
            self.assertEqual(uv.shape, (0, 2))
            self.assertEqual(depth.shape, (0,))
            self.assertFalse(mask.any())


if __name__ == "__main__":
    unittest.main()
