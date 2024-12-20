import pygame
import pygame.midi
import rtmidi
import time
from collections import deque
from midiutil import MIDIFile
from dataclasses import dataclass
from typing import List, Deque

@dataclass
class MidiEvent:
    note: int
    velocity: int
    timestamp: float

class MidiPiano:
    def __init__(self):
        # Initialize Pygame
        pygame.init()
        pygame.midi.init()
        
        # Set up display
        self.width = 600
        self.height = 400
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("MIDI Piano")
        
        # Initialize MIDI output
        self.midiout = rtmidi.MidiOut()
        self.midiout.open_port(0)  # Open first available port
        
        # Button properties
        self.buttons = [
            {"rect": pygame.Rect(50 + i*100, 150, 80, 150),
             "color": (200, 200, 200),
             "note": 60 + i}  # Starting from middle C
            for i in range(5)
        ]
        
        # Save button
        self.save_button = pygame.Rect(250, 320, 100, 40)
        
        # Recording buffer (30 seconds)
        self.recording_buffer: Deque[MidiEvent] = deque()
        self.start_time = time.time()

    def handle_midi_event(self, note: int, velocity: int):
        """Send MIDI message and store in buffer"""
        if velocity > 0:  # Note On
            self.midiout.send_message([0x90, note, velocity])
        else:  # Note Off
            self.midiout.send_message([0x80, note, 0])
            
        # Store event in buffer
        current_time = time.time() - self.start_time
        self.recording_buffer.append(MidiEvent(note, velocity, current_time))
        
        # Remove events older than 30 seconds
        while (self.recording_buffer and 
               current_time - self.recording_buffer[0].timestamp > 30):
            self.recording_buffer.popleft()

    def save_recording(self):
        """Save the last 30 seconds of MIDI events to a file"""
        if not self.recording_buffer:
            return

        midi = MIDIFile(1)  # One track
        midi.addTempo(0, 0, 120)  # Track 0, time 0, tempo 120 BPM

        # Convert buffer events to MIDI file
        for event in self.recording_buffer:
            if event.velocity > 0:  # Note On
                # Convert time to beats (assuming 120 BPM)
                time_beats = event.timestamp * 2  # 2 beats per second at 120 BPM
                midi.addNote(0, 0, event.note, time_beats, 0.5, event.velocity)

        # Save MIDI file
        with open("recording.mid", "wb") as f:
            midi.writeFile(f)

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    # Check piano keys
                    for button in self.buttons:
                        if button["rect"].collidepoint(event.pos):
                            button["color"] = (150, 150, 150)
                            self.handle_midi_event(button["note"], 100)
                    
                    # Check save button
                    if self.save_button.collidepoint(event.pos):
                        self.save_recording()
                
                if event.type == pygame.MOUSEBUTTONUP:
                    # Reset piano keys
                    for button in self.buttons:
                        if button["rect"].collidepoint(event.pos):
                            button["color"] = (200, 200, 200)
                            self.handle_midi_event(button["note"], 0)

            # Draw interface
            self.screen.fill((255, 255, 255))
            
            # Draw piano keys
            for button in self.buttons:
                pygame.draw.rect(self.screen, button["color"], button["rect"])
                pygame.draw.rect(self.screen, (0, 0, 0), button["rect"], 2)
            
            # Draw save button
            pygame.draw.rect(self.screen, (100, 200, 100), self.save_button)
            font = pygame.font.Font(None, 36)
            text = font.render("Save", True, (0, 0, 0))
            text_rect = text.get_rect(center=self.save_button.center)
            self.screen.blit(text, text_rect)
            
            pygame.display.flip()

        # Cleanup
        self.midiout.close_port()
        pygame.midi.quit()
        pygame.quit()

if __name__ == "__main__":
    piano = MidiPiano()
    piano.run()