"""
User Behavior Simulation
Simulates realistic user interactions to trigger EDR behavioral analysis
"""

import time
import random
import logging
from typing import Optional

try:
    import pyautogui
    import pynput
    from pynput.mouse import Controller as MouseController
    from pynput.keyboard import Controller as KeyboardController, Key
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False
    pyautogui = None
    pynput = None

logger = logging.getLogger(__name__)


class UserBehaviorSimulator:
    """
    Simulates user mouse and keyboard interactions

    This helps trigger EDR behavioral analysis by demonstrating
    realistic user behavior rather than automated execution.
    """

    def __init__(self, enabled: bool = True):
        """
        Initialize user behavior simulator

        Args:
            enabled: Whether simulation is enabled
        """
        self.enabled = enabled and AUTOMATION_AVAILABLE

        if self.enabled:
            self.mouse = MouseController()
            self.keyboard = KeyboardController()
            self.logger = logging.getLogger(__name__)
        else:
            if not AUTOMATION_AVAILABLE:
                logger.warning("User simulation libraries not available (pyautogui, pynput)")

    def simulate_user_interaction(self, duration_seconds: int = 60):
        """
        Simulate user interactions for a period of time

        Args:
            duration_seconds: How long to simulate (seconds)
        """
        if not self.enabled:
            time.sleep(duration_seconds)
            return

        self.logger.info(f"Starting user behavior simulation for {duration_seconds}s")

        end_time = time.time() + duration_seconds

        while time.time() < end_time:
            # Random choice of action
            action = random.choice([
                'mouse_move',
                'mouse_click',
                'key_press',
                'scroll',
                'wait'
            ])

            try:
                if action == 'mouse_move':
                    self._move_mouse()
                elif action == 'mouse_click':
                    self._click_mouse()
                elif action == 'key_press':
                    self._press_key()
                elif action == 'scroll':
                    self._scroll()
                else:
                    # Just wait
                    time.sleep(random.uniform(0.5, 2.0))

            except Exception as e:
                self.logger.debug(f"Error during simulation action {action}: {e}")

            # Small delay between actions
            time.sleep(random.uniform(0.2, 1.5))

        self.logger.info("User behavior simulation completed")

    def _move_mouse(self):
        """Move mouse to random position"""
        if not self.enabled:
            return

        try:
            # Get screen size
            screen_width, screen_height = pyautogui.size()

            # Move to random position (avoiding edges)
            x = random.randint(100, screen_width - 100)
            y = random.randint(100, screen_height - 100)

            pyautogui.moveTo(x, y, duration=random.uniform(0.3, 0.8))

        except Exception as e:
            self.logger.debug(f"Mouse move error: {e}")

    def _click_mouse(self):
        """Click mouse"""
        if not self.enabled:
            return

        try:
            pyautogui.click()
        except Exception as e:
            self.logger.debug(f"Mouse click error: {e}")

    def _press_key(self):
        """Press random key"""
        if not self.enabled:
            return

        try:
            # Safe keys to press
            keys = ['down', 'up', 'left', 'right', 'space', 'enter', 'tab']
            key = random.choice(keys)

            pyautogui.press(key)

        except Exception as e:
            self.logger.debug(f"Key press error: {e}")

    def _scroll(self):
        """Scroll mouse wheel"""
        if not self.enabled:
            return

        try:
            # Scroll up or down
            scroll_amount = random.choice([-3, -2, -1, 1, 2, 3])
            pyautogui.scroll(scroll_amount)

        except Exception as e:
            self.logger.debug(f"Scroll error: {e}")

    def enable_office_macros(self):
        """
        Attempt to enable macros in Office applications

        This simulates clicking "Enable Content" button
        """
        if not self.enabled:
            return

        self.logger.info("Attempting to enable Office macros")

        try:
            # Wait for Office to load
            time.sleep(3)

            # Try to find and click "Enable Content" button
            # This is a simplified approach - real implementation would use
            # image recognition or UI automation
            try:
                # Look for "Enable Content" button (yellow bar in Office)
                button = pyautogui.locateOnScreen('enable_content_button.png', confidence=0.8)
                if button:
                    pyautogui.click(button)
                    self.logger.info("Clicked Enable Content button")
            except:
                # Fallback: try keyboard shortcut
                pyautogui.hotkey('alt', 'f')
                time.sleep(0.5)
                pyautogui.press('e')
                time.sleep(0.5)
                pyautogui.press('m')

        except Exception as e:
            self.logger.debug(f"Error enabling macros: {e}")

    def simulate_document_reading(self, duration_seconds: int = 30):
        """
        Simulate reading a document (scrolling, pauses)

        Args:
            duration_seconds: How long to simulate reading
        """
        if not self.enabled:
            time.sleep(duration_seconds)
            return

        self.logger.info(f"Simulating document reading for {duration_seconds}s")

        end_time = time.time() + duration_seconds

        while time.time() < end_time:
            # Scroll down
            pyautogui.scroll(-2)

            # Pause as if reading
            time.sleep(random.uniform(2, 5))

            # Sometimes scroll up to re-read
            if random.random() < 0.2:
                pyautogui.scroll(1)
                time.sleep(random.uniform(1, 2))

    def simulate_typing(self, text: Optional[str] = None, duration_seconds: int = 10):
        """
        Simulate typing

        Args:
            text: Text to type (if None, types random keys)
            duration_seconds: How long to type for
        """
        if not self.enabled:
            time.sleep(duration_seconds)
            return

        self.logger.info("Simulating typing")

        if text:
            for char in text:
                pyautogui.write(char)
                time.sleep(random.uniform(0.1, 0.3))
        else:
            # Type random keys
            end_time = time.time() + duration_seconds
            sample_text = "This is a test document. We are simulating user behavior. "

            i = 0
            while time.time() < end_time:
                if i < len(sample_text):
                    pyautogui.write(sample_text[i])
                    i += 1
                else:
                    i = 0

                time.sleep(random.uniform(0.1, 0.4))

    def close_application(self):
        """Attempt to close the active application"""
        if not self.enabled:
            return

        try:
            # Alt+F4 on Windows
            pyautogui.hotkey('alt', 'F4')
            time.sleep(1)

            # If prompted to save, press No
            pyautogui.press('n')

        except Exception as e:
            self.logger.debug(f"Error closing application: {e}")
