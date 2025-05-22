# Start with an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# - ffmpeg is crucial for yt-dlp format conversions (e.g., to mp3, or merging video and audio)
# - git and other build tools might be needed for some python packages, though not strictly for yt-dlp/fastapi usually
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp directly to get the latest version
RUN pip install --no-cache-dir yt-dlp

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container at /app
COPY . .

# Make port 80 available to the world outside this container (FastAPI default is 8000)
# The EXPOSE instruction does not actually publish the port.
# It functions as a type of documentation between the person who builds the image and the person who runs the container.
EXPOSE 8000

# Set environment variable for API key (should be overridden at runtime)
ENV API_KEY=changeme

# Define environment variable if needed (e.g. for yt-dlp options, though not used here)
# ENV NAME World

# Run main.py when the container launches
# Uvicorn is an ASGI server, good for FastAPI
# --host 0.0.0.0 makes it accessible from outside the container
# --port 8000 matches the EXPOSE instruction
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# Example entrypoint (user should override API_KEY at runtime):
# docker run -e API_KEY=your_secret_key ...