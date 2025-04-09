# Dockerfile
FROM python:3.10-slim

# Set work directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Expose any necessary ports (for the web app, for instance)
EXPOSE 8000

# Set environment variables (if any)
ENV PYTHONUNBUFFERED=1

# Command to run your application (you might run the bot or the processor)
# For example, to run the processor:
CMD ["python", "processor/reposting_live.py"]
