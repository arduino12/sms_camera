import os
import time
import logging
import datetime
from PIL import Image
from picamera import PiCamera
from pyshorteners import Shortener

from infra.app import app
from infra.modules.gdrive import gdrive
from sms_camera.src.camera_gsm_to_url import constants


class CameraGsmToUrl(app.App):
    _logger = logging.getLogger('camera_gsm_to_url')

    def __init__(self):
        app.App.__init__(self, constants)
        # google drive uploader
        self.gdrive = gdrive.Gdrive(constants.SERVICE_ACCOUNT)
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

    def draw_pictures(self):
        # draw pictures overlays
        for i, p in enumerate(self.pictures):
            p.window = (self.pictures_l + i * (self.pictures_w + self.sep), self.pictures_t, self.pictures_w, self.pictures_h)

    def take_picture(self):
        # capture picture and return its path
        self.camera.preview.alpha = 100
        time.sleep(0.7)
        path = constants.IMAGES_PATH % (datetime.datetime.now().strftime(constants.IMAGES_DATETIME_FORMAT),)
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
        self.camera.image_effect = constants.CAMERA_EFFECTS[index % len(constants.CAMERA_EFFECTS)]

    def upload_picture(self, path):
        file_id = self.gdrive.upload_file(path, share=True, delete=True, parent_directory=constants.SMS_CAMERA_FOLDER)
        url = self.short_url(self.gdrive.VIEW_FILE_URL % (file_id,))
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

    def __exit__(self):
        try:
            self.camera.close()
        except:
            pass
        app.App.__exit__(self)
