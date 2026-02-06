# /backend_api/Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy requirements first for better build caching, then install deps
COPY ./backend_api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend app into the container
COPY ./backend_api/ /app/

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variable
ENV FLASK_APP=api.py
ENV FLASK_RUN_HOST=0.0.0.0

# Run api.py when the container launches
CMD ["flask", "run"]
