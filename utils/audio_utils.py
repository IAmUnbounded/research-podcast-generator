import os
import io
import tempfile
import time
from typing import Optional, Tuple, Union, BinaryIO

# Try to import pydub for audio playback, but make it optional
try:
    from pydub import AudioSegment
    from pydub.playback import play
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("[WARNING] pydub not available. Audio playback will be be limited.")
    
    # Create dummy classes for type checking
    class AudioSegment:
        @staticmethod
        def from_file(*args, **kwargs):
            raise ImportError("pydub is not installed")
    
    def play(*args, **kwargs):
        print("[WARNING] Audio playback requires pydub to be installed")

# Import Murf SDK
try:
    from murf import Murf
    MURF_AVAILABLE = True
except ImportError:
    MURF_AVAILABLE = False
    print("[WARNING] murf package not installed. Text-to-speech will not be available.")
    
    # Create dummy class for type checking
    class Murf:
        def __init__(self, *args, **kwargs):
            raise ImportError("murf package is not installed")

class MurfAIClient:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Murf.ai client with API key."""
        if not MURF_AVAILABLE:
            raise ImportError("murf package is not installed. Please install it with: pip install murf")
            
        self.api_key = api_key or os.getenv('MURF_API_KEY') or os.getenv('MURFAI_API_KEY')
        if not self.api_key:
            raise ValueError("Murf.ai API key is required. Set MURF_API_KEY in .env file.")
        
        try:
            self.client = Murf(api_key=self.api_key)
            print("[INFO] Successfully initialized Murf.ai client")
        except Exception as e:
            print(f"[ERROR] Failed to initialize Murf.ai client: {str(e)}")
            raise
    
    def create_tts_job(self, text: str, voice_id: str = "en-US-terrell", format: str = "mp3") -> Optional[str]:
        """
        Create a new text-to-speech job using the official Murf.ai SDK.
        
        Args:
            text (str): Text to convert to speech
            voice_id (str): Voice ID to use (default: en-US-terrell)
            format (str): Output format (mp3, wav, etc.)
            
        Returns:
            str: Job ID if successful, None otherwise
        """
        if not MURF_AVAILABLE:
            print("[ERROR] Murf SDK is not available")
            return None
            
        if len(text) > 5000:
            text = text[:5000]  # Truncate to 5000 characters as per API limit
            print("[WARNING] Text truncated to 5000 characters")
        
        try:
            print(f"[INFO] Generating speech with voice: {voice_id}, format: {format}")
            
            # Use the official SDK to generate speech
            response = self.client.text_to_speech.generate(
                text=text,
                voice_id=voice_id,
                format=format
            )
            
            # Save the audio data to a temporary file
            if hasattr(response, 'audio_file') and response.audio_file:
                self.last_audio_data = response.audio_file.read()
                return "direct_audio"  # Return a dummy job ID since we have the audio data
                
            print("[ERROR] No audio data in response")
            return None
            
        except Exception as e:
            print(f"[ERROR] Failed to generate speech: {str(e)}")
            return None
    
    def get_job_status(self, job_id: str) -> Tuple[Optional[dict], str]:
        """
        Check the status of a TTS job.
        
        Since we're using the synchronous API, this is mostly a dummy function
        that returns 'completed' if we have audio data.
        
        Args:
            job_id (str): The job ID to check
            
        Returns:
            tuple: (status_data, status) where status is one of: 'pending', 'processing', 'completed', 'failed', 'unknown'
        """
        if job_id == "direct_audio" and hasattr(self, 'last_audio_data') and self.last_audio_data:
            return {"status": "completed"}, "completed"
        return None, "failed"
    
    def wait_for_job_completion(self, job_id: str, poll_interval: int = 1, max_attempts: int = 5) -> Optional[dict]:
        """
        Wait for a TTS job to complete.
        
        Since we're using the synchronous API, we just need to check once.
        
        Args:
            job_id (str): The job ID to wait for
            poll_interval (int): Unused, kept for compatibility
            max_attempts (int): Unused, kept for compatibility
            
        Returns:
            dict: The completed job data, or None if failed
        """
        if job_id == "direct_audio" and hasattr(self, 'last_audio_data') and self.last_audio_data:
            return {
                "status": "completed",
                "audio_data": self.last_audio_data,
                "download_url": None
            }
        return None
    
    def text_to_speech(self, text: str, voice_id: str = "en-US-terrell", output_format: str = "mp3") -> Tuple[Optional[bytes], Optional[str]]:
        """
        Convert text to speech using the official Murf.ai SDK.
        
        Args:
            text (str): Text to convert to speech
            voice_id (str): Voice ID to use (default: en-US-terrell)
            output_format (str): Output format (mp3, wav, etc.)
            
        Returns:
            tuple: (audio_data, audio_url)
        """
        if not MURF_AVAILABLE:
            print("[ERROR] Murf SDK is not available")
            return None, None
            
        try:
            print(f"[INFO] Generating speech with voice: {voice_id}, format: {output_format}")
            
            # Use the official SDK to generate speech
            # The SDK expects a file-like object for text, so we use io.StringIO
            with io.StringIO(text) as text_file:
                response = self.client.text_to_speech.generate(
                    text=text_file,
                    voice_id=voice_id,
                    format=output_format.lower()
                )
            
            # Get the audio data
            if hasattr(response, 'audio_file') and response.audio_file:
                audio_data = response.audio_file.read()
                print(f"[INFO] Successfully generated {len(audio_data)} bytes of audio data")
                return audio_data, None
                
            print("[ERROR] No audio data in response")
            return None, None
            
        except Exception as e:
            print(f"[ERROR] Failed to generate speech: {str(e)}")
            return None, None

    def save_audio(self, audio_data: Union[bytes, BinaryIO], output_path: Optional[str] = None) -> Optional[str]:
        """
        Save audio data to a file.
        
        Args:
            audio_data: Binary audio data or file-like object
            output_path: Path to save the audio file. If None, a temporary file is created.
            
        Returns:
            str: Path to the saved audio file, or None if failed
        """
        try:
            if output_path is None:
                # Create a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                    if isinstance(audio_data, bytes):
                        f.write(audio_data)
                    else:
                        f.write(audio_data.read())
                    output_path = f.name
            else:
                # Save to the specified path
                with open(output_path, 'wb') as f:
                    if isinstance(audio_data, bytes):
                        f.write(audio_data)
                    else:
                        f.write(audio_data.read())
            
            print(f"[INFO] Audio saved to: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"[ERROR] Failed to save audio file: {str(e)}")
            return None

def play_audio(audio_data: bytes) -> None:
    """
    Play audio data using pydub if available.
    
    Args:
        audio_data (bytes): Binary audio data to play
    """
    if not audio_data:
        print("[ERROR] No audio data provided to play")
        return
        
    if not PYDUB_AVAILABLE:
        print("[WARNING] Audio playback requires pydub to be installed")
        return
        
    temp_path = None
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
            f.write(audio_data)
            temp_path = f.name
        
        print("[INFO] Playing audio...")
        
        # Load and play the audio
        audio = AudioSegment.from_file(temp_path, format='mp3')
        play(audio)
        
    except Exception as e:
        print(f"[ERROR] Failed to play audio: {str(e)}")
    finally:
        # Clean up the temporary file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                print(f"[WARNING] Failed to delete temporary file: {str(e)}")


# Example usage
if __name__ == "__main__":
    # Initialize the client with your API key
    client = MurfAIClient()
    
    # Example text to convert to speech
    test_text = "Hello, this is a test of the Murf.ai text-to-speech service."
    
    # Convert text to speech
    audio_data, audio_url = client.text_to_speech(test_text)
    
    if audio_data:
        # Save the audio to a file
        saved_path = client.save_audio(audio_data, "test_output.mp3")
        print(f"Audio saved to: {saved_path}")
        
        # Play the audio (requires pyaudio)
        try:
            play_audio(audio_data)
        except Exception as e:
            print(f"Could not play audio (pyaudio may not be installed): {e}")
    else:
        print(f"Failed to generate audio. Audio URL: {audio_url}")
