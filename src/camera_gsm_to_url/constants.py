import logging
import os.path

from infra.core.ansi import Ansi
from infra.run.common import *


LOGOR_LEVEL = logging.DEBUG

GSM_UART = {'url': 'loop://' if IS_WINDOWS else '/dev/ttyGsmUart', 'baudrate': 38400, 'timeout': 1}

CAMERA_EFFECTS = ['none', 'negative', 'solarize', 'sketch', 'emboss', 'hatch', 'watercolor', 'colorswap', 'posterise', 'cartoon']
# CAMERA_FPS = 30
# CAMERA_RESIZE = (480, 360)
# CAMERA_RESOLUTION = (1680, 1050)

SEP_SCALE = 0.005

PICTURES_HEIGHT_SCALE = 0.2
PICTURES_PATH = '/tmp/%s.jpg'
PICTURES_DATETIME_FORMAT = DATETIME_FORMAT.replace('-', '_').replace(':', '_').replace(' ', '_')

LOGO0_PATH, LOGO1_PATH, LOGO2_PATH = [os.path.join(BASIC_PATH, 'sms_camera', 'res', 'logo%s.png' % (i,)) for i in range(3)]

GSM_SEND_SMS_FORMAT = 'התמונה שלך:\n%s'

KEYS_PATH = os.path.join(BASIC_PATH, 'keys')
# SHORT_URL_ARGS = {'engine': 'Google', 'api_key': open(os.path.join(KEYS_PATH, 'google_api_key.txt'), 'r').read(), 'timeout': 1} # {'engine': 'Tinyurl', 'timeout': 1}
SHORT_URL_ARGS = {'engine': 'Google', 'api_key': open(os.path.join(KEYS_PATH, 'old/logger_api_key.txt'), 'r').read(), 'timeout': 1} # {'engine': 'Tinyurl', 'timeout': 1}
SERVICE_ACCOUNT_PATH = os.path.join(KEYS_PATH, 'old/logger-995ad2d4b91d.json')
# SERVICE_ACCOUNT_PATH = os.path.join(KEYS_PATH, 'google_service_account.json')
DRIVE_SMS_CAMERA_FOLDER = '0B2AIf2iKCHvpYkxMM0NUNFE0bG8'
DRIVE_UPLOAD_TIMEOUT = 50
SHEET_SMS_LOG_NAME = 'sms_log'
WORKSHEET_SMS_NAME = '0'
