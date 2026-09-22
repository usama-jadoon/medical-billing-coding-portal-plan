#!/bin/sh
# Initialize MinIO bucket for medical documents
/usr/bin/mc alias set local http://minio:9000 minioadmin minioadmin
/usr/bin/mc mb local/medical-documents
/usr/bin/mc anonymous set none local/medical-documents
echo "MinIO medical-documents bucket created."
