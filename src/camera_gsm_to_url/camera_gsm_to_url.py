import os
import time
import logging
import datetime

from PIL import Image
from picamera import PiCamera

from infra.app import app
from sms_camera.src.camera_gsm_to_url import constants


class CameraGsmToUrl(app.App):
    _logger = logging.getLogger('camera_gsm_to_url')

    def __init__(self):
        app.App.__init__(self, constants)
        self.left, self.top = 0, 0
        # get current screen size
        self.width, self.height = map(int, os.popen(r'tvservice -s | grep -oP "\d\d+x\d\d+"', 'r').read().strip().split('x'))
        # attach to raspberrypi camera
        self.camera = PiCamera()
        self.camera.framerate = constants.CAMERA_FPS
        # logos overlays
        self.logo1 = self._image_to_overlay(constants.LOGO0_PATH)
        self.logo2 = self._image_to_overlay(constants.LOGO1_PATH)
        self.logo3 = self._image_to_overlay(constants.LOGO2_PATH)
        # get camera pictures scale
        self.camera_scale = self.camera.resolution.width / self.camera.resolution.height
        # last pictures overlays
        self.pictures = []
        # draw evrything
        self.redraw()

    def redraw(self):
        self.sep = int(min(self.width, self.height) * constants.SEP_SCALE)
        self.pictures_h = int((self.height - 3 * self.sep) * constants.PICTURES_HEIGHT_SCALE)
        self.pictures_w = int(self.camera_scale * self.pictures_h)
        self.pictures_c = int((self.width - self.sep) / (self.pictures_w + self.sep))
        self.pictures_l = int((self.width - self.pictures_c * (self.pictures_w + self.sep) - self.sep) / 2) + self.sep + self.left
        self.pictures_t = self.sep + self.top

        self._logger.info('main window: %s', (self.left, self.top, self.width, self.height))
        self._logger.info('camera resolution: %sx%s @ %s fps', self.camera.resolution.width, self.camera.resolution.height, self.camera.framerate)
        self._logger.info('first picture window: %s', (self.pictures_l, self.pictures_t, self.pictures_w, self.pictures_h))
        self._logger.info('pictures count: %s, sep: %s', self.pictures_c, self.sep)
        
        if not self.camera.closed:
            if not self.camera.previewing:
                self.camera.start_preview()
                self.camera.preview.fullscreen=False
                self.logo1.layer = self.camera.preview.layer + 1
                self.logo2.layer = self.logo1.layer
                self.logo3.layer = self.logo1.layer
            camera_t = self.sep + self.pictures_h + self.sep 
            camera_h = self.height - camera_t - self.sep
            camera_w = int(self.camera_scale * camera_h)
            camera_l = int((self.width - camera_w) / 2) + self.left
            self.camera.preview.window = [camera_l, camera_t, camera_w, camera_h]
            self.logo1.window = [camera_l, camera_t, self.logo1.width, self.logo1.height]
            self.logo2.window = [camera_l + camera_w - self.logo2.width, camera_t, self.logo2.width, self.logo2.height]
            self.logo3.window = [camera_l, camera_t + camera_h - self.logo3.height, self.logo3.width, self.logo3.height]
        self.draw_pictures()

    def draw_pictures(self):
        for i, p in enumerate(self.pictures):
            p.window = (self.pictures_l + i * (self.pictures_w + self.sep), self.pictures_t, self.pictures_w, self.pictures_h)

    def take_picture(self):
        self.camera.preview.alpha = 100
        time.sleep(0.7)
        path = constants.IMAGES_PATH % (datetime.datetime.now().strftime(constants.DATETIME_FORMAT),)
        self.camera.capture(path) # resize=(480, 360)
        self.camera.preview.alpha = 255
        self.add_picture(path)
        return path

    def add_picture(self, path):
        self.pictures.append(self._image_to_overlay(path, resize=(self.pictures_w, self.pictures_h), transparent=False))
        if len(self.pictures) > self.pictures_c:
            self.pictures[0].close()
            self.pictures.pop(0)
        self.draw_pictures()

    def set_effect(self, index):
        # set camera image effect by its index
        self.camera.image_effect = constants.CAMERA_EFFECTS[index % len(constants.CAMERA_EFFECTS)]
        
    def _image_to_overlay(self, image_path, layer=0, alpha=255, fullscreen=False, resize=None, transparent=True):
        # open image and resize it if needed
        img = Image.open(image_path)
        if resize is not None:
            img = img.resize(resize)
        # create required size (32, 16) padding for the image 
        pad = Image.new('RGBA' if transparent else 'RGB', [((x + y - 1) // y) * y for x, y in zip(img.size, (32, 16))])
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
