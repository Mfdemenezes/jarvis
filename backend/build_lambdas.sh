#!/bin/bash

echo "📦 Preparando Lambda functions para deploy..."

# Criar diretório de build
mkdir -p build

# Chat Handler
echo "Building chat_handler..."
cd lambda
pip install -r requirements.txt -t chat_handler_package/
cp chat_handler.py chat_handler_package/index.py
cd chat_handler_package
zip -r ../../build/chat_handler.zip .
cd ../..

# Notification Sender
echo "Building notification_sender..."
cd lambda
pip install -r requirements.txt -t notification_sender_package/
cp notification_sender.py notification_sender_package/index.py
cd notification_sender_package
zip -r ../../build/notification_sender.zip .
cd ../..

echo "✅ Lambda packages criados em build/"
