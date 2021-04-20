#! /usr/bin/env python3

# Imports
import os
import boto3
import logging
import sys
import uuid

# Global Resources
APP_NAME = "acs-assignment"
CREATION_ID = str(uuid.uuid4())
ec2 = boto3.resource('ec2')
s3 = boto3.resource('s3')


# Logging Configuration
logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(message)s",
    filename="./log.log",
    filemode="w",
    level="INFO"
)


# Definitions
def createKeyPair(name: str, id: str):
    """
    Creates an EC2 Key Pair and saves it as a file accessable to the user.

    name -> String:
        The name to be given to the Key. It will be given the postfix 'key'
    id -> String:
        The ID with which to identify all resources.
    """

    logging.info("Creating Key Pair")
    key = ec2.create_key_pair(
        KeyName=f"{name}-key",
        TagSpecifications=[
            {
                "ResourceType": "key-pair",
                "Tags": [
                    {
                        "Key": "ID",
                        "Value": id
                    },
                ]
            },
        ]
    )

    # Writes the key to a file
    keyFile = open(f"{key.key_name}.pem", "w")
    keyFile.write(key.key_material)
    keyFile.close()

    return key


def createVpc(name: str, id: str, cidr: str, dry: bool) -> object:
    """
    The function creates a VPC and names it as specified.

    name -> String:
        The name to be given to the VPC. It will be given the postfix 'vpc'
    id -> String:
        The ID with which to identify all resources.
    cidr -> String: 
        The CIDR block with which to create the VPC.
    dry -> Boolean: 
        Whether or not to run as a dry run.
    """

    logging.info(f"Creating VPC with CIDR: {cidr}")
    vpc = ec2.create_vpc(
        CidrBlock=cidr,
        DryRun=dry,
        TagSpecifications=[
            {
                "ResourceType": "vpc",
                "Tags": [
                    {
                        "Key": "Name",
                        "Value": f"{name}-vpc"
                    },
                    {
                        "Key": "ID",
                        "Value": id
                    }
                ]
            }
        ]
    )
    return vpc


def createSubnets(name: str, id: str, vpc: object, dry: bool):
    """
    The function creates Subnets and names them as specified.

    name -> String:
        The name to be given to the subnet. They will be given the 
        postfix 'Private Subnet-a', with the letter indicating the 
        avalability zone.
    id -> String:
        The ID with which to identify all resources.
    vpc -> Object:
        The VPC Object within which to create the Subnets.
    dry -> Boolean:
        Whether or not to run as a dry run.
    """

    # A for loop to create 6 Subnets, a private and a public subnet in all
    # three Avalability Zones
    logging.info("Creating Subnets")
    subnets = []
    for i in range(3):
        subnets[i] = vpc.create_subnet(
            AvalabilityZoneId=f"euw1-az{i+1}",
            DryRun=dry,
            TagSpecifications=[
                {
                    "ResourceType": "subnet",
                    "Tags": [
                        {
                            "Key": "Name",
                            "Value": f"{name} Public Subnet-{i+1}"
                        },
                        {
                            "Key": "ID",
                            "Value": id
                        }
                    ]
                }
            ]
        )

        subnets[i+3] = vpc.create_subnet(
            AvalabilityZone=f"euw1-az{i+1}",
            DryRun=dry,
            TagSpecifications=[
                {
                    "ResourceType": "subnet",
                    "Tags": [
                        {
                            "Key": "Name",
                            "Value": f"{name} Private Subnet-{i+1}"
                        },
                        {
                            "Key": "ID",
                            "Value": id
                        }
                    ]
                }
            ]
        )
    return subnets


def createSecurityGroups(name: str, id: str, vpc: object, dry: bool):
    """
    The function creates a Security Group and names it as specified.

    name -> String:
        The name to be given to the Security Group.
    id -> String:
        The ID with which to identify all resources.
    vpc -> Object:
        The VPC Object within which to create the Security Group.
    dry -> Boolean:
        Whether or not to run as a dry run.
    """

    logging.info("Creating Security Group")
    sg = vpc.create_security_group(
        Description=f"A security group for the {name} app.",
        GroupName=f"{name}-security-group",
        DryRun=dry,
        TagSpecifications=[
            {
                    "ResourceType": "security-group",
                    "Tags": [
                        {
                            "Key": "ID",
                            "Value": id
                        }
                    ]
            }
        ]
    )

    # Allow HTTP access for viewing of the webserver
    sg.authorize_ingress(IpPermissions=[{
        "FromPort": 80,
        "ToPort": 80,
        "IpProtocol": "tcp",
        "IpRanges": [
            {
                "CidrIp": "0.0.0.0/0",
                "Description": "Allow HTTP access."
            }
        ]
    }])

    # Allow HTTPs access for viewing of the webserver
    sg.authorize_ingress(IpPermissions=[{
        "FromPort": 443,
        "ToPort": 443,
        "IpProtocol": "tcp",
        "IpRanges": [
            {
                "CidrIp": "0.0.0.0/0",
                "Description": "Allow HTTPs access."
            }
        ]
    }])

    # Allow SSH access for configuration of the webserver
    sg.authorize_ingress(IpPermissions=[{
        "FromPort": 22,
        "ToPort": 22,
        "IpProtocol": "tcp",
        "IpRanges": [
            {
                "CidrIp": "0.0.0.0/0",
                "Description": "Allow SSH access for configuration of the EC2 instances."
            }
        ]
    }])
    return sg


def createLoadBalancer():
    """
    """

    logging.info("Creating Load Balancer")
    lb = ""

    return lb


def createAmazonMachineImage(name: str, id: str, key: object, vpc: object, script: str, dry: bool):
    """
    This function creates a AMI based of off a EC2 instance that is created
    and then terminated.
    """

    logging.info("Create AMI")
    instance = ec2.create_instances(
        ImageId="ami-096f43ef67d75e998",
        InstanceType="t2.nano",
        KeyName=key.key_name,
        MaxCount=1,
        MinCount=1,
        Monitoring={
            "Enabled": False
        },
        SecurityGroupIds=[vpc.security_groups.all()[0].group_id],
        SubnetId=vpc.subnets.all()[0].subnet_id,
        UserData=script,
        DisableApiTermination=False,
        EbsOptimized=False,
        InstanceInitiatedShutdownBehavior="stop",
        DryRun=dry,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {
                        "Key": "Name",
                        "Value": f"{name}-image-creation-instance"
                    },
                    {
                        "Key": "ID",
                        "Value": id
                    }
                ]
            }
        ]
    )[0]

    image = instance.create_image(
        TagSpecifications=[
            {
                "ResourceType": "image",
                "Tags": [
                    {
                        "Key": "Name",
                        "Value": ""
                    },
                    {
                        "Key": "ID",
                        "Value": id
                    }
                ]
            }
        ]
    )

    instance.terminate()

    return image


# Main
def main():
    logging.info("Starting Program")
    script = open(f"./scripts/startupScript.sh", "r").read()

    key = createKeyPair()

    vpc = createVpc(APP_NAME, CREATION_ID, "10.0.0.0/16")
    createSubnets(APP_NAME, CREATION_ID, vpc)
    createSecurityGroups(APP_NAME, CREATION_ID, vpc)

    image = createAmazonMachineImage(APP_NAME, CREATION_ID, key, vpc, "")

    lb = createLoadBalancer()


if sys.version_info[0] >= 3 and sys.version_info[1] >= 7:
    main()
else:
    logging.error("Python version out of date!")
    print(
        "You're Python version can't run this script.\nPlease make sure " +
        "you're updated to Python 3.7 or newer."
    )
