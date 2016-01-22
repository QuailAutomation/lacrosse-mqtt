__author__ = 'craigh'

import os
#from logentries import LogentriesHandler
import logging
import json

from twisted.protocols.basic import LineReceiver

from twisted.internet import reactor
from twisted.internet.serialport import SerialPort
from twisted.python import usage
import paho.mqtt.client as mqtt
import thread
from collections import deque

from twisted.python import log as twisted_log


# read some env variables
config_file = os.getenv('SENSORCONFIGFILE', './sensors.json')
serial_port = os.getenv('JEELINKUSBPORT', '/dev/ttyUSB0')
mosquitto_url = os.getenv('MQTTBROKERURL', '192.168.1.122')
# TODO this needs to be converted to some map config file with device id, topic
mosquitto_topic = os.getenv('MOSQUITTOTOPIC', 'sensors/garage-south/temperature')
logentries_key = os.getenv('logentries-key', '9401ac1a-b3ba-45bf-8b48-df0fe1ecd5b0')


class TempSensor:
    def __init__(self, topic, min, max):
        self.topic = str(topic)
        self.min = min
        self.max = max
        self.last10Readings = deque(maxlen=10)

    def sma(self):
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
            #TODD get these from config map
            if self.min <= sample <= self.max:
                self.last10Readings.append(sample)
                log.debug( 'Submitted sample')
            else:
                log.debug( 'Sample out of range')

    def topic(self):
        return self.topic

    def remove(self, count):
        for x in range(count):
            self.last10Readings.popleft()

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
            log.info(msg)
            if msg.startswith('D:') and len(msg) >= 13:
                msgElements = msg.split(':')
                key = msgElements[1]
                log.debug('key: %s' % key)
                temp = float(msgElements[2])
                log.debug("temp: '%f'" % temp)
                try:
                    configInfo = deviceToTopicMap[key]
                    print("Config info is: %s" %  configInfo)
                    topic = configInfo.topic
                    print("Topic is :%s"% topic)
                    configInfo.submitSample(temp)
                    sma = configInfo.sma()
                    if sma is not None:
                        log.debug( 'Writing to topic: ' + topic)
                        self.mqttc.connect(mosquitto_url, 1883, keepalive=1000)
                        self.mqttc.publish(topic, str(sma))
                        # let's remove 5 oldest readings so we can build deque back to 10
                        configInfo.remove(5)
                    else:
                        log.debug( 'Did not write sma because is None')
                    #mqttc.loop(2)
                except KeyError:
                    log.warning('Key not found: ' + key)
        except (ValueError, IndexError):
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

print 'Starting'

with open(config_file) as json_file:
    sensorConfig = json.load(json_file)

# for each id, let's create a dict with the id, and a temp sensor cloass
#TempSensor
deviceToTopicMap = {}
for key in sensorConfig:
    topic = sensorConfig[key]['mqtt-topic']
    print ('Topic: ',topic)
    min = sensorConfig[key]['valid-range']['min']
    print ('Min: ', min)
    deviceToTopicMap[key] = TempSensor(sensorConfig[key]['mqtt-topic'],sensorConfig[key]['valid-range']['min'],sensorConfig[key]['valid-range']['max'])

#log = logging.getLogger('logentries')
#log.setLevel(logging.INFO)
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()
#log.addHandler(LogentriesHandler(logentries_key))

observer = twisted_log.PythonLoggingObserver(loggerName='logentries')
observer.start()
thread.start_new_thread(SerialInit())