__author__ = 'craigh'

import serial
import time
import sys
from threading import Thread
import signal
import paho.mqtt.client as mqtt

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
                if (sr.isOpen() == False):
                    sr.open()

            except Exception, e:
                print "Fatal error opening serial port, aborting..."
                print str(e)
                sys.exit(3)


            mqttc = mqtt.Client('python_pub')
            mqttc.connect('192.168.1.120', 1883)

            time.sleep(2)

            if self.debug:
                print "Starting reading serial port."

            while self.stopFlag == False:
                msg = sr.readline().decode('utf-8')[:-2]
                if len(msg) >= 13:
                    currentTime = time.strftime("%Y-%m-%d %H:%M:%S ")
                    if self.debug:
                        print currentTime + msg
                        # save into shared variable
                    key = msg[2:4]
                    if key is not '\x00\x00':
                        #self.data[key] = (currentTime + msg)
                        mqttc.publish('/test', (currentTime + msg))
                        #mqttc.loop(2)
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
th = spReader('/dev/tty.usbserial-AJ02W9RV', debug)
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
