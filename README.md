# MediFlow AI

### Emergency Department Triage & Waiting-Time Prediction System

MediFlow AI is an AI-powered emergency department management prototype designed to support patient intake, clinical triage, queue management, and waiting-time prediction through an integrated web-based platform.

The system combines **machine learning, FastAPI, PostgreSQL, React, TypeScript, WebSockets, and Docker** into a unified workflow for reception staff, triage personnel, doctors, administrators, and patient-facing queue displays.

> **Academic AI Prototype — Not intended for real clinical decisions, diagnosis, or treatment.**

---

## Overview

Emergency departments require fast and organized coordination between patient registration, triage, doctors, and queue management.

MediFlow AI provides a centralized workflow that allows healthcare staff to:

* Register and manage patients
* Record clinical information
* Perform human-assisted triage
* Generate AI-supported acuity predictions
* Predict estimated waiting time
* Manage emergency department queues
* Track patient visits and clinical workflow
* Provide role-based access for different staff members
* Display queue information in real time
* Support Arabic and English interfaces
* Maintain audit information for important clinical operations

The system is designed as an **academic software and machine learning prototype** demonstrating how AI can be integrated into an emergency department workflow.

---

## Key Features

### Patient Registration

Reception staff can register patients and collect relevant administrative information, including:

* Patient identity
* Contact information
* Department
* Insurance information
* Identification information
* Military/service information where applicable

Each visit receives a queue ticket that can be used throughout the emergency department workflow.

---

### AI-Assisted Triage

MediFlow AI combines human clinical assessment with machine learning-based decision support.

The system predicts an emergency department acuity category and provides the result as decision-support information rather than replacing professional clinical judgment.

The implemented classification target groups the original triage levels into three categories:

| Category | Original Levels |
| -------- | --------------- |
| High     | 1–2             |
| Medium   | 3               |
| Low      | 4–5             |

The final application keeps the **human triage workflow** as part of the process while providing an additional AI-generated prediction.

---

## Machine Learning

The machine learning pipeline was developed using emergency department records from the **NHAMCS 2018–2022 dataset**.

The project includes preprocessing, feature engineering, model training, evaluation, and model persistence.

### Classification Models Evaluated

Several machine learning algorithms were compared:

| Model               | Evaluation Score |
| ------------------- | ---------------: |
| Logistic Regression |       **0.9203** |
| Random Forest       |       **0.9200** |
| Gradient Boosting   |       **0.9175** |
| Decision Tree       |       **0.8715** |

Based on the evaluation results, **Logistic Regression was selected as the final triage classification model** for the prototype.

The trained pipeline is integrated with the backend AI service for inference.

### Why Logistic Regression?

The model provided competitive predictive performance while remaining relatively lightweight and interpretable compared with more complex ensemble approaches.

This makes it suitable for an academic decision-support prototype where model transparency and maintainability are important considerations.

---

## Waiting-Time Prediction

In addition to triage classification, the project includes a regression component for estimating patient waiting time.

The objective is to estimate:

```text
Expected Waiting Time → minutes
```

The prediction can be incorporated into the emergency department queue workflow to provide an estimated waiting period based on available patient and operational information.

The waiting-time component is intended as a predictive prototype and should not be interpreted as a guaranteed real-world waiting time.

---

## System Architecture

MediFlow AI follows a layered architecture:

```text
                         ┌─────────────────────┐
                         │     React Frontend  │
                         │  TypeScript / Vite  │
                         └──────────┬──────────┘
                                    │
                             REST / WebSocket
                                    │
                         ┌──────────▼──────────┐
                         │     FastAPI API     │
                         │      Backend        │
                         └──────────┬──────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
       ┌─────────────┐       ┌─────────────┐      ┌─────────────┐
       │ PostgreSQL  │       │ AI Services │      │  WebSocket  │
       │  Database   │       │ ML Pipeline │      │ Real-Time   │
       └─────────────┘       └─────────────┘      └─────────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Trained ML Pipeline │
                         │ Logistic Regression │
                         └─────────────────────┘
```

---

## Application Workflow

```text
Patient Registration
        │
        ▼
Patient / Visit Creation
        │
        ▼
Human Clinical Assessment
        │
        ├───────────────┐
        │               │
        ▼               ▼
 Human Triage       AI Prediction
        │               │
        └───────┬───────┘
                ▼
        Acuity / Priority
                │
                ▼
        Queue Management
                │
                ▼
      Waiting-Time Prediction
                │
                ▼
         Doctor Workflow
                │
                ▼
       Visit Completion
```

---

## Main User Roles

### Reception

* Register patients
* Create visits
* Generate queue tickets
* Manage patient intake information

### Triage

* Review patient information
* Perform clinical assessment
* Review AI-supported acuity prediction
* Assign/update patient priority

### Doctor

* Review waiting patients
* Access patient and visit information
* Manage clinical workflow
* Complete visits and record outcomes

### Administrator

* Manage system information
* Manage departments and users
* Review operational information
* Access administrative workflows

### Queue Display

A dedicated display interface provides real-time queue information for the emergency department waiting area.

---

## Technology Stack

### Backend

* Python
* FastAPI
* SQLAlchemy
* Alembic
* PostgreSQL
* Pydantic
* JWT-based authentication
* WebSockets
* Pytest

### Machine Learning

* Python
* Scikit-learn
* Pandas
* NumPy
* Jupyter Notebook
* Logistic Regression
* Decision Tree
* Random Forest
* Gradient Boosting

### Frontend

* React
* TypeScript
* Vite
* Tailwind CSS
* Vitest

### Infrastructure

* Docker
* Docker Compose
* Nginx

---

## Project Structure

```text
mediflow-ai/
│
├── ai/
│   ├── data/
│   │   └── ...
│   ├── models/
│   │   └── ...
│   └── src/
│       ├── ml99999999.ipynb
│       └── model.ipynb
│
├── backend/
│   ├── alembic/
│   ├── app/
│   │   ├── core/
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── routers/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── tests/
│   │   ├── utils/
│   │   └── websocket/
│   │
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── store/
│   │   └── styles.css
│   │
│   ├── package.json
│   ├── Dockerfile
│   └── nginx.conf
│
├── docker-compose.yml
└── .gitignore
```

---

## Security & Access Control

The backend implements several security-oriented mechanisms, including:

* JWT-based authentication
* Password-based authentication
* Role-based permissions
* Protected API routes
* Environment-based configuration
* Audit-related services
* Input validation
* Database constraints
* Separation of secrets from source code

Sensitive configuration values are intentionally excluded from version control.

Create your local environment file from:

```text
backend/.env.example
```

and configure the required environment variables before running the application.

---

## Database

MediFlow AI uses **PostgreSQL** as its primary relational database.

Database migrations are managed through **Alembic**.

The database layer contains entities supporting:

* Patients
* Visits
* Departments
* Doctors
* Triage
* Queue management
* Authentication
* Clinical workflows
* Administrative operations
* Audit information

---

## Testing

The project includes automated backend and frontend tests covering areas such as:

* Authentication and security
* Patient management
* Clinical validation
* Triage workflows
* Queue management
* Visit workflows
* Administrative validation
* AI decision support
* Doctor workflows
* Completed patient management

Backend tests use:

```text
Pytest
```

Frontend tests use:

```text
Vitest
```

---

## Running with Docker

The recommended deployment method for the complete application is Docker Compose.

### 1. Clone the repository

```bash
git clone https://github.com/HusseinZahran-1/mediflow-ai.git
cd mediflow-ai
```

### 2. Configure environment variables

Create the backend environment file:

```bash
cp backend/.env.example backend/.env
```

Then update the values according to your local environment.

### 3. Start the application

```bash
docker compose up --build
```

The services can then be accessed through the configured frontend and backend endpoints.

---

## API

The backend is built using FastAPI and provides REST endpoints for the application's major workflows.

During development, FastAPI provides interactive API documentation through:

```text
/docs
```

and:

```text
/redoc
```

when enabled by the application configuration.

---

## Machine Learning Workflow

The general ML workflow used in the project is:

```text
NHAMCS Dataset
      │
      ▼
Data Cleaning
      │
      ▼
Exploratory Data Analysis
      │
      ▼
Feature Engineering
      │
      ▼
Preprocessing
      │
      ▼
Train / Validation / Test
      │
      ▼
Model Comparison
      │
      ▼
Model Selection
      │
      ▼
Pipeline Persistence
      │
      ▼
FastAPI AI Service
      │
      ▼
Application Inference
```

The trained preprocessing and model pipeline is persisted and consumed by the backend rather than retraining the model during normal application use.

---

## Dataset

The machine learning component was developed using emergency department data from the **National Hospital Ambulatory Medical Care Survey (NHAMCS)** covering 2018–2022.

The dataset is **not included in this repository**.

This repository intentionally excludes raw datasets and generated model artifacts that are unsuitable for source-control distribution.

---

## Disclaimer

> **This project is an academic AI/software engineering prototype. It is not a medical device and is not intended to provide medical diagnosis, treatment recommendations, or autonomous clinical decisions.**
>
> AI-generated predictions are demonstrations of machine learning integration and should not replace qualified healthcare professionals, clinical guidelines, or institutional protocols.

---

## Project Goals

MediFlow AI was developed to demonstrate practical integration between:

* Artificial Intelligence
* Machine Learning
* Backend Engineering
* Database Systems
* Frontend Development
* Real-Time Communication
* Authentication & Authorization
* Automated Testing
* Containerization

The project focuses on building a complete end-to-end system rather than a standalone machine learning model.

---

## Future Improvements

Potential future development includes:

* Improved waiting-time prediction models
* Additional model interpretability techniques
* Model monitoring and performance tracking
* More comprehensive clinical validation
* Real-time operational analytics
* Advanced queue optimization
* Expanded multilingual support
* Production-grade deployment infrastructure
* Additional security hardening
* Integration with standardized healthcare interoperability systems

---

## Author

**Hussein Zahran**

Artificial Intelligence Student
Al-Zaytoonah University of Jordan

* GitHub: [HusseinZahran-1](https://github.com/HusseinZahran-1)
* LinkedIn: [Hussein Zahran](https://www.linkedin.com/in/hussein-zahran-911481358/)

---

## License

This project is currently provided for **academic and portfolio purposes**.

A formal open-source license can be added in a future release.
