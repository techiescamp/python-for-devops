#! /bin/python3

import boto3, os
from botocore.exceptions import ClientError

vpc_id = "vpc-0d42bf2f27be967ff"
subnet_id = "subnet-00b5ede5e160caa59"
ami_id = "ami-0ddf424f81ddb0720"
instance_type = "t2.small"
app_name = "flask"

create_key = True
key_name = "dev-key"
key_location = "/Users/bibinwilson/.ssh/devops-class/"

ec2 = boto3.client('ec2')

def createSecurityGroup():
    global security_group_id
    try:
        response = ec2.create_security_group(GroupName=app_name + "-sg",
                                            Description=app_name + " Security Group",
                                            VpcId=vpc_id,
                                            TagSpecifications=[
                                                    {
                                                        'ResourceType': 'security-group',
                                                        'Tags': [
                                                            {
                                                                'Key': 'Name',
                                                                'Value': app_name + "-sg"
                                                            }
                                                        ]
                                                    },
                                                ],
                                            )
        security_group_id = response['GroupId']
        print('Security Group Created %s in vpc %s.' % (security_group_id, vpc_id))

        ingress = ec2.authorize_security_group_ingress(
                            GroupId=security_group_id,
                            IpPermissions=[
                                {
                                    'IpProtocol': 'tcp',
                                    'FromPort': 80,
                                    'ToPort': 80,
                                    'IpRanges': [
                                        {
                                            'CidrIp': '0.0.0.0/0'
                                        }
                                    ]
                                },
                                {
                                    'IpProtocol': 'tcp',
                                    'FromPort': 22,
                                    'ToPort': 22,
                                    'IpRanges': [
                                        {
                                            'CidrIp': '0.0.0.0/0'
                                        }
                                    ]
                                }
                            ])
        print('Ingress Successfully Set %s' % ingress)
    except ClientError as e:
        print(e)

def createKeyPair():

    try:
        key_pair = ec2.create_key_pair(KeyName=key_name)

        ssh_private_key = key_pair["KeyMaterial"]
        
        with os.fdopen(os.open(key_location + key_name + ".pem", os.O_WRONLY | os.O_CREAT, 0o400), "w+") as handle:
            handle.write(ssh_private_key)
    except ClientError as e:
        print(e)
    
def createInstance():
    blockDeviceMappings = [
        {
            'DeviceName': "/dev/sda1",
            'Ebs': {
                'DeleteOnTermination': True,
                'VolumeSize': 20,
                'VolumeType': 'gp2'
            }
        },
    ]

    instances = ec2.run_instances(
        ImageId= ami_id,
        MinCount=1,
        MaxCount=1,
        InstanceType=instance_type,
        SubnetId=subnet_id,
        KeyName=key_name,
        SecurityGroupIds=[security_group_id],
        BlockDeviceMappings=blockDeviceMappings,
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': app_name + "-server"
                    }
                ]
            },
            {
                'ResourceType': 'volume',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': app_name + "-root-disk"
                    }
                ]
            }
        ]
    )

    print(instances["Instances"][0]["InstanceId"])


if __name__ == "__main__":
    
    createSecurityGroup()

    if create_key == True:
        createKeyPair();

    createInstance()


# References
# [1] https://codeflex.co/boto3-create-ec2-with-tags/
# [2] https://www.learnaws.org/2020/12/16/aws-ec2-boto3-ultimate-guide/
# [3] https://arjunmohnot.medium.com/aws-ec2-management-with-python-and-boto-3-59d849f1f58f

