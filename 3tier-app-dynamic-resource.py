"""
VPC, Subnet(Public, Private), InternetGateway, Natgateway,
Session Manager, Userdata(Nodejs, index.js for mariadb, MariaDB-client), 
RDS(MariaDB with secret)
"""

import sys
from tkinter import W
import iam
import json
import base64
import pulumi
import pulumi_aws as aws
import pulumi_mysql as mariadb
from mysql_dynamic_provider import *


config = pulumi.Config()
# admin_name = config.require('DB_USER'),
# admin_password = config.require('DB_PASSWORD'),

NAME = 'iac-example'
#machine_img = "ami-067abcae434ee508b"  # Ubuntu Server 20.04 LTS (HVM), SSD Volume Type
machine_img = "ami-0f6f6d4cd303f364a"  # Amazon Linux AMI 2.0.20220209 x86_64 ECS HVM GP2


f=open("node.js","r")
nodejs_file = f.read()
f.close()

# VPC

vpc = aws.ec2.Vpc(
    resource_name = f'vpc-{NAME}',
    cidr_block = "10.0.0.0/16",
    enable_dns_hostnames = True,
    enable_dns_support = True,
    tags = {
        'Name': 'my-vpc',
    },
)

# Subnet: public/private/db

#zones = get_availability_zones()
zones = ['ap-northeast-2a', 'ap-northeast-2c']
public_subnet_ids = []
private_subnet_ids = []
db_subnet_ids = []

public_zone_size, private_zone_size, db_zone_size = 1, 5, 10

for zone in zones:
    if zone == 'ap-northeast-2a':
        zone_index = 1
    elif zone == 'ap-northeast-2c':
        zone_index = 3

    # public subnet (for web/jump)
    public_subnet = aws.ec2.Subnet(
        f'my-public-web-subnet-{zone}',
        assign_ipv6_address_on_creation = False,
        vpc_id = vpc.id,
        map_public_ip_on_launch = True,
        cidr_block = f'10.0.{public_zone_size*zone_index}.0/24',
        availability_zone = zone,
        tags={
            'Name': f'my-public-web-subnet-{zone}',
        },
    )
    public_subnet_ids.append(public_subnet.id)

    # private subnet (for app)
    private_subnet = aws.ec2.Subnet(
        f'my-private-app-subnet-{zone}',
        assign_ipv6_address_on_creation = False,
        vpc_id = vpc.id,
        cidr_block = f'10.0.{private_zone_size*zone_index}.0/24',
        availability_zone = zone,
        tags = {
            'Name': f'my-private-app-subnet-{zone}',
        },
    )
    private_subnet_ids.append(private_subnet.id)

    # private subnet (for db)
    db_subnet = aws.ec2.Subnet(
        f'my-private-db-subnet-{zone}',
        assign_ipv6_address_on_creation = False,
        vpc_id = vpc.id,
        cidr_block = f'10.0.{db_zone_size*zone_index}.0/24',
        availability_zone = zone,
        tags = {
            'Name': f'my-private-db-subnet-{zone}',
        },
    )
    db_subnet_ids.append(db_subnet.id)    

# Internet Gateway 
igw = aws.ec2.InternetGateway(
    resource_name = f'my-internet-gateway-{NAME}',
    vpc_id = vpc.id,
    tags = {
        'Name': 'my-internet-gateway',
    },
)

## Assign an Elastic IP address to the NAT gateway
gateway_eip = aws.ec2.Eip(
    resource_name = f'gateway-eip-{NAME}',
    vpc = True
)

# Nat Gateway
nat_gateway = aws.ec2.NatGateway(
    resource_name = f'my-nat-gateway-{NAME}',
    # TODO: Connectivity type (review)
    allocation_id = gateway_eip.id,  # eip 할당
    subnet_id = public_subnet_ids[0]  # public subnet 중 하나에 설치
)

# route

routetable_gateway = aws.ec2.RouteTable(
    resource_name = f'routetable-gateway-{NAME}',
    vpc_id=vpc.id,
    routes=[
        {
            "cidrBlock": "0.0.0.0/0",
            "gatewayId": igw.id
        }
    ],
    tags = {"Name": "my-public-web-route-table"}
)

routetable_app = aws.ec2.RouteTable(
    resource_name = f'routetable-app-{NAME}',
    vpc_id=vpc.id,
    routes=[
        {
            "cidrBlock": "0.0.0.0/0",
            "gatewayId": nat_gateway.id
        }
    ],
    tags = {"Name": "private-app-route-table"}
)

routetable_db = aws.ec2.RouteTable(
    resource_name = f'routetable-db-{NAME}',
    vpc_id=vpc.id,
    # TODO: Add route (review)
    routes=[
        {
            "cidrBlock": "0.0.0.0/0",
            "gatewayId": igw.id
        }
    ],
    tags = {"Name": "private-db-route-table"}
)


## Assocate route table

subnet_types = ['public', 'private', 'db']
table_associations = []

for subnet in subnet_types:
    if subnet == 'public':
        for i in range(0, len(zones)):
            table_association = aws.ec2.RouteTableAssociation(
                resource_name = f'table-association-web-{i}',
                subnet_id = public_subnet_ids[i],
                route_table_id = routetable_gateway)
            table_associations.append(table_association.id)
    elif subnet == 'private':
        for j in range(0, len(zones)):
            table_association = aws.ec2.RouteTableAssociation(
                resource_name = f'table-association-app-{j}',
                subnet_id = private_subnet_ids[j],
                route_table_id = routetable_app)
            table_associations.append(table_association.id)
    elif subnet == 'db':
        for k in range(0, len(zones)):
            table_association = aws.ec2.RouteTableAssociation(
                resource_name = f'table-association-db-{k}',
                subnet_id = db_subnet_ids[k],
                route_table_id = routetable_db)
            table_associations.append(table_association.id)

# EC2

## security group

ec2_security_group = aws.ec2.SecurityGroup(
    resource_name = f"ec2-security-group-{NAME}",
    vpc_id=vpc.id,
    # Outbound traffic
    egress=[{
        'from_port': 0,
        'to_port': 0,
        'protocol': '-1',
        # 'from_port': 80,
        # 'to_port': 80,
        # 'protocol': 'tcp',
        'cidr_blocks': ['0.0.0.0/0']
    }],
    # Inbound traffic
    ingress=[{
        'from_port': 80,
        'to_port': 80,
        'protocol': 'tcp',
        'cidr_blocks': ['0.0.0.0/0']
    }]
)

## EC2 App server
ec2_servers = []
for zone in zones:
    if zone == 'ap-northeast-2a':
        m = 0
    elif zone == 'ap-northeast-2c':
        m = 1
    server = aws.ec2.Instance(
        resource_name = f"ec2-app-{zone}",
        ami = machine_img,
        instance_type = "t2.micro",
        availability_zone = f"{zone}",
        vpc_security_group_ids = [ec2_security_group.id],
        subnet_id = private_subnet_ids[m],
        #key_name = "aws-iac-remote-login-key",
        iam_instance_profile = iam.testSSMProfile,
        # User data: health check & ssm agent setup
        user_data = nodejs_file,
        tags = {"Name": f"my-app-server-{zone}"}
    )
    ec2_servers.append(server.private_ip)

# ELB

## security group for elb

elb_security_group = aws.ec2.SecurityGroup(
    resource_name = f"my-alb-sg",
    vpc_id=vpc.id,
    # Outbound traffic
    egress=[{
        'from_port': 0,
        'to_port': 0,
        'protocol': '-1', # all
        'cidr_blocks': ['0.0.0.0/0']
    }],
    # Inbound traffic
    ingress=[{
        'description' : 'Allow internet access to instance',
        'from_port' : 80,
        'to_port' : 80,
        'protocol' : 'tcp',
        'cidr_blocks' : ['0.0.0.0/0']
    }]
)


## load balancer

load_balancer = aws.lb.LoadBalancer(
    resource_name = f"my-alb",
    internal = False,
    security_groups = [elb_security_group.id],
    subnets = [public_subnet_ids[0], public_subnet_ids[1]],
    load_balancer_type = "application",
    tags = {"Name": "my-alb"}
)

## target group

target_group = aws.lb.TargetGroup(
    resource_name = "my-alb-tg",
    port = 80,  # [로드밸런서 -> 타겟그룹] 요청이 80번 포트에서 처리
    vpc_id = vpc.id,
    protocol = "HTTP",
    target_type = "ip"  # ip를 기준으로 ec2 인스턴스를 target group에 등록
    
)

listener = aws.lb.Listener(
    resource_name = "listener",
    load_balancer_arn = load_balancer.arn,
    port = 80,  # [클라이언트 -> 로드밸런서] 요청이 80번 포트에서 처리
    protocol = "HTTP",
    default_actions = [{"type": "forward", "target_group_arn": target_group.arn}],
)

## register targets
tg_ec2_attachments = []
for zone in zones:
    if zone == 'ap-northeast-2a':
        n = 0
    elif zone == 'ap-northeast-2c':
        n = 1
    tg_ec2_attachment = aws.lb.TargetGroupAttachment(
        resource_name = f"tg-ec2-attachment-{zone}",
        target_group_arn = target_group.arn,
        target_id = ec2_servers[n],
        port = 80,
    )
    tg_ec2_attachments.append(tg_ec2_attachment.id)

# DB

## Security Group

# make a public security group for our cluster for the migration
db_security_group = aws.ec2.SecurityGroup(
    resource_name = f"db-security-group-{NAME}",
    vpc_id=vpc.id,
    ingress=[aws.ec2.SecurityGroupIngressArgs(
        protocol="-1",
        from_port=0,
        to_port=0,
        cidr_blocks=["0.0.0.0/0"]
    )],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        protocol="-1",
        from_port=0,
        to_port=0,
        cidr_blocks=["0.0.0.0/0"]
    )])

db_security_group_rule = aws.ec2.SecurityGroupRule(
    resource_name = f"db-security-group-rule-{NAME}",
    type = "ingress",
    security_group_id = db_security_group.id,
    source_security_group_id = ec2_security_group,
    protocol = "tcp",
    from_port = 3306,
    to_port = 3306
)

## subnet group

db_subnet_group = aws.rds.SubnetGroup(
    resource_name = f"db-subnet-group-{NAME}",
    subnet_ids = [db_subnet_ids[0], db_subnet_ids[1]]
)

## instance

# An RDS instnace is created to hold our MariaDB database
rds_database = aws.rds.Instance(
    resource_name = f"rds-database-{NAME}",
    db_subnet_group_name = db_subnet_group.name,
    allocated_storage = 10,  # rds 용량 10GB
    storage_type = "gp2",
    instance_class = "db.t2.micro",
    engine = "mariadb",
    engine_version = "10.5.13",
    #port = 3306,
    name = f"adt",  # DB name
    identifier = f"iac-mariadb",  # RDS instance name
    username = config.require('DB_USER'),  # master DB user
    password = config.require('DB_PASSWORD'),  # user Password
    multi_az = False,
    skip_final_snapshot = True,
    publicly_accessible=True,
    vpc_security_group_ids = [db_security_group.id]
)

# # Creating a Pulumi MariaDB provider to allow us to interact with the RDS instance
# mariadb_provider = mariadb.Provider("mariadb-provider",
#     endpoint=rds_database.endpoint,
#     username=config.require('DB_USER'),
#     password=config.require('DB_PASSWORD'))

# # Initializing a basic database on the RDS instance
# mariadb_database = mariadb.Database("mariadb-database",
#     name="adt",
#     opts=pulumi.ResourceOptions(provider=mariadb_provider))

# The database schema and initial data to be deployed to the database
creation_script = """
    CREATE TABLE tab1 (
        col1 int PRIMARY KEY,
        col2 int,
        col3 char(20),
        col4 char(100)
    ) ENGINE=InnoDB;
    """

# The SQL commands the database performs when deleting the schema
deletion_script = "DROP TABLE tab1 CASCADE"

# Creating our dynamic resource to deploy the schema during `pulumi up`. The arguments
# are passed in as a SchemaInputs object
mariadb_table = Schema(name="mariadb_tab1_table",
    args=SchemaInputs(
        config.require('DB_USER'), 
        config.require('DB_PASSWORD'), 
        rds_database.address,
        "adt",
        #mariadb_database.name, 
        creation_script,
        deletion_script))

pulumi.export("url", load_balancer.dns_name)
pulumi.export("db_host", rds_database.endpoint)
pulumi.export("db_address", rds_database.address)

# aws ssm start-session --target i-09181f7fab11ee265