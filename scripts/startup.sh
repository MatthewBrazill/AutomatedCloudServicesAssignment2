#! /bin/bash

yum update
yum install httpd -y
systemctl enable httpd
systemctl start httpd