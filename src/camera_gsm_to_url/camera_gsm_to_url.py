import os
import time
import logging
import datetime
from PIL import Image
from picamera import PiCamera
from pyshorteners import Shortener
import serial
import serial.threaded
import pygsheets

from infra.app import app
from infra.modules.gdrive import gdrive
from infra.old_modules.m590 import m590
from sms_camera.src.camera_gsm_to_url import constants


class CameraGsmToUrl(app.App):
    _logger = logging.getLogger('camera_gsm_to_url')

    def __init__(self):
        app.App.__init__(self, constants)
        # ignore sheets DEBUG and INFO spam
        for i in ('googleapiclient.discovery', 'oauth2client.transport', 'oauth2client.crypt', 'oauth2client.client', 'PIL.PngImagePlugin'):
            try:
                logging.getLogger(i).setLevel(logging.WARNING)
            except:
                pass
        # google drive uploader
        self.gdrive = gdrive.Gdrive(constants.SERVICE_ACCOUNT_PATH)
        # url shorter
        self.short_url = Shortener('Tinyurl').short
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
        self._logger.info('\nmain window: %s sep: %s\ncamera resolution: %sx%s @ %s fps\nfirst picture window: %s count: %s', 
            (self.left, self.top, self.width, self.height), self.sep,
            self.camera.resolution.width, self.camera.resolution.height, self.camera.framerate,
            (self.pictures_l, self.pictures_t, self.pictures_w, self.pictures_h), self.pictures_c)
        # draw camera preview
        self.camera.start_preview()
        self.camera.preview.fullscreen = False
        camera_topper_layer = self.camera.preview.layer + 1
        self.camera.preview.window = [camera_l, camera_t, camera_w, camera_h]
        # draw logos overlays
        self.logo1 = self._image_to_overlay(constants.LOGO0_PATH, layer=camera_topper_layer)
        self.logo2 = self._image_to_overlay(constants.LOGO1_PATH, layer=camera_topper_layer)
        self.logo3 = self._image_to_overlay(constants.LOGO2_PATH, layer=camera_topper_layer)
        self.logo1.window = [camera_l, camera_t, self.logo1.width, self.logo1.height]
        self.logo2.window = [camera_l + camera_w - self.logo2.width, camera_t, self.logo2.width, self.logo2.height]
        self.logo3.window = [camera_l, camera_t + camera_h - self.logo3.height, self.logo3.width, self.logo3.height]
        # draw pictures overlays
        self.draw_pictures()

        try:
            # open sheet using the SHEET_FILE_SERVICE key
            self._drive_sheets = pygsheets.authorize(**constants.SHEET_SMS_LOG_ARGS)
            self._sms_sheet = self._drive_sheets.open(constants.SHEET_SMS_LOG_NAME)
            # open the worksheet within the sheet for sms logging
            self._update_sms_workseet()
        except:
            self._logger.exception('sms_workseet')

        try:
            self._gsm_uart = serial.serial_for_url(**constants.GSM_UART)
            self._gsm_reader = serial.threaded.ReaderThread(self._gsm_uart, m590.M590)
            self._gsm_reader.start()
            self.gsm = self._gsm_reader.connect()[1]
        except:
            self._logger.exception('gsm')
        else:
            self.gsm.status_changed = self.gsm_status_changed
            self.gsm.sms_recived = self.gsm_sms_recived
            
    def gsm_status_changed(self):
        self._logger.info('gsm_status_changed: %s', self.gsm.status)
        if self.gsm.status == 'ALIVE':
            if constants.GSM_SIM_NUMBER == '0':
                constants.GSM_SIM_NUMBER = self.gsm.normalize_phone_number(self.gsm.get_sim_number())
                self._logger.info('sim_number: %s', constants.GSM_SIM_NUMBER)
                self._update_sms_workseet()
        elif self.gsm.status == 'TIMEOUT':
            self._logger.warning('gsm did not respond')

    def gsm_sms_recived(self, number, send_time, text):
        # normalize sms text, number and send_time
        text = text.encode(errors='replace').decode().strip().replace('\n', ' ').replace('\t', ' ').replace('\r', '')
        normalize_number = self.gsm.normalize_phone_number(number)
        send_time = send_time.strftime(constants.DATETIME_FORMAT)
        # log the sms to console and file
        self._logger.info('AT: %s FROM: %s MESSAGES: %s', send_time, normalize_number, text)
        # 
        try:
            # self.set_effect(int(text))
            path = self.take_picture()
            url = self.upload_picture(path)
            self.gsm.send_sms(number, 'התמונה שלך:\n%s' % (url,))
        except:
            pass
        # log the sms to the workseet
        try:
            self.sms_workseet.append_table(values=(send_time, normalize_number, text))
        except:
            pass

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
        self._logger.info('upload_picture: %s', path)
        file_id = self.gdrive.upload_file(path, share=True, delete=True, parent_directory=constants.DRIVE_SMS_CAMERA_FOLDER)
        url = self.short_url(self.gdrive.VIEW_FILE_URL % (file_id,))
        self._logger.debug('upload_picture url: %s', url)
        return url

    def _update_sms_workseet(self):
        # open the worksheet with the matching gsm number
        sms_workseet = self._sms_sheet.worksheet_by_title(constants.GSM_SIM_NUMBER)
        if sms_workseet is None:
            self._logger.warning('sms_workseet named %s didn\'t found', constants.GSM_SIM_NUMBER)
            return
        self.sms_workseet = sms_workseet

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
