#! /bin/bash

# Install Git to get web app files
yum update -y
yum install git -y

# Install node.js
curl -o https://raw.githubusercontent.com/nvm-sh/nvm/v0.34.0/install.sh | bash
. ~/.nvm/nvm.sh
nvm install node

# Download the web app files and start the node.js server
git clone https://github.com/MatthewBrazill/acs-web-app.git
cd ./acs-web-app
npm install .
node server.js