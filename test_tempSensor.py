from unittest import TestCase
from sensors import TempSensor


class TestTempSensor(TestCase):

    def test_average(self):
        sensor = TempSensor(min=12,max=15)
        for _ in range(10):
            sensor.submitsample(15)
        self.assertTrue(sensor.sma() == 15)

    def test_detect_outlier(self):
        sensor = TempSensor(min=12, max=25)
        for _ in range(9):
            sensor.submitsample(15)
        self.assertRaises(ValueError, sensor.submitsample,24)



