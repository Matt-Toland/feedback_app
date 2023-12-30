from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables and instantiate OpenAI client
load_dotenv()
client = OpenAI()

# Define paths
recordings_path = 'feedback/mp4'
output_path = 'output/audio_transcripts'

# Ensure the output directory exists
if not os.path.exists(output_path):
    os.makedirs(output_path)

# Process each audio file
filenames = [filename for filename in os.listdir(recordings_path) if os.path.isfile(os.path.join(recordings_path, filename))]
for filename in filenames:
    full_transcript = ""  # Initialize a variable to hold the combined transcript

    # Split the audio file into chunks
    audio_chunks = split_audio(os.path.join(recordings_path, filename))
    
    # Transcribe each chunk
    for chunk in audio_chunks:
        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:  # Save each chunk to a temporary file
            chunk.export(temp_file.name, format="mp3")
            with open(temp_file.name, "rb") as audio_file:
                transcript_part = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format='text'
                )
                full_transcript += transcript_part['text']  # Append each part to the full transcript

    # Save the combined transcript
    with open(os.path.join(output_path, filename.split('.')[0] + '.txt'), 'w') as f:
        f.write(full_transcript)
