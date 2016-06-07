from collections import deque

import logging

log = logging.getLogger(__name__)


class TempSensor:
    def __init__(self,  min, max):
        self.min = min
        self.max = max
        log.info('Sensor created: Min: %s, Max: %s' % (min, max))

        self.last10Readings = deque(maxlen=10)

    def average(self):
        sumSamples = sum(self.last10Readings)
        numSamples = len(self.last10Readings)
        if numSamples > 0:
            return sumSamples/numSamples
        else:
            return None

    def sma(self):
        if len(self.last10Readings) < 10:
            log.debug('SMA is None because # samples is: %s' % len(self.last10Readings))
            return None
        else:
            avg = self.average();
            log.debug('Avg %f' % avg)
            return avg

    def submitsample(self, sample):
        log.debug('submit sample called with: ' + str(sample))
        # check if within 1 degree of sma, if it exists
        mostRecentAvg = self.average()
        log.debug('most recent sma: ' + str(mostRecentAvg))
        if mostRecentAvg is not None:
            if abs(sample - mostRecentAvg) < 1:
                self.last10Readings.append(sample)
                log.debug('Submitted sample')
            else:
                log.warn('Did not accept sample: %f , because it was too different than average: %f ' %(sample,mostRecentAvg))
                raise ValueError('Sample was greater than 1 degrees higher than average')
        else:
            if self.min <= sample <= self.max:
                self.last10Readings.append(sample)
                log.debug('Submitted sample')
            else:
                log.warn('Sample out of range, sample value: %f, min: %f, max: %f'
                         % ( sample, self.min, self.max))

    def remove(self, count):
        for _ in range(count):
            self.last10Readings.popleft()
