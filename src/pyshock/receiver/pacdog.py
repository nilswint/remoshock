#!/usr/bin/python3
#
# Copyright nilswinter 2020-2021. License: AGPL
#_______________________________________________


import re
import threading

from pyshock.core.action import Action
from pyshock.receiver.receiver import Receiver

lock = threading.RLock()

class Pacdog(Receiver):

    button_codes = [
        #8 22 23
        [0, 0, 0],  # E/P left
        [0, 1, 1],  # B1  right 1
        [0, 1, 0],  # B2  right 2, E/P right
        [1, 1, 0],  # B3  right 3
        [1, 0, 0],  # B4  left 1
        [0, 0, 1],  # B5  left 2
        [1, 0, 1],  # B6  left 3
        [1, 1, 1]   # unused
    ]

    def __init__(self, name, color, code, button):
        super().__init__(name, color)
        self.code = code
        self.button = button

    def validate_config(self):
        if re.fullmatch("^[01]{9}$", self.code) == None:
            print("ERROR: Invalid transmitter_code \"" + self.code + "\" in pyshock.ini.")
            print("The transmitter_code must be sequence of length 9 consisting of the characters 0 and 1")
            return False

        if self.button < 0 or self.button > 7:
            print("ERROR: Invalid button \"" + str(self.button) + "\" in pyshock.ini.")
            print("This parameter needs to be a whole number between 0 and 7 inclusive.")
            return False

        return True

    def is_sdr_required(self):
        return True

    def boot(self, _arduino_manader, sdr_sender):
        self.sender = sdr_sender

    def generate(self, code, intensity, button, beep):
        pre_checksum = code[0:2] + self.calculate_intensity_code(intensity) + str(self.button_codes[button][0]) + code[2:]
        post_checksum = str(beep) + str(self.button_codes[button][1]) + str(self.button_codes[button][2])
        data = pre_checksum + "CCCCC" + post_checksum
        return pre_checksum + self.calculate_checksum(data) + post_checksum

    def calculate_intensity_code(self, intensity):
        res = ""
        for i in range(0, 6):
            res = res + str(intensity // 2**i % 2)
        return res

    def calculate_checksum(self, data):
        # a b c d e f g h i  j  k  l  m  n  o p q  r  s
        # 7 6 5 4 3 2 1 0 15 14 13 12 11 10 9 8 23 22 21
        res =       str((int(data[0]) + int(data[ 8])) % 2)
        res = res + str((int(data[1]) + int(data[ 9]) + int(data[21])) % 2)
        res = res + str((int(data[2]) + int(data[10]) + int(data[22])) % 2)
        res = res + str((int(data[3]) + int(data[11]) + int(data[23])) % 2)
        res = res + str((int(data[4]) + int(data[12])) % 2)
        return res

    def encode(self, data):
        prefix = "0101010101010101111"
        filler = "10"
        res = prefix + filler
        for bit in data:
            res = res + bit + filler
        return res


    def send(self, data):
        self.sender.send(
            frequency=27.1e6,
            sample_rate=2e6,
            carrier_frequency=27.1e6,
            modulation_type="FSK",
            samples_per_symbol=3100,
            low_frequency=92e3,
            high_frequency=95e3,
            pause=262924,
            data=data)


    def command(self, action, level, duration):
        message = ""
        if action == Action.BEEPZAP:
            message = self.encode(self.generate(self.code, 0, self.button, 1)) + "/1s"

        beep = 0
        if action == Action.BEEP or action == Action.VIB:
            beep = 1
        if action == Action.LED:
            # Note: even level 0 creates a tiny shock
            level = 0

        if duration < 250:
            duration = 250
        if duration > 10000:
            duration = 10000

        message_template = self.encode(self.generate(self.code, level * 63 // 100, self.button, beep))
        for _ in range(0, (duration + 5) // 250):
            message = message + " " + message_template

        self.send(message)

