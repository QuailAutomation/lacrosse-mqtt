import os
import json
import logging

import thread
from flask import Flask, Response
from prometheus_client import generate_latest
from sensors import TempSensor, MqttMonitor
try:
    import graypy
except ImportError:
    pass


app = Flask(__name__)

# instrumentation
CONTENT_TYPE_LATEST = str('text/plain; version=0.0.4; charset=utf-8')

config_file = os.getenv('SENSORCONFIGFILE', './sensors.json')
with open(config_file) as json_file:
    config = json.load(json_file)

# read some env variables
mosquitto_url = config['mqtt-url']

log = logging.getLogger()

try:
    gelf_url = config['gelf-url']
except KeyError:
    gelf_url = None

# if we have log configuration for log servers, add that, otherwise let's use basic logging
isLogConfigInfo = False

#TODO should test setting the url, but not having graypy avail as lib
if gelf_url is not None:
    handler = graypy.GELFHandler(gelf_url, 12201, localname='lacrosse-processing', facility="maui")
    log.addHandler(handler)
    isLogConfigInfo = True

if not isLogConfigInfo:
    logging.basicConfig(level=logging.INFO)

logging_level = config['log-level'] or "INFO"
log.setLevel(level=logging_level or logging.INFO)


# used for dumping the dicts, probably could move over to MonitorMQTT class
class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, TempSensor):
            return obj.toJSON()
        return json.JSONEncoder.default(self, obj)


def flask_thread():
     app.run(host='0.0.0.0')

thread.start_new_thread(flask_thread,())


@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


mqtt_monitor = MqttMonitor(config['sensors'], mosquitto_url)


# add rest interface
@app.route('/lacrosse/1.0/sensors/temperature', methods=['GET'])
def get_sensors_temperature():
    return json.dumps(mqtt_monitor.device_id_to_temp_sensor_map,cls=SetEncoder,
                      sort_keys=True,indent=4, separators=(',', ': '))


@app.route('/lacrosse/1.0/sensors/humidity', methods=['GET'])
def get_sensors_humidity():
    return json.dumps(mqtt_monitor.device_id_to_humidity_sensor_map,cls=SetEncoder,
                      sort_keys=True,indent=4, separators=(',', ': '))


# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
try:
    mqtt_monitor.loop_forever()
except:
    log.exception("Exception caught in forever loop")
