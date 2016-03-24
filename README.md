A docker container which reads the usb port for output from an arduino sketch which is running on a jeelink, which is monitoring for lacrosse temperature settings.

Sample to run:

docker run -d -t -e SENSORCONFIGFILE=/config/sensors.json -v /home/pi/lacrosse-config-maui:/config --device=/dev/ttyUSB0 --name lacrosse-temp 192.168.0.230:5000/craigham/lacrosse-mqtt-twisted

Note, this is meant to run within docker on an arm based system.  you'd have to modify the from image to switch it to x86.