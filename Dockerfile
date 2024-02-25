# Use Ubuntu Jammy as the base image
FROM ubuntu:jammy

# Install necessary packages in a single RUN command to reduce layers and clean up afterwards
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -yq \
    python3 \
    python3-pip \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Create the /state directory for the SQLite database
RUN mkdir -p /state && chmod 777 /state

# Set the working directory to /simulator
WORKDIR /simulator

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt /simulator/
# Install Python dependencies
RUN pip3 install -r requirements.txt

# Copy the rest of the application files
COPY prediction_system.py trained_model.pkl test_prediction_system.py /simulator/
# Copy additional files needed for the application
COPY messages.mllp /data/
COPY hospital-history/history.csv /hospital-history/

# Convert line endings and adjust permissions
RUN dos2unix prediction_system.py && chmod +x prediction_system.py

# Run tests to ensure everything is set up correctly. Docker build will stop if this fails.
RUN python3 test_prediction_system.py --pathname=/hospital-history/history.csv

# Set environment variable to ensure Python output is displayed in the Docker logs in real-time
ENV PYTHONUNBUFFERED=1

# Command to run the prediction system. Ensure this matches your application's needs.
CMD ["python3", "prediction_system.py", "--pathname=/hospital-history/history.csv", "--db_path=/state/my_database.db"]


