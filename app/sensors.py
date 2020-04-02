from collections import deque

import logging
import json
import datetime
import time
import socket

from prometheus_client import Summary, Counter, Gauge
import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)


class TempSensor:
    def __init__(self, id, location="unspecified", min=0, max=50,
                 max_difference_from_average=4):
        self.id = id
        self.location = location
        self.min = min
        self.max = max
        log.info('Sensor created: Min: %s, Max: %s' % (min, max))
        self.last_10_readings = deque(maxlen=10)
        self.max_diff_from_average = max_difference_from_average

        # when we start accepting samples we are vulnerable to accepting a bad
        # value early, which will result in not accepting more appropriate
        # values later because of an inaccurate early reading
        # so, if we reject 4 samples consecutively, we will flush the
        # readings and start again
        self.current_number_sample_rejections = 0

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
            avg = self.average()
            log.debug('Avg %f' % avg)
            return avg

    def submit_sample(self, temperature):
        log.debug('submit sample called with: ' + str(temperature))
        # check if within 1 degree of sma, if it exists
        most_recent_average = self.average()
        log.debug('most recent sma: ' + str(most_recent_average))
        if most_recent_average is not None:
            if abs(temperature - most_recent_average) < self.max_diff_from_average:
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
                        % (str(id), temperature, most_recent_average, self.max_diff_from_average,
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

    def number_samples(self):
        return len(self.last_10_readings)

    def toJSON(self):
        return {'id': self.id, 'min': self.min, 'max': self.max,
                'currentnumberrejections': self.current_number_sample_rejections,
                'readings': json.dumps(list(self.last_10_readings))}


class MqttMonitor:
    SENSOR_SAMPLES = Counter('lacrosse_samples_submitted', 'Number of samples processed',
                             ['sensor_key', 'topic', 'location'])
    INVALID_SENSOR_RANGE_COUNTER = Counter('lacrosse_samples_invalid_range_submitted',
                                           'Number unknown key samples processed', ['sensor_key', 'topic'])
    INVALID_SENSOR_KEY_COUNTER = Counter('lacrosse_samples_invalid_key_submitted',
                                         'Number unknown key samples processed', ['sensor_key'])
    MQTT_SUBMIT_DURATION = Summary('lacrosse_mqtt_submit_duration',
                                   'Latency of submitting to mqtt')
    MQTT_EXCEPTIONS = Counter('lacrosse_mqtt_submit_exceptions_total',
                              'Exceptions thrown submitting to mqtt')
    CURRENT_NUMBER_SAMPLES = Gauge('lacrosse_samples_current_number', 'Current number samples for averaging',
                                   ['sensor_key', 'type', 'location'])

    def __init__(self, sensor_config, mqtt_broker_url, mqtt_broker_port=1883,
                 broker_client_id="lacrosse-mqtt"):
        self.client = mqtt.Client(client_id=broker_client_id + "craig")
        self.mqtt_broker_url = mqtt_broker_url
        self.mqtt_broker_port = 1883

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        # for each id, let's create a dict with the id, and a temp sensor class
        self.device_id_to_temp_sensor_map = {}
        self.device_id_to_humidity_sensor_map = {}
        # this dict will keep track of last time we received a message for the
        # sensors.  more than 1 jeelink may pick up the reading from a temp
        # sensor, so igore readings within a recent window...ie within 3
        # seconds
        self.device_id_to_last_reading_time = {}

        # this dict is sensors id, mqtt topic to write to
        self.deviceIdtoTopic = {}

        for key in sensor_config:
            log.info("watching for sensor with id: %s" % key)
            topic = sensor_config[key]['mqtt-topic']
            try:
                location = sensor_config[key]['location']
            except KeyError:
                location = topic

            log.info('Topic: %s' % topic)
            min = sensor_config[key]['valid-range']['min']
            self.device_id_to_temp_sensor_map[key] = TempSensor(key, location, sensor_config[key]['valid-range']['min'],
                                                           sensor_config[key]['valid-range']['max'])
            self.device_id_to_humidity_sensor_map[key] = TempSensor(id=key, location=location, min=0, max=97,
                                                               max_difference_from_average=15)
            self.deviceIdtoTopic[key] = topic

    def on_disconnect(self, client, userdata, rc):
        log.warn("disconnected with rtn code [%d]" % (rc))

    def on_connect(self, client, userdata, flags, rc):
        log.info("Connected with result code " + str(rc))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe("private/jeelink/+")

    # if i we reject 5 entries in a
    def is_ok_to_accept_reading(self, key):
        return_value = True
        log.debug("checking if we've had a reading within the ignore window")
        now = datetime.datetime.now()
        try:
            time_last_reading = self.device_id_to_last_reading_time[key]
            elapsed_time = now - time_last_reading
            if elapsed_time.total_seconds() > 3:
                return_value = True
                log.debug("we can accept, elapsed time: %f" % elapsed_time.total_seconds())
            else:
                return_value = False
                log.debug("Did not accept, elapsed time: {}".format(elapsed_time.total_seconds()))
        except KeyError:
            log.info('Key not found in last reading: ' + key)

        self.device_id_to_last_reading_time[key] = datetime.datetime.now()
        return return_value

    def get_sensor(self, key, type):
        try:
            if type == 'temperature':
                return self.device_id_to_temp_sensor_map[key]
            elif type == 'humidity':
                return self.device_id_to_humidity_sensor_map[key]
            else:
                log.error('Illegal sensor type: "%s"' % type)
        except KeyError:
            log.info('Key not found: %s, type: %s' % (key, type))

    def write_to_mqtt(self, topic, value):
        log.info('Writing to topic: %s, val: %s' % (topic, str(value)))
        try:
            startTime = time.time()
            self.client.publish(topic, str(value))
            MqttMonitor.MQTT_SUBMIT_DURATION.observe(time.time() - startTime)
        except socket.error:
            log.warn('Could not connect to mosquitto')
            MqttMonitor.MQTT_EXCEPTIONS.inc()
            self.client.connect(self.mqtt_broker_url, self.mqtt_broker_port, keepalive=1000)

    def submit_sample(self, sensor, sample_value, topic, type):
        log.debug("submit sample called :" + str(sample_value))
        try:
            sensor.submit_sample(sample_value)
            sma = sensor.sma()
            if sma is not None:
                if type == 'temperature':
                   self. write_to_mqtt(topic + type, round(sma, 1))
                elif type == 'humidity':
                    self.write_to_mqtt(topic + type, round(sma, 0))
                else:
                    log.warn("Received unexpected sample type: %s" % type)

                # let's remove 5 oldest readings so we can build deque back to 10
                sensor.remove(5)
            else:
                log.debug('Did not write sma because is None')
        except ValueError:
            log.info('Invalid reading. Sample ignored. sensor: {}, value={}'.format(sensor, sample_value))

    def on_message(self, client, userdata, msg):
        try:
            payload = str(msg.payload).replace("'", "")
            log.debug("payload: %s" % payload)
            msgElements = payload.split(':')
            key = msgElements[1]
            log.debug('key: %s' % key)
            if self.is_ok_to_accept_reading(key):
                temp = float(msgElements[2])
                log.debug("temp: '%f'" % temp)
                label_dict = {"sensor_key": key, "topic": msg.topic}
                sensor = self.get_sensor(key, 'temperature')
                if sensor is not None:
                    label_dict['location'] = sensor.location
                    MqttMonitor.SENSOR_SAMPLES.labels(**label_dict).inc()
                    topic = self.deviceIdtoTopic[key]
                    self.submit_sample(sensor, temp, topic, 'temperature')
                    MqttMonitor.CURRENT_NUMBER_SAMPLES.labels(sensor_key=key, type='temperature', location=sensor.location).set(
                        sensor.number_samples())
                    log.debug('Submitted temperature reading. key=%s value=%f' % (key, temp))
                    humidity = float(msgElements[3])
                    sensor = self.get_sensor(key, 'humidity')
                    if humidity < 99:
                        log.debug("humidity: '%f'" % humidity)
                        self.submit_sample(sensor, humidity, topic, 'humidity')
                        MqttMonitor.CURRENT_NUMBER_SAMPLES.labels(sensor_key=key, type='humidity', location=sensor.location).set(
                            sensor.number_samples())
                else:
                    MqttMonitor.INVALID_SENSOR_KEY_COUNTER.labels(sensor_key=key).inc()
        except Exception as e:
            log.exception(e)

    def loop_forever(self):
        while True:
            try:
                log.info('Connecting to mqtt: %s' % self.mqtt_broker_url)
                self.client.connect(self.mqtt_broker_url, self.mqtt_broker_port, 60)
                self.client.loop_forever()
            except Exception:
                log.warn('Could not connect to mqtt, retrying in 1 minute(s)')
                time.sleep(60)
