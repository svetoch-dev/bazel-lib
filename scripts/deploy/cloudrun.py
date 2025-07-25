import click
import os
from infra.libs.py.gcp.cloudrun import get_cloudrun_service, update_cloudrun_service


@click.command()
@click.argument("project", required=True, type=click.STRING)
@click.argument("location", required=True, type=click.STRING)
@click.argument("cloudrun_name", required=True, type=click.STRING)
@click.argument("image_name", required=True, type=click.STRING)
@click.argument("image_tag", required=True, type=click.STRING)
def deploy(project, location, cloudrun_name, image_name, image_tag):
    service = get_cloudrun_service(project, location, cloudrun_name)

    # Used in bazel CD targets
    # when file with stamped info is passed
    if os.path.isfile(image_tag):
        with open(image_tag) as f:
            image_tag = f.read()

    image = f"{image_name}:{image_tag}"
    service.template.containers[0].image = image
    result = update_cloudrun_service(service)
    print(result)


if __name__ == "__main__":
    deploy()
