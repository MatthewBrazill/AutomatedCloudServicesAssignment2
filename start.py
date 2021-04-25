#! /usr/bin/env python3

# Imports
import re
import boto3
import logging
import sys
import os
import uuid
import subprocess

# Global Resources
APP_NAME = "acs-assignment"
CREATION_ID = str(uuid.uuid4())
ec2 = boto3.resource("ec2")
s3 = boto3.resource("s3")
asg = boto3.client("autoscaling")
elb = boto3.client("elbv2")


# Logging Configuration
logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(message)s",
    filename="./log.log",
    filemode="w",
    level="INFO"
)


# Definitions
def createKeyPair(name: str, id: str, dry=False) -> object:
    """
    Creates an EC2 Key Pair and saves it as a file accessable to the user.

    name -> String:
        The name to be given to the Key.
    id -> String:
        The ID with which to identify all resources.
    dry -> Boolean:
        Whether or not to run as a dry run.
    """

    logging.info("Creating Key Pair...")
    key = ec2.create_key_pair(
        KeyName=f"{name}-key",
        DryRun=dry,
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
    logging.info(f"Created Key Pair. Saved file as: '{key.key_name}.pem'")

    return key


def createVpc(name: str, id: str, cidr: str, dry=False) -> object:
    """
    The function creates a VPC and names it as specified.

    name -> String:
        The name to be given to the VPC.
    id -> String:
        The ID with which to identify all resources.
    cidr -> String:
        The CIDR block with which to create the VPC.
    dry -> Boolean:
        Whether or not to run as a dry run.
    """

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
    logging.info(f"Created VPC with CIDR: '{cidr}'")
    return vpc


def createRouteTable(name: str, id: str, vpc: object, dry=False) -> object:
    """
    Creates a route table for the specified VPC.

    name -> String:
        The name to be given to the route table.
    id -> String:
        The ID with which to identify all resources.
    vpc -> Object:
        The VPC Object to which to attach the route table.
    dry -> Boolean:
        Whether or not to run as a dry run.
    """

    for gate in vpc.internet_gateways.all():
        gateId = gate.id

    for route in vpc.route_tables.all():
        rt = route

    rt.create_route(
        DestinationCidrBlock="0.0.0.0/0",
        GatewayId=gateId,
        DryRun=dry,
        TagSpecifications=[
            {
                "ResourceType": "route-table",
                "Tags": [
                    {
                        "Key": "Name",
                        "Value": f"{name}-route-table"
                    },
                    {
                        "Key": "ID",
                        "Value": id
                    }
                ]
            }
        ]
    )

    logging.info("Created Route Table")
    return rt


def createGateway(name: str, id: str, vpc: object, dry=False) -> object:
    """
    The function creates a Internet Gateway, names it as specified
    and then attaches it to the given VPC.

    name -> String:
        The name to be given to the gatway.
    id -> String:
        The ID with which to identify all resources.
    vpc -> Object:
        The VPC Object to which to attach the gateway.
    dry -> Boolean:
        Whether or not to run as a dry run.
    """

    gateway = ec2.create_internet_gateway(
        DryRun=dry,
        TagSpecifications=[
            {
                "ResourceType": "internet-gateway",
                "Tags": [
                    {
                        "Key": "Name",
                        "Value": f"{name}-gateway"
                    },
                    {
                        "Key": "ID",
                        "Value": id
                    }
                ]
            }
        ]
    )

    vpc.attach_internet_gateway(
        InternetGatewayId=gateway.id,
        DryRun=dry
    )
    logging.info("Created Internet Gateway")
    return gateway


def createSubnets(name: str, id: str, vpc: object, dry=False) -> object:
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
    cidrStart = re.sub(r"([.]\d+){2}([/]\d+){1}", "", vpc.cidr_block)
    subnets = [None] * 6
    for i in range(3):
        subnets[i] = vpc.create_subnet(
            AvailabilityZoneId=f"euw1-az{i+1}",
            CidrBlock=f"{cidrStart}.{i+1}.0/24",
            DryRun=dry,
            TagSpecifications=[
                {
                    "ResourceType": "subnet",
                    "Tags": [
                        {
                            "Key": "Name",
                            "Value": f"{name}-public-subnet-{i+1}"
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
            AvailabilityZoneId=f"euw1-az{i+1}",
            CidrBlock=f"{cidrStart}.{i+4}.0/24",
            DryRun=dry,
            TagSpecifications=[
                {
                    "ResourceType": "subnet",
                    "Tags": [
                        {
                            "Key": "Name",
                            "Value": f"{name}-private-subnet-{i+1}"
                        },
                        {
                            "Key": "ID",
                            "Value": id
                        }
                    ]
                }
            ]
        )
    logging.info("Created Subnets")
    return subnets


def createSecurityGroups(name: str, id: str, vpc: object, dry=False) -> object:
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

    sg = vpc.create_security_group(
        Description=f"A security group for the {name} app.",
        GroupName=f"{name}-security-group",
        DryRun=dry,
        TagSpecifications=[
            {
                    "ResourceType": "security-group",
                    "Tags": [
                        {
                            "Key": "Name",
                            "Value": f"{name}-security"
                        },
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
    logging.info("Created Security Group")
    return sg


def createTargetGroup(name: str, id: str, vpc: object, dry=False) -> dict:
    """
    This function creates a Target Group referencing all public EC2 instances.

    name -> String:
        The name to be given to the Auto Scaler.
    id -> String:
        The ID with which to identify all resources.
    vpc -> Object:
        The VPC Object whose instances to reference.
    """

    targetGroup = elb.create_target_group(
        Name=f"{name}-target-group",
        Protocol="HTTP",
        Port=80,
        VpcId=vpc.vpc_id,
        TargetType="instance",
        Tags=[
            {
                "Key": "Name",
                "Value": f"{name}-gateway"
            },
            {
                "Key": "ID",
                "Value": id
            }
        ]
    )["TargetGroups"][0]
    return targetGroup


def createAutoScaler(name: str, id: str, vpc: object, launchConfig: str, targetGroup: dict, dry=False) -> str:
    """
    This function creates an Auto Scaler based of off a EC2 Launch Configuration.

    name -> String:
        The name to be given to the Auto Scaler.
    id -> String:
        The ID with which to identify all resources.
    vpc -> Object:
        The VPC Object within which to create the Auto Scaler.
    launchCongif -> String:
        The name of the Launch Configuration on which the scaled resources will be based.
    targetGroup -> String:
        The name of the Target Group that represents the
    dry -> Boolean:
        Whether or not to run as a dry run.
    """

    subnets = ""
    count = 0
    for subnet in vpc.subnets.all():
        if "public" in subnet.tags[0]["Value"] or "public" in subnet.tags[1]["Value"]:
            if count <= 1:
                subnets += f"{subnet.subnet_id}, "
                count += 1
            elif count == 2:
                subnets += f"{subnet.subnet_id}"
                count += 1
                break

    asg.create_auto_scaling_group(
        AutoScalingGroupName=f"{name}-auto-scaling-group",
        LaunchConfigurationName=launchConfig,
        VPCZoneIdentifier=subnets,
        MinSize=1,
        MaxSize=10,
        DesiredCapacity=1,
        DefaultCooldown=180,
        TargetGroupARNs=[targetGroup["TargetGroupArn"]],
        Tags=[
            {
                "Key": "Name",
                "Value": f"{name}-auto-scaling-group"
            },
            {
                "Key": "ID",
                "Value": id
            }
        ]
    )
    logging.info("Created Auto Scaler")
    return f"{name}-auto-scaling-group"


def createLoadBalancer(name: str, id: str, vpc: object, targetGroup, dry=False) -> dict:
    """
    Creates a load balancer that is named as specified.

    name -> String:
        The name to be given to the Load Balancer.
    id -> String:
        The ID with which to identify all resources.
    vpc -> Object:
        The VPC Object within which to create the Load Balancer.
    targetGroup -> String:
        tr
    dry -> Boolean:
        Whether or not to run as a dry run.
    """

    for sg in vpc.security_groups.all():
        if sg.group_name != "default":
            secGroup = sg.group_id
            break

    subnetIds = []
    for subnet in vpc.subnets.all():
        if "public" in subnet.tags[0]["Value"] or "public" in subnet.tags[1]["Value"]:
            subnetIds.append(subnet.subnet_id)

    loadBalancer = elb.create_load_balancer(
        Name=f"{name}-load-balancer",
        Subnets=subnetIds,
        SecurityGroups=[secGroup],
        Type="application",
        IpAddressType="ipv4",
        Tags=[
            {
                "Key": "ID",
                "Value": id
            }
        ]
    )["LoadBalancers"][0]

    elb.create_listener(
        LoadBalancerArn=loadBalancer["LoadBalancerArn"],
        Protocol="HTTP",
        Port=80,
        DefaultActions=[
            {
                "Type": "forward",
                "TargetGroupArn": targetGroup["TargetGroupArn"]
            }
        ],
        Tags=[
            {
                "Key": "Name",
                "Value": f"{name}-listener"
            },
            {
                "Key": "ID",
                "Value": id
            }
        ]
    )
    logging.info(f"Created Load Balancer: {loadBalancer['DNSName']}")
    print(f"Address: http://{loadBalancer['DNSName']}/index")
    return loadBalancer


def createLaunchConfig(name: str, id: str, key: object, vpc: object, script, dry=False) -> str:
    """
    Creates a launch configuration that is named as specified.

    name -> String:
        The name to be given to the AMI.
    id -> String:
        The ID with which to identify all resources.
    key -> String:
        The Pey Pair with which to create the Launch Configuration.
    vpc -> Object:
        The VPC Object within which to create the Load Balancer.
    script -> String:
        The startup script to pass on to the Launch Configuration
        that is executed at the start of the instances launch.
    dry -> Boolean:
        Whether or not to run as a dry run.
    """

    for sg in vpc.security_groups.all():
        if sg.group_name != "default":
            sgId = sg.group_id
            break

    asg.create_launch_configuration(
        LaunchConfigurationName=f"{name}-launch-config",
        ImageId="ami-04d76fb85cd82256b",
        KeyName=key.key_name,
        UserData=script,
        SecurityGroups=[sgId],
        InstanceType="t2.nano",
        Tags=[
            {
                "Key": "Name",
                "Value": f"{name}-launch-configuration"
            },
            {
                "Key": "ID",
                "Value": id
            }
        ]
    )
    logging.info("Created Launch Configuration")
    return f"{name}-launch-config"


def cleanup(key: object, vpc: object):
    """
    A function to delete all the created resources.

    key -> Object:
        The key resource to delete.
    vpc -> Object:
        The VPC resource to delete.
    launchConfig -> String:
        The name of the launch configuration to delete.
    targetGroup -> String:
        The target group to delete.
    autoScaler -> String:
        The name of the auto scaler to delete.
    """

    success = True
    try:
        if key != None:
            key.delete()

        if vpc != None:
            for securityGroup in vpc.security_groups.all():
                if securityGroup.group_name != "default":
                    securityGroup.delete()

            for gateway in vpc.internet_gateways.all():
                gateway.detach_from_vpc(VpcId=vpc.vpc_id)
                gateway.delete()

            for subnet in vpc.subnets.all():
                subnet.delete()

            for route in vpc.route_tables.all():
                if hasattr(route, "tags"):
                    route.delete()

            vpc.delete()
    except Exception:
        success = False

    return success


# Main
def main():
    logging.info("Starting Program...")
    logging.info(f"App name set to: {APP_NAME}")
    logging.info(f"ID generated as: {CREATION_ID}")

    # Ensure that variables exist:
    key = None
    vpc = None
    launchConfig = ""
    loadBalancer = ""
    autoScaler = ""

    try:
        # Generate a new Key Pair for this environment.
        key = createKeyPair(APP_NAME, CREATION_ID)

        # Build the VPC along with subnets, gateways
        # and security groups.
        vpc = createVpc(APP_NAME, CREATION_ID, "10.0.0.0/16")
        createGateway(APP_NAME, CREATION_ID, vpc)
        createRouteTable(APP_NAME, CREATION_ID, vpc)
        createSubnets(APP_NAME, CREATION_ID, vpc)
        createSecurityGroups(APP_NAME, CREATION_ID, vpc)

        # Create and configure the components for the auto scaling.
        webAppScript = open(f"./scripts/webapp.sh", "r").read()
        launchConfig = createLaunchConfig(APP_NAME, CREATION_ID, key, vpc, webAppScript)
        targetGroup = createTargetGroup(APP_NAME, CREATION_ID, vpc)
        loadBalancer = createLoadBalancer(APP_NAME, CREATION_ID, vpc)
        autoScaler = createAutoScaler(APP_NAME, CREATION_ID, vpc, launchConfig, targetGroup)

    except Exception as err:
        logging.error(f"An error occurred: {err}")
        print(err)
        logging.info("Attempting cleanup...")
        if cleanup(key, vpc):
            logging.info("Cleanup Succeeded!")
            print("Cleanup Succeeded!")
        else:
            logging.info("Cleanup Failed! To avoid unexpected costs please check for remaining resources on AWS.")
            print("Cleanup Failed! To avoid unexpected costs please check for remaining resources on AWS.")


if sys.version_info[0] >= 3 and sys.version_info[1] >= 7:
    main()
else:
    logging.error("Python version out of date!")
    print(
        "Your Python version can't run this script.\nPlease make sure " +
        "you're updated to Python 3.7 or newer."
    )
