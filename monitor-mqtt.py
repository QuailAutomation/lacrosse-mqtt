import time
import os
import json
import paho.mqtt.client as mqtt
import logging
import socket
import datetime
from time import sleep
#some optional logging choices
try:
    from logentries import LogentriesHandler
except ImportError:
    pass
try:
    import graypy
except ImportError:
    pass


from sensors import TempSensor


config_file = os.getenv('SENSORCONFIGFILE', './sensors.json')
with open(config_file) as json_file:
    config = json.load(json_file)

# read some env variables
mosquitto_url = config['mqtt-url']

log = logging.getLogger()

try:
    logentries_key = config['log-entries-key']
except KeyError:
    logentries_key = None

try:
    gelf_url = config['gelf-url']
except KeyError:
    gelf_url = None

# if we have log configuration for log servers, add that, otherwise let's use basic loggin
isLogConfigInfo = False

if logentries_key is not None:
    try:
        log.addHandler(LogentriesHandler(logentries_key))
        isLogConfigInfo = True
    except NameError:
        pass

if gelf_url is not None:
    handler = graypy.GELFHandler(gelf_url, 12201, localname='lacrosse-processing', facility="maui")
    log.addHandler(handler)
    isLogConfigInfo = True

if not isLogConfigInfo:
    logging.basicConfig(level=logging.INFO)

logging_level = config['log-level'] or "INFO"
log.setLevel(level=logging_level or logging.INFO)

# for each id, let's create a dict with the id, and a temp sensor class
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
    device_id_to_temp_sensor_map[key] = TempSensor(key,sensorConfig[key]['valid-range']['min'], sensorConfig[key]['valid-range']['max'])
    device_id_to_humidity_sensor_map[key] = TempSensor(id=key,min=0, max=97, max_difference_from_average=15)
    deviceIdtoTopic[key] = topic


def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("private/jeelink/+")

# this dict will keep track of last time we received a message for the sensors.
# more than 1 jeelink may pick up the reading from a temp sensor, so igore readings
# within a recent window...ie within 3 seconds
device_id_to_last_reading_time = {}


# if i we reject 5 entries in a
def is_ok_to_accept_reading(key):
    return_value = True
    log.debug("checking if we've had a reading within the ingore window")
    now = datetime.datetime.now()
    try:
        time_last_reading = device_id_to_last_reading_time[key]
        elapsed_time = now  - time_last_reading
        if elapsed_time.total_seconds() > 3:
            return_value = True
            log.debug("we can accept, elapsed time: %f" % elapsed_time.total_seconds())
        else:
            return_value = False
    except KeyError:
        log.info('Key not found: ' + key)

    device_id_to_last_reading_time[key] = datetime.datetime.now()
    return return_value


def get_sensor(key, type):
    try:
        if type == 'temperature':
            return device_id_to_temp_sensor_map[key]
        elif type == 'humidity':
            return device_id_to_humidity_sensor_map[key]
        else:
            log.error('Illegal sensor type: "%s"' % type)
    except KeyError:
        log.info('Key not found: ' + key)


def write_to_mqtt(topic, value):
    log.info('Writing to topic: %s, val: %s' % (topic, str(value)))
    try:
        client.publish(topic, str(value))
    except socket.error:
        log.warn('Could not connect to mosquitto')
        client.connect(mosquitto_url, 1883, keepalive=1000)


def submit_sample(sensor, sample_value, topic, type):
    log.debug("submit sample called :" + str(sample_value))
    try:
        sensor.submit_sample(sample_value)
        sma = sensor.sma()
        if sma is not None:
            if type == 'temperature':
                write_to_mqtt(topic + type, str("%.1f" % sma))
            elif type == 'humidity':
                write_to_mqtt(topic + type, str("%.0f" % sma))
            # let's remove 5 oldest readings so we can build deque back to 10
            else:
                log.warn("Received unexpected sample type: %s" % type)
            sensor.remove(5)
        else:
            log.debug('Did not write sma because is None')
    except ValueError:
        log.info('Invalid reading. Sample ignored. value=%f' % sample_value)


def on_message(client, userdata, msg):
    payload = msg.payload
    msgElements = payload.split(':')
    key = msgElements[1]
    log.debug('key: %s' % key)
    if is_ok_to_accept_reading(key):
        temp = float(msgElements[2])
        log.debug("temp: '%f'" % temp)
        sensor = get_sensor(key, 'temperature')
        if sensor is not None:
            topic = deviceIdtoTopic[key]
            submit_sample(sensor, temp, topic, 'temperature')
            log.debug('Submitted temperature reading. key=%s value=%f' % (key, temp))
            humidity = float(msgElements[3])
            sensor = get_sensor(key, 'humidity')
            if humidity < 99:
                log.debug("humidity: '%f'" % humidity)
                submit_sample(sensor, humidity, topic, 'humidity')

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(mosquitto_url, 1883, 60)

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()
