from google.cloud import tasks_v2


def get_cloud_queue(project, location, queue_name):
    client = tasks_v2.CloudTasksClient()

    request = tasks_v2.GetQueueRequest(
        name=f"projects/{project}/locations/{location}/queues/{queue_name}",
    )

    task = client.get_queue(request=request)

    return task


def get_cloud_queues(project, location):
    client = tasks_v2.CloudTasksClient()

    request = tasks_v2.ListQueuesRequest(
        parent=f"projects/{project}/locations/{location}",
    )

    queues = client.list_queues(request=request)

    return queues
