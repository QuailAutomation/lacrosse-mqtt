A docker container which monitors a mqtt topic for readings which are in the format a jeelink outputs for lacrosse sensors.
eg. D:80: 29.5:99

Sample to run:

docker run -d --restart=always --name=lacrosse -e SENSORCONFIGFILE=/config.json -v /home/craigh/rpi-lacrosse-config/sensors.json:/config.json registry.m.quailholdings.com/rpi-lacrosse


Sketch for the jeelink:
https://bitbucket.org/quailholdings/arduino-jeelink-lacrosse
