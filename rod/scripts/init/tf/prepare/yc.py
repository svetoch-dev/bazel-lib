from rod.libs.py.yc.sa import sa_create
from rod.libs.py.settings import YcSettings


def prepare_yc(folder_id: str) -> bool:
    yc_settings = YcSettings()
    sa = sa_create(folder_id, yc_settings.token, yc_settings.tf_state_sa)
    print(sa.id)
