from shared.common import *
from shared.error_handler import exception
from typing import List

class ECS(object):
    
    def __init__(self, vpc_options: VpcOptions):
        self.vpc_options = vpc_options

    @exception
    def run(self) -> List[Resource]:

        client = self.vpc_options.client('ecs')
        ec2_client = self.vpc_options.client('ec2')

        resources_found = []

        clusters_list = client.list_clusters()
        response = client.describe_clusters(
            clusters=clusters_list['clusterArns']
        )

        message_handler("Collecting data from ECS CLUSTER...", "HEADER")

        if len(response['clusters']) > 0:
            
            for data in response['clusters']:

                """ Searching all cluster services """
                paginator = client.get_paginator('list_services')
                pages = paginator.paginate(
                    cluster=data['clusterName']
                )

                for services in pages:

                    if len(services['serviceArns']) > 0:
                        service_details = client.describe_services(
                            cluster=data['clusterName'],
                            services=services['serviceArns']
                        )

                        for data_service_detail in service_details['services']:
                            if data_service_detail['launchType'] == 'FARGATE':
                                service_subnets = data_service_detail["networkConfiguration"]["awsvpcConfiguration"]["subnets"]

                                """ describe subnet to get VpcId """
                                ec2 = self.vpc_options.client('ec2')

                                subnets = ec2.describe_subnets(SubnetIds=service_subnets)

                                """ Iterate subnet to get VPC """
                                for data_subnet in subnets['Subnets']:

                                    if data_subnet['VpcId'] == self.vpc_options.vpc_id:

                                        resources_found.append(Resource(id=data['clusterArn'],
                                                                        name=data["clusterName"],
                                                                        type='aws_ecs_cluster',
                                                                        details=''))
                            else:
                                """ EC2 services require container instances, list of them should be fine for now """
                                pass

                """ Looking for container instances - they are dynamically associated, so manual review is necessary """
                list_paginator = client.get_paginator('list_container_instances')
                list_pages = list_paginator.paginate(
                    cluster=data['clusterName']
                )
                for list_page in list_pages:
                    if len(list_page['containerInstanceArns']) == 0:
                        continue

                    container_instances = client.describe_container_instances(
                        cluster=data['clusterName'],
                        containerInstances=list_page['containerInstanceArns']
                    )
                    ec2_ids = []
                    for instance_details in container_instances['containerInstances']:
                        ec2_ids.append(instance_details['ec2InstanceId'])
                    paginator = ec2_client.get_paginator('describe_instances')
                    pages = paginator.paginate(
                        InstanceIds=ec2_ids
                    )
                    for page in pages:
                        for reservation in page['Reservations']:
                            for instance in reservation['Instances']:
                                for network_interfaces in instance['NetworkInterfaces']:
                                    if network_interfaces['VpcId'] == self.vpc_options.vpc_id:

                                        resources_found.append(Resource(id=instance['InstanceId'],
                                                                        name=data["clusterName"],
                                                                        type='aws_ecs_cluster',
                                                                        details='Instance in EC2 cluster'))
                                    pass
                            pass
                        pass

        return resources_found