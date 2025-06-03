# /shiny_app/Dockerfile

FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy only the shiny_app directory contents into the container at /app
COPY ./shiny_app/ /app/

COPY ./data/ /app/data/

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["shiny", "run", "--host", "0.0.0.0", "--port", "8000", "app.py"]