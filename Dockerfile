# Base image for Python 3.10 Lambda
FROM public.ecr.aws/lambda/python:3.10

# Install system dependencies needed for pandas, mplfinance, ta
RUN yum install -y \
    gcc \
    gcc-c++ \
    make \
    libffi-devel \
    openssl-devel \
    lapack \
    lapack-devel \
    blas \
    blas-devel \
    freetype-devel \
    libpng-devel \
    && yum clean all

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy requirements and install dependencies
COPY requirements.txt .

# Upgrade pip
RUN pip install --upgrade pip

# Install heavy numerical libs first to avoid build errors
RUN pip install numpy pandas matplotlib

# Install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY app.py .

# Set Lambda entrypoint
CMD ["app.lambda_handler"]
