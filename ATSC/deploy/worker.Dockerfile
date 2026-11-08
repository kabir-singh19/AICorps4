# ATSC batch worker (ICD Table 2: S1/S2/S3 batch jobs, 2 vCPU, 3.5 GB). The repo is mounted at /atsc.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 time && rm -rf /var/lib/apt/lists/*
COPY S1_Road_Network_Database/requirements.txt /tmp/s1.txt
COPY S2_Risk_Model_Backtest/requirements.txt /tmp/s2.txt
RUN pip install --no-cache-dir -r /tmp/s1.txt -r /tmp/s2.txt
WORKDIR /atsc
