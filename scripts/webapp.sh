#cloud-boothook
#! /bin/bash

# Download the web app files and start the node.js server
rm -fR -- /home/ec2-user/acs-web-app
git clone https://github.com/MatthewBrazill/acs-web-app.git /home/ec2-user/acs-web-app
npm install /home/ec2-user/acs-web-app
node /home/ec2-user/acs-web-app/server.js