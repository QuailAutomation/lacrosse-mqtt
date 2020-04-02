from app.sensors import TempSensor

import logging

logging.basicConfig(level=logging.DEBUG)


def test_average():
    sensor = TempSensor(1, min=12, max=15)
    for _ in range(10):
        sensor.submit_sample(15)
    assert(sensor.sma() == 15)


# def test_detect_outlier():
#     sensor = TempSensor(1, min=12, max=25)
#     try:
#         for _ in range(9):
#             sensor.submit_sample(15)
#         assert(False)
#     except ValueError:
#         pass


def test_clears_samples():
    sensor = TempSensor(1, min=12, max=25)
    for _ in range(4):
        sensor.submit_sample(24)
    # now let's accept something lower
    for _ in range(4):
        try:
            sensor.submit_sample(12)
            assert(False)
        except ValueError:
            pass
    sensor.submit_sample(12)
