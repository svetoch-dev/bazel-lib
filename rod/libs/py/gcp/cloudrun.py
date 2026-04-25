from google.cloud import run_v2
from google.api_core import exceptions

gcp_exceptions = exceptions


def get_cloudrun_service(project, location, cloudrun_name):
    client = run_v2.ServicesClient()

    request = run_v2.GetServiceRequest(
        name=f"projects/{project}/locations/{location}/services/{cloudrun_name}",
    )

    cloudrun_service = client.get_service(request=request)

    return cloudrun_service


def get_cloudrun_services(project, location):
    client = run_v2.ServicesClient()

    request = run_v2.ListServicesRequest(
        parent=f"projects/{project}/locations/{location}",
    )

    cloudrun_services = client.list_services(request=request)

    return cloudrun_services


def get_cloudrun_revision(project, location, service, revision, full_revision=None):
    client = run_v2.RevisionsClient()

    revision = f"projects/{project}/locations/{location}/services/{service}/revisions/{revision}"

    request = run_v2.GetRevisionRequest(name=revision)

    cloudrun_revision = client.get_revision(request=request)

    return cloudrun_revision


def update_cloudrun_service(new_service):
    client = run_v2.ServicesClient()

    request = run_v2.UpdateServiceRequest(service=new_service)

    operation = client.update_service(request=request)

    print("Waiting for operation to complete...")

    response = operation.result()

    return response
