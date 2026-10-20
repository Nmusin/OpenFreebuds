from openfreebuds.driver.huawei.driver.generic import OfbDriverHuaweiGeneric
from openfreebuds.driver.huawei.handler import *


class OfbDriverHuawei5I(OfbDriverHuaweiGeneric):
    """
    HUAWEI FreeBuds 5i
    """
    def __init__(self, address):
        super().__init__(address)
        self.handlers = [
            OfbHuaweiInfoHandler(),
            OfbHuaweiDeviceIdentityHandler(),
            OfbHuaweiStateInEarHandler(),
            OfbHuaweiBatteryHandler(),
            OfbHuaweiAncHandler(w_cancel_lvl=True, w_cancel_dynamic=True),
            OfbHuaweiActionDoubleTapHandler(w_in_call=True),
            OfbHuaweiActionTripleTapHandler(),
            OfbHuaweiActionLongTapSplitHandler(w_right=True),
            OfbHuaweiActionSwipeGestureHandler(),
            OfbHuaweiActionFindMyBudsHandler(),
            OfbHuaweiFitTestHandler(),
            OfbHuaweiConfigAutoPauseHandler(),
            OfbHuaweiConfigWindSuppressionHandler(),
            OfnHuaweiSoundQualityPreferenceHandler(),
            OfbHuaweiLowLatencyPreferenceHandler(),
            OfbHuaweiEqualizerPresetHandler(w_presets={
                1: "default",
                2: "hardbass",
                3: "treble",
                9: "voices",
            }, w_custom=True, w_custom_local=True),
            OfbHuaweiVoiceLanguageHandler(),
            OfbHuaweiDualConnectHandler(),
        ]
