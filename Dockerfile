FROM ubuntu:jammy
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -yq install python3 python3-pip
COPY simulator.py /simulator/
COPY simulator_test.py /simulator/
COPY prediction_system.py /simulator/
COPY trained_model.pkl /simulator/
COPY messages.mllp /data/
COPY data/history.csv /data/
WORKDIR /simulator
RUN ./simulator_test.py
EXPOSE 8440
EXPOSE 8441
CMD ./simulator.py --messages=/data/messages.mllp && python prediction_system.py
