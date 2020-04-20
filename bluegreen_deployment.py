from time import sleep
from spotinst_sdk import spotinst_blue_green_deployment
import spotinst_sdk
import base64
import uuid
import boto3
import json
import sys


def lambda_handler(event, context):
    codepipeline_client = boto3.client('codepipeline')
    pipeline_event = str(event["CodePipeline.job"]["data"]["actionConfiguration"]["configuration"]["UserParameters"])
    decoded_params = json.loads(pipeline_event)

    try:
        api_token = decoded_params["API_TOKEN"]
        account_id = decoded_params["ACCOUNT_ID"]
        group_id = decoded_params["GROUP_ID"]
        app_name = decoded_params["APP_NAME"]
        deployment_group_name = decoded_params["DEPLOYMENT_GROUP"]
        timeout = decoded_params["TIMEOUT"]
        github_repo = decoded_params["GITHUB_REPO"]
        commit_id = decoded_params["COMMIT_ID"]

    except KeyError:
        codepipeline_client.put_job_failure_result(
            jobId=event["CodePipeline.job"]["id"],
            failureDetails={"type": "ConfigurationError", "message": "Missing Parameters!"}
        )
        sys.exit(1)

    launcher(api_token, account_id, group_id, app_name, deployment_group_name,
             timeout, github_repo, commit_id)

    codepipeline_client.put_job_success_result(
        jobId=event["CodePipeline.job"]["id"]
    )

    return {
        'message': "Success! Blue Green Deployment Complete"
    }


def launcher(api_token, account_id, group_id, app_name, deployment_group_name,
             timeout, github_repo, commit_id):

    unique_id = get_uuid()[2:-1]
    spot_client = spotinst_sdk.SpotinstClient(
        auth_token=api_token,
        account_id=account_id)

    green_tag = spotinst_blue_green_deployment.Tag()
    green_tag.tag_key = 'GreenIdentifier'
    green_tag.tag_value = unique_id

    deployment_group = spotinst_blue_green_deployment.DeploymentGroup()
    deployment_group.deployment_group_name = deployment_group_name
    deployment_group.application_name = app_name

    deployment = spotinst_blue_green_deployment.BlueGreenDeployment(tags=[green_tag],
                                                                    deployment_groups=[deployment_group],
                                                                    timeout=timeout)
    spot_client.create_blue_green_deployment(group_id, deployment)

    print('sleeping 300 seconds')
    sleep(320)

    git_loc = gitHubLocation(github_repo, commit_id)

    revision = Revision('GitHub', git_loc)
    tags = Tags(Key='GreenIdentifier', Value=unique_id, Type='KEY_AND_VALUE')
    tag_filters = tagFilters([tags])
    bg = BlueGreenDeployment(applicationName=app_name,
                             deploymentGroupName=deployment_group_name, revision=revision,
                             targetInstances=tag_filters)

    codedeploy_client = boto3.client('codedeploy')
    codedeploy_client.create_deployment(applicationName=bg.applicationName,
                                        deploymentGroupName=bg.deploymentGroupName,
                                        revision=todict(bg.revision),
                                        targetInstances=todict(bg.targetInstances))

    print("Launcher function complete")


def todict(obj, classkey=None):
    if isinstance(obj, dict):
        data = {}
        for (k, v) in obj.items():
            data[k] = todict(v, classkey)
        return data
    elif hasattr(obj, "_ast"):
        return todict(obj._ast())
    elif hasattr(obj, "__iter__") and not isinstance(obj, str):
        return [todict(v, classkey) for v in obj]
    elif hasattr(obj, "__dict__"):
        data = dict([(key, todict(value, classkey))
                     for key, value in obj.__dict__.items()
                     if not callable(value) and not key.startswith('_')])
        if classkey is not None and hasattr(obj, "__class__"):
            data[classkey] = obj.__class__.__name__
        return data
    else:
        return obj


def get_uuid():
    r_uuid = str(base64.urlsafe_b64encode(uuid.uuid4().bytes))
    return r_uuid.replace('=', '')

# region Class Definitions


class Tags:
    def __init__(self,
                 Key=None,
                 Value=None,
                 Type=None):
        self.Key = Key
        self.Value = Value
        self.Type = Type


class tagFilters:
    def __init__(self,
                 tagFilters=None):
        self.tagFilters = tagFilters


class gitHubLocation:
    def __init__(
            self,
            repository=None,
            commitId=None):
        self.repository = repository
        self.commitId = commitId


class Revision:
    def __init__(
            self,
            revisionType=None,
            gitHubLocation=None):
        self.revisionType = revisionType
        self.gitHubLocation = gitHubLocation


class BlueGreenDeployment:

    def __init__(
            self,
            applicationName=None,
            deploymentGroupName=None,
            revision=None,
            targetInstances=None):
        self.applicationName = applicationName
        self.deploymentGroupName = deploymentGroupName
        self.revision = revision
        self.targetInstances = targetInstances

    def to_json(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)
# endregion


