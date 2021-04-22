#! /bin/bash

KEY=$1
IP=$2

# Modify the permitions to use key
chmod 600 $KEY

# Upload webserver files and start it.
scp -r -i $KEY ./webserver ec2-user@$IP:~
wait $!
ssh -i $KEY ec2-user@$IP "node ~/webserver/server.js"