import grpc
import yandexcloud

from rod.libs.py.utils.logger import CliLogger, BaseLogger
from rod.libs.py.yc.client import sdk_get

from yandex.cloud.containerregistry.v1.registry_pb2 import Registry
from yandex.cloud.containerregistry.v1.registry_service_pb2 import (
    ListRegistriesRequest,
    CreateRegistryRequest,
    CreateRegistryMetadata,
    GetRegistryRequest
)
from yandex.cloud.containerregistry.v1.registry_service_pb2_grpc import (
    RegistryServiceStub,
)

from yandex.cloud.containerregistry.v1.image_service_pb2 import (
    ListImagesRequest,
    DeleteImageRequest,
    DeleteImageMetadata,
)
from yandex.cloud.containerregistry.v1.image_service_pb2_grpc import (
    ImageServiceStub,
)


class YcRegistry:
    def __init__(
        self,
        folder_id: str,
        name: str = None,
        registry_id: str = None,
        token: str = None,
        logger: BaseLogger = None,
        create_if_missing: bool = True,
    ):
        logger = logger or CliLogger("rod.libs.py.yc.registry.YcRegistry")

        self.sdk = sdk_get(token)
        self.folder_id = folder_id
        self.name = name
        self._id = registry_id
        self.logger = logger
        if self._id:
            self._registry = self._find_by_id()
        elif self.name:
            self._registry = self._find()
        else:
            raise NotImplemented("name or registry_id should be set")

        if self._registry:
            self.logger.info(f"registry {self._registry.name} found")
        elif create_if_missing:
            self.logger.info(f"registry {self._registry.name} not found creating")
            self.create()
        else:
            self.logger.info(f"registry {self._registry.name} found")

    def __getattr__(self, name):
        return getattr(self._registry, name)

    def __bool__(self):
        return self._registry is not None

    def _find(self) -> Registry | None:
        registry_service = self.sdk.client(RegistryServiceStub)

        response = registry_service.List(
            ListRegistriesRequest(
                folder_id=self.folder_id,
                page_size=1000,
            )
        )

        return next((x for x in response.registries if x.name == self.name), None)

    def _find_by_id(self) -> Registry:
        registry_service = self.sdk.client(RegistryServiceStub)
        return registry_service.Get(
            GetRegistryRequest(registry_id=self._id)
        )

    def create(self) -> None:
        registry_service = self.sdk.client(RegistryServiceStub)

        operation = registry_service.Create(
            CreateRegistryRequest(
                folder_id=self.folder_id,
                name=self.name,
            )
        )

        result = self.sdk.wait_operation_and_get_result(
            operation,
            response_type=Registry,
            meta_type=CreateRegistryMetadata,
        )

        self.logger.info(f"Registry {self.name} created successfully")
        self._registry= result.response

    def purge_images(self) -> None:
        image_service = self.sdk.client(ImageServiceStub)

        page_token = ""

        while True:
            response = image_service.List(
                ListImagesRequest(
                    registry_id=self.id,
                    page_size=1000,
                    page_token=page_token,
                )
            )

            for image in response.images:
                try:
                    operation = image_service.Delete(
                        DeleteImageRequest(image_id=image.id)
                    )

                    self.sdk.wait_operation_and_get_result(
                        operation,
                        meta_type=DeleteImageMetadata,
                    )

                    self.logger.info(f"Deleted image: {image.name or image.id}")

                except grpc.RpcError as e:
                    if e.code() == grpc.StatusCode.NOT_FOUND:
                        self.logger.info(f"Already deleted: {image.id}")
                        continue
                    raise

            if not response.next_page_token:
                break

            page_token = response.next_page_token


