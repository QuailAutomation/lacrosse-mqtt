from collections import deque

import logging
import json

log = logging.getLogger(__name__)

class TempSensor:
    max_allowable_difference_from_average = 4
    # when we start accepting samples we are vulnerable to accepting a bad value early, which will
    # result in not accepting more appropriate values later because of an inaccurate early reading
    # so, if we reject 4 samples consecutively, we will flush the readings and start again
    current_number_sample_rejections = 0

    def __init__(self,id, min, max, max_difference_from_average=4):
        self.id = id
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
                self.current_number_sample_rejections = 0
                log.debug('Submitted sample')
            else:
                if self.current_number_sample_rejections == 3:
                    self.last_10_readings.clear()
                    log.debug("Cleared last 10 readings because we've rejected too many samples")
                else:
                    self.current_number_sample_rejections += 1
                    log.warn(
                        'Did not accept sample.  id=%s ,value=%f , because it was too different than average=%f , max_allowable=%f elements=%s'
                        % (str(id), temperature, mostRecentAvg, self.max_allowable_difference_from_average,
                           self.last_10_readings))
                raise ValueError('Sample variance was greater allowable average')
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

    def toJSON(self):
        return {'id': self.id,'min':self.min,'max':self.max,'currentnumberrejections':self.current_number_sample_rejections,'readings':json.dumps(list(self.last_10_readings))}