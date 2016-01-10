__author__ = 'craigh'
import logging
from twisted.protocols.basic import LineReceiver

from twisted.internet import reactor
from twisted.internet.serialport import SerialPort
from twisted.python import usage
import paho.mqtt.client as mqtt
import thread
from collections import deque

class THOptions(usage.Options):
    optParameters = [
        ['baudrate', 'b', 57600, 'Serial baudrate'],
        ['port', 'p', '/dev/ttyUSB0', 'Serial port to use'],]


class ProcessTempSensor(LineReceiver):
    debug = True
    mqttc = mqtt.Client('python_pub')
    deviceToTopicMap = {'3C': "sensors/basement/winecellar/temperature"}

    last10Readings = deque(maxlen=10)

    def sma(self):
        sumSamples = sum(self.last10Readings)
        numSamples = len(self.last10Readings)
        if self.debug:
            print 'Sum: ' + str(sumSamples)
            print 'Num samples: ' + str(numSamples)
        if len(self.last10Readings) < 10:
            if self.debug:
                print 'SMA is None because # samples is: ' + str(len(self.last10Readings))
            return None
        else:
            avg = sumSamples/numSamples;
            if self.debug:
                print 'Avg ' + str(avg)
            return avg

    def submitSample(self, sample):
        if self.debug:
            'submit sample called with: ' + str(sample)
        # check if within 1 degree of sma, if it exists
        mostRecentAvg = self.sma()
        if self.debug:
            print 'sma: ' + str(mostRecentAvg)
        if mostRecentAvg is not None:
            if abs(sample - mostRecentAvg) < 1:
                self.last10Readings.append(sample)
                if self.debug:
                    print 'Submitted sample'
        else:
            if 10.0 <= sample <= 25:
                self.last10Readings.append(sample)
                if self.debug:
                    print 'Submitted sample'
            else:
                if self.debug:
                    print 'Sample out of range'

    def lineReceived(self, line):
        try:
            msg = line.rstrip()
            if self.debug:
                print msg
            if len(msg) >= 13:
                msgElements = msg.split(':')
                if self.debug:
                    'Num elements' + str(msgElements)
                key = msgElements[1]
                if self.debug:
                    print 'key: ' + key
                temp = float(msgElements[2])
                if self.debug:
                    print "temp: '" + str(temp) + "'"
                try:
                    topic = self.deviceToTopicMap[key]
                    self.submitSample(temp)
                    print self.last10Readings
                    sma = self.sma()
                    if sma is not None:
                        if self.debug:
                            print 'Writing to topic: ' + topic
                        self.mqttc.connect('192.168.1.122', 1883,keepalive=1000)
                        self.mqttc.publish(topic, str(sma))
                        if self.debug:
                            print 'Apparent success writing to mqtt'
                            for x in xrange(5):
                                self.last10Readings.popleft()
                                # let's remove 5 oldest readings so we can build deque back to 10

                    else:
                        if self.debug:
                            print 'Did not write sma because is None'
                    #mqttc.loop(2)
                except KeyError:
                    print 'Key not found: ' + key
        except ValueError:
            logging.error('Unable to parse data %s' % line)
            return

def SerialInit():
    o = THOptions()
    try:
        o.parseOptions()
    except usage.UsageError, errortext:
        logging.error('%s %s' % (sys.argv[0], errortext))
        logging.info('Try %s --help for usage details' % sys.argv[0])
        raise SystemExit, 1

    baudrate = o.opts['baudrate'] #int('115200')
    port = o.opts['port']
    logging.debug('About to open port %s' % port)
    s = SerialPort(ProcessTempSensor(), port, reactor, baudrate=baudrate)
    reactor.run()


thread.start_new_thread(SerialInit())