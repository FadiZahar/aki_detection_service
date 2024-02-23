FROM ubuntu:jammy
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -yq install python3 python3-pip
RUN apt-get update && apt-get install -y dos2unix
COPY requirements.txt /simulator/
RUN pip3 install -r /simulator/requirements.txt
COPY prediction_system.py /simulator/
COPY trained_model.pkl /simulator/
COPY test_prediction_system.py /simulator/
COPY messages.mllp /data/
COPY data/history.csv /data/
RUN dos2unix /simulator/prediction_system.py && \
    chmod +x /simulator/prediction_system.py
WORKDIR /simulator
## add line here
CMD python3 prediction_system.py --pathname=/data/history.csv

FROM ubuntu:jammy
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -yq install python3 python3-pip
RUN apt-get update && apt-get install -y dos2unix
COPY requirements.txt /simulator/
RUN pip3 install -r /simulator/requirements.txt
COPY prediction_system.py /simulator/
COPY trained_model.pkl /simulator/
COPY test_prediction_system.py /simulator/
COPY messages.mllp /data/
COPY data/history.csv /data/
RUN dos2unix /simulator/prediction_system.py && \
    chmod +x /simulator/prediction_system.py
WORKDIR /simulator
# Run tests before executing final command
RUN python3 test_prediction_system.py
# Check the exit status of the previous command and proceed accordingly
RUN TEST_RESULT=$? && if [ $TEST_RESULT -eq 0 ]; then \
                            echo "Tests passed, proceeding with CMD."; \
                        else \
                            echo "Tests failed, skipping CMD."; \
                            exit 1; \
                        fi
# Final command to execute if tests pass
CMD python3 prediction_system.py --pathname=/data/history.csv
