import logging
import os.path

from infra.core.ansi import Ansi
from infra.run.common import *


CAMERA_EFFECTS = ['none', 'negative', 'solarize', 'sketch', 'emboss', 'hatch', 'watercolor', 'colorswap', 'posterise', 'cartoon']
CAMERA_FPS = 30
PICTURES_HEIGHT_SCALE = 0.2
SEP_SCALE = 0.005

IMAGES_PATH = '/tmp/%s.png'

LOGO0_PATH, LOGO1_PATH, LOGO2_PATH = [os.path.join(BASIC_PATH, 'sms_camera', 'res', 'logo%s.png' % (i,)) for i in range(3)]

# LOGOR_LEVEL = logging.DEBUG
