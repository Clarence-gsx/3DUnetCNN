from unittest import TestCase
import os

from unet3d.data import DataFile
import numpy as np


class TestDataFile(TestCase):
    def setUp(self):
        self.filename = os.path.abspath('test.h5')
        self.data_file = DataFile(self.filename)

    def test_file_exists(self):
        self.assertTrue(os.path.exists(self.filename))

    def test_add_data(self):
        features = np.zeros((9, 9, 9))
        targets = np.ones(features.shape)
        affine = np.diag(np.ones(4))
        subject_id = 'mydata'
        self.data_file.add_data(features, targets, subject_id)
        x, y = self.data_file.get_data(subject_id)
        np.testing.assert_array_equal(features, x)
        np.testing.assert_array_equal(targets, y)

        subject_id = 'yourdata'
        features = features.copy()
        features[3:6, 3:6, 3:6] = 5
        targets = np.zeros(features.shape)
        targets[3:6, 3:6, 3:6] = 1
        self.data_file.add_data(features, targets, subject_id, affine=affine)
        x_image, y_image = self.data_file.get_images(subject_id)
        np.testing.assert_array_equal(x_image.get_data(), features)

    def tearDown(self):
        self.data_file.close()
        os.remove(self.filename)
