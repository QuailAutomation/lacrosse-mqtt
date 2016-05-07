__author__ = 'craigh'
import sys,traceback
import os
from logentries import LogentriesHandler
import logging
import json
import socket
import math

import numpy
from twisted.protocols.basic import LineReceiver

from twisted.internet import reactor
from twisted.internet.serialport import SerialPort
from twisted.python import usage
import paho.mqtt.client as mqtt
import thread
from collections import deque

from twisted.python import log as twisted_log


class TempSensor:
    def __init__(self, topic, min, max):
        self.topic = str(topic)
        self.min = min
        self.max = max
        self.last10Readings = deque(maxlen=10)

    def sma(self):
        sd = numpy.std(self.last10Readings, ddof=1)
        log.debug('Standard deviation is: %f' % sd)
        sumSamples = sum(self.last10Readings)
        numSamples = len(self.last10Readings)
        log.debug('Sum: ' + str(sumSamples))
        log.debug('Num samples: ' + str(numSamples))
        if len(self.last10Readings) < 10:
            log.debug('SMA is None because # samples is: %s' % len(self.last10Readings))
            return None
        else:
            avg = sumSamples/numSamples;
            logging.debug('Avg %f' % avg)
            return avg


    def submitSample(self, sample):
        log.debug('submit sample called with: ' + str(sample))
        # check if within 1 degree of sma, if it exists
        mostRecentAvg = self.sma()
        log.debug('most recent sma: ' + str(mostRecentAvg))
        if mostRecentAvg is not None:
            if abs(sample - mostRecentAvg) < 1:
                self.last10Readings.append(sample)
                log.debug( 'Submitted sample')
            else:
                log.debug('Did not accept sample: %f , because it was too different than average: %f ' %(sample,mostRecentAvg))
        else:
            if self.min <= sample <= self.max:
                self.last10Readings.append(sample)
                log.debug('Submitted sample')
            else:
                log.warn('Sample out of range, topic: %s, sample value: %f, min: %f, max: %f'
                         % (self.topic, sample, self.min, self.max))

    def topic(self):
        return self.topic

    def remove(self, count):
        for x in range(count):
            self.last10Readings.popleft()

config_file = os.getenv('SENSORCONFIGFILE', './sensors.json')
with open(config_file) as json_file:
    config = json.load(json_file)

# read some env variables

serial_port = config['serial-port']
mosquitto_url = config['mqtt-url']
logentries_key = config['log-entries-key']
logging_level = config['log-level']

#logging.basicConfig(level=logging_level or logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
#log = logging.getLogger()

log = logging.getLogger('logentries')
log.setLevel(level=logging_level or logging.INFO)

log.addHandler(LogentriesHandler(logentries_key))

# for each id, let's create a dict with the id, and a temp sensor cloass
#TempSensor
deviceToTopicMap = {}
sensorConfig = config['sensors']
for key in sensorConfig:
    log.info("watching for sensor with id: %s" % key)
    topic = sensorConfig[key]['mqtt-topic']
    log.info('Topic: %s' % topic)
    min = sensorConfig[key]['valid-range']['min']
    log.info('Min: %s, Max: %s' % (min,sensorConfig[key]['valid-range']['max']))
    deviceToTopicMap[key] = TempSensor(sensorConfig[key]['mqtt-topic'],sensorConfig[key]['valid-range']['min'],sensorConfig[key]['valid-range']['max'])


class THOptions(usage.Options):
    optParameters = [
        ['baudrate', 'b', 57600, 'Serial baudrate'],
        ['port', 'p', serial_port, 'Serial port to use'],]

class ProcessTempSensor(LineReceiver):
    debug = True
    mqttc = mqtt.Client('python_pub')
#    deviceToTopicMap = {'80': mosquitto_topic}


    def lineReceived(self, line):
        try:
            msg = line.rstrip()
            log.debug(msg)
            if msg.startswith('D:') and len(msg) >= 13:
                log.info("Processing: %s" % msg)
                msgElements = msg.split(':')
                key = msgElements[1]
                log.debug('key: %s' % key)
                temp = float(msgElements[2])
                log.debug("temp: '%f'" % temp)
                try:
                    configInfo = deviceToTopicMap[key]
                    topic = configInfo.topic
                    configInfo.submitSample(temp)
                    sma = configInfo.sma()
                    if sma is not None:
                        log.info( 'Writing to topic: %s, val: %s' % (topic, str(sma)))
                        try:
                            self.mqttc.connect(mosquitto_url, 1883, keepalive=1000)
                            self.mqttc.publish(topic, str(sma))
                            # let's remove 5 oldest readings so we can build deque back to 10
                            configInfo.remove(5)
                        except socket.error:
                            #if serr.errno != errno.ECONNREFUSED:
                                # Not the error we are looking for, re-raise
                            #    raise serr
                            #else:
                            log.warn('Could not connect to mosquitto')
                    else:
                        log.debug( 'Did not write sma because is None')
                    #mqttc.loop(2)
                except KeyError:
                    log.info('Key not found: ' + key)
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

    baudrate = o.opts['baudrate'] #int('115200')
    port = o.opts['port']
    log.debug('About to open port %s' % port)
    s = SerialPort(ProcessTempSensor(), port, reactor, baudrate=baudrate)
    reactor.run()

log.info('Starting')

observer = twisted_log.PythonLoggingObserver(loggerName='logentries')
observer.start()
thread.start_new_thread(SerialInit())