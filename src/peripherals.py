#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import RPi.GPIO as GPIO
#import io
import time

from threading import Timer
import threading
try:
    import queue as Queue
except ImportError:
    import Queue as Queue

import spidev
from math import ceil

def clean():
    GPIO.cleanup()

global status
status = False
def button_default_push_cb():
    '''
    Dummy action
    '''
    
    global status
    if status:
        print("the last button push is ongoing, nothing to be done")
        return status
    
    print("dummy function for the button, sleep 3")
    time.sleep(3)
    status=False # release for further push

class Button(object):
    '''
    Botón del ReSpeakerHat
    '''
    
    def __init__(self, gpio_pin, push_callback=None):
        self._gpio_pin = gpio_pin
        if push_callback is not None:
            self.gpio_init(push_callback)

    def gpio_init(self, push_callback=button_default_push_cb):
        self._push_cb = push_callback
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._gpio_pin, GPIO.IN)
            # wait for falling and set bouncetime to prevent the callback function from being called multiple times when the button is pressed
        GPIO.add_event_detect(self._gpio_pin, GPIO.FALLING, callback=self.push, bouncetime=200)

    def push(self,ev=None):
        print("[Button] has been pushed")
        self._push_cb()

    def clear(self, with_gpio=True):
        if with_gpio:
            GPIO.cleanup()    


class Alarm(object):
    '''
    Horn sounder, auto off with timeout, optional callback when off
    '''
    
    def __init__(self, gpio_pin, timeout_seconds):
        self._gpio_pin = gpio_pin
        self.__timeout_seconds = timeout_seconds
        
        self._gpio_init()
        self.__timer_to_stop = None
        self.__off_callback = None
        
    def _gpio_init(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._gpio_pin, GPIO.OUT)

        GPIO.output(self._gpio_pin, GPIO.LOW)
        self.__raised = False
        
    def on(self, delay=0, off_callback=None):
        def _execute_on():
            print("[Alarm] is raised")
            self.__raised = True
            GPIO.output(self._gpio_pin, GPIO.HIGH)
            self.__timer_to_stop = Timer(self.__timeout_seconds, self.off) 
            self.__timer_to_stop.start()
            self.__off_callback = off_callback
        if delay > 0:
            print("[Alarm] will be on in %d seconds" % (delay))
            t = Timer(delay,_execute_on)
            t.start()
        else:
            _execute_on()

    def off(self, dismiss_callback=False):
        print("[Alarm] is cleared")
        self.__raised = False
        GPIO.output(self._gpio_pin, GPIO.LOW)
        if self.__timer_to_stop is not None:
            self.__timer_to_stop.cancel()
            self.__timer_to_stop = None
        if self.__off_callback is not None and not dismiss_callback:
            self.__off_callback()
        self.__off_callback = None
        
    def is_on(self):
        return self.__raised

    def clear(self, with_gpio=True):
        if with_gpio:
            GPIO.cleanup()    
        if self.__timer_to_stop is not None:
            self.__timer_to_stop.cancel()
            self.__timer_to_stop = None

    
class Pixels:
    '''
    Leds del ReSpeakerHat
    from https://github.com/respeaker/mic_hat.git
    '''

    def __init__(self, PIXELS_N=3):
        self.PIXELS_N = PIXELS_N
        self.basis = [0] * 3 * self.PIXELS_N
        self.basis[0] = 2
        self.basis[3] = 1
        self.basis[4] = 1
        self.basis[7] = 2

        self.colors = [0] * 3 * self.PIXELS_N
        self.dev = APA102(num_led=self.PIXELS_N)

        self.next = threading.Event()
        self.queue = Queue.Queue()
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()

    def wakeup(self, direction=0):
        def f():
            self._wakeup(direction)

        self.next.set()
        self.queue.put(f)

    def listen(self):
        self.next.set()
        self.queue.put(self._listen)

    def think(self):
        self.next.set()
        self.queue.put(self._think)

    def speak(self):
        self.next.set()
        self.queue.put(self._speak)

    def off(self):
        self.next.set()
        self.queue.put(self._off)

    def _run(self):
        while True:
            func = self.queue.get()
            func()

    def _wakeup(self, direction=0):
        for i in range(1, 25):
            colors = [i * v for v in self.basis]
            self.write(colors)
            time.sleep(0.01)

        self.colors = colors

    def _listen(self):
        for i in range(1, 25):
            colors = [i * v for v in self.basis]
            self.write(colors)
            time.sleep(0.01)

        self.colors = colors

    def _think(self):
        colors = self.colors

        self.next.clear()
        while not self.next.is_set():
            colors = colors[3:] + colors[:3]
            self.write(colors)
            time.sleep(0.2)

        t = 0.1
        for i in range(0, 5):
            colors = colors[3:] + colors[:3]
            self.write([(v * (4 - i) / 4) for v in colors])
            time.sleep(t)
            t /= 2

        # time.sleep(0.5)

        self.colors = colors

    def _speak(self):
        colors = self.colors
        gradient = -1
        position = 24

        self.next.clear()
        while not self.next.is_set():
            position += gradient
            self.write([(v * position / 24) for v in colors])

            if position == 24 or position == 4:
                gradient = -gradient
                time.sleep(0.2)
            else:
                time.sleep(0.01)

        while position > 0:
            position -= 1
            self.write([(v * position / 24) for v in colors])
            time.sleep(0.01)

        # self._off()

    def _off(self):
        self.write([0] * 3 * self.PIXELS_N)

    def write(self, colors):
        for i in range(self.PIXELS_N):
            self.dev.set_pixel(i, int(colors[3*i]), int(colors[3*i + 1]), int(colors[3*i + 2]))

        self.dev.show()

# ==========================================================================
# APA102 from https://github.com/respeaker/mic_hat.git
# ==========================================================================

"""
The code is based on https://github.com/tinue/APA102_Pi
This is the main driver module for APA102 LEDs
License: GPL V2
"""

RGB_MAP = { 'rgb': [3, 2, 1], 'rbg': [3, 1, 2], 'grb': [2, 3, 1],
            'gbr': [2, 1, 3], 'brg': [1, 3, 2], 'bgr': [1, 2, 3] }

class APA102:
    """
    Driver for APA102 LEDS (aka "DotStar").
    (c) Martin Erzberger 2016-2017
    My very first Python code, so I am sure there is a lot to be optimized ;)
    Public methods are:
     - set_pixel
     - set_pixel_rgb
     - show
     - clear_strip
     - cleanup
    Helper methods for color manipulation are:
     - combine_color
     - wheel
    The rest of the methods are used internally and should not be used by the
    user of the library.
    Very brief overview of APA102: An APA102 LED is addressed with SPI. The bits
    are shifted in one by one, starting with the least significant bit.
    An LED usually just forwards everything that is sent to its data-in to
    data-out. While doing this, it remembers its own color and keeps glowing
    with that color as long as there is power.
    An LED can be switched to not forward the data, but instead use the data
    to change it's own color. This is done by sending (at least) 32 bits of
    zeroes to data-in. The LED then accepts the next correct 32 bit LED
    frame (with color information) as its new color setting.
    After having received the 32 bit color frame, the LED changes color,
    and then resumes to just copying data-in to data-out.
    The really clever bit is this: While receiving the 32 bit LED frame,
    the LED sends zeroes on its data-out line. Because a color frame is
    32 bits, the LED sends 32 bits of zeroes to the next LED.
    As we have seen above, this means that the next LED is now ready
    to accept a color frame and update its color.
    So that's really the entire protocol:
    - Start by sending 32 bits of zeroes. This prepares LED 1 to update
      its color.
    - Send color information one by one, starting with the color for LED 1,
      then LED 2 etc.
    - Finish off by cycling the clock line a few times to get all data
      to the very last LED on the strip
    The last step is necessary, because each LED delays forwarding the data
    a bit. Imagine ten people in a row. When you yell the last color
    information, i.e. the one for person ten, to the first person in
    the line, then you are not finished yet. Person one has to turn around
    and yell it to person 2, and so on. So it takes ten additional "dummy"
    cycles until person ten knows the color. When you look closer,
    you will see that not even person 9 knows its own color yet. This
    information is still with person 2. Essentially the driver sends additional
    zeroes to LED 1 as long as it takes for the last color frame to make it
    down the line to the last LED.
    """
    # Constants
    MAX_BRIGHTNESS = 0b11111 # Safeguard: Set to a value appropriate for your setup
    LED_START = 0b11100000 # Three "1" bits, followed by 5 brightness bits

    def __init__(self, num_led, global_brightness=MAX_BRIGHTNESS,
                 order='rgb', bus=0, device=1, max_speed_hz=8000000):
        self.num_led = num_led  # The number of LEDs in the Strip
        order = order.lower()
        self.rgb = RGB_MAP.get(order, RGB_MAP['rgb'])
        # Limit the brightness to the maximum if it's set higher
        if global_brightness > self.MAX_BRIGHTNESS:
            self.global_brightness = self.MAX_BRIGHTNESS
        else:
            self.global_brightness = global_brightness

        self.leds = [self.LED_START,0,0,0] * self.num_led # Pixel buffer
        self.spi = spidev.SpiDev()  # Init the SPI device
        self.spi.open(bus, device)  # Open SPI port 0, slave device (CS) 1
        # Up the speed a bit, so that the LEDs are painted faster
        if max_speed_hz:
            self.spi.max_speed_hz = max_speed_hz

    def clock_start_frame(self):
        """Sends a start frame to the LED strip.
        This method clocks out a start frame, telling the receiving LED
        that it must update its own color now.
        """
        self.spi.xfer2([0] * 4)  # Start frame, 32 zero bits


    def clock_end_frame(self):
        """Sends an end frame to the LED strip.
        As explained above, dummy data must be sent after the last real colour
        information so that all of the data can reach its destination down the line.
        The delay is not as bad as with the human example above.
        It is only 1/2 bit per LED. This is because the SPI clock line
        needs to be inverted.
        Say a bit is ready on the SPI data line. The sender communicates
        this by toggling the clock line. The bit is read by the LED
        and immediately forwarded to the output data line. When the clock goes
        down again on the input side, the LED will toggle the clock up
        on the output to tell the next LED that the bit is ready.
        After one LED the clock is inverted, and after two LEDs it is in sync
        again, but one cycle behind. Therefore, for every two LEDs, one bit
        of delay gets accumulated. For 300 LEDs, 150 additional bits must be fed to
        the input of LED one so that the data can reach the last LED.
        Ultimately, we need to send additional numLEDs/2 arbitrary data bits,
        in order to trigger numLEDs/2 additional clock changes. This driver
        sends zeroes, which has the benefit of getting LED one partially or
        fully ready for the next update to the strip. An optimized version
        of the driver could omit the "clockStartFrame" method if enough zeroes have
        been sent as part of "clockEndFrame".
        """

        self.spi.xfer2([0xFF] * 4)

        # Round up num_led/2 bits (or num_led/16 bytes)
        #for _ in range((self.num_led + 15) // 16):
        #    self.spi.xfer2([0x00])


    def clear_strip(self):
        """ Turns off the strip and shows the result right away."""

        for led in range(self.num_led):
            self.set_pixel(led, 0, 0, 0)
        self.show()


    def set_pixel(self, led_num, red, green, blue, bright_percent=100):
        """Sets the color of one pixel in the LED stripe.
        The changed pixel is not shown yet on the Stripe, it is only
        written to the pixel buffer. Colors are passed individually.
        If brightness is not set the global brightness setting is used.
        """
        if led_num < 0:
            return  # Pixel is invisible, so ignore
        if led_num >= self.num_led:
            return  # again, invisible

        # Calculate pixel brightness as a percentage of the
        # defined global_brightness. Round up to nearest integer
        # as we expect some brightness unless set to 0
        brightness = int(ceil(bright_percent*self.global_brightness/100.0))

        # LED startframe is three "1" bits, followed by 5 brightness bits
        ledstart = (brightness & 0b00011111) | self.LED_START

        start_index = 4 * led_num
        self.leds[start_index] = ledstart
        self.leds[start_index + self.rgb[0]] = red
        self.leds[start_index + self.rgb[1]] = green
        self.leds[start_index + self.rgb[2]] = blue


    def set_pixel_rgb(self, led_num, rgb_color, bright_percent=100):
        """Sets the color of one pixel in the LED stripe.
        The changed pixel is not shown yet on the Stripe, it is only
        written to the pixel buffer.
        Colors are passed combined (3 bytes concatenated)
        If brightness is not set the global brightness setting is used.
        """
        self.set_pixel(led_num, (rgb_color & 0xFF0000) >> 16,
                       (rgb_color & 0x00FF00) >> 8, rgb_color & 0x0000FF,
                        bright_percent)


    def rotate(self, positions=1):
        """ Rotate the LEDs by the specified number of positions.
        Treating the internal LED array as a circular buffer, rotate it by
        the specified number of positions. The number could be negative,
        which means rotating in the opposite direction.
        """
        cutoff = 4 * (positions % self.num_led)
        self.leds = self.leds[cutoff:] + self.leds[:cutoff]


    def show(self):
        """Sends the content of the pixel buffer to the strip.
        Todo: More than 1024 LEDs requires more than one xfer operation.
        """
        self.clock_start_frame()
        # xfer2 kills the list, unfortunately. So it must be copied first
        # SPI takes up to 4096 Integers. So we are fine for up to 1024 LEDs.
        data = list(self.leds)
        while data:
            self.spi.xfer2(data[:32])
            data = data[32:]
        self.clock_end_frame()


    def cleanup(self):
        """Release the SPI device; Call this method at the end"""

        self.spi.close()  # Close SPI port

    @staticmethod
    def combine_color(red, green, blue):
        """Make one 3*8 byte color value."""

        return (red << 16) + (green << 8) + blue


    def wheel(self, wheel_pos):
        """Get a color from a color wheel; Green -> Red -> Blue -> Green"""

        if wheel_pos > 255:
            wheel_pos = 255 # Safeguard
        if wheel_pos < 85:  # Green -> Red
            return self.combine_color(wheel_pos * 3, 255 - wheel_pos * 3, 0)
        if wheel_pos < 170:  # Red -> Blue
            wheel_pos -= 85
            return self.combine_color(255 - wheel_pos * 3, 0, wheel_pos * 3)
        # Blue -> Green
        wheel_pos -= 170
        return self.combine_color(0, wheel_pos * 3, 255 - wheel_pos * 3)


    def dump_array(self):
        """For debug purposes: Dump the LED array onto the console."""

        print(self.leds)
        
        
