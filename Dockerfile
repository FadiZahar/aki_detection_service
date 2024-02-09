FROM ubuntu:jammy
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -yq install python3 python3-pip
RUN apt-get update && apt-get install -y dos2unix
COPY requirements.txt /simulator/
RUN pip3 install -r /simulator/requirements.txt
COPY prediction_system.py /simulator/
COPY trained_model.pkl /simulator/
COPY messages.mllp /data/
COPY data/history.csv /data/
RUN dos2unix /simulator/prediction_system.py && \
    chmod +x /simulator/prediction_system.py
WORKDIR /simulator
CMD python3 prediction_system.py --pathname=/data/history.csv
