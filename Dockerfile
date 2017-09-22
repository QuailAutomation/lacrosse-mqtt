#FROM python

FROM hypriot/rpi-python:2.7.3
MAINTAINER craig

RUN apt-get update && \
    apt-get -y install vim python-twisted python-pip gcc && \
    apt-get clean

# Install Python requirements
ADD requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

#ENV TZ=America/Los_Angeles
#RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Create runtime user
RUN useradd pi
RUN mkdir -p /home/pi
RUN usermod -a -G dialout pi
ADD sensors.py /home/pi/sensors.py
ADD monitor-mqtt.py /home/pi/monitor-mqtt.py
RUN chown -R pi /home/pi/
USER pi

LABEL git-commit=$GIT_COMMIT

#RUN chown -R pi /home/pi/
EXPOSE 5000
CMD ["python","/home/pi/monitor-mqtt.py"]
