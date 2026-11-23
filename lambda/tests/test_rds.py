import boto3

from cost_guard import app


def paused_arns():
    return {
        item["resource_id"]
        for item in boto3.resource("dynamodb").Table("cost-guard-state").scan()["Items"]
    }


def instance_status(name):
    return boto3.client("rds").describe_db_instances(DBInstanceIdentifier=name)[
        "DBInstances"
    ][0]["DBInstanceStatus"]


def cluster_status(name):
    return boto3.client("rds").describe_db_clusters(DBClusterIdentifier=name)[
        "DBClusters"
    ][0]["Status"]


def test_pause_then_restore_an_instance(db):
    arn = db("orders")

    out = app.handler({}, None)
    assert out["lines"] == [f"paused rds {arn}"]
    assert instance_status("orders") == "stopped"
    assert paused_arns() == {arn}

    app.handler({"action": "restore"}, None)
    assert instance_status("orders") == "available"
    assert paused_arns() == set()


def test_untagged_instance_is_left_alone(db):
    db("orders", tagged=False)

    out = app.handler({}, None)

    assert out["lines"] == []
    assert instance_status("orders") == "available"


def test_pause_then_restore_an_aurora_cluster(aurora):
    arn = aurora("reports")

    out = app.handler({}, None)
    # One line for the cluster, none for its member instance
    assert out["lines"] == [f"paused rds {arn}"]
    assert cluster_status("reports") == "stopped"

    app.handler({"action": "restore"}, None)
    assert cluster_status("reports") == "available"
    assert paused_arns() == set()


def test_restore_copes_with_aws_restarting_the_database_itself(db):
    arn = db("orders")
    app.handler({}, None)
    boto3.client("rds").start_db_instance(DBInstanceIdentifier="orders")

    out = app.handler({"action": "restore"}, None)

    assert out["lines"] == [f"restored rds {arn}"]
    assert paused_arns() == set()


def test_dry_run_leaves_databases_running(monkeypatch, db):
    monkeypatch.setenv("MODE", "dry_run")
    arn = db("orders")

    out = app.handler({}, None)

    assert out["lines"] == [f"would pause rds {arn}"]
    assert instance_status("orders") == "available"
