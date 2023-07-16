#   Benjamin DELPY `gentilkiwi`
#   https://blog.gentilkiwi.com / 
#   benjamin@gentilkiwi.com
#   Licence : https://creativecommons.org/licenses/by/4.0/
#
#   High Level Analyzer for Texas Instrument TRF7970A NFC chip on SPI bus
#   SPI settings:
#    - Significant Bit:   MSB
#    - Bits per Transfer: 8
#    - Clock State:       CPOL = 0
#    - Clock Phase:       CPHA = 1
#    - Enable Line:       Active Low

from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame
from enum import Enum

class TRF7970A_DECODER_STATE(Enum):
    START = 0
    GET_INSTRUCTION = 1
    GET_DATA = 2

class TRF7970A_TYPE(Enum):
    Address = 0
    Command = 1

class TRF7970A_OPERATION(Enum):
    Write = 0
    Read = 1

class TRF7970A_ADDRESS_MODE(Enum):
    Direct = 0
    Continuous = 1

COMMAND_CODE = {
    0x00: 'IDLE',
    0x03: 'SOFT_INIT',
    0x04: 'INITIAL_RF_COLLISION_AVOID',
    0x05: 'PERFORM_RES_RF_COLLISION_AVOID',
    0x06: 'PERFORM_RES_RF_COLLISION_AVOID_N0',
    0x0f: 'RESET_FIFO',
    0x10: 'TRANSMIT_NO_CRC',
    0x11: 'TRANSMIT_CRC',
    0x12: 'DELAY_TRANSMIT_NO_CRC',
    0x13: 'DELAY_TRANSMIT_CRC',
    0x14: 'TRANSMIT_NEXT_SLOT',
    0x15: 'CLOSE_SLOT_SEQUENCE',
    0x16: 'STOP_DECODERS',
    0x17: 'RUN_DECODERS',
    0x18: 'TEST_INTERNAL_RF',
    0x19: 'TEST_EXTERNAL_RF',
    0x1a: 'RX_ADJUST_GAIN',
}

REGISTER_ADDRESS = {
    0x00: 'CHIP_STATUS_CTRL',
    0x01: 'ISO_CONTROL',
    0x02: 'ISO14443B_OPTIONS',
    0x03: 'ISO14443A_OPTIONS',
    0x04: 'TX_TIMER_EPC_HIGH',
    0x05: 'TX_TIMER_EPC',
    0x06: 'TX_PULSE_LENGTH_CTRL',
    0x07: 'RX_NO_RESPONSE_WAIT',
    0x08: 'RX_WAIT_TIME',
    0x09: 'MODULATOR_CONTROL',
    0x0a: 'RX_SPECIAL_SETTINGS',
    0x0b: 'REGULATOR_CONTROL',
    0x0c: 'IRQ_STATUS',
    0x0d: 'IRQ_MASK',
    0x0e: 'COLLISION_POSITION',
    0x0f: 'RSSI_LEVEL',
    0x10: 'SPECIAL_FUNC_1',
    0x11: 'SPECIAL_FUNC_2',
    0x14: 'FIFO_IRQ_LEVEL',
    0x16: 'NFC_LOW_DETECTION_LEVEL',
    0x17: 'NFC_ID',
    0x18: 'NFC_TARGET_LEVEL',
    0x19: 'NFC_TARGET_PROTOCOL',
    0x1a: 'TEST_SETTING1',
    0x1b: 'TEST_SETTING2',
    0x1c: 'FIFO_STATUS',
    0x1d: 'TX_LENGTH_BYTE1',
    0x1e: 'TX_LENGTH_BYTE2',
    0x1f: 'FIFO',
}

class Hla(HighLevelAnalyzer):

    result_types = {
        'Command': {'format': 'CMD {{data.command}}'},
        'Address': {'format':  '{{data.command}} @ {{data.address}} [ {{data.data}}]'},
    }

    def __init__(self):

        state = TRF7970A_DECODER_STATE.START


    def decode(self, frame: AnalyzerFrame):

        if frame.type == 'enable':
            
            self.state = TRF7970A_DECODER_STATE.GET_INSTRUCTION


        elif frame.type == 'result':
            
            if self.state == TRF7970A_DECODER_STATE.GET_INSTRUCTION:
            
                data = int.from_bytes(frame.data['mosi'], 'big')
            
                if data & 0x80:

                    self.type = TRF7970A_TYPE.Command
                    data &= 0x1f
                    
                    return AnalyzerFrame('Command', frame.start_time, frame.end_time, {
                        'command': '{0:#0{1}x}'.format(data, 4) + ' - ' + COMMAND_CODE.get(data, '?')
                    })


                else:

                    self.type = TRF7970A_TYPE.Address
                    self.begin_frame = frame.start_time
                
                    self.operation = TRF7970A_OPERATION.Read if (data & 0x40) else TRF7970A_OPERATION.Write
                    self.mode = TRF7970A_ADDRESS_MODE.Continuous if (data & 0x20) else TRF7970A_ADDRESS_MODE.Direct
                    self.address_command = ('READ(c)' if (self.operation == TRF7970A_OPERATION.Read) else 'WRITE(c)') if (self.mode == TRF7970A_ADDRESS_MODE.Continuous) else ('READ' if (self.operation == TRF7970A_OPERATION.Read) else 'WRITE')
                    self.begin_address = data & 0x1f
                
                    self.data = ''
                    self.state = TRF7970A_DECODER_STATE.GET_DATA

                
            elif self.state == TRF7970A_DECODER_STATE.GET_DATA:

                self.data += '{0:#0{1}x}'.format(int.from_bytes(frame.data['miso' if (self.operation == TRF7970A_OPERATION.Read) else 'mosi'], 'big'), 4) + ' '

                if self.mode == TRF7970A_ADDRESS_MODE.Direct:

                    self.state = TRF7970A_DECODER_STATE.GET_INSTRUCTION
                    
                    return AnalyzerFrame('Address', self.begin_frame, frame.end_time, {
                        'command': self.address_command,
                        'address': '{0:#0{1}x}'.format(self.begin_address, 4) + ' - ' + REGISTER_ADDRESS.get(self.begin_address, '?'),
                        'data': self.data
                    })

               
        elif frame.type == 'disable':

            self.state = TRF7970A_DECODER_STATE.START
            
            if (self.type == TRF7970A_TYPE.Address) and (self.mode == TRF7970A_ADDRESS_MODE.Continuous):

                return AnalyzerFrame('Address', self.begin_frame, frame.end_time, {
                    'command': self.address_command,
                    'address': '{0:#0{1}x}'.format(self.begin_address, 4) + ' - ' + REGISTER_ADDRESS.get(self.begin_address, '?'),
                    'data': self.data
                })