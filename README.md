# Research Paper to Podcast Generator

Transform research papers into engaging podcast episodes using AI. This application takes a research paper (PDF or URL) and converts it into a conversational podcast script using Google's Gemini AI.

## Features

- Extract text from PDF files or web URLs
- Convert academic content into engaging podcast scripts
- Web interface for easy interaction
- (Coming soon) Integration with Murf.ai for text-to-speech

## Prerequisites

- Python 3.8+
- Google Gemini API key
- (Optional) Murf.ai API key (for future audio generation)

## Setup

1. Clone this repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the project root and add your API key:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```

## Usage

1. Run the application:
   ```
   python app.py
   ```
2. Open your browser and navigate to `http://localhost:5000`
3. Enter a PDF URL or upload a PDF file
4. Click "Generate Podcast" and wait for the magic to happen!

## Future Improvements

- [ ] Integrate Murf.ai API for text-to-speech
- [ ] Add user accounts and history
- [ ] Support for more document formats
- [ ] Customizable podcast styles and voices

## License

This project is licensed under the MIT License - see the LICENSE file for details.
