import os
import fitz  # PyMuPDF
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify, send_from_directory
import tempfile
import sys
import uuid
import shutil
from pathlib import Path
import asyncio
import google.generativeai as genai
from dotenv import load_dotenv
from datetime import datetime
from murf import Murf

# Import magic with Windows compatibility
magic_available = False
try:
    import magic
    magic_available = True
except ImportError:
    try:
        import magic
        magic_available = True
    except Exception as e:
        print(f"Warning: python-magic not available. File type checking will be limited. Error: {e}")
        magic_available = False

# Import Murf.ai client
from utils.audio_utils import MurfAIClient

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['AUDIO_FOLDER'] = 'static/audio'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload and audio directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['AUDIO_FOLDER'], exist_ok=True)

# Initialize Murf.ai client
try:
    murf_client = MurfAIClient()
except Exception as e:
    print(f"Warning: Could not initialize Murf.ai client: {e}")
    murf_client = None

# Configure Google's Generative AI
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("Please set the GEMINI_API_KEY environment variable in .env file")

genai.configure(api_key=GEMINI_API_KEY)

# Initialize the model with safety settings
safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    },
]

model = genai.GenerativeModel('gemini-1.5-flash', safety_settings=safety_settings)

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    try:
        # Check if the file exists and is a PDF
        if not os.path.exists(pdf_path):
            print(f"Error: File not found: {pdf_path}")
            return None
            
        # Verify it's a PDF file by extension if magic is not available
        if not pdf_path.lower().endswith('.pdf'):
            print("Error: File does not have a .pdf extension")
            return None
            
        # Additional check using magic if available
        if magic_available:
            try:
                mime = magic.Magic(mime=True)
                file_type = mime.from_file(pdf_path)
                if file_type != 'application/pdf':
                    print(f"Warning: File may not be a valid PDF. Detected type: {file_type}")
                    # Continue anyway since the extension is .pdf
            except Exception as e:
                print(f"Warning: Could not verify file type with magic: {e}")
        
        # Extract text from PDF
        with fitz.open(pdf_path) as doc:
            text = ""
            for page in doc:
                text += page.get_text()
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None
    return text

def extract_text_from_url(url):
    """Extract text from a URL (handles both web pages and direct PDF links)."""
    try:
        response = requests.get(url, timeout=10)
        content_type = response.headers.get('content-type', '')
        
        if 'application/pdf' in content_type:
            # Handle direct PDF URLs
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(response.content)
                return extract_text_from_pdf(tmp_file.name)
        else:
            # Handle web pages
            soup = BeautifulSoup(response.text, 'html.parser')
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.extract()
            return soup.get_text()
    except Exception as e:
        print(f"Error extracting text from URL: {e}")
        return None

def generate_podcast_script(text):
    """Generate a podcast script from the given text using Google's Gemini AI."""
    if not text or not text.strip():
        print("Error: Empty or invalid text provided for script generation")
        return None
        
    try:
        # Prepare the prompt with clear instructions
        prompt_parts = [
            "You are a professional podcast host. Transform the following research paper "
            "into an engaging, conversational podcast script. The script should be "
            "informative but accessible to a technical audience.\n\n"
            "Structure your response with these sections:\n"
            "1. [Engaging introduction that hooks the listener]\n"
            "2. [Key findings and their significance]\n"
            "3. [Methodology overview - simplified]\n"
            "4. [Results and their implications]\n"
            "5. [Thought-provoking conclusion]\n\n"
            "Make it sound natural and engaging, as if it's being presented by an expert host.\n\n"
            f"Here's the research paper content:\n{text[:15000]}"  # Limit context length
        ]
        
        print("Sending request to Gemini API...")
        
        # Generate content using the model with retry logic
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                print(f"Attempt {attempt + 1} of {max_retries}")
                response = model.generate_content(prompt_parts)
                
                # Debug: Print the raw response
                print(f"Raw response type: {type(response)}")
                print(f"Response attributes: {dir(response)}")
                
                # Handle different response formats
                if hasattr(response, 'text'):
                    print("Found response.text")
                    return response.text
                    
                if hasattr(response, 'parts'):
                    print("Found response.parts")
                    parts_text = [part.text for part in response.parts if hasattr(part, 'text')]
                    if parts_text:
                        return ' '.join(parts_text)
                        
                if hasattr(response, 'candidates'):
                    print(f"Found {len(response.candidates)} candidates")
                    for i, candidate in enumerate(response.candidates):
                        print(f"  Candidate {i} type: {type(candidate)}")
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            parts = [p.text for p in candidate.content.parts if hasattr(p, 'text')]
                            if parts:
                                return ' '.join(parts)
                
                # If we get here, log the unexpected response
                print(f"Unexpected response format on attempt {attempt + 1}")
                print(f"Response: {response}")
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Retrying in {wait_time} seconds...")
                    import time
                    time.sleep(wait_time)
                    
            except Exception as e:
                last_error = e
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                print(f"Error type: {type(e).__name__}")
                
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    print(f"API Error response: {e.response.text}")
                
                if attempt == max_retries - 1:
                    print("All attempts failed")
                    break
                    
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Retrying in {wait_time} seconds...")
                import time
                time.sleep(wait_time)
        
        error_msg = "Failed to generate podcast script"
        if last_error:
            error_msg += f": {str(last_error)}"
        print(error_msg)
        return None
    except Exception as e:
        print(f"Error generating podcast script: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(app.config['AUDIO_FOLDER'], filename)

@app.route('/generate', methods=['POST'])
def generate_podcast():
    """Handle podcast generation from a research paper URL or uploaded PDF."""
    try:
        paper_text = None
        
        # Case 1: Handle file upload
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No selected file'}), 400
            
            if file and file.filename.lower().endswith('.pdf'):
                # Save the uploaded file temporarily
                filename = str(uuid.uuid4()) + ".pdf"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Extract text from the PDF
                paper_text = extract_text_from_pdf(filepath)
                
                # Clean up the uploaded file
                os.remove(filepath)
            else:
                return jsonify({'error': 'Invalid file type. Please upload a PDF.'}), 400

        # Case 2: Handle URL input
        elif request.is_json:
            data = request.get_json()
            url = data.get('source')
            if not url:
                return jsonify({'error': 'No URL provided'}), 400
            
            # Extract text from the URL
            paper_text = extract_text_from_url(url)
        
        # If no text could be extracted
        if not paper_text:
            return jsonify({'error': 'Could not extract text from the source.'}), 400
            
        # Generate podcast script using Gemini
        podcast_script = generate_podcast_script(paper_text)
        if not podcast_script:
            return jsonify({'error': 'Failed to generate podcast script'}), 500
            
        print("Successfully generated podcast script")
        
        # Save the script to a file (optional, but good for debugging)
        script_id = str(uuid.uuid4())
        script_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{script_id}.txt")
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(podcast_script)
        
        audio_url = None
        
        # Convert script to speech using Murf.ai
        if not murf_client:
            return jsonify({
                'status': 'success',
                'script': podcast_script,
                'audio_url': None,
                'warning': 'Text-to-speech service not available'
            })
        
        try:
            # Generate a unique filename for the audio
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_filename = f"podcast_{timestamp}.mp3"
            audio_path = os.path.join(app.config['AUDIO_FOLDER'], audio_filename)
            
            # Split the script into chunks to handle long texts
            max_chunk_length = 3000  # Characters per chunk
            chunks = [podcast_script[i:i+max_chunk_length] 
                     for i in range(0, len(podcast_script), max_chunk_length)]
            
            all_audio_data = bytearray()
            
            # Process each chunk
            for i, chunk in enumerate(chunks):
                print(f"[INFO] Processing audio chunk {i+1}/{len(chunks)} (length: {len(chunk)} chars)")
                
                client = Murf(api_key=murf_client.api_key)
                # Call Murf.ai to generate speech for this chunk
                response = client.text_to_speech.generate(
                    text=chunk,
                    voice_id="en-US-julia",
                    format="MP3",
                    channel_type="STEREO",
                    sample_rate=44100
                )
                
                if response and hasattr(response, 'audio_file') and response.audio_file:
                    # The response.audio_file is a URL to the generated audio
                    audio_url = response.audio_file
                    print(f"[INFO] Downloading audio from URL: {audio_url}")
                    audio_response = requests.get(audio_url)
                    if audio_response.status_code == 200:
                        all_audio_data.extend(audio_response.content)
                    else:
                        print(f"[WARNING] Failed to download audio from {audio_url}. Status: {audio_response.status_code}")
                else:
                    print(f"[WARNING] Failed to generate audio for chunk {i+1}. Response: {response}")
            
            if not all_audio_data:
                return jsonify({
                    'status': 'success',
                    'script': podcast_script,
                    'audio_url': None,
                    'warning': 'Failed to generate audio. The text might be too long or contain unsupported characters.'
                })
            
            # Save the combined audio file
            with open(audio_path, 'wb') as f:
                f.write(all_audio_data)
            
            audio_url = f"/static/audio/{audio_filename}"
            print(f"[INFO] Successfully saved audio to {audio_path} (size: {len(all_audio_data)} bytes)")
            
        except Exception as e:
            print(f"[ERROR] Error generating audio: {str(e)}")
            import traceback
            traceback.print_exc()
            # Continue without audio if there's an error
        
        return jsonify({
            'status': 'success',
            'script': podcast_script,
            'audio_url': audio_url
        })
        
    except Exception as e:
        print(f"An unexpected error occurred in generate_podcast: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred."}), 500

if __name__ == '__main__':
    # Create the uploads and static/audio directories if they don't exist
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('static/audio', exist_ok=True)
    app.run(debug=True, port=5000)
