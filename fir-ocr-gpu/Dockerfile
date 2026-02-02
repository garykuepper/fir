FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip libgl1 libglib2.0-0 curl libgomp1 binutils \
 && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y --no-install-recommends \
    libcublas-12-2 libcublas-dev-12-2 \
    libcusolver-12-2 \
    libcusparse-12-2 \
    libcurand-12-2 \
    libcufft-12-2 \
    cuda-nvrtc-12-2 cuda-nvrtc-dev-12-2 \
 && rm -rf /var/lib/apt/lists/*

# Make sure the generic cuDNN soname exists (some frameworks dlopen("libcudnn.so"))
RUN ln -sf /usr/lib/x86_64-linux-gnu/libcudnn.so.8 /usr/lib/x86_64-linux-gnu/libcudnn.so && ldconfig

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

RUN pip3 install --no-cache-dir paddlepaddle-gpu==2.6.2

COPY app.py /app/app.py

EXPOSE 9000
CMD ["python3", "/app/app.py"]
