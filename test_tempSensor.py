import unittest
from unittest import TestCase
from sensors import TempSensor

import logging

logging.basicConfig(level=logging.DEBUG)


class TestTempSensor(TestCase):

    def test_average(self):
        sensor = TempSensor(1,min=12,max=15)
        for _ in range(10):
            sensor.submit_sample(15)
        self.assertTrue(sensor.sma() == 15)

    def test_detect_outlier(self):
        sensor = TempSensor(1,min=12, max=25)
        for _ in range(9):
            sensor.submit_sample(15)
        self.assertRaises(ValueError, sensor.submit_sample, 24)

    def test_clears_samples(self):
        logging.debug("testing clear_samples")
        sensor = TempSensor(1,min=12, max=25)
        for _ in range(4):
            sensor.submit_sample(24)
        # now let's accept something lower
        for _ in range(4):
            try:
                sensor.submit_sample(12)
                self.fail
            except ValueError:
                pass
        sensor.submit_sample(12)

if __name__ == '__main__':
    unittest.main()
