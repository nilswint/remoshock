#
# Copyright nilswinter 2020-2021. License: AGPL
# _____________________________________________


# Please ignore this file. It is unfinished and unusable.
# It requires a connected Arduino with the arshock code.


import time
from enum import Enum
from threading import RLock
import serial

from pyshock.core.action import Action
from pyshock.receiver.receiver import Receiver

# type            code, code, channel
#  0  Pettainer,            sender code first byte, seonder code second byte, channel
#  1  Opto-isolator 1,      beep pin,               vibrate pin,              shock pin
#  2  Opto-isolator 2,      beep modifier pin,      ignored,                  pin



class ProtocolAction(Enum):
    """actions used by the communication protocl between pyshock and arshock.
    Note: This this enum extends pyshock.core.action.Action"""
    LIGHT = 10
    BEEP = 11
    VIBRATE = 12
    SHOCK = 13
    BEEPSHOCK = 99

    BOOT = 100
    BOOTED = 101
    ADD = 102

    ACKNOWLEDGE = 200
    PING = 201
    PONG = 202

    DEBUG = 253
    ERROR = 254
    CRASH = 255


class ReceiverType(Enum):
    """receiver types supported by arshock"""
    PETAINER = 0
    OPTOCOUPLER = 1
    OPTOCOUPLER_BEEP_MODIFIER = 2


class ArduinoBasedReceiver(Receiver):
    """parent class for receivers controlled via arshock on Arduino"""

    def __init__(self, name, color, receiver_type, arg1, arg2, arg3):
        super().__init__(name, color)
        self.receiver_type = receiver_type
        self.arg1 = arg1
        self.arg2 = arg2
        self.arg3 = arg3


    def is_arduino_required(self):
        return True


    def boot(self, _pyshock, _receiver, arduino_manager, _sdr_sender):
        self.arduino_manager = arduino_manager
        self.index = arduino_manager.register_receiver(self.receiver_type.value, self.arg1, self.arg2, self.arg3)


    def get_impulse_duration(self):
        """duration of one impulse in milliseconds"""
        return 500


    def command(self, action, power, duration):
        if action == Action.BEEPSHOCK:
            self.arduino_manager.command(Action.BEEP, self.index, 0, 0)
            time.sleep(1)
            action = Action.SHOCK
        self.arduino_manager.command(action, self.index, power, duration)


class ArduinoPetainer(ArduinoBasedReceiver):
    def __init__(self, name, color, code_first_byte, code_second_byte, channel):
        super().__init__(name, color, ReceiverType.PETAINER, code_first_byte, code_second_byte, channel)


class ArduinoOptocoupler(ArduinoBasedReceiver):
    def __init__(self, name, color, pin_beep, pin_vib, pin_SHOCK):
        super().__init__(name, color, ReceiverType.OPTOCOUPLER, pin_beep, pin_vib, pin_SHOCK)


class ArduinoOptocouplerBeepModifier(ArduinoBasedReceiver):
    def __init__(self, name, color, pin_modifier_beep, pin_button):
        super().__init__(name, color, ReceiverType.OPTOCOUPLER_BEEP_MODIFIER, pin_modifier_beep, 0, pin_button)


class ArduinoManager():
    """handles communication with arshock running on Arduino connected via USB"""

    def read_responses(self, read_until=ProtocolAction.ACKNOWLEDGE):
        while True:
            if self.ser.in_waiting < 2:
                time.sleep(0.1)
                continue
            data = self.ser.read(2)
            if data[0] == read_until.value:
                break

            params = self.ser.read(data[1])
            if data[0] != ProtocolAction.DEBUG.value:
                print(data[0])
            print(params)
            print(" ")


    def send(self, data):
        """sends data and waits for an acknowledgement.

        @param data bytes data to send
        """
        with self.serial_lock:
            self.ser.write(data)
            self.read_responses()


    def command(self, action, receiver, power, duration):
        data = [action.value, 4, receiver, power, int(duration / 256), duration % 256]
        message = bytes(data)
        self.send(message)


    def boot(self):
        """Boots the Arduino and registers receivers"""

        self.ser = serial.Serial('/dev/ttyACM0')
        self.serial_lock = RLock()
        self.receiver_index = -1

        with self.serial_lock:
            time.sleep(1)
            self.ser.flushInput()

            self.ser.write(bytes([ProtocolAction.BOOT.value, 0]))
            self.read_responses(ProtocolAction.BOOTED)
            self.read_responses()


    def register_receiver(self, receiver_type, arg1, arg2, arg3):
        with self.serial_lock:
            self.send(bytes([ProtocolAction.ADD.value, 4, receiver_type, arg1, arg2, arg3]))
        self.receiver_index = self.receiver_index + 1
        return self.receiver_index
