from pulumi_aws import config, iam
import json

## Ec2 NodeGroup Role

ec2_role = iam.Role(
    'ec2-nodegroup-iam-role',
    assume_role_policy=json.dumps({
        'Version': '2012-10-17',
        'Statement': [
            {
                'Action': 'sts:AssumeRole',
                'Principal': {
                    'Service': 'ec2.amazonaws.com'
                },
                'Effect': 'Allow',
                'Sid': ''
            }
        ],
    }),
)

iam.RolePolicyAttachment(
    'ec2-nodegroup-policy-attachment',
    role=ec2_role.id,
    policy_arn='arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore',
)

testSSMProfile = iam.InstanceProfile(
    "testSSMProfile", 
    name = "testSSMProfile", 
    role = ec2_role)