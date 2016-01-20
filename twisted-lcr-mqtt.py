__author__ = 'craigh'

import os
#from logentries import LogentriesHandler
import logging
from twisted.protocols.basic import LineReceiver

from twisted.internet import reactor
from twisted.internet.serialport import SerialPort
from twisted.python import usage
import paho.mqtt.client as mqtt
import thread
from collections import deque

from twisted.python import log as twisted_log


# read some env variables
serial_port = os.getenv('JEELINKUSBPORT', '/dev/ttyUSB0')
mosquitto_url = os.getenv('MQTTBROKERURL', '192.168.1.122')
# TODO this needs to be converted to some map config file with device id, topic
mosquitto_topic = os.getenv('MOSQUITTOTOPIC', 'sensors/basement/winecellar/temperature')
logentries_key = os.getenv('logentries-key', '9401ac1a-b3ba-45bf-8b48-df0fe1ecd5b0')


class THOptions(usage.Options):
    optParameters = [
        ['baudrate', 'b', 57600, 'Serial baudrate'],
        ['port', 'p', serial_port, 'Serial port to use'],]

class ProcessTempSensor(LineReceiver):
    debug = True
    mqttc = mqtt.Client('python_pub')
    deviceToTopicMap = {'28': mosquitto_topic}

    last10Readings = deque(maxlen=10)

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
            if self.debug:
                logging.debug('Avg %f' % avg)
            return avg

    def submitSample(self, sample):
        log.debug('submit sample called with: ' + str(sample))
        # check if within 1 degree of sma, if it exists
        mostRecentAvg = self.sma()
        log.debug('sma: ' + str(mostRecentAvg))
        if mostRecentAvg is not None:
            if abs(sample - mostRecentAvg) < 1:
                self.last10Readings.append(sample)
                log.debug( 'Submitted sample')
        else:
            if 10.0 <= sample <= 25:
                self.last10Readings.append(sample)
                log.debug( 'Submitted sample')
            else:
                log.debug( 'Sample out of range')

    def lineReceived(self, line):
        try:
            msg = line.rstrip()
            log.info(msg)
            if len(msg) >= 13:
                msgElements = msg.split(':')
                log.debug('Elements: ', msgElements)
                key = msgElements[1]
                log.debug('key: %s' % key)
                temp = float(msgElements[2])
                log.debug("temp: '%f'" % temp)
                try:
                    topic = self.deviceToTopicMap[key]
                    self.submitSample(temp)
                    sma = self.sma()
                    if sma is not None:
                        log.debug( 'Writing to topic: ' + topic)
                        self.mqttc.connect(mosquitto_url, 1883, keepalive=1000)
                        self.mqttc.publish(topic, str(sma))
                        # let's remove 5 oldest readings so we can build deque back to 10
                        for x in xrange(5):
                            self.last10Readings.popleft()
                    else:
                        log.debug( 'Did not write sma because is None')
                    #mqttc.loop(2)
                except KeyError:
                    log.warning('Key not found: ' + key)
        except ValueError:
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

log = logging.getLogger('logentries')
log.setLevel(logging.INFO)
#log.addHandler(LogentriesHandler(logentries_key))

observer = twisted_log.PythonLoggingObserver(loggerName='logentries')
observer.start()
thread.start_new_thread(SerialInit())