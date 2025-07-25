from google.cloud import datastore_admin_v1


def get_datastore_index(project, location, index_name):
    client = datastore_admin_v1.DatastoreAdminClient()

    request = datastore_admin_v1.GetIndexRequest(
        project_id=project, index_id=index_name
    )

    index = client.get_index(request=request)

    return index


def get_datastore_indices(project, location):
    client = datastore_admin_v1.DatastoreAdminClient()

    request = datastore_admin_v1.ListIndexesRequest(
        project_id=project,
    )

    indices = client.list_indexes(request=request)

    return indices


def export_datastore_entities(project, gcs_url):
    client = datastore_admin_v1.DatastoreAdminClient()

    request = datastore_admin_v1.ExportEntitiesRequest(
        project_id=project,
        output_url_prefix=gcs_url,
    )

    operation = client.export_entities(request=request)

    return operation.result()
