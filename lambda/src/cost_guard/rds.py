import boto3


def find(tag_key, tag_value):
    rds = boto3.client("rds")
    for page in rds.get_paginator("describe_db_clusters").paginate():
        for cluster in page["DBClusters"]:
            if cluster["Status"] == "available" and tagged(cluster, tag_key, tag_value):
                yield cluster["DBClusterArn"], {"cluster": cluster["DBClusterIdentifier"]}

    for page in rds.get_paginator("describe_db_instances").paginate():
        for instance in page["DBInstances"]:
            # Aurora members only stop through their cluster
            if "DBClusterIdentifier" in instance:
                continue
            if instance["DBInstanceStatus"] == "available" and tagged(instance, tag_key, tag_value):
                yield instance["DBInstanceArn"], {"instance": instance["DBInstanceIdentifier"]}


def tagged(resource, tag_key, tag_value):
    return any(t["Key"] == tag_key and t["Value"] == tag_value for t in resource.get("TagList", []))


def pause(arn, snapshot):
    rds = boto3.client("rds")
    if "cluster" in snapshot:
        rds.stop_db_cluster(DBClusterIdentifier=snapshot["cluster"])
    else:
        rds.stop_db_instance(DBInstanceIdentifier=snapshot["instance"])


def resume(arn, snapshot):
    # AWS restarts stopped databases after 7 days, and starting a running one errors
    if status(snapshot) == "available":
        return
    rds = boto3.client("rds")
    if "cluster" in snapshot:
        rds.start_db_cluster(DBClusterIdentifier=snapshot["cluster"])
    else:
        rds.start_db_instance(DBInstanceIdentifier=snapshot["instance"])


def status(snapshot):
    rds = boto3.client("rds")
    if "cluster" in snapshot:
        return rds.describe_db_clusters(DBClusterIdentifier=snapshot["cluster"])["DBClusters"][0]["Status"]
    return rds.describe_db_instances(DBInstanceIdentifier=snapshot["instance"])["DBInstances"][0]["DBInstanceStatus"]
