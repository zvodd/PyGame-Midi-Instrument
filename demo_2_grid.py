import pygame
import pygame.midi
import rtmidi
import time
import argparse
from collections import deque
from midiutil import MIDIFile
from dataclasses import dataclass
from typing import List, Deque, Optional, Callable
from datetime import datetime

@dataclass
class MidiEvent:
    note: int
    velocity: int
    timestamp: float

@dataclass
class PianoButton:
    rect: pygame.Rect
    color: tuple
    note: int
    is_pressed: bool = False
    label: str = ""

class MidiBuffer:
    def __init__(self, buffer_duration: float = 30.0):
        self.buffer: Deque[MidiEvent] = deque()
        self.buffer_duration = buffer_duration
        self.start_time = time.time()

    def add_event(self, event: MidiEvent):
        current_time = time.time() - self.start_time
        self.buffer.append(event)
        
        # Cleanup old events
        while (self.buffer and 
               current_time - self.buffer[0].timestamp > self.buffer_duration):
            self.buffer.popleft()

    def save_to_file(self, filename: str = None):
        if not self.buffer:
            print("No events to save")
            return

        if filename is None:
            filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mid"

        midi = MIDIFile(1)
        midi.addTempo(0, 0, 120)

        for event in self.buffer:
            # if event.velocity > 0:
            time_beats = event.timestamp * 2
            midi.addNote(0, 0, event.note, time_beats, 0.5, event.velocity)

        with open(filename, "wb") as f:
            midi.writeFile(f)
        print(f"Saved recording to {filename}")


class MidiDevice:
    def __init__(self, port_name: str = None):
        self.midiout = rtmidi.MidiOut()
        self.port_name = port_name
        self.port_index = self._find_port()
        
        if self.port_index is not None:
            self.midiout.open_port(self.port_index)
            print(f"Opened MIDI port: {port_name}")
        else:
            print("No MIDI port found matching the specified name")
            self._list_ports()
            raise ValueError("Invalid MIDI port name")

    def _find_port(self) -> Optional[int]:
        available_ports = self.midiout.get_ports()
        if self.port_name:
            for i, port in enumerate(available_ports):
                if self.port_name.lower() in port.lower():
                    return i
        return None if not available_ports else 0

    @staticmethod
    def _list_ports():
        midi_out = rtmidi.MidiOut()
        ports = midi_out.get_ports()
        print("\nAvailable MIDI ports:")
        for i, port in enumerate(ports):
            print(f"{i}: {port}")
        midi_out.delete()

    def send_message(self, message: List[int]):
        if self.midiout:
            self.midiout.send_message(message)

    def cleanup(self):
        if self.midiout:
            self.midiout.close_port()


class MidiPiano:
    NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    def __init__(self, midi_device: MidiDevice):
        pygame.init()
        pygame.midi.init()
        
        self.width = 1200
        self.height = 800
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("MIDI Piano")
        
        self.midi_device = midi_device
        self.event_handlers: List[Callable[[MidiEvent], None]] = []
        
        self.margin = 20
        self.button_width = 80
        self.button_height = 80
        self.grid_offset = 100  # Space for save button and other controls
        
        # Create button grid
        self.buttons = self.create_button_grid(start_note=36) 
        
        self.save_button = pygame.Rect(250, 320, 100, 40)

        # Initialize font
        self.font = pygame.font.Font(None, 24)

    def create_button_grid(self, start_note: int) -> List[PianoButton]:
        buttons = []
        rows = 6
        cols = 12
        
        for row in range(rows):
            for col in range(cols):
                note_number = start_note + row * 12 + col
                x = self.margin + col * (self.button_width + 5)
                y = self.grid_offset + row * (self.button_height + 5)
                
                # Get note name and octave
                note_name = self.NOTE_NAMES[note_number % 12]
                octave = (note_number // 12) - 1
                label = f"{note_name}{octave}"
                
                # Use different colors for white and black keys
                is_black_key = '#' in note_name
                color = (100, 100, 100) if is_black_key else (200, 200, 200)
                
                button = PianoButton(
                    rect=pygame.Rect(x, y, self.button_width, self.button_height),
                    color=color,
                    note=note_number,
                    label=label
                )
                buttons.append(button)
        
        return buttons

    def add_event_handler(self, handler: Callable[[MidiEvent], None]):
        self.event_handlers.append(handler)

    def emit_midi_event(self, note: int, velocity: int):
        """Emit MIDI event to device and notify handlers"""
        if velocity > 0:
            self.midi_device.send_message([0x90, note, velocity])
        else:
            self.midi_device.send_message([0x80, note, 0])
            
        event = MidiEvent(note, velocity, time.time())
        for handler in self.event_handlers:
            handler(event)

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    for button in self.buttons:
                        if button.rect.collidepoint(event.pos):
                            if button.is_pressed:
                                continue
                            button.is_pressed = True
                            button.color = (150, 150, 150)
                            self.emit_midi_event(button.note, 100)
                    
                    # if self.save_button.collidepoint(event.pos):
                    #     self.emit_midi_event(0, 0)  # Signal for save
                
                if event.type == pygame.MOUSEBUTTONUP:
                    for button in (b for b in self.buttons if b.is_pressed):
                        if not button.is_pressed:
                            continue
                        button.is_pressed = False
                        button.color = (200, 200, 200)
                        self.emit_midi_event(button.note, 0)

            # Draw interface
            self.screen.fill((255, 255, 255))
            
            # Draw piano grid
            for button in self.buttons:
                pygame.draw.rect(self.screen, button.color, button.rect)
                pygame.draw.rect(self.screen, (0, 0, 0), button.rect, 2)
                
                # Draw note label
                text = self.font.render(button.label, True, (0, 0, 0))
                text_rect = text.get_rect(center=button.rect.center)
                self.screen.blit(text, text_rect)
            
            # pygame.draw.rect(self.screen, (100, 200, 100), self.save_button)
            # font = pygame.font.Font(None, 36)
            # text = font.render("Save", True, (0, 0, 0))
            # text_rect = text.get_rect(center=self.save_button.center)
            # self.screen.blit(text, text_rect)
            
            pygame.display.flip()

        self.midi_device.cleanup()
        pygame.midi.quit()
        pygame.quit()


def enumerate_midi_devices():
    # Initialize MIDI input and output interfaces
    midi_out = rtmidi.MidiOut()

    try:
        output_ports = midi_out.get_ports()

        # Print available output ports
        print("\nAvailable MIDI output ports:")
        for i, port in enumerate(output_ports):
            print(f"{i}: {port}")

    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        # Close the MIDI interfaces
        midi_out.close_port()
        del midi_out



def main():
    parser = argparse.ArgumentParser(description='MIDI Piano')
    parser.add_argument('--output-device', type=str, help='MIDI device name (partial match)')
    args = parser.parse_args()

    # Call the function to enumerate MIDI devices
    enumerate_midi_devices()
    try:
        midi_device = MidiDevice(args.output_device)
        midi_buffer = MidiBuffer()
        piano = MidiPiano(midi_device)
        
        # Connect buffer to piano events
        piano.add_event_handler(midi_buffer.add_event)
        
        piano.run()
        
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()