__author__ = 'craigh'

import sys, traceback
import os

import logging
import json
import socket
import thread

#some optional logging choices
try:
    from logentries import LogentriesHandler
except ImportError:
    pass
try:
    import graypy
except ImportError:
    pass

from twisted.protocols.basic import LineReceiver

from twisted.internet import reactor
from twisted.internet.serialport import SerialPort
from twisted.python import usage
import paho.mqtt.client as mqtt



from twisted.python import log as twisted_log

from sensors import TempSensor


config_file = os.getenv('SENSORCONFIGFILE', './sensors.json')
with open(config_file) as json_file:
    config = json.load(json_file)

# read some env variables
serial_port = config['serial-port']
mosquitto_url = config['mqtt-url']
try:
    logentries_key = config['log-entries-key']
except KeyError:
    logentries_key = None

try:
    gelf_url = config['gelf-url']
except KeyError:
    gelf_url = None

logging_level = config['log-level'] or "INFO"

if logentries_key is not None:
    log = logging.getLogger()
    log.addHandler(LogentriesHandler(logentries_key))
elif gelf_url is not None:
    log = logging.getLogger('temp')
    handler = graypy.GELFHandler(gelf_url, 12201, localname='lacrosse-temp', facility='maui')
    log.addHandler(handler)
else:
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger()

log.setLevel(level=logging_level or logging.INFO)
# for each id, let's create a dict with the id, and a temp sensor cloass
device_id_to_temp_sensor_map = {}
device_id_to_humidity_sensor_map = {}

# this dict is sensors id, mqtt topic to write to
deviceIdtoTopic = {}

sensorConfig = config['sensors']
for key in sensorConfig:
    log.info("watching for sensor with id: %s" % key)
    topic = sensorConfig[key]['mqtt-topic']
    log.info('Topic: %s' % topic)
    min = sensorConfig[key]['valid-range']['min']
    device_id_to_temp_sensor_map[key] = TempSensor(sensorConfig[key]['valid-range']['min'], sensorConfig[key]['valid-range']['max'])
    device_id_to_humidity_sensor_map[key] = TempSensor(min=0, max=97, max_difference_from_average=15)
    deviceIdtoTopic[key] = topic


class THOptions(usage.Options):
    optParameters = [
        ['baudrate', 'b', 57600, 'Serial baudrate'],
        ['port', 'p', serial_port, 'Serial port to use'],]


class ProcessTempSensor(LineReceiver):
    debug = True
    mqttc = mqtt.Client('python_pub')

    def write_to_mqtt(self, topic, value):
        log.info('Writing to topic: %s, val: %s' % (topic, str(value)))
        try:
            self.mqttc.connect(mosquitto_url, 1883, keepalive=1000)
            self.mqttc.publish(topic, str(value))
        except socket.error:
            log.warn('Could not connect to mosquitto')

    def get_sensor(self,key, type):
        try:
            if type == 'temperature':
                return device_id_to_temp_sensor_map[key]
            elif type == 'humidity':
                return device_id_to_humidity_sensor_map[key]
            else:
                log.error('Illegal sensor type: "%s"' % type)
        except KeyError:
            log.info('Key not found: ' + key)

    def submit_sample(self, sensor, sample_value, topic, type):
        log.debug("submit sample called :" + str(sample_value) )
        try:
            sensor.submit_sample(sample_value)
            sma = sensor.sma()
            if sma is not None:
                self.write_to_mqtt(topic + type, sma)
                # let's remove 5 oldest readings so we can build deque back to 10
                sensor.remove(5)
            else:
                log.debug('Did not write sma because is None')
        except ValueError:
            log.info('Value error, sample ignored: %f' % sample_value)

    def lineReceived(self, line):
        try:
            msg = line.rstrip()
            log.debug(msg)
            if msg.startswith('D:') and len(msg) >= 11:
                log.debug("Processing: %s" % msg)
                msgElements = msg.split(':')
                key = msgElements[1]
                log.debug('key: %s' % key)
                temp = float(msgElements[2])
                log.debug("temp: '%f'" % temp)
                sensor = self.get_sensor(key,'temperature')
                if sensor is not  None:
                    topic = deviceIdtoTopic[key]
                    self.submit_sample(sensor,temp, topic, 'temperature')
                    humidity = float(msgElements[3])
                    sensor = self.get_sensor(key, 'humidity')
                    if humidity < 99:
                        self.submit_sample(sensor, humidity, topic, 'humidity')
                    log.debug("humidity: '%f'" % humidity)

        except (ValueError, IndexError):
            traceback.print_exc()
            log.error('Unable to parse data %s' % line)
            return


def SerialInit():
    o = THOptions()
    try:
        o.parseOptions()
    except usage.UsageError, errortext:
        log.error('%s %s' % (sys.argv[0], errortext))
        log.info('Try %s --help for usage details' % sys.argv[0])
        raise SystemExit, 1

    baudrate = o.opts['baudrate']
    port = o.opts['port']
    log.debug('About to open port %s' % port)
    s = SerialPort(ProcessTempSensor(), port, reactor, baudrate=baudrate)
    reactor.run()

log.info('Starting')

observer = twisted_log.PythonLoggingObserver(loggerName='temp')
observer.start()
thread.start_new_thread(SerialInit())