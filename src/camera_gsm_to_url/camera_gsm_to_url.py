import os
import time
import logging
import datetime
import platform
from PIL import Image
from picamera import PiCamera
from pyshorteners import Shortener
import serial
import serial.threaded


from infra.app import app
from infra.old_modules.sim800 import sim800
from infra.modules.google.drive import drive
from infra.modules.google.sheets import sheets
from sms_camera.src.camera_gsm_to_url import constants


class CameraGsmToUrl(app.App):
    _logger = logging.getLogger('camera_gsm_to_url')


    def __init__(self):
        app.App.__init__(self, constants, spam_loggers=sheets.Sheets.SPAM_LOGGERS +
            ('PIL.PngImagePlugin', 'urllib3.connectionpool'))
        self._modules.extend((sim800, drive, sheets))
        # google drive uploader
        try:
            self.drive = drive.Drive(constants.SERVICE_ACCOUNT_PATH)
        except:
            self._logger.exception('self.drive')
            self.drive = None
        # google sheets logger
        try:
            self.sheets = sheets.Sheets(constants.SERVICE_ACCOUNT_PATH)
        except:
            self._logger.exception('self.sheet')
            self.sheet = None
        # url shorter
        try:
            self.short_url = Shortener(**constants.SHORT_URL_ARGS).short
        except:
            self._logger.exception('self.short_url')
            self.short_url = None
        # google sheets name is the hostname
        constants.WORKSHEET_SMS_NAME = platform.node()
        # last pictures overlays
        self.pictures = []
        # attach to raspberrypi camera
        self.camera = PiCamera()
        # configure camera
        if hasattr(constants, 'CAMERA_FPS'):
            self.camera.framerate = constants.CAMERA_FPS
        if hasattr(constants, 'CAMERA_RESOLUTION'):
            self.camera.resolution = constants.CAMERA_RESOLUTION
        if not hasattr(constants, 'CAMERA_RESIZE'):
            constants.CAMERA_RESIZE = None
        # get current screen size
        self.left, self.top = 0, 0
        self.width, self.height = map(int, os.popen(r'tvservice -s | grep -oP "\d\d+x\d\d+"', 'r').read().strip().split('x'))
        # calc draw stuff
        camera_scale = self.camera.resolution.width / self.camera.resolution.height
        self.sep = int(min(self.width, self.height) * constants.SEP_SCALE)
        self.pictures_h = int((self.height - 3 * self.sep) * constants.PICTURES_HEIGHT_SCALE)
        self.pictures_w = int(camera_scale * self.pictures_h)
        self.pictures_c = int((self.width - self.sep) / (self.pictures_w + self.sep))
        self.pictures_l = int((self.width - self.pictures_c * (self.pictures_w + self.sep) - self.sep) / 2) + self.sep + self.left
        self.pictures_t = self.sep + self.top
        camera_t = self.sep + self.pictures_h + self.sep 
        camera_h = self.height - camera_t - self.sep
        camera_w = int(camera_scale * camera_h)
        camera_l = int((self.width - camera_w) / 2) + self.left
        self._logger.info('\nmain window: %s sep: %s\ncamera resolution: %sx%s @ %s fps', 
            (self.left, self.top, self.width, self.height), self.sep,
            self.camera.resolution.width, self.camera.resolution.height, self.camera.framerate)
        self._logger.debug('\nfirst picture window: %s count: %s', 
            (self.pictures_l, self.pictures_t, self.pictures_w, self.pictures_h), self.pictures_c)
        # draw camera preview
        self.camera.start_preview()
        self.camera.preview.fullscreen = False
        camera_topper_layer = self.camera.preview.layer + 1
        self.camera.preview.window = [camera_l, camera_t, camera_w, camera_h]
        # draw logos overlays
        # self.logo1 = self._image_to_overlay(constants.LOGO0_PATH, layer=camera_topper_layer)
        # self.logo2 = self._image_to_overlay(constants.LOGO1_PATH, layer=camera_topper_layer)
        # self.logo3 = self._image_to_overlay(constants.LOGO2_PATH, layer=camera_topper_layer)
        self.logo4 = self._image_to_overlay(constants.LOGO3_PATH, layer=camera_topper_layer)
        self.logo4.window = [camera_l + int((camera_w - self.logo4.width) / 2), camera_t + camera_h - self.logo4.height, self.logo4.width, self.logo4.height]
        # self.logo1.window = [camera_l, camera_t, self.logo1.width, self.logo1.height]
        # self.logo2.window = [camera_l + camera_w - self.logo2.width, camera_t, self.logo2.width, self.logo2.height]
        # self.logo3.window = [camera_l, camera_t + camera_h - self.logo3.height, self.logo3.width, self.logo3.height]
        # draw pictures overlays
        self.draw_pictures()
        # gsm module
        try:
            self._gsm_uart = serial.serial_for_url(**constants.GSM_UART)
            self._gsm_reader = serial.threaded.ReaderThread(self._gsm_uart, sim800.Sim800)
            self._gsm_reader.start()
            self.gsm = self._gsm_reader.connect()[1]
        except:
            self._logger.exception('gsm')
            self.gsm = None
        else:
            self.gsm.status_changed = self.gsm_status_changed
            self.gsm.sms_recived = self.gsm_sms_recived

    def gsm_status_changed(self):
        self._logger.info('gsm_status_changed: %s', self.gsm.status)
        if self.gsm.status == 'ALIVE':
            self._logger.info(constants.GSM_DATA_FORMAT,
                self.gsm.get_csq(), self.gsm.get_vbat(), self.gsm.get_temperature())
        elif self.gsm.status == 'TIMEOUT':
            self._logger.warning('gsm did not respond')

    def gsm_sms_recived(self, number, send_time, text):
        # normalize sms text, number and send_time
        text = text.encode(errors='replace').decode().strip().replace('\n', ' ').replace('\t', ' ').replace('\r', '')
        normalize_number = self.gsm.normalize_phone_number(number)
        send_time = send_time.strftime(constants.DATETIME_FORMAT)
        self._logger.info('AT: %s FROM: %s MESSAGES: %s', send_time, normalize_number, text)
        if text == 'REBOOT':
            # self._logger.info(constants.REBOOT_FORMAT)
            self.send_sms(number, constants.REBOOT_FORMAT, False)
            os.system('shutdown -r')
        elif text == 'GSM DATA':
            try:
                t = constants.GSM_DATA_FORMAT % (
                    self.gsm.get_csq(), self.gsm.get_vbat(), self.gsm.get_temperature())
            except:
                self._logger.warning('cant read gsm data')
                return
            # self._logger.info(t)
            self.send_sms(number, t.replace(', ', '\n'), False)
        else:
            url = self.capture_and_share(number)
            # log to worksheet
            if self.sheets is not None:
                try:
                    self.sheets.append_worksheet_table(constants.SHEET_SMS_LOG_NAME, constants.WORKSHEET_SMS_NAME,
                        send_time, normalize_number, text, url)
                except:
                    self._logger.exception('self.sheets')
                    self.sheets = None

    def capture_and_share(self, number):
        try:
            path = self.take_picture()
        except:
            self._logger.error('capture_and_share: take_picture failed')
            return ''
        try:
            url = self.upload_picture(path)
        except:
            self._logger.exception('capture_and_share: upload_picture failed')
            return ''
        try:
            self.send_sms(number, constants.GSM_SEND_SMS_FORMAT % (url,))
        except:
            self._logger.error('capture_and_share: send_sms failed')
        return url

    def draw_pictures(self):
        # draw pictures overlays
        for i, p in enumerate(self.pictures):
            p.window = (self.pictures_l + i * (self.pictures_w + self.sep), self.pictures_t, self.pictures_w, self.pictures_h)

    def take_picture(self):
        # capture picture and return its path
        self.camera.preview.alpha = 100
        time.sleep(0.7)
        path = constants.PICTURES_PATH % (datetime.datetime.now().strftime(constants.PICTURES_DATETIME_FORMAT),)
        self._logger.info('take_picture: %s', path)
        self.camera.capture(path, resize=constants.CAMERA_RESIZE)
        self.camera.preview.alpha = 255
        
        img = Image.open(path, 'r').convert('RGBA')
        draw = Image.open(constants.LOGO3_PATH, 'r').convert('RGBA')
        img_w, img_h = img.size
        draw_w, draw_h = draw.size
        img.paste(draw, (int((img_w - draw_w) / 2), img_h - draw_h), draw)
        img = img.convert('RGB')
        img.save(path)

        self.add_picture(path)
        return path

    def add_picture(self, path):
        # add the given picture to pictures list
        self.pictures.append(self._image_to_overlay(path, resize=(self.pictures_w, self.pictures_h), transparent=False))
        if len(self.pictures) > self.pictures_c:
            self.pictures[0].close()
            self.pictures.pop(0)
        self.draw_pictures()

    def set_effect(self, index):
        # set camera image effect by its index
        self._logger.info('set_effect: %s', index)
        self.camera.image_effect = constants.CAMERA_EFFECTS[index % len(constants.CAMERA_EFFECTS)]

    def upload_picture(self, path):
        if self.drive is None:
            raise IOError('can\t upload: self.drive is None')
        self._logger.info('upload_picture: %s', path)
        file_id = self.drive.upload_file(path, share=True, delete=True,
            parent_directory=constants.DRIVE_SMS_CAMERA_FOLDER, timeout=constants.DRIVE_UPLOAD_TIMEOUT)
        url = self.drive.VIEW_FILE_URL % (file_id,)
        if self.short_url is not None:
            url = self.short_url(self.drive.VIEW_FILE_URL % (file_id,))
        self._logger.debug('upload_picture url: %s', url)
        return url

    def _image_to_overlay(self, image_path, layer=0, alpha=255, fullscreen=False, resize=None, transparent=True):
        # open image and resize it if needed
        img = Image.open(image_path)
        if resize is not None:
            img = img.resize(resize)
        # create required size (32, 16) padding for the image 
        pad = Image.new('RGBA' if transparent else 'RGB', [((n + m - 1) // m) * m for n, m in zip(img.size, (32, 16))])
        # paste the original image into the padding
        pad.paste(img)
        # crearw image overlay, and return it with its size
        overlay = self.camera.add_overlay(pad.tobytes(), img.size, layer=layer, alpha=alpha, fullscreen=fullscreen)
        overlay.width, overlay.height = img.size
        return overlay

    def send_sms(self, number, text, raise_exception=True):
        try:
            self.gsm.send_sms(number, text)
        except:
            if raise_exception:
                raise

    def __exit__(self):
        try:
            self._gsm_reader.close()
        except:
            pass
        try:
            self.camera.close()
        except:
            pass
        app.App.__exit__(self)
