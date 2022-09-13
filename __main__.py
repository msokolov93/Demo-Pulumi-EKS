import iam
import vpc
import utils
import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s
from pulumi_aws import eks
from pulumi_kubernetes.helm.v3 import Chart, LocalChartOpts

## EKS Cluster

eks_cluster = eks.Cluster(
    'eks-cluster',
    role_arn=iam.eks_role.arn,
    tags={
        'Name': 'pulumi-eks-cluster',
    },
    vpc_config=eks.ClusterVpcConfigArgs(
        public_access_cidrs=['0.0.0.0/0'],
        security_group_ids=[vpc.eks_security_group.id],
        subnet_ids=vpc.subnet_ids,
    ),
)

eks_node_group = eks.NodeGroup(
    'eks-node-group',
    instance_types=['c5.xlarge'],
    cluster_name=eks_cluster.name,
    node_group_name='pulumi-eks-nodegroup',
    node_role_arn=iam.ec2_role.arn,
    subnet_ids=vpc.subnet_ids,
    tags={
        'Name': 'pulumi-cluster-nodeGroup',
    },
    scaling_config=eks.NodeGroupScalingConfigArgs(
        desired_size=1,
        max_size=4,
        min_size=1,
    ),
)

#ingress = k8s.yaml.ConfigFile('ingress-nginx', 'ingress-nginx.yaml')
demoapp = k8s.yaml.ConfigFile('demoapp', 'demoapp.yaml')

# Export the public IP for WordPress.
frontend = demoapp.get_resource('v1/Service', 'frontend')

pulumi.export('cluster-name', eks_cluster.name)
pulumi.export('kubeconfig', utils.generate_kube_config(eks_cluster))
#pulumi.export('frontend_ip', frontend.status.load_balancer.ingress[0].ip)

### S3 Bucket

bucket = aws.s3.Bucket("bucket",
    acl="private",
    tags={
        "Environment": "Dev",
        "Name": "My bucket",
    })

s3bucketname = pulumi.export('s3bucket', bucket.bucket);
s3bucketarn = pulumi.export('s3bucketarn', bucket.arn);

### Lambda

iam_for_lambda = aws.iam.Role("iamForLambda", assume_role_policy="""{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    },
    {
      "Action": {
      "Sid": "Allow_S3_Access",
      "Action": [
	"s3:PutObject",
	"s3:GetObject",
	"s3:DeleteObject"
      ],
      "Effect": "Allow",
      "Resource": [
	"*"
      ]
    }
    }
  ]
}
""")

test_lambda = aws.lambda_.Function("testLambda",
    code=pulumi.FileArchive("lambda_function_payload.zip"),
    role=iam_for_lambda.arn,
    handler="index.js",
    runtime="nodejs12.x",
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "s3bucket": str(s3bucketname),
        },
    ))


