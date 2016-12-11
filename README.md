A docker container which monitors a mqtt topic for readings which are in the format a jeelink outputs for lacrosse sensors.
eg. D:80: 29.5:99

Sample to run:

docker run -d --restart=always --name=lacrosse -e SENSORCONFIGFILE=/config.json -v /home/craigh/rpi-lacrosse-config/sensors.json:/config.json registry.m.quailholdings.com/rpi-lacrosse

Note, this is meant to run within docker on an arm based system.  you'd have to modify the from image to switch it to x86.

Sketch for the jeelink:
https://bitbucket.org/quailholdings/arduino-jeelink-lacrosse
