Sample to run:

docker run -d -t -e SENSORCONFIGFILE=/config/sensors.json -v /home/pi/lacrosse-config-maui:/config --device=/dev/ttyUSB0 --name lacrosse-temp 192.168.0.230:5000/craigham/lacrosse-mqtt-twisted


