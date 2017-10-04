import logging
import os.path

from infra.core.ansi import Ansi
from infra.run.common import *


LOGOR_LEVEL = logging.DEBUG

GSM_UART = {'url': 'loop://' if IS_WINDOWS else '/dev/ttyGsmUart', 'baudrate': 57600, 'timeout': 1}
GSM_SIM_NUMBER = '0'

CAMERA_EFFECTS = ['none', 'negative', 'solarize', 'sketch', 'emboss', 'hatch', 'watercolor', 'colorswap', 'posterise', 'cartoon']
# CAMERA_FPS = 30
# CAMERA_RESIZE = (480, 360)
# CAMERA_RESOLUTION = (1680, 1050)

SEP_SCALE = 0.005

PICTURES_HEIGHT_SCALE = 0.2
PICTURES_PATH = '/tmp/%s.png'
PICTURES_DATETIME_FORMAT = DATETIME_FORMAT.replace('-', '_').replace(':', '_').replace(' ', '_')

LOGO0_PATH, LOGO1_PATH, LOGO2_PATH = [os.path.join(BASIC_PATH, 'sms_camera', 'res', 'logo%s.png' % (i,)) for i in range(3)]

SERVICE_ACCOUNT_PATH = os.path.join(BASIC_PATH, 'logger-995ad2d4b91d.json')
DRIVE_SMS_CAMERA_FOLDER = '0B2AIf2iKCHvpYkxMM0NUNFE0bG8'
SHEET_SMS_LOG_ARGS = {'service_file': SERVICE_ACCOUNT_PATH, 'no_cache': IS_WINDOWS}
SHEET_SMS_LOG_NAME = 'sms_log'
