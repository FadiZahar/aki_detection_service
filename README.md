# SWEMLS — AKI Detection Service

This document provides detailed instructions on how to set up, run, and test the AKI Detection Service, a project designed for the reliable detection of Acute Kidney Injury (AKI) using HL7 messages.

## Table of Contents

- [Project Overview](#project-overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Running the Service](#running-the-service)
  - [Unit Testing](#unit-testing)
  - [Simulation](#simulation)
  - [Monitoring Metrics](#monitoring-metrics)
- [Project Structure](#project-structure)
- [Built With](#built-with)
- [Engineering Quality](#engineering-quality)
- [Incidents and SLA Compliance](#incidents-and-sla-compliance)
- [Authors](#authors)

## Project Overview

The AKI Detection Service analyses HL7 messages for the detection of AKI events. It's designed to operate within a Kubernetes cluster and is encapsulated in a Docker container for ease of deployment and scalability.

## Key Features

- **Real-Time Data Processing**: Analyses incoming HL7 messages containing patient information and test results.
- **Acute Kidney Illness Prediction**: Uses a pre-trained Random Forest model to predict the likelihood of acute kidney illness.
- **Rapid Alert System**: Aims to alert medical teams through paging via HTTP within 3 seconds of detection.
- **Scalable Infrastructure**: Deployed on Kubernetes for efficient scaling and management.
- **High Availability**: Designed to be resilient and continuously operational.


## Getting Started

### Prerequisites

- Docker
- Kubernetes
- Python 3.8+
- Prometheus (for monitoring)
- See `requirements.txt` for a full list of required dependencies.

### Installation

1. Clone the repository:
    ```bash
    git clone https://gitlab.doc.ic.ac.uk/cv23/devesa.git
    ```
2. Install required Python libraries:
    ```bash
    pip install -r requirements.txt
    ```

## Running the Simulation

### Unit Testing

To run unit tests, execute the following command:

```bash
python -m unittest test/test_prediction_system.py
```

### Simulation

To run the simulation, two terminal should be opened concurrently:

1. Terminal 1: Start the simulator:
    ```bash
    python src/simulator.py
    ```
2. Terminal 2: Run the prediction system
    ```bash
    python src/prediction_system.py
    ```

### Monitoring Metrics

Access Prometheus metrics at `http://localhost:8000/` during simulation.


## Project Structure

- `config/` - Configuration files for different coursework stages.
- `data/` - Contains hospital history data and test data.
- `docs/` - Miscellaneous documentation including Docker and Kubernetes commands.
- `models/` - Trained machine learning models.
- `src/` - Source code for the prediction system and simulator.
- `state/` - Persistent storage for Docker.
- `test/` - Unit and integration tests.
- `.gitignore` - Specifies intentionally untracked files to ignore.
- `Dockerfile` - Docker image specification.
- `coursework6.yaml` - yaml configuration file for Kubernetes deployment
- `README.md` - Project documentation.
- `requirements.txt` - Python dependencies.


## Build With
- *Docker*: Containerisation.
- *Kubernetes*: Orchestration.
- *Prometheus*: Monitoring.
- *Random Forest Algorithm*: Pre-trained Machine Learning model.


## Engineering Quality
We follow best practices in software development, ensuring code quality through unit tests, code reviews, and continuous integration.


## Incidents and SLA Compliance
The service aims to meet specified SLAs, including f3 score performance and alert delivery timing. Incident management procedures are in place to address and mitigate system failures.


## Authors
- *Kyoya Higashino* **(kyoya.higashino23@imperial.ac.uk)**
- *Fadi Zahar* **(fadi.zahar23@imperial.ac.uk)**
- *Carlos Villalobos Sanchez* **(carlos.villalobos-sanchez22@imperial.ac.uk)**
- *Evangelos Georgiadis* **(evangelos.geordiadis23@imperial.ac.uk)**
