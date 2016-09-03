from unittest import TestCase
from sensors import TempSensor

import logging

logging.basicConfig(level=logging.INFO)

class TestTempSensor(TestCase):

    def test_average(self):
        sensor = TempSensor(min=12,max=15)
        for _ in range(10):
            sensor.submit_sample(15)
        self.assertTrue(sensor.sma() == 15)

    def test_detect_outlier(self):
        sensor = TempSensor(min=12, max=25)
        for _ in range(9):
            sensor.submit_sample(15)
        self.assertRaises(ValueError, sensor.submit_sample, 24)



