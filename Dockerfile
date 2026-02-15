FROM python:3.12-slim

# Best practices for Python in containers
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for PostgreSQL and building
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . .

# Collect static files during build
RUN python manage.py collectstatic --noinput

# Run with Gunicorn on port 8080 (App Runner's requirement)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "codeapt_site.wsgi:application"]