# /shiny_app/Dockerfile

FROM python:3.9-slim

# Copy the entire repo so the image includes all data and project files.
WORKDIR /app
COPY ./ /app/

# Run the Shiny app from its directory.
WORKDIR /app/shiny_app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["shiny", "run", "--host", "0.0.0.0", "--port", "8000", "app.py"]
