__author__ = 'craigh'

import sys, traceback
import os
from logentries import LogentriesHandler
import logging
import json
import socket
import thread

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
logentries_key = config['log-entries-key'] or  None
logging_level = config['log-level'] or "INFO"

if logentries_key is not None:
    log = logging.getLogger()
    log.addHandler(LogentriesHandler(logentries_key))
else:
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger()

log.setLevel(level=logging_level or logging.INFO)
# for each id, let's create a dict with the id, and a temp sensor cloass
deviceIdtoSensorMap = {}

# this dict is sensors id, mqtt topic to write to
deviceIdtoTopic = {}

sensorConfig = config['sensors']
for key in sensorConfig:
    log.info("watching for sensor with id: %s" % key)
    topic = sensorConfig[key]['mqtt-topic']
    log.info('Topic: %s' % topic)
    min = sensorConfig[key]['valid-range']['min']
    deviceIdtoSensorMap[key] = TempSensor(sensorConfig[key]['valid-range']['min'], sensorConfig[key]['valid-range']['max'])
    deviceIdtoTopic[key] = topic


class THOptions(usage.Options):
    optParameters = [
        ['baudrate', 'b', 57600, 'Serial baudrate'],
        ['port', 'p', serial_port, 'Serial port to use'],]


class ProcessTempSensor(LineReceiver):
    debug = True
    mqttc = mqtt.Client('python_pub')

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
                    configInfo = deviceIdtoSensorMap[key]
                    try:
                        configInfo.submitsample(temp)
                        sma = configInfo.sma()
                        if sma is not None:
                            topic = deviceIdtoTopic[key]
                            log.info('Writing to topic: %s, val: %s' % (topic, str(sma)))
                            try:
                                self.mqttc.connect(mosquitto_url, 1883, keepalive=1000)
                                self.mqttc.publish(topic, str(sma))
                                # let's remove 5 oldest readings so we can build deque back to 10
                                configInfo.remove(5)
                            except socket.error:
                                log.warn('Could not connect to mosquitto')
                        else:
                            log.debug( 'Did not write sma because is None')
                    except ValueError:
                        log.info('Value error, sample ignored: %f' % temp)
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

    baudrate = o.opts['baudrate']
    port = o.opts['port']
    log.debug('About to open port %s' % port)
    s = SerialPort(ProcessTempSensor(), port, reactor, baudrate=baudrate)
    reactor.run()

log.info('Starting')

observer = twisted_log.PythonLoggingObserver(loggerName='logentries')
observer.start()
thread.start_new_thread(SerialInit())