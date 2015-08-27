__author__ = 'craigh'

import serial
import time
import sys
from threading import Thread
import signal
import paho.mqtt.client as mqtt
from collections import deque


# default settings
debug = False
sstopFlag = False


# signal  handler for dumping internal state
def sig_handler(signum, frame):
    if debug:
        print
        'Signal handler called with signal ', signum
    f = open('dump.log', 'w+')
    f.write("--- DUMPING STATE ---\n")
    for key, val in th.data.iteritems():
        f.write("[" + key + "] " + val)
    f.write("---------------------\n")
    f.close()


# prints usage
def show_usage(argv):
    print
    "Usage: "
    print
    str(argv[0]) + " <port> " + " [debug]"
    print
    "  port - port number to listen for incoming connections"
    print
    "  debug - if passed then debug mode is on"


# thread for reading from JeeLink/Node over serial port
class spReader(Thread):
    deviceToTopicMap = {'3C': "sensors/basement/winecellar/temperature"}
    last10Readings = deque(maxlen=10)

    def __init__(self, serialPort, debug):
        Thread.__init__(self)
        self.debug = debug
        self.serialPort = serialPort
        self.data = {}
        self.stopFlag = False;

    def notifyStop(self):
        self.stopFlag = True
        print
        "Shutting down serial port thread, notified stop."

    def sma(self):
        sumSamples = sum(self.last10Readings)
        numSamples = len(self.last10Readings)
        if self.debug:
            print 'Sum: ' + str(sumSamples)
            print 'Num samples: ' + str(numSamples)
        if len(self.last10Readings) < 5:
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

    def run(self):
        while self.stopFlag == False:
            try:
                # configure the serial connections
                sr = serial.Serial(port=self.serialPort, baudrate=57600,
                                   parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS,
                                   xonxoff=False, rtscts=False, dsrdtr=False, timeout=2)
                if self.debug:
                    print
                    "Trying to open serial port " + self.serialPort + ", settings: " + str(sr)
                if sr.isOpen() == False:
                    sr.open()

            except Exception, e:
                print "Fatal error opening serial port, aborting..."
                print str(e)
                sys.exit(3)


            mqttc = mqtt.Client('python_pub')
            mqttc.connect('192.168.1.122', 1883,keepalive=1000)

            time.sleep(2)

            if self.debug:
                print "Starting reading serial port."

            while self.stopFlag == False:
                msg = sr.readline().decode('utf-8')[:-2]
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
                        print 'Connection alive: ' + str(mqttc._check_keepalive())
                        topic = self.deviceToTopicMap[key]
                        self.submitSample(temp)
                        sma = self.sma()
                        if sma is not None:
                            if self.debug:
                                print 'Writing to topic: ' + topic
                            mqttc.publish(topic, str(sma))
                            if self.debug:
                                print 'Apparent success writing to mqtt'
                            self.last10Readings.clear()
                        else:
                            if self.debug:
                                print 'Did not write sma because is None'
                        #mqttc.loop(2)
                    except KeyError:
                        print 'Key not found: ' + key
                else:
                    if self.debug:
                            print "Nothing read from serial port"  # close serial port
            sr.close()
            print "Closing serial port."  # ----- MAIN --------------
# read input arguments

if len(sys.argv) >= 2:
    arg = sys.argv[1]
    if arg == "debug":
        debug = True;

signal.signal(signal.SIGUSR1, sig_handler)
if debug:
    print "Handler registred for SIGUSR1"

# start serial port thread
th = spReader('/dev/ttyUSB0', debug)
th.start()

# start TCP listener
try:
    # check for serial port thread erros first
    if not th.isAlive():
        sstopFlag = True;

    while sstopFlag == False:
        if not th.isAlive():
            sstopFlag = True;
        time.sleep(5)

except KeyboardInterrupt:
    print
    "  SIGINT caught, stopping thread..."
    th.notifyStop()
    sstopFlag = True;


# wait for serial port reader thread to end
th.join()
sys.exit(0)

