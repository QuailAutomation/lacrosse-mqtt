from collections import deque

import logging

log = logging.getLogger(__name__)


class TempSensor:
    max_allowable_difference_from_average = 4

    def __init__(self, min, max, max_difference_from_average=4):
        self.min = min
        self.max = max
        log.info('Sensor created: Min: %s, Max: %s' % (min, max))
        self.last_10_readings = deque(maxlen=10)
        self.max_allowable_difference_from_average = max_difference_from_average

    def average(self):
        sum_samples = sum(self.last_10_readings)
        num_samples = len(self.last_10_readings)
        if num_samples > 3:
            return sum_samples/num_samples
        else:
            return None

    def sma(self):
        if len(self.last_10_readings) < 10:
            log.debug('SMA is None because # samples is: %s' % len(self.last_10_readings))
            return None
        else:
            avg = self.average();
            log.debug('Avg %f' % avg)
            return avg

    def submit_sample(self, temperature):
        log.debug('submit sample called with: ' + str(temperature))
        # check if within 1 degree of sma, if it exists
        mostRecentAvg = self.average()
        log.debug('most recent sma: ' + str(mostRecentAvg))
        if mostRecentAvg is not None:
            if abs(temperature - mostRecentAvg) < self.max_allowable_difference_from_average:
                self.last_10_readings.append(temperature)
                log.debug('Submitted sample')
            else:
                log.warn('Did not accept sample: %f , because it was too different than average: %f , max allowable: %f'
                         % (temperature, mostRecentAvg, self.max_allowable_difference_from_average))
                raise ValueError('Sample was greater than 1 degrees higher than average')
        else:
            if self.min <= temperature <= self.max:
                self.last_10_readings.append(temperature)
                log.debug('Submitted sample')
            else:
                log.warn('Sample out of range, sample value: %f, min: %f, max: %f'
                         % (temperature, self.min, self.max))

    def remove(self, count):
        for _ in range(count):
            self.last_10_readings.popleft()
