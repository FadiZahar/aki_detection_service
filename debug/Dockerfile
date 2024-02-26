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

# Set the working directory to /deployment
WORKDIR /deployment

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt /deployment/
# Install Python dependencies
RUN pip3 install -r requirements.txt

# Copy the rest of the application files
COPY update_database.py /deployment/
# Copy additional files needed for the application
COPY state/my_database.db /deployment/state/
COPY data/recovery-data/messages.txt /deployment/data/recovery-data/

# Convert line endings and adjust permissions
RUN dos2unix prediction_system.py && chmod +x update_database.py

# Command to run the prediction system. Ensure this matches your application's needs.
CMD ["python3", "update_database.py"]


