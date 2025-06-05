# /home/ubuntu/mega_secretary/Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for psycopg2 (if not using -binary)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
# Note: psycopg2-binary includes dependencies, so the above is likely not needed.

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
# Copy config first to potentially leverage Docker cache if only app code changes
COPY ./config /app/config
COPY ./app /app/app

# Make port 8000 available to the world outside this container (Gunicorn default)
EXPOSE 8000

# Define the command to run the application using Gunicorn
# The number of workers can be adjusted based on the server resources
# Ensure the module path 'app.main:app' matches your Flask app instance location
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app.main:app"]

