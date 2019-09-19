# -*- coding: utf-8 -*-


import random
import time
import paho.mqtt.client as mqtt

mqtt_broker_host = "192.168.1.20"
mqtt_broker_port = 1883
mqtt_client_id = "homie_3.0_temperature_sensor"
mqtt_client_keepalive = 60

homie_prefix = "homie"
homie_version = "3.0.0"
homie_device_id = "homie-3-temperature-humidity-sensor-basement"
homie_device_name = "Lacrosse sensor"
homie_device_ip = "192.168.1.150"
homie_device_mac = "DE:AD:BE:EF:FE:ED"
homie_device_nodes = ["temperature", "humidity"]
homie_device_state = None

homie_lacrosse_sensor_ids = ["C4", "D8"]

degree_sign= u'\N{DEGREE SIGN}'

def publish_info(topic, attribute, value):
    client.publish("{}/{}".format(topic, attribute), value, 1, True)


def publish_homie_version(client):
    topic = "{}/{}/{}".format(homie_prefix, homie_device_id, "$homie")
    client.publish(topic, homie_version, 1, True)


def advertize_device(lacrosse_code):
    device_id = "lacrosse-temperature-humidity-sensor-{}".format(lacrosse_code)
    device_topic = "homie/{}".format(device_id)
    publish_info(device_topic, "$state", "init")
    publish_device_info(lacrosse_code)
    publish_node_info(lacrosse_code)
    publish_info(device_topic,"$state", "ready")

def publish_device_info(lacrosse_code):
    device_id = "lacrosse-temperature-humidity-sensor-{}".format(lacrosse_code)
    device_topic = "homie/{}".format(device_id)

    publish_info(device_topic,"$homie", homie_version)
    publish_info(device_topic, "$name", homie_device_name)
    publish_info(device_topic, "$localip", homie_device_ip)
    publish_info(device_topic, "$mac", homie_device_mac)
    publish_info(device_topic, "$fw/name", "sensor-firmware")
    publish_info(device_topic, "$fw/version", "1.0.0")
    publish_info(device_topic, "$nodes", "temperature,humidity")
    publish_info(device_topic, "$implementation", "homie-python")
    publish_info(device_topic, "$stats/interval", "60")

def publish_node_info(lacrosse_code):
    device_id = "lacrosse-temperature-humidity-sensor-{}".format(lacrosse_code)
    device_topic = "homie/{}/temperature".format(device_id)

    publish_info(device_topic, "$name", "temperature")
    
    publish_info(device_topic, "$type", "Temperature")
    publish_info(device_topic, "$properties", "temperature")

    device_topic = "homie/{}/temperature/temperature".format(device_id)
    publish_info(device_topic, "temperature", 23)
    publish_info(device_topic, "$name", "temperature")
    publish_info(device_topic, "$settable", "false")
    publish_info(device_topic, "$unit", degree_sign + "C")
    publish_info(device_topic, "$datatype", "float")
    publish_info(device_topic, "$format", "-20:120")

    # humidity
    device_topic = "homie/{}/humidity".format(device_id)
    publish_info(device_topic, "$name", "humidity")
    publish_info(device_topic, "$type", "Humidity")
    publish_info(device_topic, "$properties", "humidity")

    device_topic = "homie/{}/humidity/humidity".format(device_id)
    publish_info(device_topic, "humidity", 55)
    publish_info(device_topic, "$name", "humidity")
    publish_info(device_topic, "$settable", "false")
    publish_info(device_topic, "$unit", "%")
    publish_info(device_topic, "$datatype", "float")
    publish_info(device_topic, "$format", "0:100")


def on_connect(client, userdata, flags, rc):
    print("Connected with result code {}".format(rc))
    advertize_device(homie_lacrosse_sensor_ids[0])
    advertize_device(homie_lacrosse_sensor_ids[1])


def on_message(client, userdata, msg):
    print("{} -> {}".format(msg.topic, msg.payload))


def loop():
    last_temperature_time = 0
    while True:
        if (time.time() - last_temperature_time) > 5:
            temperature_value = random.uniform(20,25)
            humidity_value = random.uniform(50,60)
            print(u"Sending tempertaure value: {0:.2f}{1}C".format(temperature_value,degree_sign))
            device_id = "lacrosse-temperature-humidity-sensor-{}".format("C4")
            device_topic = "homie/{}".format(device_id)
            client.publish("{}/temperature/temperature".format(device_topic), "{0:.2f}".format(temperature_value), 1, True)
            client.publish("{}/humidity/humidity".format(device_topic),
                           "{0:.2f}".format(humidity_value), 1, True)
            last_temperature_time = time.time()


client = mqtt.Client(mqtt_client_id)
client.on_connect = on_connect
client.on_message = on_message

device_id = "lacrosse-temperature-humidity-sensor-{}".format("C4")
device_topic = "homie/{}/".format(device_id)
client.will_set("{}/$state".format(device_topic), "lost", 1, True)

client.connect(mqtt_broker_host, mqtt_broker_port, mqtt_client_keepalive)

client.loop_start()

try:
    loop()
except KeyboardInterrupt:
    print("Stopping client")
    #client.publish("homie/homie-3-temperature-sensor/$state", "disconnected", 1, True)
    client.disconnect()
    client.loop_stop()