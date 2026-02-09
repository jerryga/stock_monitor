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

# Upgrade pip
RUN pip install --upgrade pip

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
WORKDIR ${LAMBDA_TASK_ROOT}

# Install heavy numerical libs first to avoid build errors
RUN pip install numpy pandas matplotlib

# Install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ${LAMBDA_TASK_ROOT}/


# Set Lambda entrypoint
CMD ["app.lambda_handler"]
