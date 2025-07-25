from google.cloud import scheduler_v1


def get_cloud_schedule(project, location, schedule_name):
    client = scheduler_v1.CloudSchedulerClient()

    request = scheduler_v1.GetJobRequest(
        name=f"projects/{project}/locations/{location}/jobs/{schedule_name}",
    )

    schedule = client.get_job(request=request)

    return schedule


def get_cloud_schedules(project, location):
    client = scheduler_v1.CloudSchedulerClient()

    request = scheduler_v1.ListJobsRequest(
        parent=f"projects/{project}/locations/{location}",
    )

    schedules = client.list_jobs(request=request)

    return schedules
