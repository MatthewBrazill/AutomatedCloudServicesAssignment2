#! /bin/bash

yum update
yum install httpd -y
yum install nodejs -y

wget -r https://[bucket].s3.amazonaws.com/webserver

npm install ~/webserver/
node ~/webserver/server.js