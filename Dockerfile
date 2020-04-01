FROM python:3.7-buster
MAINTAINER craig

ARG git_commit
ARG version

RUN apt-get update && \
    apt-get -y install python-pip gcc && \
    apt-get clean

# Install Python requirements
ADD requirements.txt /tmp/requirements.txt
RUN pip install  -r /tmp/requirements.txt

# Create runtime user
RUN useradd pi
RUN mkdir -p /home/pi
RUN usermod -a -G dialout pi
ADD sensors.py /home/pi/sensors.py
ADD monitor-mqtt.py /home/pi/monitor-mqtt.py
RUN chown -R pi /home/pi/
USER pi

LABEL git-commit=$git_commit
LABEL version=$version

#RUN chown -R pi /home/pi/
EXPOSE 5000
CMD ["python","/home/pi/monitor-mqtt.py"]