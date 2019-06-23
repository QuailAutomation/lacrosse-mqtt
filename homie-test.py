import random
import time
import paho.mqtt.client as mqtt

mqtt_broker_host = "192.168.1.20"
mqtt_broker_port = 1883
mqtt_client_id = "homie_3.0_temperature_sensor"
mqtt_client_keepalive = 60

homie_prefix = "homie"
homie_version = "3.0.0"
homie_device_id = "homie-3-temperature-humidity-sensor"
homie_device_name = "Lacrosse sensor"
homie_device_ip = "192.168.1.150"
homie_device_mac = "DE:AD:BE:EF:FE:ED"
homie_device_nodes = ["temperature", "humidity"]
homie_device_state = None

def publish_homie_version(client):
    topic = "{}/{}/{}".format(homie_prefix, homie_device_id, "$homie")
    client.publish(topic, homie_version, 1, True)

def advertize_device():
    client.publish("homie/homie-3-temperature-sensor/$state", "init", 1, True)
    publish_device_info()
    publish_node_info()
    client.publish("homie/homie-3-temperature-sensor/$state", "ready", 1, True)

def publish_device_info():
    client.publish("homie/homie-3-temperature-sensor/$homie", homie_version, 1, True)
    client.publish("homie/homie-3-temperature-sensor/$name", homie_device_name, 1, True)
    client.publish("homie/homie-3-temperature-sensor/$localip", homie_device_ip, 1, True)
    client.publish("homie/homie-3-temperature-sensor/$mac", homie_device_mac, 1, True)
    client.publish("homie/homie-3-temperature-sensor/$fw/name", "sensor-firmware", 1, True)
    client.publish("homie/homie-3-temperature-sensor/$fw/version", "1.0.0", 1, True)
    client.publish("homie/homie-3-temperature-sensor/$nodes", "temperature", 1, True)
    client.publish("homie/homie-3-temperature-sensor/$implementation", "homie-python", 1, True)
    client.publish("homie/homie-3-temperature-sensor/$stats/interval", "60", 1, True)

def publish_node_info():
    client.publish("homie/homie-3-temperature-sensor/temperature/$name", "Indoor temperature", 1, True)
    client.publish("homie/homie-3-temperature-sensor/temperature/$type", "Temperature", 1, True)
    client.publish("homie/homie-3-temperature-sensor/temperature/$properties", "temperature", 1, True)

    client.publish("homie/homie-3-temperature-sensor/temperature/temperature", 23, 1, True)
    client.publish("homie/homie-3-temperature-sensor/temperature/temperature/$name", "Indoor temperature", 1, True)
    client.publish("homie/homie-3-temperature-sensor/temperature/temperature/$settable", "false", 1, True)
    client.publish("homie/homie-3-temperature-sensor/temperature/temperature/$unit", "C", 1, True)
    client.publish("homie/homie-3-temperature-sensor/temperature/temperature/$datatype", "float", 1, True)
    client.publish("homie/homie-3-temperature-sensor/temperature/temperature/$format", "-20:120", 1, True)

def on_connect(client, userdata, flags, rc):
    print("Connected with result code {}".format(rc))
    advertize_device()


def on_message(client, userdata, msg):
    print("{} -> {}".format(msg.topic, msg.payload))


def loop():
    last_temperature_time = 0
    while True:
        if (time.time() - last_temperature_time) > 5:
            temperature_value = random.uniform(20,25)
            print("Sending tempertaure value: {0:.2f}C".format(temperature_value))
            client.publish("homie/homie-3-temperature-sensor/temperature/temperature", "{0:.2f}".format(temperature_value), 1, True)
            last_temperature_time = time.time()


client = mqtt.Client(mqtt_client_id)
client.on_connect = on_connect
client.on_message = on_message

client.will_set("homie/homie-3-temperature-sensor/$state", "lost", 1, True)

client.connect(mqtt_broker_host, mqtt_broker_port, mqtt_client_keepalive)

client.loop_start()

try:
    loop()
except KeyboardInterrupt:
    print("Stopping client")
    client.publish("homie/homie-3-temperature-sensor/$state", "disconnected", 1, True)
    client.disconnect()
    client.loop_stop()