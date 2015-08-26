FROM hypriot/rpi-python:2.7.3
MAINTAINER craig

RUN apt-get update && \
    apt-get -y install net-tools python-pip && \
    apt-get clean

# Install Python requirements
ADD requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

ENV TZ=America/Los_Angeles
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Create runtime user
RUN useradd pi
RUN mkdir -p /home/pi
RUN chown -R pi:pi /home/pi
RUN usermod -a -G dialout pi
USER pi

ADD lcr-mqtt.py /home/pi/lcr-mqtt.py

CMD python /home/pi/lcr-mqtt.py
