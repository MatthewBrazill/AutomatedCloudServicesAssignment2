#! /usr/bin/env python3

# Imports
import re
import boto3
import logging
import sys
import os
import uuid

# Global Resources
APP_NAME = "acs-assignment"
CREATION_ID = str(uuid.uuid4())
ec2 = boto3.resource("ec2")
s3 = boto3.resource("s3")
asg = boto3.client("autoscaling")
elb = boto3.client("elb")


# Logging Configuration
logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(message)s",
    filename="./log.log",
    filemode="w",
    level="INFO"
)


# Definitions
def createKeyPair(name: str, id: str, dry=False):
    """
    Creates an EC2 Key Pair and saves it as a file accessable to the user.

    name -> String:
        The name to be given to the Key.
    id -> String:
        The ID with which to identify all resources.
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


def createGateway(name: str, id: str, vpc: object, dry=False):
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


def createSubnets(name: str, id: str, vpc: object, dry=False):
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
            AvailabilityZoneId=f"euw1-az{i+1}",
            CidrBlock=f"{cidrStart}.{i+4}.0/24",
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
    logging.info("Created Subnets")
    return subnets


def createSecurityGroups(name: str, id: str, vpc: object, dry=False):
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


def createAmazonMachineImage(name: str, id: str, key: object, vpc: object, script: str, dry=False):
    """
    This function creates a AMI based of off a EC2 instance that is created
    and then terminated.

    name -> String:
        The name to be given to the AMI.
    id -> String:
        The ID with which to identify all resources.
    key -> Object:
        The Pey Pair with which to create the AMI.
    vpc -> Object:
        The VPC Object within which to create the AMI.
    script -> String:
        The startup script to pass on to the AMI that is executed at the 
        start of the instances launch.
    dry -> Boolean:
        Whether or not to run as a dry run.
    """

    for sg in vpc.security_groups.all():
        sgId = sg.group_id
        break

    for subnet in vpc.subnets.all():
        subnetId = subnet.subnet_id
        break

    logging.info("Creating AMI base Instance...")
    instance = ec2.create_instances(
        ImageId="ami-096f43ef67d75e998",
        InstanceType="t2.nano",
        KeyName=key.key_name,
        MaxCount=1,
        MinCount=1,
        Monitoring={
            "Enabled": False
        },
        SecurityGroupIds=[sgId],
        SubnetId=subnetId,
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

    # Wait for the server to be running and then
    # stop the instance to create the AMI.
    instance.wait_until_running()
    instance.stop()
    instance.wait_until_stopped()

    logging.info("Creating AMI...")
    image = instance.create_image(
        Name=f"{name}-load-balancer-image",
        Description=f"A autogenerated image for {name} that is used by the connected load balancer.",
        DryRun=dry,
        TagSpecifications=[
            {
                "ResourceType": "image",
                "Tags": [
                    {
                        "Key": "Name",
                        "Value": f"{name}-base-image"
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

    logging.info("Created AMI")
    return image


def createS3(name: str, id: str):
    """
    The function creates an S3 bucket to make resources 
    better available for the web server 

    name -> String:
        The name to be given to the AMI.
    id -> String:
        The ID with which to identify all resources.
    """

    logging.info("Creating S3 Bucket...")
    bucket = s3.create_bucket(
        Bucket=f"{name}-storage",
        CreateBucketConfiguration={
            "LocationConstraint": "eu-west-1"
        }
    )

    logging.info("Uploading Files to Bucket...")
    for root, dirs, files in os.walk("./webserver"):
        if "node_modules" not in root:
            for file in files:
                path = os.path.join(root, file)
                bucket.upload_file(
                    path,
                    path[2:],
                    ExtraArgs={"ACL": "public-read"}
                )
    logging.info(f"Created S3 Bucket as '{bucket.name}'")

    return bucket


def createAutoScaler(name: str, id: str, vpc: object, launchConfig: str, loadBalancer: str, dry=False):
    """
    """

    subnets = ""
    count = 0
    for subnet in vpc.subnets.all():
        if count <= 1:
            subnets += f"{subnet.subnet_id}, "
            count += 1
        elif count == 2:
            subnets += f"{subnet.subnet_id}"
            count += 1
            break

    autoScaler = f"{name}-auto-scaling-group"
    asg.create_auto_scaling_group(
        AutoScalingGroupName=autoScaler,
        LaunchConfigurationName=launchConfig,
        VPCZoneIdentifier=subnets,
        MinSize=1,
        MaxSize=10,
        DesiredCapacity=1,
        DefaultCooldown=180,
        LoadBalancerNames=[loadBalancer]
    )
    logging.info("Created Auto Scaler")
    return autoScaler


def createLoadBalancer(name: str, id: str, vpc: object, dry=False):
    """
    Creates a load balancer that is named as specified.    
    """

    for sg in vpc.security_groups.all():
        print(sg)
        secGroup = sg.group_id
        break

    subnetIds = []
    for subnet in vpc.subnets.all():
        subnetIds.append(subnet.subnet_id)

    loadBalancer = f"{name}-load-balancer"
    elb.create_load_balancer(
        LoadBalancerName=loadBalancer,
        Listeners=[
            {
                "Protocol": "HTTP",
                "LoadBalancerPort": 80,
                "InstanceProtocol": "HTTP",
                "InstancePort": 80
            }
        ],
        Subnets=subnetIds[0:3],
        SecurityGroups=[secGroup],
        Tags=[
            {
                "Key": "ID",
                "Value": id
            }
        ]
    )
    logging.info("Created Load Balancer")
    return loadBalancer


def createLaunchConfig(name: str, id: str, key: object, vpc: object, image: object, dry=False):
    """
    """

    for sg in vpc.security_groups.all():
        print(sg)
        sgId = sg.group_id
        break

    launchConfig = f"{name}-launch-config"
    asg.create_launch_configuration(
        LaunchConfigurationName=launchConfig,
        ImageId=image.image_id,
        KeyName=key.key_name,
        SecurityGroups=[sgId],
        InstanceType="t2.nano"
    )
    logging.info("Created Launch Configuration")
    return launchConfig


def buildDatabase(name: str, id: str, key: object, vpc: object, script: str, dry=False):
    return


def cleanup(key: object, vpc: object, bucket: object, image: object, launchConfig: str, loadBalancer: str, autoScaler: str):
    """
    A function to delete all the created resources.

    key -> Object:
        The key resource to delete.
    vpc -> Object:
        The VPC resource to delete.
    bucket -> Object:
        The S3 bucket to delete.
    image -> Object:
        The AMI image to delete.
    launchConfig -> String:
        The name of the launch configuration to delete.
    loadBalancer -> String:
        The name of the load balancer to delete.
    autoScaler -> String:
        The name of the auto scaler to delete.
    """

    if key is not None:
        key.delete(KeyPairId=key.key_pair_id)

    if vpc is not None:
        vpc.subnets.all().delete()
        vpc.security_groups.all().delete()
        vpc.internet_gateways.all().delete()
        vpc.delete()

    if bucket is not None:
        bucket.objects.all().delete()
        bucket.delete()

    if image is not None:
        image.deregister()

    if launchConfig is not "":
        asg.delete_launch_configuration(LaunchConfigurationName=launchConfig)

    if loadBalancer is not "":
        elb.delete_load_balancer(LoadBalancerName=loadBalancer)

    if autoScaler is not "":
        asg.update_auto_scaling_group(
            AutoScalingGroupName=autoScaler,
            MinSize=0,
            MaxSize=0,
            DesiredCapacity=0
        )
        asg.delete_auto_scaling_group(
            AutoScalingGroupName=autoScaler,
            ForceDelete=True
        )
    return


# Main
def main():
    logging.info("Starting Program...")
    logging.info(f"App name set to: {APP_NAME}")
    logging.info(f"ID generated as: {CREATION_ID}")

    # Ensure that variables exist:
    key = None
    vpc = None
    bucket = None
    image = None
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
        createSubnets(APP_NAME, CREATION_ID, vpc)
        createSecurityGroups(APP_NAME, CREATION_ID, vpc)

        # Create a S3 Bucket to provide a place to resources
        # for the web app.
        bucket = createS3(APP_NAME, CREATION_ID)

        # Build a EC2 Instance to generate a AMI based on it,
        # including all necessary configuration.
        amiScript = re.sub("[bucket]", bucket.name, open(f"./scripts/ami.sh", "r").read())
        logging.info("Script loaded from file: ./scripts/startup.sh")
        image = createAmazonMachineImage(APP_NAME, CREATION_ID, key, vpc, amiScript)

        # Create and configure the components for the auto scaling.
        launchConfig = createLaunchConfig(APP_NAME, CREATION_ID, key, vpc, image)
        loadBalancer = createLoadBalancer(APP_NAME, CREATION_ID, vpc)
        autoScaler = createAutoScaler(APP_NAME, CREATION_ID, vpc, launchConfig, loadBalancer)

        # Build a database to access from the web app.
        databaseScript = re.sub("[bucket]", bucket.name, open(f"./scripts/database.sh", "r").read())
        buildDatabase(APP_NAME, CREATION_ID, key, vpc, databaseScript)

    except Exception as err:
        logging.error(f"An error occurred: {err}")
        logging.info("Attempting cleanup...")
        cleanup(key, vpc, bucket, image, launchConfig, loadBalancer, autoScaler)


if sys.version_info[0] >= 3 and sys.version_info[1] >= 7:
    main()
else:
    logging.error("Python version out of date!")
    print(
        "You're Python version can't run this script.\nPlease make sure " +
        "you're updated to Python 3.7 or newer."
    )
